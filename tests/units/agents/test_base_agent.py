import pytest
from src.agents.base_agent import BaseAgent

def test_base_agent_is_abstract():
    # Instantiating BaseAgent directly should raise TypeError
    with pytest.raises(TypeError):
        BaseAgent()

def test_base_agent_subclass_enforcement():
    # Subclassing without implementing abstract methods should raise TypeError upon instantiation
    class IncompleteAgent(BaseAgent):
        pass
        
    with pytest.raises(TypeError):
        IncompleteAgent()

def test_base_agent_complete_subclass():
    # Subclassing with all abstract methods implemented should succeed
    class CompleteAgent(BaseAgent):
        async def extract_schemas(self, files: list[dict]) -> list[dict]:
            return []
            
        async def extract_schemas_stream(self, files: list[dict]):
            yield {}
            
        async def extract_single_document_schema(self, metadata: dict):
            yield {}
            
        async def extract_document_values_stream(self, doc_to_extract: list):
            yield {}
            
        async def extract_single_document_values_stream(self, doc_to_extract, cache_content=None, prompt=None):
            yield {}
            
    agent = CompleteAgent()
    assert agent.WORKER_EXTRACT_SCHEMAS_PROMPT is not None
