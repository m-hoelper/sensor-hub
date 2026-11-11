import json

import httpx
import pytest

from sensor_hub.config import Settings
from sensor_hub.models import Notification
from sensor_hub.telegram import TelegramError, make_telegram_sender
from sensor_hub.worker import choose_sender, log_send, send_notification

TOKEN = '123456:FAKE-TOKEN-must-never-leak'
CHAT_ID = '42'


def client_returning(status_code=200, body=None, requests=None):
    """httpx client whose transport answers locally — no network."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return httpx.Response(status_code, json=body if body is not None else {"ok": True})

    return httpx.Client(transport=httpx.MockTransport(handler))


def client_raising(error: Exception):

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sends_to_the_bot_url_with_chat_id_and_text():

    requests = []
    send = make_telegram_sender(TOKEN, CHAT_ID, client_returning(requests=requests))

    send('OPEN_RECOMMENDED', 'Open the window: CO2 too high')

    assert len(requests) == 1
    assert requests[0].url.path == f'/bot{TOKEN}/sendMessage'
    assert json.loads(requests[0].content) == {'chat_id': CHAT_ID, 'text': '🪟 Open the window: CO2 too high'}


@pytest.mark.parametrize(
        ['status_code', 'body', 'expected'],
        [(401, {"ok": False, "description": "Unauthorized"}, 'telegram returned 401: Unauthorized'),
         (400, {"ok": False, "description": "Bad Request: chat not found"}, 'telegram returned 400: Bad Request: chat not found')]
)
def test_error_response_raises_without_token(status_code, body, expected):

    send = make_telegram_sender(TOKEN, CHAT_ID, client_returning(status_code, body))

    with pytest.raises(TelegramError) as exc_info:
        send('CLOSED', 'Close the window')

    assert str(exc_info.value) == expected
    assert TOKEN not in str(exc_info.value)


def test_network_error_raises_without_token():

    error = httpx.ConnectError(f'cannot reach https://api.telegram.org/bot{TOKEN}/sendMessage')
    send = make_telegram_sender(TOKEN, CHAT_ID, client_raising(error))

    with pytest.raises(TelegramError) as exc_info:
        send('CLOSED', 'Close the window')

    assert str(exc_info.value) == 'telegram request failed: ConnectError'
    assert exc_info.value.__suppress_context__              # `from None`: a logged traceback won't show the original error (with the URL)


def test_failed_send_never_stores_the_token(db_session):

    notification = Notification(new_state='OPEN_RECOMMENDED', message='Open the window')
    db_session.add(notification)
    db_session.flush()
    send = make_telegram_sender(TOKEN, CHAT_ID, client_raising(httpx.ReadTimeout(f'timeout for bot{TOKEN}')))

    assert send_notification(db_session, send) is False

    db_session.refresh(notification)
    assert notification.attempts == 1
    assert notification.last_error == 'telegram request failed: ReadTimeout'


@pytest.mark.parametrize(
        ['token', 'chat_id', 'telegram'],
        [(None, None, False), (TOKEN, None, False), (None, CHAT_ID, False), (TOKEN, CHAT_ID, True)]
)
def test_worker_uses_telegram_only_when_fully_configured(token, chat_id, telegram):

    settings = Settings(api_key='k', database_url='d', redis_url='r',
                        telegram_bot_token=token, telegram_chat_id=chat_id)

    assert (choose_sender(settings) is not log_send) == telegram
