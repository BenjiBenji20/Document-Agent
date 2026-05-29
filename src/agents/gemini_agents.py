import asyncio
from io import BytesIO
import json
import typing
from google import genai
from google.genai import types
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
        
        yield {"status": f"Collecting metadata for document: {file_name}."}

        if not mime_type:
            yield {"status": "Found missing metadata..."}
            yield {"result": self._failed_response(file_id, file_name, "Missing mime_type.")}
            return

        uploaded_file = None

        try:
            from src.infrastructure.gcs_service import gcs_service

            object_key = gcs_service.get_gcs_storage_path(file_id)
            file_bytes = await asyncio.to_thread(gcs_service.download_object_as_bytes, object_key)

            yield {"status": f"Collecting actual document contents for {file_name}..."}

            # Upload to Gemini File API
            uploaded_file = await self.client.aio.files.upload(
                file=BytesIO(file_bytes),
                config=types.UploadFileConfig(mime_type=mime_type)
            )

            # Poll until ACTIVE
            attempts = 0
            while uploaded_file.state.name == "PROCESSING" and attempts < 15:
                await asyncio.sleep(1)
                uploaded_file = await self.client.aio.files.get(name=uploaded_file.name)
                attempts += 1

            if uploaded_file.state.name != "ACTIVE":
                raise ValueError(f"File stuck in state: {uploaded_file.state.name}")

            yield {"status": f"Reading the document {file_name} and extracting fields..."}

            response = await self.client.aio.models.generate_content(
                model=self.worker_model,
                contents=[
                    uploaded_file,  # Gemini File API reference
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
        finally:
            # Always delete from Gemini File API regardless of outcome
            if uploaded_file is not None:
                try:
                    await self.client.aio.files.delete(name=uploaded_file.name)
                    logger.info(f"[CLEANUP] Deleted Gemini file: {uploaded_file.name}")
                except Exception as e:
                    logger.warning(f"[CLEANUP] Failed to delete Gemini file {uploaded_file.name}: {e}")
                    

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
        manager = WorkloadManager(worker_fn=self.extract_single_document_schema)
        async for event in manager.process_batch_stream(files):
            yield event
    
    
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
    