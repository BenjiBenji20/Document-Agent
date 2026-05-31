import typing
from google import genai
from google.genai import types
from src.agents.schemas.agent_extract_values_schemas import AgentExtractValuesResponse, FieldsToExtractByAgent, ValuesExtractedByAgent
from src.modules.values_extraction.extract_document_values_schema import DocumentToExtactValues
from src.agents.schemas.agent_extract_schemas import AgentExtractedDocumentMetadata, ExtractionStatus, AgentExtractedSchemaResponse
from src.agent_tasks.workload_manager import WorkloadManager
from src.agents.base_agent import BaseAgent
from src.core.settings import settings
import logging
logger = logging.getLogger(__name__)

class GeminiAgents(BaseAgent):
    def __init__(self):
        """In provider's class genai client instance"""
        super().__init__() # to call all the prompts
        
        self.client = genai.Client(api_key=settings.AGENT_API_KEY)
        # one client call for multiple agents
        self.orchestrator_model = "gemini-2.5-pro"
        self.worker_model = "gemini-2.5-flash"
        self.validator_model = "gemini-2.5-pro"
        
        
    async def extract_single_document_schema(self, metadata: dict) -> typing.AsyncGenerator[dict, None]:
        file_id = metadata.get("id", "unknown")
        file_name = metadata.get("file_name", "unknown")
        mime_type = metadata.get("file_type")
        gcs_url = metadata.get("gcs_url")
        
        yield {"status": f"Collecting metadata for document: {file_name}."}

        if not mime_type:
            yield {"status": "Found missing metadata..."}
            yield {"result": self._failed_response(file_id, file_name, "Missing mime_type.")}
            return

        try:
            if not gcs_url:
                from src.infrastructure.gcs_service import gcs_service
                object_key = gcs_service.get_gcs_storage_path(file_id)
                gcs_url = gcs_service._get_model_file_uri(object_key, settings.AGENT_PROVIDER)

            yield {"status": f"Reading the document {file_name} and extracting fields..."}

            response = await self.client.aio.models.generate_content(
                model=self.worker_model,
                contents=[
                    types.Part.from_uri(file_uri=gcs_url, mime_type=mime_type),
                    "Identify and extract the document structural fields."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.WORKER_EXTRACT_SCHEMAS_PROMPT,
                    response_mime_type="application/json",
                    response_schema=AgentExtractedDocumentMetadata,
                    temperature=0.1
                )
            )

            yield {"status": f"Done extracting fields for {file_name}."}

            llm_result = AgentExtractedDocumentMetadata.model_validate_json(response.text)
            result = AgentExtractedSchemaResponse(
                id=file_id,
                document_name=llm_result.document_name,
                fields=llm_result.fields,
                file_name=file_name,
                confidence_score=llm_result.confidence_score,
                status=ExtractionStatus.SUCCESS
            ).model_dump()
            yield {"result": result}

        except genai.errors.ServerError as e:
            logger.warning(f"[RETRYABLE] Gemini error for {file_name}: {e}")
            yield {"result": self._failed_response(file_id, file_name, str(e))}
        except Exception as e:
            logger.error(f"[FATAL] {file_name}: {e}")
            yield {"result": self._failed_response(file_id, file_name, str(e))}
                    

    async def extract_schemas(self, files: list[dict]) -> list[dict]:
        """
        High-level orchestrator entry point called by the service layer.
        Hands off execution control directly to the agnostic WorkloadManager.
        """
        # Inject our single-document worker function directly into the manager
        manager = WorkloadManager(worker_fn=self.extract_single_document_schema)
        
        # Await the controlled chunking and rate-limited processing execution results
        return await manager.process_batch(files)
        
        
    async def extract_schemas_stream(self, files: list[dict]) -> typing.AsyncGenerator[dict, None]:
        """
        Stream agent schema extraction progress and results.
        """
        manager = WorkloadManager(lambda f: self.extract_single_document_schema(f))
        async for event in manager.process_batch_stream(files):
            yield event
    
    
    async def extract_single_document_values_stream(
        self, doc_to_extract: DocumentToExtactValues,
        cache_content = None, prompt: str = None
    ) -> typing.AsyncGenerator[dict, None]:
        """Stream response every single processed document"""
        file_name = doc_to_extract.gcs_file_metadata.file_name
        file_id = doc_to_extract.gcs_file_metadata.id
        
        try:
            yield {"status": f"Processing file: {file_name}"}
            signed_uri = doc_to_extract.downloadable_url
            
            if cache_content:
                cache_name = getattr(cache_content, "name", cache_content)
                config = types.GenerateContentConfig(
                    cached_content=cache_name,
                    response_mime_type="application/json",
                    response_schema=ValuesExtractedByAgent,
                    temperature=0.1
                )
            else:
                config = types.GenerateContentConfig(
                    system_instruction=prompt,
                    response_mime_type="application/json",
                    response_schema=ValuesExtractedByAgent,
                    temperature=0.1
                )
            
            response = await self.client.aio.models.generate_content(
                model=self.worker_model,
                config=config,
                contents=[
                    types.Part.from_uri(file_uri=signed_uri, mime_type=doc_to_extract.gcs_file_metadata.file_type),
                    "Extract values from the listed document fields."
                ]
            )
            
            yield {"status": f"Done extract document values from {file_name}."}
            
            llm_result = ValuesExtractedByAgent.model_validate_json(response.text)
            success_status = self._extraction_status(llm_result.confidence_score)
            
            # Convert list of FieldValuePair to a dictionary
            flat_field_values = {item.field: item.value for item in llm_result.field_values}
            
            result = AgentExtractValuesResponse(
                document_id=str(doc_to_extract.document_id),
                file_id=file_id,
                document_name=doc_to_extract.document_name,
                file_name=doc_to_extract.gcs_file_metadata.file_name,
                field_values=flat_field_values,
                confidence_score=llm_result.confidence_score,
                score_reason=llm_result.score_reason,
                status=success_status
            ).model_dump()
            yield {"result": result}
        except genai.errors.ServerError as e:
            logger.warning(f"[RETRYABLE] Gemini error for {file_name}: {e}")
            yield {"result": self._failed_values_response(str(doc_to_extract.document_id), file_id, doc_to_extract.document_name, file_name, str(e))}
        except Exception as e:
            logger.error(f"[FATAL] {file_name}: {e}")
            yield {"result": self._failed_values_response(str(doc_to_extract.document_id), file_id, doc_to_extract.document_name, file_name, str(e))}
    
    
    async def extract_document_values_stream(
        self, doc_to_extract: list[DocumentToExtactValues]
    ) -> typing.AsyncGenerator[dict, None]:
        """Stream agent document field's values extraction batch processing"""
        yield {"status": "Start to process documents..."}
        
        from collections import defaultdict
        grouped = defaultdict(list)
        for doc in doc_to_extract:
            grouped[doc.document_id].append(doc)
            
        for _, group in grouped.items():
            first_doc = group[0]
            meta = FieldsToExtractByAgent(
                document_name=first_doc.document_name,
                fields=[f.model_dump() for f in first_doc.fields]
            )
            
            prompt = await self._prompt_builder(self.WORKER_EXTRACT_SCHEMA_VALUES_PROMPT, meta)
            cached_content = None
            need_to_cache = self.count_tokens(prompt) >= 1_024
            
            try:
                if need_to_cache:
                    cached_content = await self._cache_content(prompt)
                    
                file_payloads = []
                for doc in group:
                    file_size = getattr(doc.gcs_file_metadata, "file_size", 0)
                    page_count = getattr(doc.gcs_file_metadata, "page_count", 0)
                    file_payloads.append({
                        "id": str(doc.gcs_file_metadata.id),
                        "file_name": doc.gcs_file_metadata.file_name,
                        "page_count": page_count,
                        "size_bytes": file_size,
                        "model_ref": doc
                    })
                
                manager = WorkloadManager(
                    worker_fn=lambda fd: self.extract_single_document_values_stream(
                        fd["model_ref"], cached_content, prompt
                    )
                )
                async for event in manager.process_batch_stream(file_payloads):
                    yield event
                    
            finally:
                if need_to_cache and cached_content:
                    try:
                        await self.client.aio.caches.delete(name=cached_content.name)
                    except Exception as e:
                        logger.warning(f"[CACHE CLEANUP] Failed to delete cache: {e}")
                    

    async def _prompt_builder(self, worker_prompt: str, meta: FieldsToExtractByAgent) -> str:
        prompt = worker_prompt
        prompt += f"\nDocument Name: {meta.document_name}"
        prompt += f"\nFields needed to extract values: "
        for field in meta.fields:
            prompt += field.field + f" ({"required" if field.is_required else "nullable"})\n"
            
        return prompt
    
    
    async def _cache_content(self, prompt: str):
        """Cache prompts + meta to agent"""
        cached_content = await self.client.aio.caches.create(
            model=self.worker_model,
            system_instruction=prompt,
            ttl="3600s" # 1hr temporary. delete after document type batch finished to process
        )
        
        return cached_content
    
    
    def _extraction_status(self, confidence_score: float = 0.10) -> ExtractionStatus:
        if confidence_score <= 0.40: ExtractionStatus.FAILED
        elif confidence_score <= 0.60: ExtractionStatus.NEEDS_REVIEW
        return ExtractionStatus.SUCCESS
    
    
    def _failed_response(self, file_id: str, file_name: str, error: str) -> dict:
        return AgentExtractedSchemaResponse(
            id=file_id,
            file_name=file_name,
            document_name="failed_extraction",
            fields=[],
            confidence_score=0.0,
            status=ExtractionStatus.FAILED,
            error=error
        ).model_dump()
        
    def _failed_values_response(self, document_id: str, file_id: str, document_name: str, file_name: str, error: str) -> dict:
        return AgentExtractValuesResponse(
            document_id=document_id,
            file_id=file_id,
            document_name=document_name,
            file_name=file_name,
            field_values={},
            confidence_score=0.0,
            score_reason=error[:100],
            status=ExtractionStatus.FAILED,
            error=error
        ).model_dump()
    