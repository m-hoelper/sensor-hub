from sqlalchemy.orm import Session
from sqlalchemy import select
import logging
from sensor_hub.models import Notification
from datetime import datetime, timezone
from sensor_hub.db import SessionLocal
import time
from sensor_hub.config import Settings, get_settings
from sensor_hub.telegram import make_telegram_sender

MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)

def log_send(state: str, message: str) -> None:
    logger.info("would send [%s]: %s", state, message)

def send_notification(db: Session, send) -> bool:

    stmt = select(Notification)
    stmt = stmt.where(Notification.sent_at.is_(None), Notification.attempts < MAX_ATTEMPTS)
    stmt = stmt.order_by(Notification.created_at.asc(), Notification.id.asc())
    stmt = stmt.limit(1)
    stmt = stmt.with_for_update(skip_locked=True)

    notification = db.execute(stmt).scalar()

    if notification is None:
        return False

    try:
        send(notification.new_state, notification.message)
        notification.sent_at = datetime.now(timezone.utc)
        status = True

    except Exception as e:
        notification.attempts += 1
        notification.last_error = str(e)[:500]
        logger.warning("send failed for notification %s (attempt %s): %s", notification.id, notification.attempts, e)

        status = False

    db.commit()

    return status

def main(send):
    while True:

        db = SessionLocal()
        try:
            processed = send_notification(db, send)
        finally:
            db.close()

        if not processed:
            time.sleep(5)


def choose_sender(settings: Settings):
    if settings.telegram_bot_token is None or settings.telegram_chat_id is None:
        logger.info("Telegram not configured, notifications are only logged")
        return log_send

    logger.info("sending notifications to Telegram")
    return make_telegram_sender(settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)      # httpx logs every request URL at INFO = the bot token
    main(send=choose_sender(get_settings()))
