"""Telegram sender for the outbox worker.

make_telegram_sender(...) returns a function with the worker's sender signature
send(state, message). Errors are re-raised as TelegramError with a message that
never contains the bot token: httpx puts the request URL (which includes the
token) into its exception text, and the worker stores str(e) in last_error.
"""
from collections.abc import Callable

import httpx

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 10
ICONS = {"OPEN_RECOMMENDED": "🪟", "CLOSED": "✅"}


class TelegramError(Exception):
    """Sending failed. The message is safe to log and to store (no token)."""


def format_text(state: str, message: str) -> str:
    return f"{ICONS.get(state, 'ℹ️')} {message}"


def make_telegram_sender(token: str, chat_id: str,
                         client: httpx.Client | None = None) -> Callable[[str, str], None]:
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    url = API_URL.format(token=token)

    def send(state: str, message: str) -> None:
        try:
            response = http.post(url, json={"chat_id": chat_id, "text": format_text(state, message)})
        except httpx.HTTPError as e:
            raise TelegramError(f"telegram request failed: {type(e).__name__}") from None

        if response.status_code != 200:
            try:
                description = response.json().get("description", "")
            except ValueError:
                description = ""
            raise TelegramError(f"telegram returned {response.status_code}: {description}")

    return send
