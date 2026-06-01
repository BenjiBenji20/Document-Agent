import os
import logging


# cloud deployment logging 
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

logger.debug(f"Starting app - PORT from env: {os.environ.get('PORT', 'not set')}")
logger.debug(f"Binding to 0.0.0.0:{os.environ.get('PORT', '8080')}")
from fastapi import FastAPI
from src.core.settings import settings
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def life_span(app: FastAPI):
    logger.info("App starting up.")
    yield
    logger.info("App shutting down.")
        
app = FastAPI(
    title="Document Agent",
    description="Extract document text in parallel with the help of agents. Best for automating data encoding.",
    lifespan=life_span
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.DEV_ORIGIN, settings.PROD_ORIGIN],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],  # Allows all headers
)
 
 
# Register routers
from src.api.document_registration_router import router as document_registration_router
from src.api.gcs_operations_router import router as gcs_operations_router
from src.api.document_values_extraction_router import router as document_values_extraction_router
app.include_router(document_registration_router)
app.include_router(gcs_operations_router)
app.include_router(document_values_extraction_router)