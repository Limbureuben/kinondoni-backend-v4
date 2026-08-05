set -e

export PGPASSWORD=1234


echo "Waiting for Postgres at db:5432..."


until pg_isready -h db -p 5432 -U postgres; do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done


echo "Postgres is up - executing command"
exec "$@"
