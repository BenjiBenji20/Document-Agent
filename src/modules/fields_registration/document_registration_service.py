import asyncio
import logging
from uuid import uuid4

from fastapi import HTTPException, Request, status
import typing
import json

from src.modules.gcs_operations.direct_gcs_operations_service import DirectGCSOperationsService
from src.modules.gcs_operations.direct_gcs_operations_schema import  GCSFileObjectMetadata
from src.agents.schemas.agent_extract_schemas import AgentExtractedSchemaResponse
from src.cache.redis_cache import RedisService, DOC_METADATA_PREFIX, DOC_METADATA_TTL
from src.modules.fields_registration.document_registration_schema import *
from src.agents.orchestrate_agent_call import OrchestrateAgentCall
from src.infrastructure.gcs_service import gcs_service
from src.core.settings import settings

logger = logging.getLogger(__name__)

class DocumentRegistration:
    def __init__(self, redis_service: RedisService, request: Request):
        self.redis_service = redis_service
        self.request = request
        self.direct_gcs_operations = DirectGCSOperationsService()
        self.agent = OrchestrateAgentCall().select_provider(settings.AGENT_PROVIDER)
        
    
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
            
            
    async def call_agent_to_extract_schema(
        self, files_metadata: list[GCSFileObjectMetadata]
    ) -> typing.AsyncGenerator[str, None]:
        logger.info(f"[LOG] Start agent to extract schemas from the documents. \n documents count: {len(files_metadata)}")
        
        def format_sse(data: dict, event: str = "message") -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            yield format_sse({"status": "Counting documents..."})            
            
            if len(files_metadata) < 1:
                logger.error(f"[DEBUG] No files uploaded.")
                yield format_sse({"error": "No files uploaded."}, event="error")
                return
            
            doc_count = len(files_metadata)
            yield format_sse({"status": f"Ok, the total the document{"s are " if doc_count > 1 else " is "}{doc_count}"})
            
            agent_workload_payloads = []
            
            # collect files metadata
            uploaded_files_path = [
                gcs_service.get_gcs_storage_path(metadata.id)
                for metadata in files_metadata
            ]
            
            # check GCS file upload existence checks in parallel
            logger.info("[LOG] Checking files in gcs...")
            yield format_sse({"status": "Checking uploaded files in storage..."})
            async def check_gcs_file_existance(file_path_url: str):
                return await asyncio.to_thread(
                    gcs_service.get_object_metadata,
                    file_path_url
                )
            
            # Parallel GCS existence checks for all uploaded files
            uploaded_files = await asyncio.gather(
                *[check_gcs_file_existance(file_path) for file_path in uploaded_files_path],
                return_exceptions=True
            )
            
            logger.info(f"[LOG] Successfull uploaded files: {len(uploaded_files)}")
            yield format_sse({"status": "Successfully collected uploaded files..."})
            for metadata, file_path in zip(files_metadata, uploaded_files_path):
                gcs_url = gcs_service._get_model_file_uri(
                    object_key=file_path, model_provider=settings.AGENT_PROVIDER
                )
                
                # This dictionary contains everything needed by both:
                # - WorkloadManager (gcs_url, page_count, size_bytes)
                # - Agents worker method (id, file_name)
                agent_workload_payloads.append({
                    "gcs_url": gcs_url,
                    "id": metadata.id,
                    "file_name": metadata.file_name,
                    "file_type": metadata.file_type,
                    "page_count": getattr(metadata, "page_count", 0),  # passed from client metadata
                    "size_bytes": getattr(metadata, "size_bytes", 0),  # passed from client metadata
                })
            
            yield format_sse({"status": f"We are beginning extract fields from these files: {len(agent_workload_payloads)}..."})   
            
            all_results = []
            async for event in self.agent.extract_schemas_stream(agent_workload_payloads):
                if "status" in event:
                    yield format_sse({"status": event["status"]}, event="status")
                elif "result" in event:
                    res = event["result"]
                    all_results.append(res)
                    yield format_sse(res, event="result")
            
            yield format_sse({
                "status": "completed",
                "results": all_results
            }, event="complete")
            
        except Exception as e:
            logger.error(f"[ERROR] Agent failed to extract document metadata: {e}")
            yield format_sse({
                "error": "Agent failed to extract document metadata.",
                "details": str(e)
            }, event="error")
