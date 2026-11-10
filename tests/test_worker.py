import logging
from datetime import datetime, timedelta, timezone

import pytest

from sensor_hub.models import Notification
from sensor_hub.worker import MAX_ATTEMPTS, send_notification

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def add_notification(db_session):

    def _add(state='OPEN_RECOMMENDED', message='Open the window', minutes=0, attempts=0, sent_at=None):
        notification = Notification(new_state=state, message=message, created_at=T0 + timedelta(minutes=minutes),
                                    attempts=attempts, sent_at=sent_at)
        db_session.add(notification)
        db_session.flush()
        return notification

    return _add


@pytest.fixture()
def calls():
    return []


@pytest.fixture()
def fake_send(calls):

    def _send(state, message):
        calls.append((state, message))

    return _send


def failing_send(state, message):
    raise ConnectionError('telegram unreachable')


def test_empty_queue_returns_false_and_sends_nothing(db_session, fake_send, calls):

    assert send_notification(db_session, fake_send) is False
    assert calls == []


def test_success_sets_sent_at(db_session, add_notification, fake_send, calls):

    notification = add_notification(message='Open the window: CO2 too high')

    assert send_notification(db_session, fake_send) is True

    db_session.refresh(notification)
    assert calls == [('OPEN_RECOMMENDED', 'Open the window: CO2 too high')]
    assert notification.sent_at is not None
    assert notification.attempts == 0
    assert notification.last_error is None


def test_sent_notification_is_not_sent_again(db_session, add_notification, fake_send, calls):

    add_notification()

    assert send_notification(db_session, fake_send) is True
    assert send_notification(db_session, fake_send) is False
    assert len(calls) == 1


def test_failure_counts_attempt_and_keeps_error(db_session, add_notification, caplog):

    notification = add_notification()

    with caplog.at_level(logging.WARNING):
        assert send_notification(db_session, failing_send) is False

    db_session.refresh(notification)
    assert notification.sent_at is None
    assert notification.attempts == 1
    assert notification.last_error == 'telegram unreachable'
    assert f'notification {notification.id}' in caplog.text


def test_last_error_is_truncated(db_session, add_notification):

    notification = add_notification()

    def long_error(state, message):
        raise RuntimeError('x' * 2000)

    send_notification(db_session, long_error)

    db_session.refresh(notification)
    assert len(notification.last_error) == 500


def test_gives_up_after_max_attempts(db_session, add_notification, fake_send, calls):

    notification = add_notification()

    for _ in range(MAX_ATTEMPTS):
        send_notification(db_session, failing_send)

    db_session.refresh(notification)
    assert notification.attempts == MAX_ATTEMPTS

    # the sender works again, but the notification is out of retries
    assert send_notification(db_session, fake_send) is False
    assert calls == []


def test_retry_succeeds_below_max_attempts(db_session, add_notification, fake_send, calls):

    notification = add_notification(attempts=MAX_ATTEMPTS - 1)

    assert send_notification(db_session, fake_send) is True

    db_session.refresh(notification)
    assert notification.sent_at is not None
    assert len(calls) == 1


def test_oldest_first_by_created_at_not_id(db_session, add_notification, fake_send, calls):

    add_notification(message='newer', minutes=10)    # id 1
    add_notification(message='older', minutes=0)     # id 2

    send_notification(db_session, fake_send)
    send_notification(db_session, fake_send)

    assert [message for _, message in calls] == ['older', 'newer']


def test_same_created_at_falls_back_to_id(db_session, add_notification, fake_send, calls):

    add_notification(message='first')
    add_notification(message='second')

    send_notification(db_session, fake_send)
    send_notification(db_session, fake_send)

    assert [message for _, message in calls] == ['first', 'second']


def test_dead_notification_does_not_block_the_queue(db_session, add_notification, fake_send, calls):

    add_notification(message='dead', minutes=0, attempts=MAX_ATTEMPTS)
    add_notification(message='alive', minutes=5)

    assert send_notification(db_session, fake_send) is True
    assert calls == [('OPEN_RECOMMENDED', 'alive')]
