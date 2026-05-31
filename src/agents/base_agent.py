import typing
from abc import ABC, abstractmethod

import tiktoken


class BaseAgent(ABC):
    _ENCODE_TOKEN = tiktoken.get_encoding("cl100k_base")
    
    def __init__(self):
        self.WORKER_EXTRACT_SCHEMAS_PROMPT = """
        You are the Data Encoder Agent with Optimized Vision OCR capabilities. 
        Extract structural metadata fields from the provided document.
        Standardize all field names into snake_case.
        e.g.: first_name
        
        Decide whether a field is required or nullable.
        Provide a confidence score between 0.0 and 1.0.
        Provide a precise bounding box of identified field sing the standard [0-1000] integer spatial grid coordinates format.
        Output must strictly match the requested JSON schema.
        """
        
        self.WORKER_EXTRACT_SCHEMA_VALUES_PROMPT = """
        You are the Data Encodent Agent. Extract document schema values present in the document.
        Provide a max 10 words reason for your confidence_score value. Put in score_reason.
        
        Constraints:
        Use null/None value if document fields aren't match to the file.
        Throw a low confidence_score value and shortly explain using score_reason.
        
        Document Metadata:
        """
    
    @abstractmethod
    async def extract_schemas(self, files: list[dict]) -> list[dict]:
        """Call agents and asked to extract schemas from documents through GCS url"""
        pass
    
    @abstractmethod
    async def extract_schemas_stream(self, files: list[dict]) -> typing.AsyncGenerator[dict, None]:
        """Stream schema extraction progress and results."""
        pass
    
    @abstractmethod
    async def extract_single_document_schema(self, metadata: dict) -> typing.AsyncGenerator[dict, None]:
        """Private worker method responsible for a single LLM API transaction yielding status and results."""
        pass
        
    @abstractmethod
    async def extract_document_values_stream(
        self, doc_to_extract: list[typing.Any]
    ) -> typing.AsyncGenerator[dict, None]:
        """Stream response every single processed document"""
        pass
        
    @abstractmethod
    async def extract_single_document_values_stream(
        self, doc_to_extract: typing.Any,
        cache_content = None, prompt: str = None
    ) -> typing.AsyncGenerator[dict, None]:
        """Stream response for extracting values from a single document."""
        pass
    
    def count_tokens(self, text: str) -> int:
        return len(self._ENCODE_TOKEN.encode(text))
