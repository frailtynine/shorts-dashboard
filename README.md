# YouTube Analytics API

FastAPI service for retrieving and storing YouTube Shorts metadata per channel.

## Setup

1. Copy `.env.example` to `.env` and fill API keys.
2. Install deps: `make install`
3. Apply migrations: `make db-upgrade`
4. Run app: `make run`

## Database migrations

- Upgrade to latest: `make db-upgrade`
- Downgrade one revision: `make db-downgrade`
- Create revision: `make db-revision m="describe_change"`

## Dashboard

- Open `http://127.0.0.1:8000/api/dashboard` for a weekly dashboard view.
- It shows weekly subject distribution (themes), duration, and views.
