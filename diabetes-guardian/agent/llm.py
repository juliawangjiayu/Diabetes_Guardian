"""
agent/llm.py

Centralised LLM instances for the agent layer.
No other file should instantiate an LLM directly.
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings

def get_llm_reflector() -> ChatGoogleGenerativeAI:
    """For clinical reasoning: deterministic, conservative output."""
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=0.1,
        max_tokens=512,
        google_api_key=settings.gemini_api_key,
    )

def get_llm_communicator() -> ChatGoogleGenerativeAI:
    """For message generation: natural, warm tone with slight creative variation."""
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=0.7,
        max_tokens=256,
        google_api_key=settings.gemini_api_key,
    )
