from fastapi import Header, HTTPException, status
from app.config import get_settings

async def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> str:
    settings = get_settings()
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )
    return x_admin_key
