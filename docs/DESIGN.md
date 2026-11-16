# Design decisions

The choices that shaped the system, what was rejected and why. How the result works is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Data path

| Decision | Chosen | Rejected alternative, and why |
|---|---|---|
| Who moves the data | **Push**: the ESP32 uploads when the backend answers | **Pull** by a backend job: the backend would need every device's address, the ESP32 would need an HTTP server open on the LAN, and the device would still need to learn what was fetched. With push, the device loop is the sync job |
| Where readings wait | **Ring buffer in the ESP32's flash** (LittleFS) | PSRAM: lost on power loss. SD card or USB stick: extra hardware for no gain. A Raspberry Pi as an always-on server: one more machine to maintain |
| Buffer size | **One week** (20,160 × 16 B ≈ 320 KB) | "Delete after a week": would drop readings that were never uploaded. The buffer is not a retention period; it is how long the backend may be offline without losing data |
| Interval | **30 s average of 1 s samples** | 5 s: six times the data and more sensor self-heating, with no benefit for a room's air |
| Timestamp | **Device time** (NTP, UTC) in every reading | Server time on arrival: a reading from 3 a.m. uploaded at 9 a.m. would be stored at 9 a.m. |
| Duplicates | **Unique `(device_id, created_at)` + `ON CONFLICT DO NOTHING`** | No protection: a lost response leads to a resend and duplicate rows. Client-side "sent" flags: still wrong when the response is lost |
| Write endpoint | **One `POST /measurements` that only takes batches** (a single reading is a batch of 1) | A single-reading endpoint next to a batch endpoint: two write paths whose validation, duplicate handling, rules and cache invalidation must stay in sync |
| Batch size | **≤ 500 readings** (about 50 KB of JSON) | Unlimited: one huge request after a week offline, too much RAM on the ESP32 for the JSON document |

## Notifications

| Decision | Chosen | Rejected alternative, and why |
|---|---|---|
| Where the rule runs | **In the API, inside the insert transaction** | A separate job that scans new rows: more moving parts, and it needs its own bookkeeping of what it has already evaluated |
| Which reading is evaluated | **The newest reading of the batch, if it is fresh** | Every reading of a backlog: replays hours of old alarms after an outage |
| How messages leave | **Outbox table + worker** | Calling Telegram inside the request: a slow or failing Telegram would slow down or fail the upload, and a crash between commit and send would lose the message |
| Worker concurrency | **`FOR UPDATE SKIP LOCKED`** | Plain `SELECT`: two workers could send the same message |
| Rule shape | **Two states with hysteresis** (open > close threshold) | One threshold: the state flips every few minutes when CO₂ hovers around it |
| Thresholds | **In the database, changed with `PATCH` at runtime** | Constants in code: every adjustment would need a rebuild and a redeploy |
| Self-adjusting thresholds from past data | **Not done** | The open thresholds are health limits, not properties of a room; learning them from data would let a stuffy room teach the system that stuffy is normal |

## Backend and deployment

| Decision | Chosen | Rejected alternative, and why |
|---|---|---|
| Visualisation | **Grafana reading Postgres directly**, provisioned from files | A custom frontend: lots of code for a personal dashboard |
| Grafana access | **Read-only role with column-level grants** | The application user: Grafana could write or read error texts it does not need |
| Cache | **Redis for the latest reading, best effort** | No cache: fine at this scale, but the endpoint is the one a dashboard or app would poll. The cache may fail without failing the API |
| Migrations | **Alembic, run by the API container on start** | `create_all` at start-up: no schema history, no safe column changes. A separate migration job: the right choice with several API replicas, unnecessary with one |
| Secrets | **`.env` injected at runtime** (`env_file`) | Baked into the image: anyone with the image has the keys |
| Packaging | **uv with a lock file, dependencies installed in their own image layer** | pip without a lock: builds that change over time. Copying the code before installing: every code change reinstalls all dependencies |
| Hosting | **Docker Compose on the laptop** | Cloud hosting: the device buffer already covers the hours when the laptop is off, so the cost and the open internet port are not worth it for one room |
