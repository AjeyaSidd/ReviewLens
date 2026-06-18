import pytest
from app.services.sentiment import analyze_sentiment_batch


def test_analyze_sentiment_batch_success():
    """Verify star ratings map exactly to expected sentiment scores and labels."""
    reviews = [
        {"review_id": "r-5", "rating": 5, "text": "Superb"},
        {"review_id": "r-4", "rating": 4, "text": "Pretty good"},
        {"review_id": "r-3", "rating": 3, "text": "Average"},
        {"review_id": "r-2", "rating": 2, "text": "Disappointed"},
        {"review_id": "r-1", "rating": 1, "text": "Broken application"}
    ]
    
    results = analyze_sentiment_batch(reviews)
    
    assert len(results) == 5
    
    # 5 Stars
    assert results[0].review_id == "r-5"
    assert results[0].sentiment_score == 1.0
    assert results[0].sentiment_label == "positive"
    
    # 4 Stars
    assert results[1].review_id == "r-4"
    assert results[1].sentiment_score == 0.5
    assert results[1].sentiment_label == "positive"
    
    # 3 Stars
    assert results[2].review_id == "r-3"
    assert results[2].sentiment_score == 0.0
    assert results[2].sentiment_label == "neutral"
    
    # 2 Stars
    assert results[3].review_id == "r-2"
    assert results[3].sentiment_score == -0.5
    assert results[3].sentiment_label == "negative"
    
    # 1 Star
    assert results[4].review_id == "r-1"
    assert results[4].sentiment_score == -1.0
    assert results[4].sentiment_label == "negative"


def test_analyze_sentiment_empty_input():
    """Verify empty input returns empty list immediately."""
    results = analyze_sentiment_batch([])
    assert results == []


from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_run_sentiment_includes_empty_body_reviews(mock_db):
    """Verify that _run_sentiment does not skip reviews with empty title/body."""
    from app.services.sync_app import _run_sentiment
    
    mock_resp = MagicMock()
    mock_resp.data = [
        {
            "id": "r-text",
            "title": "Good",
            "body": "It works well.",
            "rating": 5,
            "catalog_app_id": "test-app-uuid",
            "platform": "play_store",
            "platform_review_id": "p-text"
        },
        {
            "id": "r-empty",
            "title": "",
            "body": "   ",
            "rating": 2,
            "catalog_app_id": "test-app-uuid",
            "platform": "app_store",
            "platform_review_id": "i-empty"
        }
    ]
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        count = await _run_sentiment("test-app-uuid")
        
        # Verify both reviews were processed
        assert count == 2
        
        # Verify bulk upsert was called with correct sentiment results
        assert mock_db.table("reviews").upsert.call_count == 1
        upserted_rows = mock_db.table("reviews").upsert.call_args[0][0]
        assert len(upserted_rows) == 2
        
        # Row 1 (rating 5 -> positive, score 1.0)
        row_text = next(r for r in upserted_rows if r["id"] == "r-text")
        assert row_text["sentiment_score"] == 1.0
        assert row_text["sentiment_label"] == "positive"
        assert row_text["catalog_app_id"] == "test-app-uuid"
        
        # Row 2 (rating 2 -> negative, score -0.5)
        row_empty = next(r for r in upserted_rows if r["id"] == "r-empty")
        assert row_empty["sentiment_score"] == -0.5
        assert row_empty["sentiment_label"] == "negative"
        assert row_empty["catalog_app_id"] == "test-app-uuid"
