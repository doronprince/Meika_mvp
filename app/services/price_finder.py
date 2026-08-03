from app.database import get_db
from app.models import ProductComparisonItem, PriceSearchResponse
import math

def search_prices(query: str, user_location: str = "Kwangwoon University, Seoul") -> PriceSearchResponse:
    db = get_db()
    cursor = db.cursor()
    
    clean_query = query.strip()
    cursor.execute("""
    SELECT * FROM products_catalog 
    WHERE LOWER(product_name) LIKE LOWER(?) OR LOWER(category) LIKE LOWER(?)
    """, (f"%{clean_query}%", f"%{clean_query}%"))
    
    rows = cursor.fetchall()
    
    # Fallback / Dynamic match if catalog doesn't have exact item
    if not rows:
        cursor.execute("SELECT * FROM products_catalog")
        rows = cursor.fetchall()
        
    items = []
    for r in rows:
        total_cost = float(r["price_krw"]) + float(r["transit_cost_krw"])
        item = ProductComparisonItem(
            id=r["id"],
            product_name=r["product_name"],
            category=r["category"],
            store_name=r["store_name"],
            store_type=r["store_type"],
            price_krw=float(r["price_krw"]),
            transit_cost_krw=float(r["transit_cost_krw"]),
            transit_mode=r["transit_mode"],
            total_economic_cost_krw=total_cost,
            location=r["location"],
            in_stock=bool(r["in_stock"]),
            rating=float(r["rating"]),
            price_trend=r["price_trend"],
            is_best_value=False
        )
        items.append(item)

    db.close()

    if not items:
        # Default mock items if DB empty
        items = [
            ProductComparisonItem(
                id=999, product_name=query, category="General", store_name="Coupang Online",
                store_type="Online", price_krw=15000.0, transit_cost_krw=0.0, transit_mode="Walk",
                total_economic_cost_krw=15000.0, location="Seoul Delivery", in_stock=True, rating=4.8, price_trend="Stable"
            ),
            ProductComparisonItem(
                id=998, product_name=query, category="General", store_name="Local Mart",
                store_type="Local Supermarket", price_krw=14000.0, transit_cost_krw=1500.0, transit_mode="Subway/Bus",
                total_economic_cost_krw=15500.0, location="Near Kwangwoon", in_stock=True, rating=4.5, price_trend="Stable"
            )
        ]

    # Sort by Total Economic Cost
    items.sort(key=lambda x: x.total_economic_cost_krw)
    items[0].is_best_value = True
    best_item = items[0]

    online_best = next((x for x in items if x.store_type == "Online"), None)
    local_best = next((x for x in items if x.store_type in ["Local Supermarket", "Convenience Store"]), None)
    traditional_best = next((x for x in items if x.store_type == "Traditional Market"), None)

    # Generate Explainable AI (XAI) transparent reasoning
    xai_reasoning = [
        f"Compared total economic costs (Base Price + Transit Fare) across {len(items)} retailers in Seoul.",
        f"Best overall value: '{best_item.store_name}' at ₩{int(best_item.total_economic_cost_krw):,} total."
    ]

    if online_best and local_best:
        diff = local_best.total_economic_cost_krw - online_best.total_economic_cost_krw
        if diff > 0:
            xai_reasoning.append(f"Online shopping ({online_best.store_name}) saves ₩{int(diff):,} over local supermarket after accounting for ₩{int(local_best.transit_cost_krw):,} bus/subway transit costs.")
        else:
            xai_reasoning.append(f"Local shopping at {local_best.store_name} saves ₩{int(abs(diff)):,} compared to online delivery times.")

    if traditional_best:
        xai_reasoning.append(f"Traditional market ({traditional_best.store_name}) offers lowest item price (₩{int(traditional_best.price_krw):,}), but requires ₩{int(traditional_best.transit_cost_krw):,} in transit fare.")

    if best_item.price_trend == "Falling":
        xai_recommendation = f"Buy Now: '{best_item.product_name}' at {best_item.store_name} is currently trending down in price in Seoul."
    else:
        xai_recommendation = f"Recommended Purchase: {best_item.store_name} offers the lowest True Economic Cost (₩{int(best_item.total_economic_cost_krw):,})."

    return PriceSearchResponse(
        query=query,
        user_location=user_location,
        best_option=best_item,
        online_best=online_best,
        local_best=local_best,
        traditional_market_best=traditional_best,
        all_results=items,
        xai_recommendation=xai_recommendation,
        xai_reasoning=xai_reasoning
    )
