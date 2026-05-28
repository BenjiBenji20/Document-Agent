from fastapi import APIRouter, Depends, HTTPException, Request, status
from src.agents.schemas.agent_extract_schemas import AgentExtractedSchemaResponse
from src.modules.gcs_operations.direct_gcs_operations_schema import GCSFileObjectMetadata
from src.modules.fields_registration.document_registration_service import DocumentRegistration
from src.modules.fields_registration.document_registration_schema import *
from src.dependencies.secrets import document_agent_secret
from src.dependencies.rate_limit import rate_limit_by_ip
from src.cache.redis_cache import redis_service

router = APIRouter(
    prefix="/api/public/document",  
    tags=[
        "Document registration",
        "Document type",
        "Fields", 
        "AI Field Extaction and marking of Required and Nullable"
    ]
)


@router.post(
    "/registration",
    response_model=list[DocumentRegistrationResponse],
    summary="User manually register document schemas",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(document_agent_secret),
        Depends(rate_limit_by_ip())
    ]
)
async def register_documents(
    request: Request,
    documents: list[DocumentRegistrationRequest]
):
    """Store document metadata in redis cache with 1 day TTL"""
    if len(documents) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document metadata found."
        )
    
    service = DocumentRegistration(redis_service, request)
    return await service.save_document_metadata(documents=documents)
    

@router.post(
    "/agent-extracts",
    response_model=list[AgentExtractedSchemaResponse],
    summary="Generate GCS signed upload URLs for multiple files at once. Agents extracts fields",
    description="User upload files and multiple agents concurrently extracts meaningful fields use for encoding.",
    dependencies=[
        Depends(document_agent_secret),
        Depends(rate_limit_by_ip())
    ]
)
async def agent_extract_schemas(
    request: Request,
    files: list[GCSFileObjectMetadata]
):
    """
    agent extract schemas and suggest if required/nullable
    
    This endpoint would be call after the client directly uploaded to GCS using Signed URL
    """
    if len(files) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files found."
        )
        
    service = DocumentRegistration(redis_service, request)
    return await service.call_agent_to_extract_schema(files)