# Architecture and internals

How the firmware, the API, the window rule and the notification worker work, and what happens when something fails. The reasons behind the main choices, with the alternatives that were rejected, are in [DESIGN.md](DESIGN.md).

## 1. Components

```
 ESP32-S3 ──POST /measurements──► api ──► Postgres ◄── grafana (read-only role)
                                   │         ▲
                                   ├──► redis│(latest-reading cache)
                                   │         │
                                   └── notifications (outbox) ◄── worker ──► Telegram Bot API
```

| Container / device | Image / code | Role |
|---|---|---|
| ESP32-S3 + SCD40 | [`firmware/src/main.cpp`](../firmware/src/main.cpp) | Measures, buffers in flash, uploads batches |
| `api` | built from the [Dockerfile](../Dockerfile) | Runs `alembic upgrade head`, then uvicorn on port 8000 |
| `worker` | same image, `python -m sensor_hub.worker` | Delivers notifications |
| `db` | `postgres:17` | Measurements, settings, notifications. Only on `127.0.0.1` |
| `redis` | `redis:7` | Cache. Only on `127.0.0.1` |
| `grafana` | `grafana/grafana-oss:11.6.0` | Dashboard from [`grafana/`](../grafana/). Only on `127.0.0.1`, anonymous read-only |

Inside the Compose network the services reach each other by name (`db`, `redis`), so `DATABASE_URL` and `REDIS_URL` are overridden in `docker-compose.yaml`. All services use `restart: unless-stopped`, so the stack comes back after a reboot. The API port is published on all interfaces because the ESP32 posts over Wi-Fi.

## 2. Firmware

**Sampling.** The SCD40 runs in periodic mode. The firmware waits 4 minutes after power-on for the sensor to settle, then checks every second whether a new value is ready and adds it to running sums. Every 30 seconds it averages the window. A window is stored only if it has at least one sample and the clock is valid (NTP has set it past a fixed date), so a reading never gets a 1970 timestamp.

**Record format.** Each window becomes a 16-byte record:

| Field | Type | Note |
|---|---|---|
| `epoch` | `uint32` | UTC seconds, from NTP |
| `co2` | `uint16` | ppm |
| `temp100` | `int16` | °C × 100, so 21.37 °C is stored exactly as 2137 |
| `hum100` | `uint16` | % × 100 |
| `spare` | 6 bytes | room for a CRC or a version |

Integers instead of floats keep the record small and the values exact. A `static_assert` checks the size at compile time.

**Ring buffer.** One LittleFS file holds 20,160 slots (one week at 30 s, about 320 KB of the 16 MB flash). A second file holds the header: read index, write index, count. The record is written before the header, so a power cut between the two loses at most the newest record and never leaves the indices pointing at garbage. When the buffer is full, the oldest record is overwritten and the read index moves with it.

**Upload loop.** Whenever the count is above zero and the sync delay has passed, the loop reads the oldest `min(count, 500)` records, builds the JSON body with ArduinoJson and POSTs it with the `X-API-Key` header (2 s connect timeout, 3 s response timeout).

| Result | Action |
|---|---|
| 2xx | Advance the read index, lower the count, save the header, send the next chunk after 50 ms |
| Anything else (timeout, 401, 422, 5xx) | Keep the records, try again in 30 s |

The device does not need to know why a send failed: a record leaves the buffer only after the server has confirmed it, and the server tolerates resends (section 3). After a long outage, a full week of backlog uploads in about 41 requests.

**Secrets.** Wi-Fi credentials, API key and backend URL live in `firmware/include/secrets.h`, which is gitignored; `secrets.example.h` lists the names.

## 3. API and storage

**Layers.** Routes (HTTP, status codes, dependencies) → services (business logic) → repositories (SQLAlchemy queries). The services get their database session and Redis client through FastAPI dependencies, which is also how the tests swap in a test database and a fake cache.

**Batch insert.**

```sql
INSERT INTO measurements (device_id, created_at, co2_ppm, temperature_c, humidity_pct)
VALUES (...), (...), ...
ON CONFLICT ON CONSTRAINT uq_measurements_device_created DO NOTHING
RETURNING *;
```

The unique constraint on `(device_id, created_at)` makes the upload idempotent. `RETURNING` yields only the rows that were actually inserted, so `duplicates = sent − returned`. The whole batch, the rule evaluation and a possible notification row are committed in one transaction.

