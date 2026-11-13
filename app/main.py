from contextlib import asynccontextmanager
from fastapi import FastAPI

from config import settings

from app.routers import license
from app.services.licensing import Licensing




@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup logic ---
    app.state.licensing = Licensing()

    yield

    # --- shutdown logic ---
    del app.state.licensing


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# Include routers
app.include_router(license.router)