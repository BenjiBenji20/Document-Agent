from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from src.modules.fields_registration.document_registration_service import DocumentRegistration
from src.modules.fields_registration.schema import DocumentRegistrationRequest, DocumentRegistrationResponse, FileUpload
from src.dependencies.secrets import document_agent_secret
from src.dependencies.rate_limit import rate_limit_by_ip
from src.cache.redis_cache import redis_service

router = APIRouter(
    prefix="/api/public/registration",  
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
    service = DocumentRegistration(redis_service)
    return await service.save_document_metadata(documents=documents, request=request)
    

@router.post(
    "ai-extracts",
    response_model=list[DocumentRegistrationResponse],
    dependencies=[
        Depends(document_agent_secret),
        Depends(rate_limit_by_ip())
    ]
)
async def ai_extract_fields(
    request: Request,
    files: list[UploadFile] = File(...),
):
    """ai extract fields and suggest if required/nullable"""
    validated_files = []
    try:
        for file in files:
            validated_files.append(FileUpload(file=file))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=e.errors()
        )
        
    # pass only the validated files
    if len(validated_files) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files found."
        )
        
    service = DocumentRegistration(redis_service)
    
    