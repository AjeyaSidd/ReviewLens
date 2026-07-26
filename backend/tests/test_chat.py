import pytest
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.services.chat import extract_metadata_filters, run_hybrid_rag


@pytest.fixture
def client(mock_settings, mock_db):
    """Create a test client with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.config.get_settings", return_value=mock_settings), \
         patch("app.database.get_supabase_client", return_value=mock_db), \
         patch("app.logging_config.setup_logging"):
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_extract_metadata_filters_date_range():
    """Verify regex correctly parses various natural date range formats."""
    # 1. ISO since date
    filters = extract_metadata_filters("what are users saying since 2024-05-15?")
    assert filters == {"filter_from_date": "2024-05-15"}
    
    # 2. ISO before date
    filters = extract_metadata_filters("get reviews before 2025-10-20")
    assert filters == {"filter_to_date": "2025-10-20"}
    
    # 3. Relative Days
    filters = extract_metadata_filters("crashes over the last 14 days")
    expected_date = (date.today() - timedelta(days=14)).isoformat()
    assert filters == {"filter_from_date": expected_date}
    
    # 4. Relative Week
    filters = extract_metadata_filters("bugs reported last week")
    expected_date = (date.today() - timedelta(days=7)).isoformat()
    assert filters == {"filter_from_date": expected_date}

    # 5. Relative Month
    filters = extract_metadata_filters("login issues last month")
    expected_date = (date.today() - timedelta(days=30)).isoformat()
    assert filters == {"filter_from_date": expected_date}

    # 6. Named Months
    filters = extract_metadata_filters("problems after Jan 15 2026")
    assert filters == {"filter_from_date": "2026-01-15"}
    
    filters = extract_metadata_filters("reviews since February 28, 2025")
    assert filters == {"filter_from_date": "2025-02-28"}


def test_extract_metadata_filters_versions():
    """Verify regex correctly parses version filters."""
    # 1. Minimum version
    filters = extract_metadata_filters("complaints since version 20.96")
    assert filters == {"filter_min_version": "20.96"}
    
    # 2. Maximum version
    filters = extract_metadata_filters("stability issues before v20.95")
    assert filters == {"filter_max_version": "20.95"}
    
    # 3. Exact version
    filters = extract_metadata_filters("crashes on version 20.99")
    assert filters == {"filter_min_version": "20.99", "filter_max_version": "20.99"}


def test_extract_metadata_filters_ratings():
    """Verify regex correctly parses rating filters."""
    # 1. Minimum rating (above X stars)
    filters = extract_metadata_filters("reviews above 3 stars")
    assert filters == {"filter_min_rating": 3}
    
    # 2. Maximum rating (below X stars)
    filters = extract_metadata_filters("complaints below 3 stars")
    assert filters == {"filter_max_rating": 2}
    
    # 3. Exact rating (X-star / X star)
    filters = extract_metadata_filters("show me 5-star reviews")
    assert filters == {"filter_min_rating": 5, "filter_max_rating": 5}
    
    filters = extract_metadata_filters("what do users write in 1 star reviews?")
    assert filters == {"filter_min_rating": 1, "filter_max_rating": 1}


def test_extract_platform_filter():
    """Verify platform extraction detects ios and android keywords properly."""
    from app.services.chat import extract_platform_filter
    assert extract_platform_filter("show iOS bugs") == "app_store"
    assert extract_platform_filter("iphone crashes") == "app_store"
    assert extract_platform_filter("android login issue") == "play_store"
    assert extract_platform_filter("google play store reviews") == "play_store"
    assert extract_platform_filter("compare iOS and Android") is None
    assert extract_platform_filter("general feedback") is None


def test_is_comparison_query():
    """Verify comparison query detection works for keywords and dual platform queries."""
    from app.services.chat import is_comparison_query
    assert is_comparison_query("Compare positive and negative feedback between iOS and Android") is True
    assert is_comparison_query("iOS vs Android complaints") is True
    assert is_comparison_query("difference between stores") is True
    assert is_comparison_query("iOS bugs only") is False
    assert is_comparison_query("just general question") is False


def test_clean_query_for_embedding():
    """Verify clean_query_for_embedding removes metadata/platform noise but preserves topic content or falls back."""
    from app.services.chat import clean_query_for_embedding
    
    assert clean_query_for_embedding("1-star reviews mentioning UPI in the last month") == "upi"
    assert clean_query_for_embedding("show iOS login bugs") == "login bugs"
    assert clean_query_for_embedding("Compare positive and negative feedback between iOS and Android") == "positive negative feedback"
    assert clean_query_for_embedding("crashes on startup") == "crashes startup"
    
    # Pure metadata / empty fallback case
    assert clean_query_for_embedding("show me 1-star reviews") == "show me 1-star reviews"
    assert clean_query_for_embedding("weather forecast for tomorrow") == "weather forecast tomorrow"




@pytest.mark.asyncio
@patch("app.services.chat.genai")
@patch("app.services.chat.retrieve_semantic_context")
@patch("app.services.chat.retrieve_trends_context")
@patch("app.services.chat.get_settings")
async def test_run_hybrid_rag_success(mock_get_settings, mock_retrieve_trends, mock_retrieve_semantic, mock_genai):
    """Verify RAG orchestrator executes concurrently and returns cited response."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_settings.rag_review_limit = 30
    mock_settings.rag_match_threshold = 0.3
    mock_get_settings.return_value = mock_settings
    
    # Mock concurrent retrieval calls
    async def mock_trends(*args, **kwargs):
        return [{"date": "2026-05-20", "avg_rating": 4.5, "review_count": 10}]
        
    async def mock_semantic(*args, **kwargs):
        return [{"id": "uuid-1", "platform": "play_store", "rating": 2, "review_date": "2026-05-20", "title": "Crash", "body": "App crashes"}]

    mock_retrieve_trends.side_effect = mock_trends
    mock_retrieve_semantic.side_effect = mock_semantic
    
    # Mock Gemini Client generate content call
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "answer": "Average rating is 4.5, but users complain about crashes.",
        "metrics": {
            "avg_rating": 4.5,
            "total_reviews": 10,
            "sample_size": 30,
            "theme_breakdown": [
                {"theme": "App Crashes", "count": 5, "percentage": 16.7}
            ]
        },
        "citations": [
            {
                "review_id": "uuid-1",
                "platform": "play_store",
                "rating": 2,
                "review_date": "2026-05-20",
                "snippet": "App crashes"
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response
    
    result = await run_hybrid_rag("test-app-id", "Show ratings and crashes since 2026-01-01")
    
    assert "Average rating is 4.5" in result["answer"]
    assert result["metrics"]["total_reviews"] == 10
    assert len(result["citations"]) == 1
    assert result["citations"][0]["review_id"] == "uuid-1"
    
    # Verify metadata-aware filters were forwarded to retrieve_semantic_context
    mock_retrieve_semantic.assert_called_once_with(
        app_id="test-app-id",
        query="ratings crashes",
        limit=30,
        filter_from_date="2026-01-01"
    )


class TestChatEndpoint:
    """Test POST /apps/{app_id}/chat API route."""
    
    def test_chat_app_not_found(self, client, mock_db):
        """Should return 404 if app uuid does not exist."""
        app_resp = MagicMock()
        app_resp.data = {}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        response = client.post(
            "/apps/non-existent-uuid/chat",
            json={"message": "Hello"}
        )
        assert response.status_code == 404

    @patch("app.routers.public.run_hybrid_rag")
    def test_chat_success(self, mock_run_rag, client, mock_db):
        """Should call run_hybrid_rag and return structured response."""
        # Mock active app validation
        app_resp = MagicMock()
        app_resp.data = {"id": "test-uuid", "is_active": True}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        # Define mock async run_hybrid_rag return
        async def mock_rag(*args):
            return {
                "answer": "This is the answer.",
                "metrics": {},
                "citations": []
            }
        mock_run_rag.side_effect = mock_rag
        
        response = client.post(
            "/apps/test-uuid/chat",
            json={"message": "Are users happy?"}
        )
        
        assert response.status_code == 200
        assert response.json()["answer"] == "This is the answer."
        mock_run_rag.assert_called_once_with("test-uuid", "Are users happy?")
