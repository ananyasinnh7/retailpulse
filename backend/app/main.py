from datetime import date, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .analytics import dashboard, forecast, recommendations
from .database import Base, SessionLocal, engine
from .models import Product, Sale

app = FastAPI(title="RetailPulse API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed():
    db = SessionLocal()
    if db.query(Product).count():
        db.close()
        return
    products = [
        Product(name="Cold Brew", category="Beverages", price=5.5, cost=1.6, stock=24, reorder_level=30),
        Product(name="Avocado Toast", category="Food", price=9.5, cost=3.1, stock=42, reorder_level=15),
        Product(name="Blueberry Muffin", category="Bakery", price=4.25, cost=1.2, stock=12, reorder_level=20),
        Product(name="Matcha Latte", category="Beverages", price=6.25, cost=2.0, stock=65, reorder_level=25),
        Product(name="Granola Bowl", category="Food", price=8.75, cost=2.9, stock=18, reorder_level=20),
    ]
    db.add_all(products)
    db.flush()
    for day in range(30):
        sale_date = date.today() - timedelta(days=29 - day)
        for product in products:
            units = max(1, ((day * (product.id + 2) + product.id * 3) % 12) + 2)
            db.add(Sale(product_id=product.id, sale_date=sale_date, units=units,
                        revenue=round(units * product.price, 2)))
    db.commit()
    db.close()


seed()

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard(db)

@app.get("/api/recommendations")
def get_recommendations(db: Session = Depends(get_db)):
    return recommendations(db)

@app.get("/api/forecast")
def get_forecast(db: Session = Depends(get_db)):
    return forecast(db)

frontend = Path(__file__).parents[2] / "frontend"
app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

@app.get("/", response_class=FileResponse)
def home():
    return frontend / "index.html"
