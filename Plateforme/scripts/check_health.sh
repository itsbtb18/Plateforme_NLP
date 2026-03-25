#!/bin/sh
set -e

echo "[healthcheck] starting startup checks"

required_vars="DJANGO_SECRET_KEY DJANGO_ALLOWED_HOSTS DATABASE_URL REDIS_URL METRICS_TOKEN"
for var_name in $required_vars; do
  eval var_value="\${$var_name}"
  if [ -z "$var_value" ]; then
    echo "[healthcheck] missing required env var: $var_name"
    exit 1
  fi
done

echo "[healthcheck] required env vars: ok"

if command -v pg_isready >/dev/null 2>&1; then
  db_url="${DATABASE_URL:-}"
  db_host="$(echo "$db_url" | sed -n 's#.*@\([^:/]*\).*#\1#p')"
  db_port="$(echo "$db_url" | sed -n 's#.*:\([0-9][0-9]*\)/.*#\1#p')"
  db_user="$(echo "$db_url" | sed -n 's#.*://\([^:]*\):.*#\1#p')"
  db_name="$(echo "$db_url" | sed -n 's#.*/\([^?]*\).*#\1#p')"

  db_host="${db_host:-db}"
  db_port="${db_port:-5432}"

  if ! pg_isready -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" >/dev/null 2>&1; then
    echo "[healthcheck] database connection check failed"
    exit 1
  fi
else
  echo "[healthcheck] pg_isready not found"
  exit 1
fi

echo "[healthcheck] database: ok"

if command -v redis-cli >/dev/null 2>&1; then
  redis_host="$(echo "$REDIS_URL" | sed -n 's#.*@\([^:/]*\).*#\1#p')"
  redis_port="$(echo "$REDIS_URL" | sed -n 's#.*:\([0-9][0-9]*\)/.*#\1#p')"
  redis_password="$(echo "$REDIS_URL" | sed -n 's#redis://:\([^@]*\)@.*#\1#p')"
  redis_host="${redis_host:-redis}"
  redis_port="${redis_port:-6379}"

  if [ -n "$redis_password" ]; then
    if ! redis-cli -h "$redis_host" -p "$redis_port" -a "$redis_password" ping | grep -q PONG; then
      echo "[healthcheck] redis connection check failed"
      exit 1
    fi
  else
    if ! redis-cli -h "$redis_host" -p "$redis_port" ping | grep -q PONG; then
      echo "[healthcheck] redis connection check failed"
      exit 1
    fi
  fi
else
  echo "[healthcheck] redis-cli not found"
  exit 1
fi

echo "[healthcheck] redis: ok"

for dir_path in /app/media /app/media/scraping; do
  if [ ! -d "$dir_path" ]; then
    mkdir -p "$dir_path"
  fi
  if [ ! -w "$dir_path" ]; then
    echo "[healthcheck] directory is not writable: $dir_path"
    exit 1
  fi
done

echo "[healthcheck] media directories: ok"

echo "[healthcheck] startup checks passed"
exec "$@"
