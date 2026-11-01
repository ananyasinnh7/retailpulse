import io
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.main import app

client = TestClient(app)


def account():
    response = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "securepass123",
    })
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "securepass123",
        })
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_dashboard_has_business_metrics():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json()["revenue"] > 0


def test_authentication_protects_inventory():
    assert client.get("/api/products").status_code == 401
    response = client.get("/api/products", headers=account())
    assert response.status_code == 200
    assert len(response.json()) >= 5


def test_sales_import_validates_and_imports_csv():
    headers = account()
    csv_file = io.BytesIO(b"date,product,units\n2026-11-01,Cold Brew,3\n")
    response = client.post("/api/import/sales", headers=headers,
                           files={"file": ("sales.csv", csv_file, "text/csv")})
    assert response.status_code == 200
    assert response.json()["imported"] == 1


def test_segments_and_alerts_are_available():
    headers = account()
    segments = client.get("/api/customers/segments", headers=headers)
    alerts = client.get("/api/alerts", headers=headers)
    assert segments.status_code == 200
    assert len(segments.json()) >= 5
    assert alerts.status_code == 200
    assert any(item["type"] == "inventory" for item in alerts.json())


def test_promotion_simulation_and_refresh():
    headers = account()
    simulation = client.post("/api/promotions/simulate", headers=headers, json={
        "weekly_revenue": 1000, "discount_percent": 15,
        "expected_volume_lift_percent": 25,
    })
    assert simulation.status_code == 200
    assert simulation.json()["projected_revenue"] == 1062.5
    refreshed = client.post("/api/operations/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert "refreshed_at" in refreshed.json()


def test_sales_report_is_protected_and_downloadable():
    assert client.get("/api/reports/sales.csv").status_code == 401
    response = client.get("/api/reports/sales.csv", headers=account())
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.splitlines()[0] == "date,product,category,units,revenue,profit"
