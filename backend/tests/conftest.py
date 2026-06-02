import os
# Pre-populate environment variables for Pydantic Settings validation during test collection
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["ADMIN_API_KEY"] = "test-admin-key"


import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient



@pytest.fixture
def mock_settings():
    """Return a mock settings object with test values."""
    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "test-key"
    settings.gemini_api_key = "test-gemini-key"
    settings.admin_api_key = "test-admin-key"
    settings.max_active_apps = 15
    settings.max_reviews_per_app = 2000
    settings.gemini_sentiment_batch_size = 30
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
    """Create a fully mocked Supabase client."""
    db = MagicMock()
    return db
