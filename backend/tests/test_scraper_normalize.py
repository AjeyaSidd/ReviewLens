from datetime import date, datetime
from unittest.mock import patch
from app.services.scrape_play import normalize_play_review, scrape_play_reviews
from app.services.scrape_ios import normalize_ios_review


def test_normalize_play_review():
    """Verify Google Play reviews normalize correctly."""
    raw = {
        "reviewId": "play-id-123",
        "score": 4,
        "content": "This app is wonderful!",
        "at": datetime(2026, 5, 20, 14, 30, 0),
        "reviewCreatedVersion": "1.2.3",
    }
    
    normalized = normalize_play_review(raw)
    
    assert normalized.platform_review_id == "play-id-123"
    assert normalized.platform == "play_store"
    assert normalized.rating == 4
    assert normalized.title == ""  # Play Store has no title
    assert normalized.body == "This app is wonderful!"
    assert normalized.review_date == date(2026, 5, 20)
    assert normalized.app_version == "1.2.3"
    assert normalized.has_text is True
    assert normalized.full_text == "This app is wonderful!"


def test_normalize_play_review_date_fallback():
    """Verify Play Store normalization handles date type in 'at' field."""
    raw = {
        "reviewId": "play-id-456",
        "score": 3,
        "content": "Nice",
        "at": date(2026, 5, 19),
        "reviewCreatedVersion": None,
    }
    
    normalized = normalize_play_review(raw)
    assert normalized.review_date == date(2026, 5, 19)


def test_normalize_ios_review():
    """Verify Apple App Store reviews normalize correctly."""
    raw = {
        "id": "ios-id-999",
        "rating": 5,
        "title": "Excellent App!",
        "review": "Fast and smooth.",
        "date": datetime(2026, 5, 18, 10, 0, 0),
        "version": "2.4.0",
    }
    
    normalized = normalize_ios_review(raw)
    
    assert normalized.platform_review_id == "ios-id-999"
    assert normalized.platform == "app_store"
    assert normalized.rating == 5
    assert normalized.title == "Excellent App!"
    assert normalized.body == "Fast and smooth."
    assert normalized.review_date == date(2026, 5, 18)
    assert normalized.app_version == "2.4.0"
    assert normalized.has_text is True
    assert normalized.full_text == "Excellent App!. Fast and smooth"


@patch("app.services.scrape_play.reviews")
def test_scrape_play_reviews_wordlength_filter(mock_reviews):
    """Verify that scrape_play_reviews clears body and title for reviews with word count <= 3."""
    mock_reviews.return_value = (
        [
            {
                "reviewId": "r1",
                "score": 5,
                "content": "This is very good",
                "at": datetime(2026, 5, 20),
                "reviewCreatedVersion": "1.0",
            },
            {
                "reviewId": "r2",
                "score": 4,
                "content": "Very good app",
                "at": datetime(2026, 5, 20),
                "reviewCreatedVersion": "1.0",
            },
            {
                "reviewId": "r3",
                "score": 1,
                "content": "Nice",
                "at": datetime(2026, 5, 20),
                "reviewCreatedVersion": "1.0",
            },
            {
                "reviewId": "r4",
                "score": 3,
                "content": "I like this app a lot",
                "at": datetime(2026, 5, 20),
                "reviewCreatedVersion": "1.0",
            },
        ],
        None,
    )
    
    result = scrape_play_reviews("com.test", max_reviews=10, delay_between_pages=0.0)
    
    assert len(result) == 4
    # r1: kept text
    assert result[0].platform_review_id == "r1"
    assert result[0].body == "This is very good"
    # r2: cleared text
    assert result[1].platform_review_id == "r2"
    assert result[1].body == ""
    # r3: cleared text
    assert result[2].platform_review_id == "r3"
    assert result[2].body == ""
    # r4: kept text
    assert result[3].platform_review_id == "r4"
    assert result[3].body == "I like this app a lot"

