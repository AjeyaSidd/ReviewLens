import pytest
from unittest.mock import MagicMock, patch
from app.services.embeddings import generate_embeddings_batch, run_embeddings


@patch("app.services.embeddings.genai")
@patch("app.services.embeddings.get_settings")
def test_generate_embeddings_batch_success(mock_get_settings, mock_genai):
    """Verify standard embedding batch generation works and extracts values correctly."""
    # Mock config settings
    mock_settings = MagicMock()
    mock_settings.gemini_embedding_model = "gemini-embedding-001"
    mock_settings.gemini_embedding_api_key = "test-gemini-embedding-key"
    mock_settings.gemini_embedding_batch_size = 100
    mock_get_settings.return_value = mock_settings
    
    # Mock genai Client
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    # Mock response object structure
    mock_emb1 = MagicMock()
    mock_emb1.values = [0.1] * 1536
    mock_emb2 = MagicMock()
    mock_emb2.values = [-0.2] * 1536
    
    mock_response = MagicMock()
    mock_response.embeddings = [mock_emb1, mock_emb2]
    mock_client.models.embed_content.return_value = mock_response
    
    texts = ["Excellent service", "Very slow interface"]
    embeddings = generate_embeddings_batch(texts)
    
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536
    assert len(embeddings[1]) == 1536
    assert embeddings[0][0] == 0.1
    assert embeddings[1][0] == -0.2
    
    mock_genai.Client.assert_called_once_with(api_key="test-gemini-embedding-key")
    mock_genai.types.EmbedContentConfig.assert_called_once_with(output_dimensionality=1536)
    call_args = mock_client.models.embed_content.call_args
    assert call_args[1]["model"] == "gemini-embedding-001"
    assert call_args[1]["contents"] == texts
    assert call_args[1]["config"] == mock_genai.types.EmbedContentConfig.return_value


@patch("app.services.embeddings.time")
@patch("app.services.embeddings.genai")
@patch("app.services.embeddings.get_settings")
def test_generate_embeddings_multiple_batches(mock_get_settings, mock_genai, mock_time):
    """Verify that text lists exceeding 100 split into multiple safe chunks."""
    mock_settings = MagicMock()
    mock_settings.gemini_embedding_model = "gemini-embedding-001"
    mock_settings.gemini_embedding_api_key = "test-gemini-embedding-key"
    mock_settings.gemini_embedding_batch_size = 100
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    # Custom side effect to return appropriate sized list of embeddings
    def embed_content_side_effect(model, contents, config=None, **kwargs):
        batch_size = len(contents)
        response = MagicMock()
        response.embeddings = [MagicMock(values=[0.5] * 1536) for _ in range(batch_size)]
        return response
        
    mock_client.models.embed_content.side_effect = embed_content_side_effect
    
    # 150 texts (should yield 2 batches: 100 items + 50 items)
    texts = [f"Text {i}" for i in range(150)]
    embeddings = generate_embeddings_batch(texts)
    
    assert mock_client.models.embed_content.call_count == 2
    assert len(embeddings) == 150
    assert mock_time.sleep.call_count == 1
    mock_time.sleep.assert_any_call(12.0)



@patch("app.services.embeddings.generate_embeddings_batch")
def test_run_embeddings_empty_or_no_text(mock_generate, mock_db):
    """Verify that rating-only or empty body reviews are completely skipped."""
    mock_resp = MagicMock()
    mock_resp.data = [
        {"id": "r1", "title": "", "body": "", "catalog_app_id": "test-app-uuid", "platform": "play_store", "platform_review_id": "r1", "rating": 5},
        {"id": "r2", "title": "   ", "body": "   ", "catalog_app_id": "test-app-uuid", "platform": "play_store", "platform_review_id": "r2", "rating": 5},
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = mock_resp
    
    with patch("app.services.embeddings.get_supabase_client", return_value=mock_db):
        count = run_embeddings("test-app-uuid")
        assert count == 0
        mock_generate.assert_not_called()


@patch("app.services.embeddings.generate_embeddings_batch")
def test_run_embeddings_e2e_success(mock_generate, mock_db):
    """Verify full end-to-end embedding pipeline with safe truncation and db updates."""
    # Mock 2 reviews needing embeddings. One is very long to test truncation.
    very_long_body = "A" * 9000
    mock_resp = MagicMock()
    mock_resp.data = [
        {"id": "uuid-1", "title": "Good", "body": "I like this app.", "catalog_app_id": "test-app-uuid", "platform": "play_store", "platform_review_id": "r1", "rating": 5},
        {"id": "uuid-2", "title": "Spam", "body": very_long_body, "catalog_app_id": "test-app-uuid", "platform": "play_store", "platform_review_id": "r2", "rating": 1},
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = mock_resp
    
    # Mock generated embeddings lists
    dummy_emb_1 = [0.01] * 1536
    dummy_emb_2 = [-0.01] * 1536
    mock_generate.return_value = [dummy_emb_1, dummy_emb_2]
    
    with patch("app.services.embeddings.get_supabase_client", return_value=mock_db):
        count = run_embeddings("test-app-uuid")
        
        assert count == 2
        
        # Verify safe truncation to 8000 characters was applied to very_long_body
        expected_texts = [
            "Good. I like this app",
            f"Spam. {very_long_body}"[:8000].strip(" ."),
        ]
        mock_generate.assert_called_once_with(expected_texts)
        
        # Verify db updates were called as a bulk upsert
        assert mock_db.table.return_value.upsert.call_count == 1
        mock_db.table.return_value.upsert.assert_called_once_with([
            {
                "id": "uuid-1",
                "catalog_app_id": "test-app-uuid",
                "platform": "play_store",
                "platform_review_id": "r1",
                "rating": 5,
                "embedding": dummy_emb_1,
            },
            {
                "id": "uuid-2",
                "catalog_app_id": "test-app-uuid",
                "platform": "play_store",
                "platform_review_id": "r2",
                "rating": 1,
                "embedding": dummy_emb_2,
            },
        ])


@patch("app.services.embeddings.time")
@patch("app.services.embeddings.genai")
@patch("app.services.embeddings.get_settings")
def test_generate_embeddings_rate_limit_retry(mock_get_settings, mock_genai, mock_time):
    """Verify that a 429 error triggers a 60-second sleep and fails after exactly 1 retry."""
    mock_settings = MagicMock()
    mock_settings.gemini_embedding_model = "gemini-embedding-001"
    mock_settings.gemini_embedding_api_key = "test-gemini-embedding-key"
    mock_settings.gemini_embedding_batch_size = 100
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    # Simulate a rate limit error on all calls
    mock_client.models.embed_content.side_effect = Exception("ResourceExhausted: 429 Too Many Requests")
    
    # Call generate_embeddings_batch and expect a failure
    with pytest.raises(Exception, match="429"):
        generate_embeddings_batch(["Sample text"])
        
    # The client should be called twice (initial attempt + exactly 1 retry)
    assert mock_client.models.embed_content.call_count == 2
    # Verify that sleep was called with 60.0 seconds to wait out the 429 limits
    mock_time.sleep.assert_called_once_with(60.0)

