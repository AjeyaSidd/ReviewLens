import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.services.chat import detect_query_intent, run_hybrid_rag


@pytest.fixture
def client(mock_settings, mock_db):
    """Create a test client with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.config.get_settings", return_value=mock_settings), \
         patch("app.database.get_supabase_client", return_value=mock_db), \
         patch("app.logging_config.setup_logging"):
        yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.services.chat.genai")
@patch("app.services.chat.get_settings")
def test_detect_query_intent_metric(mock_get_settings, mock_genai):
    """Verify Gemini classifies trend/aggregate queries as METRIC_TRENDS."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = "METRIC_TRENDS"
    mock_client.models.generate_content.return_value = mock_response
    
    intent = detect_query_intent("What is my average rating over the last 7 days?")
    assert intent == "METRIC_TRENDS"


@patch("app.services.chat.genai")
@patch("app.services.chat.get_settings")
def test_detect_query_intent_semantic(mock_get_settings, mock_genai):
    """Verify Gemini classifies experience/complaint queries as SEMANTIC_FEEDBACK."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = "SEMANTIC_FEEDBACK"
    mock_client.models.generate_content.return_value = mock_response
    
    intent = detect_query_intent("Are users complaining about dark mode?")
    assert intent == "SEMANTIC_FEEDBACK"


@patch("app.services.chat.genai")
@patch("app.services.chat.get_settings")
def test_detect_query_intent_hybrid(mock_get_settings, mock_genai):
    """Verify Gemini classifies multi-part queries as HYBRID."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = "HYBRID"
    mock_client.models.generate_content.return_value = mock_response
    
    intent = detect_query_intent("What is our average rating this week and what specific bugs were reported?")
    assert intent == "HYBRID"


@patch("app.services.chat.genai")
@patch("app.services.chat.detect_query_intent")

@patch("app.services.chat.retrieve_semantic_context")
@patch("app.services.chat.get_settings")
def test_run_hybrid_rag_semantic(mock_get_settings, mock_retrieve_context, mock_detect_intent, mock_genai):
    """Verify RAG synthesizes semantic reviews context into cited answer shape."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_detect_intent.return_value = "SEMANTIC_FEEDBACK"
    
    # Mock retrieved review context
    mock_retrieve_context.return_value = [
        {"id": "uuid-1", "platform": "play_store", "rating": 2, "review_date": "2026-05-20", "title": "Crash", "body": "App crashes on login"}
    ]
    
    # Mock Gemini answer synthesis return
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "answer": "Users are complaining about app crashes on the login screen.",
        "metrics": {},
        "citations": [
            {
                "review_id": "uuid-1",
                "platform": "play_store",
                "rating": 2,
                "review_date": "2026-05-20",
                "snippet": "App crashes on login"
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response
    
    result = run_hybrid_rag("app-uuid", "Why is it crashing?")
    
    assert "crashes on the login screen" in result["answer"]
    assert len(result["citations"]) == 1
    assert result["citations"][0]["review_id"] == "uuid-1"


@patch("app.services.chat.genai")
@patch("app.services.chat.detect_query_intent")
@patch("app.services.chat.retrieve_trends_context")
@patch("app.services.chat.get_settings")
def test_run_hybrid_rag_trends(mock_get_settings, mock_retrieve_context, mock_detect_intent, mock_genai):
    """Verify RAG synthesizes daily rollups context into metric summary shape."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_detect_intent.return_value = "METRIC_TRENDS"
    
    # Mock retrieved daily rollups context
    mock_retrieve_context.return_value = [
        {"date": "2026-05-20", "avg_rating": 4.5, "review_count": 10}
    ]
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "answer": "Your average rating is 4.5 across 10 reviews.",
        "metrics": {"avg_rating": 4.5, "total_reviews": 10},
        "citations": []
    })
    mock_client.models.generate_content.return_value = mock_response
    
    result = run_hybrid_rag("app-uuid", "What are my metrics?")
    
    assert "average rating is 4.5" in result["answer"]
    assert result["metrics"]["total_reviews"] == 10
    assert result["citations"] == []


@patch("app.services.chat.genai")
@patch("app.services.chat.detect_query_intent")
@patch("app.services.chat.retrieve_semantic_context")
@patch("app.services.chat.retrieve_trends_context")
@patch("app.services.chat.get_settings")
def test_run_hybrid_rag_hybrid(mock_get_settings, mock_retrieve_trends, mock_retrieve_semantic, mock_detect_intent, mock_genai):
    """Verify RAG handles HYBRID queries by pulling both SQL rollups and pgvector reviews."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_detect_intent.return_value = "HYBRID"
    
    # Mock both rollups and semantic reviews context
    mock_retrieve_trends.return_value = [
        {"date": "2026-05-20", "avg_rating": 4.5, "review_count": 10}
    ]
    mock_retrieve_semantic.return_value = [
        {"id": "uuid-1", "platform": "play_store", "rating": 2, "review_date": "2026-05-20", "title": "Crash", "body": "App crashes on login"}
    ]
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "answer": "Average rating is 4.5, but iOS has 1 crash.",
        "metrics": {"avg_rating": 4.5, "total_reviews": 10},
        "citations": [
            {
                "review_id": "uuid-1",
                "platform": "play_store",
                "rating": 2,
                "review_date": "2026-05-20",
                "snippet": "App crashes on login"
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response
    
    result = run_hybrid_rag("app-uuid", "Compare my rating and list crashes.")
    
    assert "Average rating is 4.5" in result["answer"]
    assert result["metrics"]["total_reviews"] == 10
    assert len(result["citations"]) == 1
    assert result["citations"][0]["review_id"] == "uuid-1"


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
        
        mock_run_rag.return_value = {
            "answer": "This is the answer.",
            "metrics": {},
            "citations": []
        }
        
        response = client.post(
            "/apps/test-uuid/chat",
            json={"message": "Are users happy?"}
        )
        
        assert response.status_code == 200
        assert response.json()["answer"] == "This is the answer."
        mock_run_rag.assert_called_once_with("test-uuid", "Are users happy?")
