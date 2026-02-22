import os
from typing import Dict, Any
from services.common.config import settings

class LLM:
    async def complete(self, system: str, user: str) -> str:
        raise NotImplementedError

class MockLLM(LLM):
    async def complete(self, system: str, user: str) -> str:
        # Deterministic mock, useful for running without keys.
        return (
            "MOCK_LLM_RESPONSE\n"
            "System: " + system[:120] + "\n"
            "User: " + user[:500] + "\n"
            "Conclusion: Revue générée en mode dégradé (mock)."
        )

def get_llm() -> LLM:
    provider = (settings.LLM_PROVIDER or "mock").lower()
    # Stubs: you can implement real calls later without changing integration contracts.
    if provider == "mock":
        return MockLLM()
    # If keys missing, fallback to mock
    return MockLLM()
