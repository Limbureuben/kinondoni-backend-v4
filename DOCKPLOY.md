# Deploying the Django API on Dockploy

Create PostgreSQL, Redis, and this Dockerfile application in the same Dockploy
project/network. The Django container port is `8000`, its health-check path is
`/health/`, and uploaded files need a persistent volume mounted at `/app/media`.

## Required environment variables

```env
DJANGO_ENVIRONMENT=production
SECRET_KEY=replace-with-a-long-random-secret
DEBUG=False
ALLOWED_HOSTS=kinodonibackend.ubunix.co.tz

POSTGRES_DB=openspace
POSTGRES_USER=openspace
POSTGRES_PASSWORD=replace-with-a-strong-password
DATABASE_HOST=your-postgres-service-name
DATABASE_PORT=5432

REDIS_URL=redis://your-redis-service-name:6379/0
CELERY_BROKER_URL=redis://your-redis-service-name:6379/0
CELERY_RESULT_BACKEND=redis://your-redis-service-name:6379/0

FRONTEND_URL=https://kinondoni.ubunix.co.tz
BACKEND_URL=https://kinodonibackend.ubunix.co.tz
CORS_ALLOWED_ORIGINS=https://kinondoni.ubunix.co.tz
CSRF_TRUSTED_ORIGINS=https://kinondoni.ubunix.co.tz

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Use Dockploy's internal service names for PostgreSQL and Redis, not
`localhost`. Do not expose either database service publicly.

Point the backend domain, such as `api.example.com`, to container port `8000`.
Before building Angular, set its production API URL:

```ts
apiUrl: 'https://api.example.com'
```

The CORS origin must exactly match the Angular origin, including `https://` and
without a trailing slash.

For background jobs, create services from the same image and override commands:

```sh
celery -A openspace worker --loglevel=info
```

```sh
celery -A openspace beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```
