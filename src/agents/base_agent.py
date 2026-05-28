from abc import ABC, abstractmethod


class BaseAgent(ABC):
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
    
    @abstractmethod
    async def extract_schemas(self, files: list[dict]) -> list[dict]:
        """Call agents and asked to extract schemas from documents through GCS url"""
        pass
    
    
    @abstractmethod
    async def extract_single_document_schema(self, metadata: dict) -> dict:
        """Private worker method responsible for a single LLM API transaction."""
        pass
