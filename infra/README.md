# Infrastructure

This directory contains infrastructure configuration and deployment files.

## Docker

Docker configuration files are at the repository root:
- `docker-compose.yml` - Production-like compose configuration
- `docker-compose.dev.yml` - Development overrides (hot reload)
- `Dockerfile` - API + Worker image
- `Dockerfile.streamlit` - UI image

## Database

Database migrations are managed by Alembic in `/alembic/`.

```bash
# Run migrations
docker compose exec api alembic upgrade head

# Create new migration
docker compose exec api alembic revision --autogenerate -m "Description"
```

## Environment Variables

See `.env.example` for required environment variables.
