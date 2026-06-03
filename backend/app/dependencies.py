from fastapi.security import APIKeyHeader
from fastapi import Security, HTTPException, status
from app.config import get_settings

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

async def verify_admin_key(api_key: str = Security(api_key_header)) -> str:
    settings = get_settings()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing X-Admin-Key header",
        )
    if api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )
    return api_key

