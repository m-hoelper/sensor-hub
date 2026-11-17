# Architecture

This document describes the firmware, the API, the window rule, and the notification worker, and what each part does when something fails. [DESIGN.md](DESIGN.md) explains why the system works this way and which alternatives I rejected.

## Components

```
 ESP32-S3 ──POST /measurements──► api ──► Postgres ◄── grafana (read-only role)
                                   │         ▲
                                   ├──► redis│(latest-reading cache)
                                   │         │
                                   └── notifications (outbox) ◄── worker ──► Telegram Bot API
```

| Component | Source | Role |
|---|---|---|
| ESP32-S3 and SCD40 | [`firmware/src/main.cpp`](../firmware/src/main.cpp) | Measures, stores readings in flash, and uploads batches. |
| `api` | Built from the [Dockerfile](../Dockerfile) | Runs `alembic upgrade head`, then uvicorn on port 8000. |
| `worker` | The `api` image, started with `python -m sensor_hub.worker` | Sends notifications. |
| `db` | `postgres:17` | Stores measurements, settings, and notifications. Listens on `127.0.0.1` only. |
| `redis` | `redis:7` | Caches the latest reading. Listens on `127.0.0.1` only. |
| `grafana` | `grafana/grafana-oss:11.6.0` | Shows the dashboard from [`grafana/`](../grafana/). Listens on `127.0.0.1` only and allows anonymous read-only access. |

Inside the Compose network, the services reach each other by name, so `docker-compose.yaml` overrides `DATABASE_URL` and `REDIS_URL` with the hosts `db` and `redis`. All services use `restart: unless-stopped`, so the stack starts again after a reboot. The API port listens on all interfaces because the ESP32 posts over Wi-Fi.

## Firmware

### Sampling

The SCD40 runs in periodic mode. After power-on, the firmware waits 4 minutes for the sensor to settle. Then it checks every second for a new value and adds the value to running sums. Every 30 seconds it computes the average of the window.

The firmware stores a window only if the window has at least one sample and the clock is valid. The clock is valid after NTP has set it past a fixed date. So no reading gets a timestamp from 1970.

### Record format

Each window becomes one 16-byte record. A `static_assert` checks the size at compile time.

| Field | Type | Content |
|---|---|---|
| `epoch` | `uint32` | UTC seconds from NTP. |
| `co2` | `uint16` | CO₂ in ppm. |
| `temp100` | `int16` | Temperature in °C × 100. 21.37 °C is stored as 2137. |
| `hum100` | `uint16` | Relative humidity in % × 100. |
| `spare` | 6 bytes | Reserved for a CRC or a version number. |

### Ring buffer

One LittleFS file holds 20,160 slots. That is one week at one record every 30 s, and about 320 KB of the 16 MB flash. A second file holds the header with the read index, the write index, and the count.

The firmware writes the record before the header. If the power fails between the two writes, the buffer loses at most the newest record, and the indices still point at valid records. When the buffer is full, the newest record overwrites the oldest one, and the read index moves forward by one.

### Upload loop

When the count is above zero and the sync delay has passed, the loop reads the oldest `min(count, 500)` records. It builds the JSON body with ArduinoJson and sends it in a POST request with the `X-API-Key` header. The connect timeout is 2 s, and the response timeout is 3 s.

| Result | Action |
|---|---|
| 2xx | Moves the read index forward, lowers the count, saves the header, and sends the next chunk after 50 ms. |
| Anything else, such as a timeout, 401, 422, or 5xx | Keeps the records and tries again after 30 s. |

