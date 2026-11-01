from datetime import date, timedelta
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Product, Sale


def sales_frame(db: Session) -> pd.DataFrame:
    rows = db.execute(select(Sale, Product).join(Product, Sale.product_id == Product.id)).all()
    return pd.DataFrame([{
        "date": sale.sale_date, "product": product.name, "category": product.category,
        "units": sale.units, "revenue": sale.revenue,
        "profit": sale.revenue - sale.units * product.cost,
    } for sale, product in rows])


def dashboard(db: Session) -> dict:
    frame = sales_frame(db)
    products = db.scalars(select(Product)).all()
    revenue = float(frame.revenue.sum())
    profit = float(frame.profit.sum())
    return {
        "revenue": round(revenue, 2),
        "profit": round(profit, 2),
        "margin": round(profit / revenue * 100, 1),
        "units": int(frame.units.sum()),
        "products": len(products),
        "low_stock": sum(p.stock <= p.reorder_level for p in products),
        "daily": [{"date": str(k), "revenue": round(v, 2)} for k, v in
                  frame.groupby("date").revenue.sum().items()],
        "categories": [{"name": k, "revenue": round(v, 2)} for k, v in
                       frame.groupby("category").revenue.sum().sort_values(ascending=False).items()],
    }


def recommendations(db: Session) -> list[dict]:
    frame = sales_frame(db)
    products = db.scalars(select(Product)).all()
    results = []
    for product in products:
        avg_daily = frame[frame.product == product.name].units.mean()
        demand = max(1, round(float(avg_daily) * 7))
        if product.stock <= product.reorder_level or product.stock < demand:
            results.append({
                "product": product.name, "category": product.category,
                "stock": product.stock, "forecast_7d": demand,
                "order": max(0, demand * 2 - product.stock),
                "priority": "high" if product.stock <= product.reorder_level else "medium",
            })
    return sorted(results, key=lambda x: (x["priority"] != "high", -x["order"]))


def forecast(db: Session) -> list[dict]:
    frame = sales_frame(db)
    latest = date.today()
    products = db.scalars(select(Product)).all()
    output = []
    for product in products:
        avg = frame[frame.product == product.name].units.mean()
        for offset in range(1, 8):
            output.append({"date": str(latest + timedelta(days=offset)),
                           "product": product.name, "units": max(1, round(float(avg)))})
    return output
