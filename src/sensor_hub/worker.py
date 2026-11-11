from sqlalchemy.orm import Session
from sqlalchemy import select
import logging
from sensor_hub.models import Notification
from datetime import datetime, timezone
from sensor_hub.db import SessionLocal
import time

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


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main(send=log_send)