A record leaves the buffer only after the server confirms it. The server accepts resent records without storing them twice, as [Batch insert](#batch-insert) shows. After an outage of one week, the backlog uploads in 41 requests.

### Secrets

`firmware/include/secrets.h` holds the Wi-Fi credentials, the API key, and the backend URL. Git ignores this file. `secrets.example.h` lists the names of the values.

## API and storage

### Layers

The code has three layers:

- Routes handle HTTP, status codes, and dependencies.
- Services hold the business logic.
- Repositories hold the SQLAlchemy queries.

The services get the database session and the Redis client through FastAPI dependencies. The tests use the same dependencies to put in a test database and a fake cache.

### Batch insert

```sql
INSERT INTO measurements (device_id, created_at, co2_ppm, temperature_c, humidity_pct)
VALUES (...), (...), ...
ON CONFLICT ON CONSTRAINT uq_measurements_device_created DO NOTHING
RETURNING *;
```

The unique constraint on `(device_id, created_at)` makes the upload idempotent. `RETURNING` returns only the rows that Postgres inserted, so `duplicates` is the number of sent rows minus the number of returned rows. One transaction commits the batch, the rule evaluation, and the notification row, if there is one.

### Validation

Pydantic checks these limits:

| Field | Limit |
|---|---|
| Batch | 1 to 500 readings. |
| `device_id` | 1 to 50 characters. |
| `created_at` | Must include a timezone. |
| `co2_ppm` | 0 to 40,000 ppm, the range of the SCD40. |
| `temperature_c` | −10 to 60 °C. |
| `humidity_pct` | 0 to 100 %. |

One invalid reading rejects the whole batch with 422. The device keeps the batch and tries again, so the error shows in the logs and no reading is lost.

### Settings

The thresholds are in a table with one row, enforced by `CHECK (id = 1)`. `PUT` replaces all values. `PATCH` merges the changes into the current values and validates the result as a whole. So a `PATCH` cannot create an invalid combination, such as a close threshold at or above the open threshold.

### Cache

`GET /measurements/latest` reads Redis first. Redis has one key per device and one key for all devices, each with a TTL of 60 s. Each successful insert or delete removes the affected keys.

Every Redis call has a socket timeout of 0.5 s. If a Redis call fails, the API logs a warning and reads from Postgres.

## Window rule

The rule is a pure function in [`rules.py`](../src/sensor_hub/rules.py). It takes the newest reading of the batch, the settings, the last notification, and the current time. It returns a new state, or `None` if the state does not change. The tests call it without a database.

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

| From | To | Condition |
|---|---|---|
| `CLOSED` | `OPEN_RECOMMENDED` | CO₂ ≥ `co2_open_ppm` and humidity > `humidity_min_pct`. |
| `CLOSED` | `OPEN_RECOMMENDED` | Humidity ≥ `humidity_open_pct`. |
| `CLOSED` | `OPEN_RECOMMENDED` | CO₂ ≥ `co2_max_ppm`. |
| `OPEN_RECOMMENDED` | `CLOSED` | CO₂ ≤ `co2_close_ppm` and humidity ≤ `humidity_close_pct`. |
| `OPEN_RECOMMENDED` | `CLOSED` | Humidity ≤ `humidity_min_pct` and CO₂ < `co2_max_ppm`. |

Two checks run before any transition:

- **Stale data.** A reading older than `ignore_measurements_older_than_min` triggers nothing.
- **Cooldown.** The state does not change within `cooldown_min` of the last notification.

### Threshold values

A fresh install starts with the defaults from the migration. The tuned values are the ones I set at home with `PATCH /settings/thresholds`. [DESIGN.md](DESIGN.md#threshold-values) explains the tuned values.

| Setting | Default | Tuned for my room |
|---|---|---|
| `co2_open_ppm` | 1200 | 1000 |
| `co2_close_ppm` | 800 | 850 |
| `co2_max_ppm` | 2000 | 1500 |
| `humidity_open_pct` | 65 | 60 |
| `humidity_close_pct` | 55 | 57 |
| `humidity_min_pct` | 30 | 35 |
| `cooldown_min` | 15 | 5 |
| `ignore_measurements_older_than_min` | 5 | 5 |

## Notification worker

The API never calls Telegram. It writes a row to the `notifications` table, which is the outbox. The worker reads the outbox with this query:

```sql
SELECT * FROM notifications
WHERE sent_at IS NULL AND attempts < 5
ORDER BY created_at, id
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

| Result | Action |
|---|---|
| Sent | Sets `sent_at = now()` and commits. |
| Failed | Adds 1 to `attempts`, stores the error text, and commits. The next loop tries the row again. |
| Failed 5 times | The query skips the row from then on, so the row no longer blocks newer messages. |
| Outbox empty | Sleeps for 5 s. |

`SKIP LOCKED` lets several workers run without sending a message twice. A partial index on `created_at WHERE sent_at IS NULL` keeps the query fast as the table grows.

### Token protection

The Telegram URL contains the bot token. httpx puts the URL into its exception text and logs every request URL at INFO level. So the sender raises a `TelegramError` that contains only the exception type or the description from Telegram. The worker also sets the httpx log level to WARNING. If Telegram is not configured, the worker only logs the messages.

## Security

| Area | Measure |
|---|---|
| Write endpoints | Need the `X-API-Key` header. The API compares it with `secrets.compare_digest`. |
| Secrets | Come from `.env` at runtime through `env_file`. `.dockerignore` keeps `.env` out of the image, and `.gitignore` keeps it out of git. Pydantic `SecretStr` keeps the secrets out of logs and reprs. |
| Grafana | Logs in as `grafana_reader`. The role has `SELECT` on `measurements` and `threshold_settings`, and `SELECT` on every column of `notifications` except `last_error`. |
| Network | Postgres, Redis, and Grafana listen on `127.0.0.1` only. Only the API is reachable on the LAN. |
| Device | The API key is in the flash of the ESP32, so anyone who holds the board can read the key. That is acceptable at home. A production system needs HTTPS and one revocable key per device. |

## Failure behavior

| Situation | What happens |
|---|---|
| The Mac sleeps or the backend is stopped | The ESP32 keeps measuring and stores up to one week of readings. Later it uploads the backlog with the original timestamps. |
| The response is lost after a successful insert | The ESP32 sends the batch again. The unique constraint counts the rows as `duplicates`, and Postgres stores nothing twice. |
| Wi-Fi is down | The ESP32 behaves as if the backend were down. It stores the readings and tries again every 30 s. |
| A batch has an invalid reading | The API returns 422. The batch stays on the device, and the device tries again. |
| Redis is down | The API logs a warning and reads from Postgres. |
| Telegram is down or the token is wrong | The notification stays in the outbox for up to 5 attempts. |
| An old backlog arrives | The API stores it but sends no notification, because the readings are older than 5 minutes. |
| The Mac reboots | Docker Desktop starts at login and restarts all containers. The ESP32 reads its buffer header from flash after its own reboot. |

## Known limitations

- The rule knows its last recommendation, not the real state of the window. If I close the window before CO₂ falls below `co2_close_ppm`, the state stays `OPEN_RECOMMENDED`. No new "open" message comes until the state has gone back to `CLOSED` once.
- The rule sends one message per state change, also at night. It has no reminders and no quiet hours.
- A full buffer overwrites the oldest readings, so an outage longer than one week loses data.
- The firmware stores nothing between power-on and the first NTP sync, because it needs NTP for the timestamps.
- All devices share one API key, and Postgres keeps old readings forever.
