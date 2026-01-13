from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, health, users
from app.config import settings
from app.database import init_db
from app.services.users import user_store

app = FastAPI(title="FastAPI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://64.225.59.206",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(auth.router)  # Compatibility for clients calling /auth/* without /api.


@app.on_event("startup")
def startup() -> None:
    init_db()
    if settings.seed_email:
        try:
            user_store.ensure_user_for_identifier(settings.seed_email)
        except ValueError:
            pass
    user_store.ensure_roles()

@app.get("/")
def root():
    return {"status": "Backend running"}
