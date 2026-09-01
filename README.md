# YouTube Analytics API

FastAPI service for retrieving and storing YouTube Shorts metadata per channel.

## Setup

1. Copy `.env.example` to `.env` and fill API keys.
2. Install deps: `make install`
3. Apply migrations: `make db-upgrade`
4. Run app: `make run`

Default local database URL:

- `sqlite:////data/youtube_analytics.db` for Docker deployments
- override `SQLITE_URL` in `.env` if you want a different path for local runs

## Database migrations

- Upgrade to latest: `make db-upgrade`
- Downgrade one revision: `make db-downgrade`
- Create revision: `make db-revision m="describe_change"`

## Docker

- Start with `make docker-up`
- App listens on `http://127.0.0.1:8400`
- Docker Compose mounts `./data` to `/data`
- The container runs `alembic upgrade head` automatically before starting `uvicorn`

## Dashboard

- Open `http://127.0.0.1:8400/` for a weekly dashboard view.
- It shows weekly subject distribution (themes), duration, and views.
