import logging
import time
from datetime import date, datetime
from typing import Optional
from app_store_web_scraper import AppStoreEntry
from app.services.models import NormalizedReview

logger = logging.getLogger(__name__)

def normalize_ios_review(raw: any, country: Optional[str] = None) -> NormalizedReview:
    """Convert a raw AppStore review to NormalizedReview.
    Supports both app-store-web-scraper AppReview objects/dicts and legacy test dicts.
    """
    def get_val(obj, attr, fallback=None):
        if isinstance(obj, dict):
            return obj.get(attr, fallback)
        return getattr(obj, attr, fallback)

    # 1. Platform Review ID
    raw_id = get_val(raw, "id")
    if raw_id is None:
        raw_id = get_val(raw, "userName", "")
    platform_review_id = str(raw_id)

    # 2. Rating
    rating_val = get_val(raw, "rating", 1)
    try:
        rating = int(rating_val)
    except (ValueError, TypeError):
        rating = 1

    # 3. Title
    title = get_val(raw, "title", "") or ""

    # 4. Body / Review Text
    body = get_val(raw, "review")
    if body is None:
        body = get_val(raw, "content", "")
    body = body or ""

    # 5. Date
    date_val = get_val(raw, "date")
    review_date = None
    if date_val:
        if isinstance(date_val, datetime):
            review_date = date_val.date()
        elif isinstance(date_val, date):
            review_date = date_val
        elif isinstance(date_val, str):
            try:
                # In case it is ISO-8601 string
                review_date = datetime.fromisoformat(date_val).date()
            except ValueError:
                pass

    # 6. App version (retrieve if present in the raw input, otherwise None)
    app_version = get_val(raw, "version")

    # 7. Country / Language
    final_country = country or get_val(raw, "country")

    return NormalizedReview(
        platform_review_id=platform_review_id,
        platform="app_store",
        rating=rating,
        title=title,
        body=body,
        review_date=review_date,
        language=final_country,
        app_version=app_version,
    )


def scrape_ios_reviews(
    app_name: str,
    app_id: str,
    country: str = "in",
    max_reviews: int = 2000,
) -> list[NormalizedReview]:
    """Scrape reviews from Apple App Store using app-store-web-scraper."""
    target_limit = 500
    
    logger.info(
        "Scraping App Store | app_name=%s | app_id=%s | max_limit=%d",
        app_name, app_id, target_limit,
    )
    
    all_reviews: list[NormalizedReview] = []
    seen_ids = set()
    
    # 1. Fetch from country "in" first (up to target_limit=500)
    try:
        logger.info("Initializing AppStoreEntry for app_id=%s, country=in", app_id)
        app_in = AppStoreEntry(app_id=int(app_id), country="in")
        
        in_count = 0
        for review in app_in.reviews(limit=target_limit):
            platform_review_id = str(getattr(review, "id", None) or (review.get("id") if isinstance(review, dict) else ""))
            if not platform_review_id:
                continue
                
            if platform_review_id not in seen_ids:
                seen_ids.add(platform_review_id)
                normalized = normalize_ios_review(review, country="in")
                all_reviews.append(normalized)
                in_count += 1
                
        logger.info("Fetched %d unique reviews for country: in", in_count)
    except Exception as e:
        logger.error("App Store scrape failed for country in | error=%s", str(e), exc_info=True)
        
    # Sleep 1 second between countries
    time.sleep(1.0)
        
    # 2. Fetch from country "us" next, if we haven't reached target_limit=500
    remaining = target_limit - len(all_reviews)
    if remaining > 0:
        try:
            logger.info("Initializing AppStoreEntry for app_id=%s, country=us, requesting remaining=%d", app_id, remaining)
            app_us = AppStoreEntry(app_id=int(app_id), country="us")
            
            us_count = 0
            for review in app_us.reviews(limit=remaining):
                platform_review_id = str(getattr(review, "id", None) or (review.get("id") if isinstance(review, dict) else ""))
                if not platform_review_id:
                    continue
                    
                if platform_review_id not in seen_ids:
                    seen_ids.add(platform_review_id)
                    normalized = normalize_ios_review(review, country="us")
                    all_reviews.append(normalized)
                    us_count += 1
                    
            logger.info("Fetched %d unique reviews for country: us", us_count)
        except Exception as e:
            logger.error("App Store scrape failed for country us | error=%s", str(e), exc_info=True)
            
    logger.info(
        "App Store scrape complete | app_id=%s | total_reviews=%d",
        app_id, len(all_reviews),
    )
    return all_reviews[:target_limit]
