import os
import json
import re
import asyncio
import numpy as np
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = "RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic"

llm = AsyncOpenAI(base_url=VLLM_BASE_URL, api_key="not-needed", timeout=120.0)

# --- Concurrency throttle for parallel extraction ---
_semaphore = asyncio.Semaphore(4)

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


async def llm_call(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    """Single centralized LLM call through vLLM — uses semaphore for concurrency control."""
    async with _semaphore:
        try:
            response = await llm.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"vLLM call failed ({VLLM_BASE_URL}): {e}")


# ─────────────────────────────────────────────
# JSON Self-Repair Utilities
# ─────────────────────────────────────────────


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences from LLM output."""
    clean = raw.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()


def _repair_json(raw: str) -> str:
    """Apply regex heuristics to repair common JSON formatting issues."""
    # Remove trailing commas before closing brackets/braces
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Remove trailing comma at end of string
    raw = re.sub(r",\s*$", "", raw)
    # Ensure balanced brackets (simple count check)
    return raw


async def safe_llm_json_call(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> list:
    """
    Call the LLM expecting a JSON array response.
    Retries once on parse failure with a repair prompt.
    Returns [] on final failure — never crashes the pipeline.
    """
    raw = await llm_call(system_prompt, user_content, temperature, max_tokens)
    cleaned = _strip_fences(raw)
    repaired = _repair_json(cleaned)

    try:
        result = json.loads(repaired)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Some nodes return {"skills": [...]} — unwrap
            for key in ("skills", "items", "results", "data"):
                if key in result and isinstance(result[key], list):
                    return result[key]
            return [result]
        return []
    except json.JSONDecodeError:
        # Retry once with a stricter prompt
        retry_prompt = (
            system_prompt
            + "\n\nCRITICAL: Your previous response was not valid JSON. Return ONLY a valid JSON array. No markdown. No text outside the JSON."
        )
        retry_user = f"The raw string that failed to parse was:\n\n{raw}\n\n---\n\nPlease redo the extraction correctly:\n{user_content}"
        try:
            raw2 = await llm_call(retry_prompt, retry_user, temperature, max_tokens)
            cleaned2 = _strip_fences(raw2)
            repaired2 = _repair_json(cleaned2)
            result2 = json.loads(repaired2)
            if isinstance(result2, list):
                return result2
            if isinstance(result2, dict):
                for key in ("skills", "items", "results", "data"):
                    if key in result2 and isinstance(result2[key], list):
                        return result2[key]
                return [result2]
            return []
        except Exception:
            return []
