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
