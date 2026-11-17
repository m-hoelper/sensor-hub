# Design decisions

This document explains the choices that shaped Sensor Hub, the alternatives I rejected, and the reasons. [ARCHITECTURE.md](ARCHITECTURE.md) describes how the result works.

## Data path

| Decision | Chosen | Rejected alternative and reason |
|---|---|---|
| Who moves the data | **Push.** The ESP32 uploads when the backend answers. | **Pull by a backend job.** The backend would need the address of every device, and the ESP32 would need an HTTP server open on the LAN. The device would still need to learn which readings the backend fetched. With push, the upload loop on the device is the sync job. |
| Where readings wait | **A ring buffer in the flash of the ESP32**, on LittleFS. | **PSRAM** loses the readings on power loss. **An SD card or a USB stick** is extra hardware with no benefit. **A Raspberry Pi as an always-on server** is one more machine to maintain. |
| Record format | **Integers**, such as temperature × 100. | **Floats** make the record larger and do not store values such as 21.37 exactly. |
| Buffer size | **One week**, 20,160 records of 16 bytes, about 320 KB. | **Deleting readings after a week** would drop readings that were never uploaded. The buffer size is not a retention period. It is how long the backend can be offline without data loss. |
| Interval | **30 s average of 1 s samples.** | **5 s** gives six times the data and heats the sensor more, with no benefit for the air in a room. |
| Timestamp | **Device time** from NTP, in UTC, in every reading. | **Server time on arrival.** A reading from 3 a.m. uploaded at 9 a.m. would be stored with 9 a.m. |
| Duplicates | **A unique constraint on `(device_id, created_at)` and `ON CONFLICT DO NOTHING`.** | **No protection.** A lost response causes a resend and duplicate rows. **A "sent" flag on the client** is still wrong when the response is lost. |
| Write endpoint | **One `POST /measurements` that takes only batches.** A single reading is a batch of 1. | **A single-reading endpoint next to a batch endpoint.** The two write paths would need the same validation, duplicate handling, rule call, and cache invalidation, and could drift apart. |
| Batch size | **500 readings or fewer**, about 50 KB of JSON. | **No limit.** After a week offline, the device would send one large request, and the JSON document would not fit in the RAM of the ESP32. |

## Notifications

| Decision | Chosen | Rejected alternative and reason |
|---|---|---|
| Where the rule runs | **In the API, inside the insert transaction.** | **A separate job that scans new rows** adds a process and needs its own record of which rows it has evaluated. |
| Which reading the rule evaluates | **The newest reading of the batch, if it is fresh.** | **Every reading of a backlog** would send hours of old messages after an outage. |
| How messages leave | **An outbox table and a worker.** | **A Telegram call inside the request.** A slow Telegram would slow down the upload, and a failing Telegram would fail it. A crash between commit and send would lose the message. |
| Concurrent workers | **`FOR UPDATE SKIP LOCKED`.** | **A plain `SELECT`** lets two workers send the same message. |
| Rule shape | **Two states with hysteresis.** The open threshold is above the close threshold. | **One threshold.** When CO₂ stays near the threshold, the state switches every few minutes. |
| Where thresholds live | **In the database, changed with `PATCH` at runtime.** | **Constants in code.** Every change would need a rebuild and a redeploy. |
| Thresholds learned from past data | **Not done.** | The open thresholds are health limits, not properties of a room. If the system learned them from data, a room with stale air would teach it that stale air is normal. |

## Threshold values

The tuned values follow the guidance of the German Environment Agency (Umweltbundesamt). It rates CO₂ below 1000 ppm as harmless and above 2000 ppm as unacceptable, and it recommends 40 to 60 % relative humidity. [ARCHITECTURE.md](ARCHITECTURE.md#threshold-values) lists the defaults and the tuned values.

The gap between the open and close thresholds is small because of real data from my room. The humidity in the room stays between 55 and 58 % whether the window is open or closed. With the close threshold at 50 %, the state stayed in `OPEN_RECOMMENDED`, and the "close" message never came. Humidity changes slowly and smoothly, so a gap of 3 percentage points is enough. CO₂ jumps by 50 to 100 ppm when someone moves, so CO₂ gets a gap of 150 ppm.

The dry-air rule exists because of heating in winter. Cold outside air holds little water, so airing a heated room makes the air drier. Below `humidity_min_pct`, the rule waits for a higher CO₂ value, `co2_max_ppm`, before it recommends airing. In dry air, it recommends closing as soon as CO₂ is below `co2_max_ppm`.

## Backend and deployment

| Decision | Chosen | Rejected alternative and reason |
|---|---|---|
| Dashboard | **Grafana reads Postgres directly** and is provisioned from files. | **A custom frontend** is a lot of code for a personal dashboard. |
| Grafana access | **A read-only role with column-level grants.** | **The application user** would let Grafana write data and read error texts it does not need. |
| Cache | **Redis for the latest reading, on a best-effort basis.** | **No cache** is fine at this scale. But `/measurements/latest` is the endpoint a dashboard or an app polls. A Redis failure does not fail the API. |
| Migrations | **Alembic, run by the API container at start.** | **`create_all` at start** keeps no schema history and cannot change columns safely. **A separate migration job** is the right choice for several API replicas, but this setup has one. |
| Secrets | **`.env`, read at runtime through `env_file`.** | **Secrets in the image.** Anyone with the image has the keys. |
| Packaging | **uv with a lock file, and dependencies in their own image layer.** | **pip without a lock file** gives builds that change over time. **Copying the code before installing the dependencies** reinstalls all dependencies after every code change. |
| Hosting | **Docker Compose on my laptop.** | **Cloud hosting.** The device buffer already covers the hours when the laptop is off. For one room, that is not worth the cost and an open internet port. |
