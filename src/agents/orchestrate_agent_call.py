from src.agents.base_agent import BaseAgent
from src.shared.agents import providers
from src.agents.gemini_agents import GeminiAgents


class OrchestrateAgentCall:
    @staticmethod
    def select_provider(provider: str = "google") -> BaseAgent:
        provider = provider.lower().strip()
        
        if not provider in providers:
            raise ValueError(
                f"Agent provider: {provider} currently not supported."
            )
            
        if provider == "google":
            agent = GeminiAgents()
            return agent
        
        raise ValueError(f"Unsupported provider: '{provider}'")
