import os
import json
import re
import asyncio
import httpx
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from dotenv import load_dotenv

load_dotenv(override=True)

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://172.20.7.22:9000")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "3699")

_semaphore = asyncio.Semaphore(4)

_tokenizer = None
_model = None

_content_cache: dict[str, list] = {}


def clear_cache():
    _content_cache.clear()


def _load_embedding_model():
    global _tokenizer, _model
    if _tokenizer is None:
        torch.set_num_threads(2)
        _tokenizer = AutoTokenizer.from_pretrained(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        _model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


def get_embedding(text: str) -> list:
    _load_embedding_model()
    inputs = _tokenizer(
        text, padding=True, truncation=True, return_tensors="pt", max_length=128
    )
    with torch.no_grad():
        outputs = _model(**inputs)
    attention_mask = inputs["attention_mask"]
    token_embeddings = outputs.last_hidden_state
    input_mask_expanded = (
        attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    )
    embedding = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9
    )
    return embedding[0].tolist()


def get_embeddings(texts: list) -> list:
    return [get_embedding(t) for t in texts]


def cosine_similarity(v1, v2) -> float:
    a, b = np.array(v1), np.array(v2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


async def check_vllm_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{VLLM_BASE_URL}/health", headers={"x-api-key": VLLM_API_KEY}
            )
            return {
                "healthy": response.status_code == 200,
                "url": VLLM_BASE_URL,
                "mode": "vllm_gateway",
            }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


async def llm_call(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    async with _semaphore:
        for attempt in range(5):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{VLLM_BASE_URL}/generate",
                        headers={
                            "x-api-key": VLLM_API_KEY,
                            "x-user-name": "kernl",
                        },
                        json={
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content},
                            ]
                        },
                    )
                    response.raise_for_status()
                    return response.json()["response"]
            except Exception as e:
                err_str = str(e)
                is_rate = (
                    "429" in err_str
                    or "413" in err_str
                    or "rate_limit" in err_str.lower()
                )
                if is_rate and attempt < 4:
                    wait = 2 ** (attempt + 1) * 5
                    print(
                        f"[vLLM Gateway] Rate limit hit, waiting {wait}s (attempt {attempt + 1})..."
                    )
                    await asyncio.sleep(wait)
                    continue
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                raise RuntimeError(
                    f"LLM Call Failed.\nURL: {VLLM_BASE_URL}\nError: {str(e)}"
                )


def _strip_fences(raw: str) -> str:
    clean = raw.strip()
    start_idx = clean.find("```json")
    if start_idx != -1:
        end_idx = clean.rfind("```")
        if end_idx != -1 and end_idx > start_idx:
            return clean[start_idx + 7 : end_idx].strip()
    start_idx = clean.find("```")
    if start_idx != -1:
        end_idx = clean.rfind("```")
        if end_idx != -1 and end_idx > start_idx:
            return clean[start_idx + 3 : end_idx].strip()
    return clean


def _repair_json(raw: str) -> str:
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    raw = re.sub(r",\s*$", "", raw)
    first_bracket = raw.find("[")
    last_bracket = raw.rfind("]")
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        if last_bracket != -1 and last_bracket > first_bracket:
            return raw[first_bracket : last_bracket + 1]
    elif first_brace != -1:
        if last_brace != -1 and last_brace > first_brace:
            return raw[first_brace : last_brace + 1]
    return raw


async def safe_llm_json_call(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    cache_key: str | None = None,
) -> list:
    if cache_key and cache_key in _content_cache:
        print(f"[LLM Cache] HIT {cache_key[:24]}...")
        return _content_cache[cache_key]

    raw = await llm_call(system_prompt, user_content, temperature, max_tokens)
    cleaned = _strip_fences(raw)
    repaired = _repair_json(cleaned)
    try:
        result = json.loads(repaired)
        if isinstance(result, list):
            if cache_key:
                _content_cache[cache_key] = result
            return result
        if isinstance(result, dict):
            for key in ("skills", "items", "results", "data"):
                if key in result and isinstance(result[key], list):
                    if cache_key:
                        _content_cache[cache_key] = result
                    return result[key]
            if cache_key:
                _content_cache[cache_key] = [result]
            return [result]
        return []
    except json.JSONDecodeError:
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
                if cache_key:
                    _content_cache[cache_key] = result2
                return result2
            if isinstance(result2, dict):
                for key in ("skills", "items", "results", "data"):
                    if key in result2 and isinstance(result2[key], list):
                        if cache_key:
                            _content_cache[cache_key] = result2
                        return result2[key]
                if cache_key:
                    _content_cache[cache_key] = [result2]
                return [result2]
            return []
        except Exception:
            return []
