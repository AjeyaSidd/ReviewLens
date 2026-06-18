import os
# Pre-populate environment variables for Pydantic Settings validation during test collection
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["GEMINI_EMBEDDING_API_KEY"] = "test-gemini-embedding-key"
os.environ["ADMIN_API_KEY"] = "test-admin-key"

from unittest.mock import MagicMock
def mock_await(self):
    async def _await_helper():
        return self
    return _await_helper().__await__()
MagicMock.__await__ = mock_await

import pytest
from unittest.mock import patch
from datetime import date
from fastapi.testclient import TestClient



@pytest.fixture
def mock_settings():
    """Return a mock settings object with test values."""
    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "test-key"
    settings.gemini_api_key = "test-gemini-key"
    settings.gemini_embedding_api_key = "test-gemini-embedding-key"
    settings.admin_api_key = "test-admin-key"
    settings.max_active_apps = 15
    settings.max_reviews_per_app = 500
    settings.gemini_sentiment_batch_size = 30
    settings.gemini_embedding_batch_size = 100
    settings.gemini_sentiment_model = "gemini-2.0-flash"
    settings.cors_origins = "http://localhost:3000"
    settings.cors_origin_list = ["http://localhost:3000"]
    settings.log_dir = "backend/logs"
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def sample_reviews():
    """Sample NormalizedReview data for testing."""
    from app.services.models import NormalizedReview
    return [
        NormalizedReview(
            platform_review_id="play_1",
            platform="play_store",
            rating=5,
            title="",
            body="This app is amazing! Love the new features.",
            review_date=date(2026, 5, 20),
            language=None,
            app_version="1.0.0",
        ),
        NormalizedReview(
            platform_review_id="play_2",
            platform="play_store",
            rating=1,
            title="",
            body="Terrible. Crashes every time I open it.",
            review_date=date(2026, 5, 19),
            language=None,
            app_version="1.0.0",
        ),
        NormalizedReview(
            platform_review_id="ios_1",
            platform="app_store",
            rating=4,
            title="Pretty good",
            body="Works well but could use dark mode.",
            review_date=date(2026, 5, 18),
            language=None,
            app_version="2.0",
        ),
        NormalizedReview(
            platform_review_id="play_3",
            platform="play_store",
            rating=3,
            title="",
            body="",  # Rating-only review, no text
            review_date=date(2026, 5, 17),
            language=None,
            app_version="1.0.0",
        ),
    ]


@pytest.fixture
def mock_db():
    """Create a fully mocked Supabase client with table-specific query chaining and async execute."""
    db = MagicMock()
    table_chains = {}
    
    # Track the initial mock response for the default table to know if it was replaced
    initial_default_resp = MagicMock()
    initial_default_resp.data = []
    initial_default_resp.count = 0
    
    def get_table_chain(table_name):
        if table_name not in table_chains:
            chain = MagicMock()
            
            # Create a unique initial empty response for this specific chain
            our_initial_empty_resp = MagicMock()
            our_initial_empty_resp.data = []
            our_initial_empty_resp.count = 0
            chain.execute.return_value = our_initial_empty_resp
            
            async def async_execute():
                # If this is not the default table, and its own execute.return_value hasn't been changed from our_initial_empty_resp,
                # check if default table's execute.return_value has been customized.
                if table_name != "default":
                    default_chain = table_chains.get("default")
                    if default_chain and chain.execute.return_value is our_initial_empty_resp:
                        if default_chain.execute.return_value is not initial_default_resp:
                            return default_chain.execute.return_value
                return chain.execute.return_value

            chain.execute.side_effect = async_execute
            
            # Set up method chaining: make each query method return the chain itself
            methods = ['select', 'insert', 'update', 'upsert', 'delete', 'eq', 'neq', 'in_', 'is_', 'order', 'limit', 'single', 'gte', 'lte', 'range']
            for method in methods:
                setattr(chain, method, MagicMock(return_value=chain))
                
            table_chains[table_name] = chain
        return table_chains[table_name]
        
    # Pre-populate "default" chain with the tracked initial response
    default_chain = get_table_chain("default")
    default_chain.execute.return_value = initial_default_resp
    
    db.table.side_effect = get_table_chain
    db.table.return_value = default_chain
    
    # For RPC
    rpc_chain = MagicMock()
    async def async_rpc_execute():
        return rpc_chain.execute.return_value
    rpc_chain.execute.side_effect = async_rpc_execute
    
    rpc_resp = MagicMock()
    rpc_resp.data = []
    rpc_chain.execute.return_value = rpc_resp
    
    methods = ['select', 'insert', 'update', 'upsert', 'delete', 'eq', 'neq', 'in_', 'is_', 'order', 'limit', 'single', 'gte', 'lte', 'range']
    for method in methods:
        setattr(rpc_chain, method, MagicMock(return_value=rpc_chain))
        
    db.rpc.return_value = rpc_chain
    
    return db
