import typing
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from src.dependencies.secrets import document_agent_secret
from src.dependencies.rate_limit import rate_limit_by_ip, check_extraction_rate_limit
from src.cache.redis_cache import redis_service
from src.modules.values_extraction.extract_document_values_schema import (
    DocumentValueExtractionRequest,
    ExtractionValueResponse
)
from src.modules.values_extraction.document_values_extraction_service import DocumentValuesExtractionService

router = APIRouter(
    prefix="/api/public/document",  
    tags=[
        "Document field values extraction",
        "AI Value Extraction and Agent coordinate"
    ]
)

@router.post(
    "/extract-values",
    response_model=list[ExtractionValueResponse],
    summary="AI Agent extracts document values from GCS based on registered schema",
    dependencies=[
        Depends(document_agent_secret),
        Depends(rate_limit_by_ip())
    ]
)
async def extract_values(
    request: Request,
    extraction_requests: list[DocumentValueExtractionRequest]
):
    """
    AI Agent extracts fields values from documents through GCS URL.
    Uses Server-Sent Events (SSE) to stream extraction status and results.
    """
    if len(extraction_requests) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extraction requests found."
        )

    # Apply the IP-based daily document extraction rate limit
    await check_extraction_rate_limit(request, len(extraction_requests))

    service = DocumentValuesExtractionService(redis_service, request)
    response = service.extract_values(extraction_requests)

    if isinstance(response, typing.AsyncGenerator):
        return StreamingResponse(response, media_type="text/event-stream")

    return response
