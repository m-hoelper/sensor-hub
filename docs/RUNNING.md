# Run Sensor Hub

This guide shows how to start the backend, flash the firmware, and run the tests.

## Start the backend

You need Docker. On macOS, use Docker Desktop.

1. Copy the example environment file:

	```bash
	cp .env.example .env
	```

2. Fill in the values in `.env`. The table after these steps describes them.
3. Start all five services in the background:

	```bash
	docker compose up -d --build
	```

4. Create the read-only Postgres role for Grafana. Run this command again each time you change `GRAFANA_DB_PASSWORD`.

	```bash
	scripts/create_grafana_role.sh
	```

| Variable | Use |
|---|---|
| `API_KEY` | The `X-API-Key` header for write endpoints. The firmware needs the same value in `secrets.h`. |
| `DB_PASSWORD` | The Postgres password. Postgres reads it only when Docker creates the database volume for the first time. |
| `DATABASE_URL`, `REDIS_URL` | The database and Redis addresses for an API that runs outside Docker, on `localhost`. Compose replaces both with the service names. |
| `TEST_DATABASE_URL` | A separate database for the tests. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional. Without them, the worker only logs the messages. To find the chat ID, send a message to the bot and run `scripts/telegram_chat_id.py`. |
| `GRAFANA_DB_PASSWORD` | The password of the read-only `grafana_reader` role. |

When the stack runs, these pages are available:

| URL | Page |
|---|---|
| `http://localhost:8000/docs` | The interactive API docs. |
| `http://localhost:3000` | The Grafana dashboard, read-only and without login. |

Do not run `uvicorn` on the host while the stack runs. It competes with the `api` container for port 8000.

## Apply a change

| Change | Command |
|---|---|
| Python code, a migration, the Dockerfile, or dependencies | `docker compose up -d --build` |
| `.env` | `docker compose up -d`. This command recreates the containers. `docker compose restart` keeps the old environment. |
| Thresholds | `PATCH /settings/thresholds`. No restart is needed. |
| Wi-Fi, API key, or backend URL on the device | Edit `secrets.h` and flash the firmware again. |

## Flash the firmware

You need PlatformIO, as the VS Code extension or as the CLI. The board is an ESP32-S3 with 16 MB flash and 8 MB PSRAM. [`platformio.ini`](../firmware/platformio.ini) sets it up as `esp32-s3-devkitc-1`.

1. Wire the SCD40 to the ESP32-S3:

	| SCD40 | ESP32-S3 |
	|---|---|
	| VDD | 3V3 |
	| GND | GND |
	| SDA | GPIO 8 |
	| SCL | GPIO 9 |

	The I²C address of the SCD40 is `0x62`.

2. Create the secrets file:

	```bash
	cd firmware
	cp include/secrets.example.h include/secrets.h
	```

3. Fill in Wi-Fi, the API key, and the backend URL in `include/secrets.h`. The backend URL has the form `http://<mac-ip>:8000/measurements`.
4. Build and flash the firmware:

	```bash
	pio run -t upload
	```

5. Open the serial log. It shows the readings, the stored records, and the POST results.

	```bash
	pio device monitor
	```

The first record arrives about 4.5 minutes after power-on: 4 minutes of warm-up, then the first 30 s window.

For the ESP32 to reach the Mac, the Mac needs a fixed address on the LAN and must allow incoming connections for Docker. To get a fixed address, set up a DHCP reservation in the router.

If the serial log shows `POST <n> records → 401`, the API key in `secrets.h` does not match `.env`. The device keeps the readings until the keys match.

## Send readings without hardware

The simulator sends random readings for three fake devices, in the same batch format as the ESP32:

```bash
uv run python scripts/simulator.py
```

## Run the tests

The tests need a separate Postgres database at `TEST_DATABASE_URL`. You can create that database in the `db` container.

```bash
uv sync
uv run pytest
```

## Inspect the running stack

```bash
docker compose ps
```

```bash
docker compose logs -f api worker
```

```bash
docker stats
```

The first command shows the status of all services. The second follows the logs of uploads, rule decisions, and Telegram sends. The third shows CPU and memory per container.

To read the thresholds and the window state:

```bash
curl -s localhost:8000/settings/thresholds
```

```bash
curl -s localhost:8000/notifications/state
```

To change one threshold:

```bash
curl -s -X PATCH localhost:8000/settings/thresholds \
	-H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
	-d '{"co2_close_ppm": 850}'
```
