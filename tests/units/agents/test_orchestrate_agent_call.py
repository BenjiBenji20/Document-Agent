import pytest
from src.agents.orchestrate_agent_call import OrchestrateAgentCall
from src.agents.gemini_agents import GeminiAgents

def test_orchestrate_agent_call_select_provider_google():
    # Arrange & Act
    agent = OrchestrateAgentCall.select_provider("google")
    
    # Assert
    assert isinstance(agent, GeminiAgents)

def test_orchestrate_agent_call_select_provider_case_insensitive():
    # Arrange & Act
    agent1 = OrchestrateAgentCall.select_provider("  GOOGLE  ")
    agent2 = OrchestrateAgentCall.select_provider("Google")
    
    # Assert
    assert isinstance(agent1, GeminiAgents)
    assert isinstance(agent2, GeminiAgents)

def test_orchestrate_agent_call_select_provider_unsupported():
    # Arrange & Act & Assert
    with pytest.raises(ValueError) as exc_info:
        OrchestrateAgentCall.select_provider("openai")
        
    assert "currently not supported" in str(exc_info.value)

def test_orchestrate_agent_call_select_provider_invalid():
    with pytest.raises(ValueError):
        OrchestrateAgentCall.select_provider("some_random_agent")
