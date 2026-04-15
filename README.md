# Billiard Silk Road Ticket System

Production-ready starter for CLICK + Telegram ticket sales.

## What this does
- Creates unique orders like `ticket_2026_00001`
- Builds CLICK payment links
- Handles CLICK `Prepare` and `Complete`
- Marks orders as paid in SQLite
- Sends Telegram confirmation when payment succeeds
- Shows simple return page after payment
- Includes admin order list endpoint

## Important security note
If you shared your Telegram bot token or CLICK secret in chat, rotate both before deployment.

## Deploy on Render
1. Create a new GitHub repo and upload these files.
2. In Render, create a new Blueprint or Web Service.
3. Set environment variables:
   - `CLICK_SECRET_KEY`
   - `BASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_CHAT_ID` (optional)
4. Deploy.

## URLs to add in CLICK Merchant
- Prepare URL: `https://YOUR-DOMAIN/click/prepare`
- Complete URL: `https://YOUR-DOMAIN/click/complete`
- Port: `443`
- Domain: your Render or custom domain

## Create an order
POST `/orders/create`

Example JSON:
```json
{
  "event_key": "final_26",
  "telegram_chat_id": "123456789",
  "telegram_user_id": "123456789",
  "customer_name": "Ali",
  "customer_phone": "+998901234567"
}
```

Response contains `payment_url`.

## Supported event keys
- `day_22`
- `day_23`
- `day_24`
- `semifinal_25`
- `final_26`
- `full_pass`

## Suggested Telegram bot flow
1. User taps a date button.
2. Bot sends a request to `/orders/create`.
3. Bot returns the `payment_url` as an inline button.
4. CLICK calls your `Prepare` and `Complete` URLs.
5. Server sends user a confirmation message after successful payment.

## Notes
- SQLite is fine for launch. Move to Postgres later if volume grows.
- Do not treat `return_url` as proof of payment. Only `Complete` success means paid.
- .
