import logging
from app.services.models import SentimentResult

logger = logging.getLogger(__name__)


def analyze_sentiment_batch(
    reviews_for_sentiment: list[dict],
    max_retries: int = 3,
) -> list[SentimentResult]:
    """Calculate sentiment score and label directly from user ratings.
    
    This avoids Gemini API rate limits and keeps trend calculations fast and local.
    
    Each item in reviews_for_sentiment should have:
        - review_id: str
        - rating: int
        - text: str (optional)
        
    Returns list of SentimentResult.
    """
    logger.info("Computing rating-based sentiment | total_reviews=%d", len(reviews_for_sentiment))
    results = []
    
    for r in reviews_for_sentiment:
        rating = r.get("rating", 3)
        # Map rating to score: 5 -> 1.0, 4 -> 0.5, 3 -> 0.0, 2 -> -0.5, 1 -> -1.0
        score = (rating - 3) / 2.0
        
        # Map rating to label
        if rating >= 4:
            label = "positive"
        elif rating <= 2:
            label = "negative"
        else:
            label = "neutral"
            
        results.append(SentimentResult(
            review_id=str(r["review_id"]),
            sentiment_score=score,
            sentiment_label=label,
        ))
        
    return results


def _parse_sentiment_response(response_text: str) -> list[SentimentResult]:
    """Deprecated: Stub kept for backward compatibility."""
    return []
