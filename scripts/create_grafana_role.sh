#!/usr/bin/env bash
# Create (or update) the read-only Postgres role Grafana logs in with.
# Idempotent: safe to run again, e.g. after changing GRAFANA_DB_PASSWORD in .env.
# Run from anywhere: scripts/create_grafana_role.sh   (needs `docker compose up -d db`)
set -euo pipefail
cd "$(dirname "$0")/.."

password=$(grep '^GRAFANA_DB_PASSWORD=' .env | cut -d= -f2-)
if [ -z "$password" ]; then
    echo "GRAFANA_DB_PASSWORD is missing in .env" >&2
    exit 1
fi

docker compose exec -T db psql -v ON_ERROR_STOP=1 -U sensor -d sensorhub -v pw="$password" <<'SQL'
-- role: create once, (re)set the password every run
SELECT 'CREATE ROLE grafana_reader LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_reader') \gexec
ALTER ROLE grafana_reader WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'pw';

-- least privilege: connect + read exactly what the dashboard queries, nothing else
GRANT CONNECT ON DATABASE sensorhub TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON measurements, threshold_settings TO grafana_reader;
REVOKE SELECT ON notifications FROM grafana_reader;
GRANT SELECT (id, measurement_id, new_state, message, created_at, sent_at, attempts)
    ON notifications TO grafana_reader;        -- column-level: last_error stays unreadable
SQL

echo "grafana_reader is ready"
