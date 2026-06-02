from supabase import create_client, Client
from app.config import get_settings

_client: Client | None = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client

def get_db() -> Client:
    return get_supabase_client()
