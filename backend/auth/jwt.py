import os
import jwt
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET: str | None = None


# Derive the JWT secret from the anon key (Supabase pattern)
# The JWT secret is base64-encoded and used to verify tokens signed by Supabase Auth
def _get_jwt_secret() -> str:
    global SUPABASE_JWT_SECRET
    if SUPABASE_JWT_SECRET:
        return SUPABASE_JWT_SECRET
    anon_key = os.getenv("SUPABASE_KEY", "")
    if not anon_key:
        raise RuntimeError("SUPABASE_KEY not configured")
    SUPABASE_JWT_SECRET = anon_key
    return SUPABASE_JWT_SECRET


async def verify_token(authorization: str = Header(None)) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        secret = _get_jwt_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        return payload
    except jwt.PyJWTError:
        return None


async def require_auth(authorization: str = Header(None)) -> dict:
    payload = await verify_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return payload
