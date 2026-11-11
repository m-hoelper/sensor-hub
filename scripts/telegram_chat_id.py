"""Print the chat IDs that have messaged the bot (send it a message first).

Reads TELEGRAM_BOT_TOKEN from .env and never prints it.
Run: uv run python scripts/telegram_chat_id.py
"""
import httpx

from sensor_hub.config import get_settings


def main() -> None:
    token = get_settings().telegram_bot_token
    if token is None:
        print("TELEGRAM_BOT_TOKEN is not set in .env")
        return

    try:
        response = httpx.get(f"https://api.telegram.org/bot{token.get_secret_value()}/getUpdates", timeout=10)
    except httpx.HTTPError as e:
        print(f"request failed: {type(e).__name__}")          # str(e) would contain the URL with the token
        return

    body = response.json()
    if not body.get("ok"):
        print(f"Telegram error {response.status_code}: {body.get('description')}")
        return

    chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
             for u in body["result"] if "message" in u}
    if not chats:
        print("no messages yet: open the bot in Telegram, press Start and send 'hi', then run this again")
    for chat_id, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={chat_id}   ({name})")


if __name__ == "__main__":
    main()
