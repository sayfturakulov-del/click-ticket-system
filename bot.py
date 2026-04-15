import os
import asyncio
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

EVENT_BUTTONS = [
    ("22 апреля — 200 000 сум", "day_22"),
    ("23 апреля — 200 000 сум", "day_23"),
    ("24 апреля — 200 000 сум", "day_24"),
    ("25 апреля (Полуфинал) — 500 000 сум", "semifinal_25"),
    ("26 апреля (Финал) — 500 000 сум", "final_26"),
    ("Абонемент на все дни — 1 600 000 сум", "full_pass"),
]


def main_menu():
    rows = [[InlineKeyboardButton(text=text, callback_data=f"buy:{key}")] for text, key in EVENT_BUTTONS]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎱 Чемпионат мира Silk Road 2026\n\nВыберите билет для оплаты:",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data.startswith("buy:"))
async def buy_ticket(callback: CallbackQuery):
    event_key = callback.data.split(":", 1)[1]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/orders/create",
            json={
                "event_key": event_key,
                "telegram_user_id": str(callback.from_user.id),
                "telegram_chat_id": str(callback.message.chat.id),
                "customer_name": callback.from_user.full_name,
            },
        )
    resp.raise_for_status()
    data = resp.json()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через CLICK", url=data["payment_url"])],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
        ]
    )

    await callback.message.edit_text(
        f"🎟 Заказ создан\n\nНомер: {data['order_id']}\nСобытие: {data['event']}\nСумма: {data['amount']} сум\n\nНажмите кнопку ниже для оплаты.",
        reply_markup=keyboard,
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎱 Чемпионат мира Silk Road 2026\n\nВыберите билет для оплаты:",
        reply_markup=main_menu(),
    )
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
