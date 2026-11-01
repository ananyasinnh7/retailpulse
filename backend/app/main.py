import csv
import io
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .analytics import (alerts, customer_segments, dashboard, forecast,
                        promotion_simulation, recommendations)
from .auth import create_token, hash_password, require_user, verify_password
from .database import Base, SessionLocal, engine
from .models import Customer, CustomerPurchase, Product, Sale, User
from .schemas import LoginRequest, ProductRequest, PromotionRequest, RegisterRequest

app = FastAPI(title="RetailPulse API", version="0.1.0")
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticated_user(authorization: str | None = Header(default=None),
                       db: Session = Depends(get_db)):
    return require_user(authorization, db)


def seed():
    db = SessionLocal()
    if not db.query(Product).count():
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
    if not db.query(Customer).count():
        customers = [Customer(name=name, email=f"{name.lower().replace(' ', '.')}@example.com",
                              joined_at=date.today() - timedelta(days=120 - index * 11))
                     for index, name in enumerate(["Maya Chen", "Jordan Lee", "Sam Rivera",
                                                   "Priya Shah", "Noah Wilson", "Olivia Brown"])]
        db.add_all(customers)
        db.flush()
        for customer in customers:
            for purchase in range(3 + customer.id):
                db.add(CustomerPurchase(
                    customer_id=customer.id,
                    purchase_date=date.today() - timedelta(days=(purchase * 6 + customer.id * 2) % 42),
                    amount=round(18 + customer.id * 7 + purchase * 4.5, 2),
                ))
    db.commit()
    db.close()


seed()

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=payload.name.strip(), email=email,
                password_hash=hash_password(payload.password),
                created_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(db, user), "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(db, user), "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/api/auth/me")
def me(user: User = Depends(authenticated_user)):
    return {"id": user.id, "name": user.name, "email": user.email}

@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard(db)

@app.get("/api/recommendations")
def get_recommendations(db: Session = Depends(get_db)):
    return recommendations(db)

@app.get("/api/forecast")
def get_forecast(db: Session = Depends(get_db)):
    return forecast(db)


@app.get("/api/customers/segments")
def get_customer_segments(db: Session = Depends(get_db), _: User = Depends(authenticated_user)):
    return customer_segments(db)


@app.get("/api/alerts")
def get_alerts(db: Session = Depends(get_db), _: User = Depends(authenticated_user)):
    return alerts(db)


@app.post("/api/promotions/simulate")
def simulate_promotion(payload: PromotionRequest,
                       _: User = Depends(authenticated_user)):
    return promotion_simulation(**payload.model_dump())


@app.post("/api/operations/refresh")
def refresh_operations(db: Session = Depends(get_db), _: User = Depends(authenticated_user)):
    return {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "recommendations": len(recommendations(db)),
        "alerts": len(alerts(db)),
    }


@app.get("/api/products")
def list_products(db: Session = Depends(get_db), _: User = Depends(authenticated_user)):
    return db.query(Product).order_by(Product.category, Product.name).all()


@app.post("/api/products", status_code=201)
def create_product(payload: ProductRequest, db: Session = Depends(get_db),
                   _: User = Depends(authenticated_user)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.patch("/api/products/{product_id}", response_model=None)
def update_product(product_id: int, payload: ProductRequest, db: Session = Depends(get_db),
                   _: User = Depends(authenticated_user)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    return product


@app.post("/api/import/sales")
async def import_sales(file: UploadFile = File(...), db: Session = Depends(get_db),
                       _: User = Depends(authenticated_user)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    raw = await file.read()
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        required = {"date", "product", "units"}
        if not rows or not required.issubset(rows[0]):
            raise ValueError("CSV must contain date, product, and units columns")
        products = {p.name.lower(): p for p in db.query(Product).all()}
        imported = 0
        for row in rows:
            product = products.get(row["product"].strip().lower())
            if not product:
                raise ValueError(f"Unknown product: {row['product']}")
            units = int(row["units"])
            if units <= 0:
                raise ValueError("Units must be positive")
            sale_date = date.fromisoformat(row["date"])
            db.add(Sale(product_id=product.id, sale_date=sale_date, units=units,
                        revenue=round(units * product.price, 2)))
            imported += 1
        db.commit()
        return {"imported": imported}
    except (UnicodeDecodeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

frontend = Path(__file__).parents[2] / "frontend"
app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

@app.get("/", response_class=FileResponse)
def home():
    return frontend / "index.html"
