# backend/app/seed_skus.py
from .db import get_session, init_db
from .models import SKU

def seed():
    init_db()
    with get_session() as s:
        examples = [
            {"sku_code":"LAPTOP123","description":"Laptop i7 16GB 512SSD","price_base":45000},
            {"sku_code":"LAPTOP124","description":"Laptop i5 8GB 256SSD","price_base":30000},
            {"sku_code":"MON100","description":"24 inch monitor","price_base":8000},
        ]
        for e in examples:
            s.add(SKU(**e))
        s.commit()

if __name__ == "__main__":
    seed()
