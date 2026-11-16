# Run notes

## Backend

Needs Docker (Docker Desktop on macOS).

```bash
cp .env.example .env               # then fill in the values below
docker compose up -d --build       # all five services in the background
scripts/create_grafana_role.sh     # once, and again after changing GRAFANA_DB_PASSWORD
```

| Variable | Used for |
|---|---|
| `API_KEY` | `X-API-Key` header for write endpoints; the same value goes into the firmware's `secrets.h` |
| `DB_PASSWORD` | Postgres password. Only applied when the database volume is created for the first time |
| `DATABASE_URL`, `REDIS_URL` | For running the API outside Docker (`localhost`). Compose overrides both with the service names |
| `TEST_DATABASE_URL` | Separate database for the tests |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional. Without them the worker only logs messages. `scripts/telegram_chat_id.py` finds the chat id after you message the bot |
| `GRAFANA_DB_PASSWORD` | Password of the read-only `grafana_reader` role |

| URL | What |
|---|---|
| `http://localhost:8000/docs` | API with interactive docs |
| `http://localhost:3000` | Grafana dashboard (no login, read-only) |

## Which command after which change

| Change | Command |
|---|---|
| Python code, migration, Dockerfile, dependencies | `docker compose up -d --build` |
| `.env` | `docker compose up -d` (recreates the containers; `restart` would keep the old environment) |
| Thresholds | `PATCH /settings/thresholds`, no restart |
| Wi-Fi, API key or backend URL on the device | Edit `secrets.h` and flash again |

Do not run `uvicorn` on the host at the same time: it competes with the `api` container for port 8000.

## Firmware

Needs PlatformIO (VS Code extension or CLI). Board: ESP32-S3 with 16 MB flash and 8 MB PSRAM (`esp32-s3-devkitc-1` in [`platformio.ini`](../firmware/platformio.ini)).

**Wiring** (SCD40 → ESP32-S3): VDD → 3V3, GND → GND, SDA → GPIO 8, SCL → GPIO 9. The SCD40's I²C address is `0x62`.

```bash
cd firmware
cp include/secrets.example.h include/secrets.h     # Wi-Fi, API key, BACKEND_URL=http://<mac-ip>:8000/measurements
pio run -t upload
pio device monitor                                  # serial log: readings, stored records, POST results
```

- The first record is stored about 4.5 minutes after power-on (warm-up plus the first 30 s window).
- The Mac needs a fixed address on the LAN (DHCP reservation in the router) and must allow incoming connections for Docker.
- A `POST … → 401` in the serial log means the API key in `secrets.h` does not match `.env`. The device keeps buffering until it matches.

## Without hardware

```bash
uv run python scripts/simulator.py      # random readings for three fake devices, same batch format as the ESP32
```

## Tests

The tests need a Postgres database at `TEST_DATABASE_URL` (the `db` container works; create a separate database for it).

```bash
uv sync
uv run pytest
```

## Useful commands

```bash
docker compose ps                         # status of all services
docker compose logs -f api worker         # live logs: uploads, rule decisions, Telegram sends
docker stats                              # CPU and memory per container
curl -s localhost:8000/settings/thresholds
curl -s localhost:8000/notifications/state
curl -s -X PATCH localhost:8000/settings/thresholds \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"co2_close_ppm": 850}'
```
