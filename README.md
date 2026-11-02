# RetailPulse

RetailPulse is an end-to-end retail intelligence platform for small businesses. It turns sales and inventory data into clear decisions about revenue, stock, demand, and promotions.

## Current MVP

- FastAPI backend with SQLite development mode and PostgreSQL deployment mode
- Seeded retail sales and inventory dataset
- Revenue, margin, inventory health, and category analytics
- Seven-day demand forecast and reorder recommendations
- Account registration/login with protected inventory APIs
- Validated CSV sales imports
- Product creation and inventory updates
- Promotion simulation with break-even analysis
- Protected operations refresh endpoint for scheduled jobs
- Downloadable CSV sales reports
- Promotion simulation history and product deletion safeguards
- Responsive dashboard served at `/`

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API documentation is available at http://127.0.0.1:8000/docs.

## Docker deployment

Docker Compose starts the API with PostgreSQL:

```bash
docker compose up --build
```

Set `DATABASE_URL` and `CORS_ORIGINS` to configure another deployment. New passwords use PBKDF2-SHA256 and sessions expire after 24 hours.

## API examples

Register or log in to receive a bearer token, then use it for protected endpoints:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex Smith","email":"alex@example.com","password":"securepass123"}'

curl http://127.0.0.1:8000/api/products \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

Sales CSV files must contain `date,product,units` columns. Product names must match the inventory catalog.

Promotion simulations accept weekly revenue, discount percentage, and expected volume lift. The API returns projected revenue, revenue change, break-even lift, and a recommendation.

Authenticated users can download the complete sales report from `GET /api/reports/sales.csv`.

The hourly operations workflow calls `/api/operations/refresh`. Configure the repository secrets `RETAILPULSE_URL` and `RETAILPULSE_TOKEN` for a deployed environment.

## Roadmap

Scheduled jobs, richer promotion experiments, and production hosting are planned next.
Retail intelligence platform for inventory forecasting, promotion analysis, and business decision support.
