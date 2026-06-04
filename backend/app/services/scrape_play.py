import logging
import time
from datetime import date, datetime
from google_play_scraper import Sort, reviews
from app.services.models import NormalizedReview

logger = logging.getLogger(__name__)

def normalize_play_review(raw: dict) -> NormalizedReview:
    """Convert a raw google-play-scraper review dict to NormalizedReview."""
    review_date = None
    if raw.get("at"):
        if isinstance(raw["at"], datetime):
            review_date = raw["at"].date()
        elif isinstance(raw["at"], date):
            review_date = raw["at"]
    
    return NormalizedReview(
        platform_review_id=str(raw.get("reviewId", "")),
        platform="play_store",
        rating=int(raw.get("score", 1)),
        title="",  # Google Play reviews don't have separate titles
        body=raw.get("content", "") or "",
        review_date=review_date,
        language=raw.get("reviewCreatedVersion"),  # not reliable for language
        app_version=raw.get("reviewCreatedVersion"),
    )


def scrape_play_reviews(
    package_name: str,
    country: str = "in",
    max_reviews: int = 2000,
    page_size: int = 200,
    delay_between_pages: float = 1.5,
) -> list[NormalizedReview]:
    """Scrape reviews from Google Play Store with pagination."""
    max_reviews = min(max_reviews, 500)
    logger.info(
        "Scraping Play Store | package=%s | country=%s | max=%d",
        package_name, country, max_reviews,
    )
    
    all_reviews: list[NormalizedReview] = []
    continuation_token = None
    pages_fetched = 0
    
    try:
        while len(all_reviews) < max_reviews:
            batch_size = min(page_size, max_reviews - len(all_reviews))
            
            result, continuation_token = reviews(
                package_name,
                lang="en",
                country=country,
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
            
            if not result:
                logger.info("No more Play Store reviews available")
                break
            
            for raw in result:
                normalized = normalize_play_review(raw)
                all_reviews.append(normalized)
            
            pages_fetched += 1
            logger.info(
                "Play Store page %d fetched | batch=%d | total=%d",
                pages_fetched, len(result), len(all_reviews),
            )
            
            if continuation_token is None:
                break
            
            # Rate limit delay
            time.sleep(delay_between_pages)
        
    except Exception as e:
        logger.error("Play Store scrape failed | package=%s | error=%s", package_name, str(e), exc_info=True)
        raise
    
    logger.info("Play Store scrape complete | package=%s | total_reviews=%d", package_name, len(all_reviews))
    return all_reviews[:max_reviews]
