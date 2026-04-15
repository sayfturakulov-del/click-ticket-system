import os
import json
import sqlite3
import hashlib
from datetime import datetime
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="BilliardSilkRoadTicketSystem")

SERVICE_ID = int(os.getenv("CLICK_SERVICE_ID", "100711"))
MERCHANT_ID = int(os.getenv("CLICK_MERCHANT_ID", "59690"))
MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "82314")
SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://example.com")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
DB_PATH = os.getenv("DB_PATH", "tickets.db")
CARD_TYPE = os.getenv("CLICK_CARD_TYPE", "uzcard")

EVENTS = {
    "day_22": {"label": "22 апреля 2026", "amount": 200000.00},
    "day_23": {"label": "23 апреля 2026", "amount": 200000.00},
    "day_24": {"label": "24 апреля 2026", "amount": 200000.00},
    "semifinal_25": {"label": "25 апреля 2026 (Полуфинал)", "amount": 500000.00},
    "final_26": {"label": "26 апреля 2026 (Финал)", "amount": 500000.00},
    "full_pass": {"label": "Абонемент на весь чемпионат", "amount": 1600000.00},
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            event_key TEXT NOT NULL,
            event_label TEXT NOT NULL,
            amount REAL NOT NULL,
            telegram_user_id TEXT,
            telegram_chat_id TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            click_trans_id TEXT,
            click_paydoc_id TEXT,
            merchant_prepare_id TEXT,
            status TEXT NOT NULL DEFAULT 'created',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            paid_at TEXT,
            raw_prepare TEXT,
            raw_complete TEXT
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


class CreateOrderRequest(BaseModel):
    event_key: str = Field(..., description="day_22/day_23/day_24/semifinal_25/final_26/full_pass")
    telegram_user_id: str | None = None
    telegram_chat_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    card_type: str = CARD_TYPE


class TicketMessageRequest(BaseModel):
    chat_id: str
    text: str


def next_order_id() -> str:
    conn = db()
    row = conn.execute("SELECT id FROM orders ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    next_num = 1 if row is None else row["id"] + 1
    return f"ticket_2026_{next_num:05d}"


def format_amount(amount: float) -> str:
    return f"{amount:.2f}"


def click_prepare_sign(click_trans_id: str, service_id: str, merchant_trans_id: str, amount: str, action: str, sign_time: str) -> str:
    raw = f"{click_trans_id}{service_id}{SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
    return hashlib.md5(raw.encode()).hexdigest()


def click_complete_sign(click_trans_id: str, service_id: str, merchant_trans_id: str, merchant_prepare_id: str, amount: str, action: str, sign_time: str) -> str:
    raw = f"{click_trans_id}{service_id}{SECRET_KEY}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
    return hashlib.md5(raw.encode()).hexdigest()


def build_return_url(order_id: str) -> str:
    return f"{BASE_URL}/return/{order_id}"


def build_click_url(order_id: str, amount: float, card_type: str) -> str:
    params = {
        "service_id": SERVICE_ID,
        "merchant_id": MERCHANT_ID,
        "merchant_user_id": MERCHANT_USER_ID,
        "amount": format_amount(amount),
        "transaction_param": order_id,
        "return_url": build_return_url(order_id),
        "card_type": card_type,
    }
    return f"https://my.click.uz/services/pay?{urlencode(params)}"


def get_order(order_id: str):
    conn = db()
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    return row


def save_order(event_key: str, telegram_user_id: str | None, telegram_chat_id: str | None, customer_name: str | None, customer_phone: str | None) -> sqlite3.Row:
    if event_key not in EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event_key")

    order_id = next_order_id()
    event = EVENTS[event_key]
    conn = db()
    conn.execute(
        """
        INSERT INTO orders (
            order_id, event_key, event_label, amount,
            telegram_user_id, telegram_chat_id, customer_name, customer_phone,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting_payment', ?, ?)
        """,
        (
            order_id,
            event_key,
            event["label"],
            event["amount"],
            telegram_user_id,
            telegram_chat_id,
            customer_name,
            customer_phone,
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    return row


def update_order(order_id: str, **fields):
    if not fields:
        return
    parts = ["updated_at = ?"]
    values = [now_iso()]
    for key, value in fields.items():
        parts.append(f"{key} = ?")
        values.append(value)
    values.append(order_id)
    conn = db()
    conn.execute(f"UPDATE orders SET {', '.join(parts)} WHERE order_id = ?", values)
    conn.commit()
    conn.close()


async def send_telegram_message(chat_id: str, text: str, button_text: str | None = None, button_url: str | None = None):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    payload = {"chat_id": chat_id, "text": text}
    if button_text and button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": button_text, "url": button_url}]]
        }
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json=payload)


def order_message(row: sqlite3.Row) -> str:
    return (
        f"🎟 Ваш билет\n"
        f"Номер: {row['order_id']}\n"
        f"Событие: {row['event_label']}\n"
        f"Сумма: {int(row['amount']):,} сум".replace(",", " ")
    )


@app.get("/")
def healthcheck():
    return {
        "ok": True,
        "service_id": SERVICE_ID,
        "merchant_id": MERCHANT_ID,
        "base_url": BASE_URL,
        "events": EVENTS,
    }


@app.post("/orders/create")
def create_order(payload: CreateOrderRequest):
    row = save_order(
        payload.event_key,
        payload.telegram_user_id,
        payload.telegram_chat_id,
        payload.customer_name,
        payload.customer_phone,
    )
    click_url = build_click_url(row["order_id"], row["amount"], payload.card_type)
    return {
        "order_id": row["order_id"],
        "event": row["event_label"],
        "amount": format_amount(row["amount"]),
        "status": row["status"],
        "payment_url": click_url,
        "return_url": build_return_url(row["order_id"]),
    }


@app.get("/orders/{order_id}")
def read_order(order_id: str):
    row = get_order(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return dict(row)


@app.get("/return/{order_id}")
def payment_return(order_id: str):
    row = get_order(order_id)
    if not row:
        return HTMLResponse("<h2>Заказ не найден</h2>", status_code=404)

    if row["status"] == "paid":
        return HTMLResponse(
            f"<h2>Оплата прошла успешно</h2><p>Билет: {row['order_id']}</p><p>{row['event_label']}</p>")
    return HTMLResponse(
        f"<h2>Платеж обрабатывается</h2><p>Номер заказа: {row['order_id']}</p><p>Через несколько секунд статус обновится в боте.</p>")


@app.post("/click/prepare")
async def click_prepare(request: Request):
    form = await request.form()
    data = {k: str(v) for k, v in form.items()}

    click_trans_id = data.get("click_trans_id", "")
    service_id = data.get("service_id", "")
    click_paydoc_id = data.get("click_paydoc_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")
    amount = data.get("amount", "")
    action = data.get("action", "")
    sign_time = data.get("sign_time", "")
    sign_string = data.get("sign_string", "")

    expected_sign = click_prepare_sign(click_trans_id, service_id, merchant_trans_id, amount, action, sign_time)

    if sign_string != expected_sign:
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": 0,
            "error": -1,
            "error_note": "SIGN CHECK FAILED"
        })

    row = get_order(merchant_trans_id)
    if not row:
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": 0,
            "error": -5,
            "error_note": "ORDER NOT FOUND"
        })

    if int(float(amount)) != int(float(row["amount"])):
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": 0,
            "error": -2,
            "error_note": "INCORRECT AMOUNT"
        })

    merchant_prepare_id = str(row["id"])
    update_order(
        merchant_trans_id,
        status="prepared",
        click_trans_id=click_trans_id,
        click_paydoc_id=click_paydoc_id,
        merchant_prepare_id=merchant_prepare_id,
        raw_prepare=json.dumps(data, ensure_ascii=False),
    )

    return JSONResponse({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": merchant_prepare_id,
        "error": 0,
        "error_note": "SUCCESS"
    })


