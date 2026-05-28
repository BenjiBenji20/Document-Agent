import logging
from uuid import uuid4

from fastapi import File, HTTPException, Request, UploadFile, status

from src.cache.redis_cache import RedisService, DOC_METADATA_PREFIX, DOC_METADATA_TTL
from src.modules.fields_registration.schema import *

logger = logging.getLogger(__name__)

class DocumentRegistration:
    def __init__(self, redis_service: RedisService, request: Request):
        self.redis_service = redis_service
        self.request = request
    
    async def save_document_metadata(
        self,
        documents: list[DocumentRegistrationRequest]
    ) -> list[DocumentRegistrationResponse]:
        logger.info(f"[LOG] Start to save document metadata. \nDocument types amount: {len(documents)}")

        try:
            key = self.request.client.host if self.request.client else "unknown"

            items = []
            tracking_pairs = []
            
            for doc in documents:
                doc_id = str(uuid4())
                redis_prefix = f"{DOC_METADATA_PREFIX}_{doc_id}"
            
            
                items.append({
                    "prefix": redis_prefix,
                    "data": {field.field: field.is_required for field in doc.fields},
                })
                
                tracking_pairs.append((doc_id, doc))
            
            # store in cache in one call
            success = await self.redis_service.set_hash_many(
                key=key, 
                items=items, 
                ttl=DOC_METADATA_TTL
            )
            
            return [
                DocumentRegistrationResponse(
                    document_metadata=DocumentMetadata(
                        id=doc_id,
                        document_name=doc.document_name,
                        fields=doc.fields
                    ),
                    details=ResponseDetails(
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
                for doc_id, doc in tracking_pairs
            ]

        except Exception as e:
            logger.error(f"[ERROR] Failed to save document metadata: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save document metadata."
            )
            
            
    async def call_agent_for_extract_schema(
        self, documents: list[UploadFile] = File(...)
    ) -> list[AgentExtractedDocumentMetadata]:
        logger.info(f"[LOG] Start agent to extract schemas from the documents. \n documents count: {len(documents)}")
        try:
            """
            1. System provides unique uuid4() for each file
            2. If passed documents len >= 8 or 8+ pdf pages or 10mb+ file size, call orchestrator to divide the labour.
            3. Call agent worker to extract document schemas.
                responsibilities:
                - worker receives passed file metadata to help extraction accuracy
                - extract document name eg. National ID (become document type)
                - extract document schemas under the document name eg. first_name, last_name,...
                - decide whether extracted schema is nullable or required
                - sends extraction confidence score to the validator # to decide
                
                constraints:
                - focus strictly on visual
                - no duplicate document type eg. User passed 2 identical documents, agents MUST identify them as one
                - standardize field names into snake_case
                - process in parallel
                
                return model (per file):
                [
                    {
                        "id": uuid4(), # provided by system
                        "document_name": "national id",
                        "file_name": "my-national-id.jpg",
                        "confidence_score": 0.92,
                        "fields": [
                            {"field": "first_name", "is_required": True},
                            {"field": "last_name", "is_required": True},...
                        ]
                    },...
                ]
            4. System validate document_name uniqueness to lessen validator call.
                - Flag: this file and this file has identical metadata (extracted by worker)
                - Use System-Level "Fuzzy" Grouping
                - groups the file with conflicting document metadata
                
                Example Case 1: Naming Inconsistency
                    File A: document_name: "National ID", fields: ["first_name", "last_name", "dob"]
                    File B: document_name: "Philsys ID", fields: ["first_name", "last_name", "dob"]

                    Logic: Even though the names differ, the field set is a 100% match. The system should group these together because they represent the same data structure.
                
                return model:
                [
                    {
                        "reason": "Fields are identical but different document_name.",
                        "candidates": [
                            {"id": "uuid_A", "document_name": "National ID", "confidence": 0.95},
                            {"id": "uuid_B", "document_name": "Philsys ID", "confidence": 0.88}
                        ]
                    },... # is this enough?
                ]
            5. Call agent validator to examine extracted schemas by the worker.
                responsibilities:
                - receives separately the cleaned and uncleaned grouped of documents
                - validator only does meaningful work on conflicting group of documents and else bypass  
                - analyze identical document metadata
                - decides which document type to use based on newest format and industry standard
                - validate and correct the extracted schemas from document type
                
                - validator returns only unique document type eg. national id, psa, etc...
                - validator returns only unique schemas under document_name eg. first_name, last_name, etc...
                - sends final confidence score to client 
                
                return model (per file): list[AgentExtractedDocumentMetadata]
            """
            # documents len >= 8 or 8+ pdf pages or 10mb+ file size, call orchestrator
            if len(documents) >= 8:
                logger.info(f"[LOG] Upload quantity exceeds to 7: {len(documents)}")
                   
            
            
        except Exception as e:
            logger.error(f"[ERROR] Agent failed to extract document metadata: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent failed to extract document metadata."
            )