**Validation** (Pydantic): 1–500 readings per batch, `created_at` must carry a timezone, CO₂ 0–40,000 ppm (the SCD40's range), temperature −10 to 60 °C, humidity 0–100 %. One bad reading rejects the whole batch with 422; the device keeps it and retries, which surfaces the problem in the logs instead of losing data silently.

**Settings.** The thresholds live in a single-row table (`CHECK (id = 1)`). `PUT` replaces all values; `PATCH` merges the changes into the current values and validates the result as a whole, so a patch cannot create an invalid combination such as close ≥ open.

**Cache.** `GET /measurements/latest` reads Redis first (key per device plus one for all devices, 60 s TTL). Every successful insert or delete deletes the affected keys. All Redis calls are wrapped: on a Redis error the API logs a warning and answers from Postgres, with 0.5 s socket timeouts so a dead Redis does not slow requests down.

## 4. Window rule

[`rules.py`](../src/sensor_hub/rules.py) is a pure function: it takes the newest reading of the batch, the settings, the last notification and the current time, and returns a new state or `None`. That makes it testable without a database.

```
                CO₂ ≥ open (and humidity > min)
                or humidity ≥ open
                or CO₂ ≥ max
   ┌────────┐ ─────────────────────────────────► ┌──────────────────┐
   │ CLOSED │                                    │ OPEN_RECOMMENDED │
   └────────┘ ◄───────────────────────────────── └──────────────────┘
                CO₂ ≤ close and humidity ≤ close
                or (humidity ≤ min and CO₂ < max)
```

Guards before any transition:
- **Stale data:** readings older than `ignore_measurements_older_than_min` (5 min) never trigger anything. Without this, uploading a night's backlog would replay old alarms.
- **Cooldown:** no state change within `cooldown_min` of the last notification.

**Dry air.** In heated rooms in winter, airing makes the air drier because cold outside air holds little water. Below `humidity_min_pct` the rule therefore waits for a higher CO₂ value (`co2_max_ppm`) before recommending airing, and recommends closing as soon as CO₂ is below that value.

**Values.** The migration seeds conservative defaults; the values I run at home were set with `PATCH /settings/thresholds` after a few days of data:

| Setting | Default (fresh install) | Tuned for my room |
|---|---|---|
| `co2_open_ppm` / `co2_close_ppm` / `co2_max_ppm` | 1200 / 800 / 2000 | 1000 / 850 / 1500 |
| `humidity_open_pct` / `humidity_close_pct` / `humidity_min_pct` | 65 / 55 / 30 | 60 / 57 / 35 |
| `cooldown_min` / `ignore_measurements_older_than_min` | 15 / 5 | 5 / 5 |

The close thresholds were tuned with real data: the room sits at 55–58 % humidity whether the window is open or not, so a close threshold of 50 % meant the "close" message never came. Humidity changes slowly and smoothly, so a 3-point gap is enough; CO₂ jumps by 50–100 ppm when someone moves, so it gets 150 ppm.

## 5. Notification worker (outbox)

The API never calls Telegram. It writes a row to `notifications`, and the worker delivers it:

```sql
SELECT * FROM notifications
WHERE sent_at IS NULL AND attempts < 5
ORDER BY created_at, id
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

| Result | Action |
|---|---|
| Sent | `sent_at = now()`, commit |
| Failed | `attempts += 1`, store the error text, commit; the row is retried on the next loop |
| 5 failures | The row is skipped from then on and no longer blocks newer messages |
| Queue empty | Sleep 5 s |

`SKIP LOCKED` lets several workers run without sending a message twice. A partial index on `created_at WHERE sent_at IS NULL` keeps the query cheap as the table grows.

**Token safety.** The Telegram URL contains the bot token. httpx puts the URL into its exception text and logs every request URL at INFO level, so the sender re-raises errors as `TelegramError` with only the exception type or Telegram's description, and the worker lowers the httpx log level. If Telegram is not configured, the worker only logs the messages.

## 6. Security

| Area | Measure |
|---|---|
| Write endpoints | `X-API-Key` header, compared with `secrets.compare_digest` |
| Secrets | `.env` at runtime via `env_file`; excluded from the image by `.dockerignore` and from git by `.gitignore`. Pydantic `SecretStr` keeps them out of logs and reprs |
| Grafana | Logs in as `grafana_reader`: `SELECT` on measurements and settings, column-level `SELECT` on notifications without `last_error` |
| Network | Postgres, Redis and Grafana only on `127.0.0.1`. Only the API is reachable on the LAN |
| Device | The API key is in the ESP32's flash, so anyone holding the board can read it. Acceptable at home; production would need per-device, revocable keys and HTTPS |

## 7. What happens when something goes wrong

| Situation | Response |
|---|---|
| Mac asleep or backend stopped | ESP32 keeps measuring and buffering (up to one week), uploads the backlog later with the original timestamps |
| Response lost after a successful insert | ESP32 resends; the unique constraint turns the rows into `duplicates`, nothing is stored twice |
| Wi-Fi down | Same as backend down: buffer and retry every 30 s |
| Invalid reading in a batch | 422, the batch stays on the device and is retried |
| Redis down | Warning in the log, reads go to Postgres |
| Telegram down or token wrong | Notification stays in the outbox, up to 5 attempts |
| Old backlog uploaded | Stored, but no notification (older than 5 min) |
| Reboot | Docker Desktop starts at login, all containers restart (`unless-stopped`); the ESP32 reloads its buffer header from flash |

## 8. Known limitations

- The rule knows its recommendation, not the real window state. If the window is closed before CO₂ drops below `co2_close_ppm`, the state stays `OPEN_RECOMMENDED` and no new "open" message comes until it has closed once.
- No reminders and no quiet hours: one message per state change, also at night.
- A full buffer overwrites the oldest readings, so an outage of more than a week loses data.
- Timestamps come from NTP; until the first sync after power-on, nothing is stored.
- One API key for every device; no retention policy for old readings.
