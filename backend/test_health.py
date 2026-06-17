import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
load_dotenv()


async def test_health():
    from backend.core.llm import check_vllm_health

    print("Checking VLLM / HF health...")
    res = await check_vllm_health()
    print("Health Result:")
    print(res)


if __name__ == "__main__":
    asyncio.run(test_health())
