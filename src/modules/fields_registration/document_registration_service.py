from datetime import datetime
import logging
from uuid import uuid4

from fastapi import HTTPException, Request, status

from src.cache.redis_cache import RedisService, DOC_METADATA_PREFIX, DOC_METADATA_TTL
from src.modules.fields_registration.schema import (
    DocumentMetadata, DocumentRegistrationRequest, 
    DocumentRegistrationResponse, ResponseDetails
)

logger = logging.getLogger(__name__)

class DocumentRegistration:
    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service
    
    async def save_document_metadata(
        self,
        request: Request, 
        documents: list[DocumentRegistrationRequest]
    ) -> list[DocumentRegistrationResponse]:
        logger.info(f"[LOG] Start to save document metadata. \nDocument types amount: {len(documents)}")

        try:
            now = datetime.now().strftime("%Y-%m-%d")
            key = request.client.host if request.client else "unknown"
            id=uuid4()
            
            # build full items
            items = [
                {
                    "prefix": DOC_METADATA_PREFIX + doc.document_name + "_" + now + "_" + id,
                    "data": {field.field: str(field.is_required) for field in doc.fields},
                }
                for doc in documents
            ]
            
            # store in cache in one call
            success = await self.redis_service.set_hash_many(
                key=key, 
                items=items, 
                ttl=DOC_METADATA_TTL
            )
            
            return [
                DocumentRegistrationResponse(
                    document_metadata=DocumentMetadata(
                        id=id,
                        document_name=doc.document_name,
                        fields=[field.field for field in doc.fields]
                    ),
                    detail=ResponseDetails(
                        description=(
                            "Document metadata successfully registered."
                            if success else
                            "Document metadata registration failed."
                        ),
                        successful=success,
                        success_count=len(documents) if success else 0,
                        failure_count=0 if success else len(documents),
                    )
                )
                for doc in documents
            ]

        except Exception as e:
            logger.error(f"[ERROR] Failed to save document metadata: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save document metadata."
            )
