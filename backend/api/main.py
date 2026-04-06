from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import cases, counties, diseases

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

app.include_router(counties.router)
app.include_router(diseases.router)
app.include_router(cases.router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "FL Outbreak Tracker API running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
