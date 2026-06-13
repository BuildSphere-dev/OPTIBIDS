from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import register_all_routes
from .db import init_db

app = FastAPI(title="RFP Prototype Backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    try:
        from .seed_sku import seed
        seed()
    except Exception as e:
        print("Seed failed:", e)


register_all_routes(app)
