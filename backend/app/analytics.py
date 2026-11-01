from datetime import date, timedelta
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Customer, CustomerPurchase, Product, Sale


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
        avg_daily = frame[frame["product"] == product.name]["units"].mean()
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
        avg = frame[frame["product"] == product.name]["units"].mean()
        for offset in range(1, 8):
            output.append({"date": str(latest + timedelta(days=offset)),
                           "product": product.name, "units": max(1, round(float(avg)))})
    return output


def customer_segments(db: Session) -> list[dict]:
    customers = db.scalars(select(Customer)).all()
    purchases = db.scalars(select(CustomerPurchase)).all()
    today = date.today()
    output = []
    for customer in customers:
        rows = [p for p in purchases if p.customer_id == customer.id]
        if not rows:
            continue
        recency = (today - max(p.purchase_date for p in rows)).days
        frequency = len(rows)
        monetary = sum(p.amount for p in rows)
        if recency <= 7 and frequency >= 8:
            segment = "Loyal"
        elif recency > 21:
            segment = "At risk"
        elif monetary >= 180:
            segment = "High value"
        else:
            segment = "Growing"
        output.append({
            "id": customer.id, "name": customer.name, "email": customer.email,
            "recency_days": recency, "frequency": frequency,
            "monetary": round(monetary, 2), "segment": segment,
        })
    return sorted(output, key=lambda x: x["monetary"], reverse=True)


def alerts(db: Session) -> list[dict]:
    products = db.scalars(select(Product)).all()
    results = []
    for product in products:
        if product.stock <= product.reorder_level:
            results.append({
                "type": "inventory", "severity": "high",
                "title": f"{product.name} needs reordering",
                "detail": f"{product.stock} units left, reorder level is {product.reorder_level}.",
                "product": product.name,
            })
    frame = sales_frame(db)
    if not frame.empty:
        recent = frame[frame["date"] >= date.today() - timedelta(days=6)].groupby("product")["units"].sum()
        previous = frame[(frame["date"] < date.today() - timedelta(days=6)) &
                         (frame["date"] >= date.today() - timedelta(days=13))].groupby("product")["units"].sum()
        for product, units in recent.items():
            earlier = previous.get(product, 0)
            if earlier and units < earlier * 0.65:
                results.append({
                    "type": "sales", "severity": "medium",
                    "title": f"{product} sales are slowing",
                    "detail": f"Sales are down {round((1 - units / earlier) * 100)}% versus the prior week.",
                    "product": product,
                })
    return results


def promotion_simulation(weekly_revenue: float, discount_percent: float,
                         expected_volume_lift_percent: float) -> dict:
    projected_revenue = (weekly_revenue * (1 - discount_percent / 100) *
                         (1 + expected_volume_lift_percent / 100))
    revenue_change = projected_revenue - weekly_revenue
    return {
        "projected_revenue": round(projected_revenue, 2),
        "revenue_change": round(revenue_change, 2),
        "revenue_change_percent": round(revenue_change / weekly_revenue * 100, 2)
        if weekly_revenue else 0,
        "break_even_lift_percent": round(
            (1 / (1 - discount_percent / 100) - 1) * 100, 2
        ) if discount_percent < 100 else None,
        "recommendation": "Test this promotion" if revenue_change > 0 else "Avoid this promotion",
    }