@app.post("/click/complete")
async def click_complete(request: Request):
    form = await request.form()
    data = {k: str(v) for k, v in form.items()}

    click_trans_id = data.get("click_trans_id", "")
    service_id = data.get("service_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")
    merchant_prepare_id = data.get("merchant_prepare_id", "")
    amount = data.get("amount", "")
    action = data.get("action", "")
    error = data.get("error", "0")
    sign_time = data.get("sign_time", "")
    sign_string = data.get("sign_string", "")

    expected_sign = click_complete_sign(click_trans_id, service_id, merchant_trans_id, merchant_prepare_id, amount, action, sign_time)

    if sign_string != expected_sign:
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": merchant_prepare_id or 0,
            "error": -1,
            "error_note": "SIGN CHECK FAILED"
        })

    row = get_order(merchant_trans_id)
    if not row:
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": merchant_prepare_id or 0,
            "error": -5,
            "error_note": "ORDER NOT FOUND"
        })

    if error == "0":
        update_order(
            merchant_trans_id,
            status="paid",
            paid_at=now_iso(),
            raw_complete=json.dumps(data, ensure_ascii=False),
        )
        paid_row = get_order(merchant_trans_id)
        if paid_row["telegram_chat_id"]:
            await send_telegram_message(
                paid_row["telegram_chat_id"],
                "✅ Оплата прошла успешно\n\n" + order_message(paid_row),
            )
        if ADMIN_CHAT_ID:
            await send_telegram_message(
                ADMIN_CHAT_ID,
                f"💰 Новый оплаченный билет\nНомер: {paid_row['order_id']}\nСобытие: {paid_row['event_label']}\nСумма: {int(paid_row['amount']):,} сум".replace(",", " "),
            )
        return JSONResponse({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": merchant_prepare_id or row["id"],
            "error": 0,
            "error_note": "SUCCESS"
        })

    update_order(
        merchant_trans_id,
        status="cancelled",
        raw_complete=json.dumps(data, ensure_ascii=False),
    )
    return JSONResponse({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": merchant_prepare_id or row["id"],
        "error": -9,
        "error_note": "CANCELLED"
    })


@app.post("/telegram/send-test")
async def send_test_message(payload: TicketMessageRequest):
    await send_telegram_message(payload.chat_id, payload.text)
    return {"ok": True}


@app.get("/admin/orders")
def admin_orders(limit: int = 100):
    conn = db()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
