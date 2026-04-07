from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware.auth import require_api_key
from backend.api.routers import cases, counties, diseases, vaccination_rates, news, alerts

app = FastAPI(
    title="FL Outbreak Tracker API",
    description="Florida vaccine-preventable disease surveillance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public endpoints (no auth required)
@app.get("/")
async def root():
    return {"status": "ok", "message": "FL Outbreak Tracker API running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Protected routers — require Bearer token when API_KEY env var is set
_auth = [Depends(require_api_key)]

app.include_router(counties.router, dependencies=_auth)
app.include_router(diseases.router, dependencies=_auth)
app.include_router(cases.router, dependencies=_auth)
app.include_router(vaccination_rates.router, dependencies=_auth)
app.include_router(news.router, dependencies=_auth)
app.include_router(alerts.router, dependencies=_auth)
