import logging
import time
from datetime import datetime, timezone
from app.config import get_settings
from app.database import get_supabase_client
from app.services.scrape_play import scrape_play_reviews
from app.services.scrape_ios import scrape_ios_reviews
from app.services.sentiment import analyze_sentiment_batch
from app.services.models import NormalizedReview
from app.services.embeddings import run_embeddings
from app.services.rollups import recompute_daily_rollups

logger = logging.getLogger(__name__)


def _set_scrape_status(app_id: str, status: str) -> None:
    """Update the scrape_status of a catalog app."""
    db = get_supabase_client()
    update_data = {"scrape_status": status}
    if status == "ready":
        update_data["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    db.table("catalog_apps").update(update_data).eq("id", app_id).execute()


def _upsert_reviews(app_id: str, reviews: list[NormalizedReview]) -> int:
    """Upsert normalized reviews into Supabase. Returns count of upserted rows."""
    if not reviews:
        return 0
    
    db = get_supabase_client()
    upserted = 0
    
    # Batch upsert in chunks of 100
    chunk_size = 100
    for i in range(0, len(reviews), chunk_size):
        chunk = reviews[i:i + chunk_size]
        rows = []
        for r in chunk:
            row = {
                "catalog_app_id": app_id,
                "platform": r.platform,
                "platform_review_id": r.platform_review_id,
                "rating": r.rating,
                "title": r.title,
                "body": r.body,
                "review_date": r.review_date.isoformat() if r.review_date else None,
                "language": r.language,
                "app_version": r.app_version,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
        
        db.table("reviews").upsert(
            rows,
            on_conflict="catalog_app_id,platform,platform_review_id",
        ).execute()
        upserted += len(chunk)
    
    logger.info("Upserted %d reviews for app %s", upserted, app_id)
    return upserted


def _prune_reviews(app_id: str, max_reviews: int) -> int:
    """Prune reviews to keep only the max_reviews most recent by review_date.
    Returns number of deleted rows."""
    db = get_supabase_client()
    
    # Get total count
    count_resp = db.table("reviews").select("id", count="exact").eq("catalog_app_id", app_id).execute()
    total = count_resp.count if count_resp.count else 0
    
    if total <= max_reviews:
        logger.info("Prune skipped | app=%s | total=%d <= max=%d", app_id, total, max_reviews)
        return 0
    
    # Get the cutoff date: the review_date of the Nth most recent review
    cutoff_resp = (
        db.table("reviews")
        .select("id, review_date")
        .eq("catalog_app_id", app_id)
        .order("review_date", desc=True)
        .range(max_reviews, max_reviews)  # 0-indexed, get the one at position max_reviews
        .execute()
    )
    
    if not cutoff_resp.data:
        return 0
    
    # Get IDs of reviews to keep (the most recent max_reviews)
    keep_resp = (
        db.table("reviews")
        .select("id")
        .eq("catalog_app_id", app_id)
        .order("review_date", desc=True)
        .limit(max_reviews)
        .execute()
    )
    
    keep_ids = {r["id"] for r in keep_resp.data}
    
    # Get all IDs for this app
    all_resp = (
        db.table("reviews")
        .select("id")
        .eq("catalog_app_id", app_id)
        .execute()
    )
    
    delete_ids = [r["id"] for r in all_resp.data if r["id"] not in keep_ids]
    
    if delete_ids:
        # Delete in batches
        for i in range(0, len(delete_ids), 100):
            batch = delete_ids[i:i + 100]
            db.table("reviews").delete().in_("id", batch).execute()
    
    deleted = len(delete_ids)
    logger.info("Pruned %d reviews for app %s (kept %d)", deleted, app_id, max_reviews)
    return deleted


def _run_sentiment(app_id: str) -> int:
    """Run Gemini sentiment analysis on reviews that need it. Returns count processed."""
    db = get_supabase_client()
    
    # Get reviews with text but no sentiment score yet
    resp = (
        db.table("reviews")
        .select("id, title, body, rating")
        .eq("catalog_app_id", app_id)
        .is_("sentiment_score", "null")
        .execute()
    )
    
    # Filter to reviews that actually have text
    reviews_to_analyze = []
    for r in resp.data:
        text = f"{r.get('title', '')}. {r.get('body', '')}".strip().strip(".")
        if text:
            reviews_to_analyze.append({
                "review_id": r["id"],
                "rating": r["rating"],
                "text": text,
            })
    
    if not reviews_to_analyze:
        logger.info("No reviews need sentiment analysis for app %s", app_id)
        return 0
    
    logger.info("Running sentiment for %d reviews | app=%s", len(reviews_to_analyze), app_id)
    
    results = analyze_sentiment_batch(reviews_to_analyze)
    
    # Update reviews with sentiment results in chunks of 100
    chunk_size = 100
    for i in range(0, len(results), chunk_size):
        chunk = results[i:i + chunk_size]
        rows = [
            {
                "id": result.review_id,
                "sentiment_score": result.sentiment_score,
                "sentiment_label": result.sentiment_label,
            }
            for result in chunk
        ]
        db.table("reviews").upsert(rows).execute()
    
    logger.info("Sentiment updated for %d reviews | app=%s", len(results), app_id)
    return len(results)


def _update_review_count(app_id: str) -> int:
    """Update the review_count on catalog_apps. Returns the count."""
    db = get_supabase_client()
    count_resp = db.table("reviews").select("id", count="exact").eq("catalog_app_id", app_id).execute()
    count = count_resp.count if count_resp.count else 0
    db.table("catalog_apps").update({"review_count": count}).eq("id", app_id).execute()
    return count


async def sync_app(app_id: str) -> None:
    """Full sync pipeline for one catalog app.
    
    Steps:
    1. Set scrape_status = 'running'
    2. Scrape Play Store (if play_package set)
    3. Scrape App Store (if ios_app_id set)
    4. Upsert reviews
    5. Prune to MAX_REVIEWS_PER_APP latest
    6. Run Gemini sentiment on text reviews
    7. Stub: embedding (Phase 2)
    8. Stub: rollup (Phase 3)
    9. Set scrape_status = 'ready', update counts
    """
    settings = get_settings()
    db = get_supabase_client()
    start_time = time.time()
    
    logger.info("=== Sync started | app_id=%s ===", app_id)
    
    try:
        # Step 1: Set status to running
        _set_scrape_status(app_id, "running")
        
        # Get app details
        app_resp = db.table("catalog_apps").select("*").eq("id", app_id).single().execute()
        app_data = app_resp.data
        
        if not app_data:
            logger.error("App not found | app_id=%s", app_id)
            _set_scrape_status(app_id, "failed")
            return
        
        all_reviews: list[NormalizedReview] = []
        
        # Step 2: Scrape Play Store
        if app_data.get("play_package"):
            try:
                play_reviews = scrape_play_reviews(
                    package_name=app_data["play_package"],
                    country=app_data.get("country", "in"),
                    max_reviews=settings.max_reviews_per_app,
                )
                all_reviews.extend(play_reviews)
                logger.info("Play Store reviews: %d | app_id=%s", len(play_reviews), app_id)
            except Exception as e:
                logger.error("Play Store scrape failed for app %s: %s", app_id, str(e), exc_info=True)
        
        # Step 3: Scrape App Store
        if app_data.get("ios_app_id"):
            try:
                ios_reviews = scrape_ios_reviews(
                    app_name=app_data.get("display_name", ""),
                    app_id=app_data["ios_app_id"],
                    country=app_data.get("country", "in"),
                    max_reviews=settings.max_reviews_per_app,
                )
                all_reviews.extend(ios_reviews)
                logger.info("App Store reviews: %d | app_id=%s", len(ios_reviews), app_id)
            except Exception as e:
                logger.error("App Store scrape failed for app %s: %s", app_id, str(e), exc_info=True)
        
        if not all_reviews:
            logger.warning("No reviews scraped for app %s", app_id)
        
        # Step 4: Upsert reviews
        upserted = _upsert_reviews(app_id, all_reviews)
        
        # Step 5: Prune to max
        pruned = _prune_reviews(app_id, settings.max_reviews_per_app)
        
        # Step 6: Sentiment analysis
        sentiment_count = _run_sentiment(app_id)
        
        # Step 7: Embedding
        run_embeddings(app_id)
        
        # Step 8: Rollup
        recompute_daily_rollups(app_id)
        
        # Step 9: Finalize
        review_count = _update_review_count(app_id)
        _set_scrape_status(app_id, "ready")
        
        duration = time.time() - start_time
        logger.info(
            "=== Sync complete | app_id=%s | duration=%.1fs | upserted=%d | pruned=%d | sentiment=%d | total=%d ===",
            app_id, duration, upserted, pruned, sentiment_count, review_count,
        )
        
    except Exception as e:
        _set_scrape_status(app_id, "failed")
        duration = time.time() - start_time
        logger.error(
            "=== Sync FAILED | app_id=%s | duration=%.1fs | error=%s ===",
            app_id, duration, str(e), exc_info=True,
        )
