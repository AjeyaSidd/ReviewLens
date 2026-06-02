import logging
import time
from datetime import date, datetime
from app_store_scraper import AppStore
from app.services.models import NormalizedReview

logger = logging.getLogger(__name__)

def normalize_ios_review(raw: dict) -> NormalizedReview:
    """Convert a raw app-store-scraper review dict to NormalizedReview."""
    review_date = None
    date_val = raw.get("date")
    if date_val:
        if isinstance(date_val, datetime):
            review_date = date_val.date()
        elif isinstance(date_val, date):
            review_date = date_val
    
    return NormalizedReview(
        platform_review_id=str(raw.get("id", raw.get("userName", ""))),
        platform="app_store",
        rating=int(raw.get("rating", 1)),
        title=raw.get("title", "") or "",
        body=raw.get("review", "") or "",
        review_date=review_date,
        language=None,
        app_version=raw.get("version"),
    )


def scrape_ios_reviews(
    app_name: str,
    app_id: str,
    country: str = "in",
    max_reviews: int = 2000,
) -> list[NormalizedReview]:
    """Scrape reviews from Apple App Store."""
    logger.info(
        "Scraping App Store | app_name=%s | app_id=%s | country=%s | max=%d",
        app_name, app_id, country, max_reviews,
    )
    
    all_reviews: list[NormalizedReview] = []
    
    try:
        app = AppStore(country=country, app_name=app_name, app_id=app_id)
        app.review(how_many=max_reviews)
        
        for raw in app.reviews:
            normalized = normalize_ios_review(raw)
            all_reviews.append(normalized)
        
    except Exception as e:
        logger.error(
            "App Store scrape failed | app_id=%s | error=%s",
            app_id, str(e), exc_info=True,
        )
        raise
    
    logger.info(
        "App Store scrape complete | app_id=%s | total_reviews=%d",
        app_id, len(all_reviews),
    )
    return all_reviews[:max_reviews]
