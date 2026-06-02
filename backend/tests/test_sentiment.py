import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.sentiment import analyze_sentiment_batch, _parse_sentiment_response


def test_parse_sentiment_response_with_markdown_fences():
    """Verify parsing handles markdown fences cleanly."""
    raw_response = """
    ```json
    [
      {
        "review_id": "r1",
        "sentiment_score": 0.8,
        "sentiment_label": "positive"
      }
    ]
    ```
    """
    results = _parse_sentiment_response(raw_response)
    assert len(results) == 1
    assert results[0].review_id == "r1"
    assert results[0].sentiment_score == 0.8
    assert results[0].sentiment_label == "positive"


def test_parse_sentiment_response_raw_json():
    """Verify parsing handles raw JSON string cleanly."""
    raw_response = '[{"review_id": "r2", "sentiment_score": -0.5, "sentiment_label": "negative"}]'
    results = _parse_sentiment_response(raw_response)
    assert len(results) == 1
    assert results[0].review_id == "r2"
    assert results[0].sentiment_score == -0.5
    assert results[0].sentiment_label == "negative"


@patch("app.services.sentiment.genai")
@patch("app.services.sentiment.get_settings")
def test_analyze_sentiment_batch_success(mock_get_settings, mock_genai):
    """Verify sentiment analysis batch succeeds and formats prompt."""
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_batch_size = 30
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    # Mock Client
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    # Mock generate_content response
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {"review_id": "r-1", "sentiment_score": 0.9, "sentiment_label": "positive"},
        {"review_id": "r-2", "sentiment_score": -0.9, "sentiment_label": "negative"}
    ])
    mock_client.models.generate_content.return_value = mock_response
    
    reviews = [
        {"review_id": "r-1", "rating": 5, "text": "Superb"},
        {"review_id": "r-2", "rating": 1, "text": "Awful"}
    ]
    
    results = analyze_sentiment_batch(reviews)
    
    assert len(results) == 2
    assert results[0].review_id == "r-1"
    assert results[0].sentiment_score == 0.9
    assert results[0].sentiment_label == "positive"
    assert mock_client.models.generate_content.call_count == 1


@patch("app.services.sentiment.genai")
@patch("app.services.sentiment.get_settings")
def test_analyze_sentiment_multiple_batches(mock_get_settings, mock_genai):
    """Verify inputs larger than batch size split into multiple requests."""
    mock_settings = MagicMock()
    mock_settings.gemini_sentiment_batch_size = 30
    mock_settings.gemini_sentiment_model = "gemini-2.0-flash"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    
    # Custom side effect to return appropriate length results
    def generate_content_side_effect(model, contents, config):
        # Determine size from prompt contents count
        batch_size = 30 if "Review 29" in contents else 20
        response = MagicMock()
        response.text = json.dumps([
            {"review_id": f"r{i}", "sentiment_score": 0.0, "sentiment_label": "neutral"}
            for i in range(batch_size)
        ])
        return response
        
    mock_client.models.generate_content.side_effect = generate_content_side_effect
    
    reviews = [
        {"review_id": f"r{i}", "rating": 3, "text": f"Review {i}"}
        for i in range(50)
    ]
    
    results = analyze_sentiment_batch(reviews)
    
    # 50 split by batch size 30 should yield 2 batches
    assert mock_client.models.generate_content.call_count == 2
    assert len(results) == 50


def test_analyze_sentiment_empty_input():
    """Verify empty input requires no API requests and returns empty array."""
    results = analyze_sentiment_batch([])
    assert results == []
