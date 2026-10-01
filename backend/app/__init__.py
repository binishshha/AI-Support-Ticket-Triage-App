from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import analysis_routes, data_routes
from .config import ALLOWED_ORIGINS

app = FastAPI(title="Ticket Support API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(data_routes.router)
app.include_router(analysis_routes.router)

__all__ = ["app", "analysis_routes", "data_routes"]
