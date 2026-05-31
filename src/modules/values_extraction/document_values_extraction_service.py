import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import HTTPException, Request, status

from src.cache.redis_cache import RedisService, DOC_METADATA_PREFIX
from src.modules.values_extraction.extract_document_values_schema import (
    DocumentValueExtractionRequest,
    DocumentToExtactValues,
    DocumentFields
)
from src.modules.gcs_operations.direct_gcs_operations_schema import GCSFileObjectMetadata
from src.agents.orchestrate_agent_call import OrchestrateAgentCall
from src.infrastructure.gcs_service import gcs_service
from src.core.settings import settings

logger = logging.getLogger(__name__)

class DocumentValuesExtractionService:
    def __init__(self, redis_service: RedisService, request: Request):
        self.redis_service = redis_service
        self.request = request
        self.agent = OrchestrateAgentCall().select_provider(settings.AGENT_PROVIDER)

    async def extract_values(
        self, req_items: list[DocumentValueExtractionRequest]
    ) -> AsyncGenerator[str, None]:
        logger.info(f"[LOG] Start agent to extract values from documents. Count: {len(req_items)}")

        def format_sse(data: dict, event: str = "message") -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            client_ip = self.request.client.host if self.request.client else "unknown"
            yield format_sse({"status": "Resolving document schemas..."})

            # Fetch and cache schemas from Redis
            schemas = {}
            for item in req_items:
                doc_id = str(item.document_id)
                if doc_id not in schemas:
                    schema_data = await self.redis_service.get_hash(
                        key=client_ip,
                        prefix=f"{DOC_METADATA_PREFIX}_{doc_id}"
                    )
                    if not schema_data:
                        logger.error(f"[ERROR] Schema {doc_id} not found in cache for IP {client_ip}")
                        yield format_sse(
                            {"error": f"Document's fields not found or expired. Try to register your document first."},
                            event="error"
                        )
                        return

                    try:
                        fields_list = json.loads(schema_data["fields"])
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to parse fields for schema {doc_id}: {e}")
                        yield format_sse(
                            {"error": f"Failed to parse registered schema fields for ID {doc_id}."},
                            event="error"
                        )
                        return

                    schemas[doc_id] = {
                        "document_name": schema_data["document_name"],
                        "fields": fields_list
                    }

            # Check file availability and size in GCS in parallel
            yield format_sse({"status": "Checking files in storage..."})

            async def prepare_gcs_metadata(item: DocumentValueExtractionRequest) -> DocumentToExtactValues:
                object_key = gcs_service.get_gcs_storage_path(str(item.file_id))
                gcs_meta = await asyncio.to_thread(gcs_service.get_object_metadata, object_key)
                if not gcs_meta:
                    raise FileNotFoundError(f"File {item.file_id} not found in GCS storage.")

                gcs_url = gcs_service._get_model_file_uri(object_key, settings.AGENT_PROVIDER)
                schema_info = schemas[str(item.document_id)]

                fields = [
                    DocumentFields(
                        field=f["field"],
                        is_required=f.get("is_required", False)
                    )
                    for f in schema_info["fields"]
                ]

                gcs_file_metadata = GCSFileObjectMetadata(
                    id=str(item.file_id),
                    file_name=item.file_name,
                    file_type=item.file_type,
                    file_size=gcs_meta["size"]
                )

                return DocumentToExtactValues(
                    document_id=item.document_id,
                    document_name=schema_info["document_name"],
                    fields=fields,
                    downloadable_url=gcs_url,
                    gcs_file_metadata=gcs_file_metadata
                )

            try:
                doc_payloads = await asyncio.gather(
                    *[prepare_gcs_metadata(item) for item in req_items]
                )
            except FileNotFoundError as e:
                logger.error(f"[ERROR] {e}")
                yield format_sse({"error": str(e)}, event="error")
                return
            except Exception as e:
                logger.error(f"[ERROR] Failed to prepare file metadata: {e}")
                yield format_sse({"error": "Failed to verify files in storage."}, event="error")
                return

            yield format_sse({"status": "Beginning value extraction..."})

            # Call agent stream
            all_results = []
            async for event in self.agent.extract_document_values_stream(doc_payloads):
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
            logger.error(f"[ERROR] Extraction service failed: {e}")
            yield format_sse({
                "error": "Extraction failed.",
                "details": str(e)
            }, event="error")
