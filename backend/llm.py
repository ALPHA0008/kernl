import os
import json
import numpy as np
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = "RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic"

llm = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="not-needed", timeout=120.0)

# --- Embedding model (local, fast, centralized here) ---
_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def get_embedding(text: str) -> list:
    """Return a single embedding vector as a Python list."""
    model = _get_embedding_model()
    return model.encode(text).tolist()

def get_embeddings(texts: list) -> list:
    """Return a list of embedding vectors."""
    model = _get_embedding_model()
    return [v.tolist() for v in model.encode(texts)]

def cosine_similarity(v1, v2) -> float:
    """Cosine similarity between two vectors."""
    a, b = np.array(v1), np.array(v2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

async def check_vllm_health() -> dict:
    """Ping the vLLM /v1/models endpoint. Returns status dict."""
    try:
        response = await llm.models.list()
        models = [m.id for m in response.data]
        return {"healthy": True, "models": models, "url": VLLM_BASE_URL}
    except Exception as e:
        return {"healthy": False, "error": str(e), "url": VLLM_BASE_URL}

async def llm_call(system_prompt: str, user_content: str, temperature: float = 0.1, max_tokens: int = 4096) -> str:
    """Single centralized LLM call through vLLM. Raises on failure."""
    try:
        response = await llm.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"vLLM call failed ({VLLM_BASE_URL}): {e}")
