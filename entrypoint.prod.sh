#!/bin/sh
set -eu

echo "Waiting for the database and applying migrations..."
attempt=1
until python manage.py migrate --noinput; do
    if [ "$attempt" -ge 30 ]; then
        echo "Database was not ready after 30 attempts."
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Django..."
exec "$@"
