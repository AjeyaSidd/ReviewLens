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


def _prune_reviews(
    app_id: str,
    max_reviews: int,
    play_provided: bool = False,
    ios_provided: bool = False,
) -> int:
    """Prune reviews for app_id in the database to maintain a total cap of max_reviews.
    
    Rules:
    1. If BOTH stores provided reviews in the current sync:
       - Keep the newest max_reviews // 2 reviews from play_store.
       - Keep the newest max_reviews // 2 reviews from app_store.
    2. If ONLY play_store provided reviews (or only play_store exists):
       - Keep the newest max_reviews reviews for this app (favoring play_store).
    3. If ONLY app_store provided reviews (or only app_store exists):
       - Keep the newest max_reviews reviews for this app (favoring app_store).
    4. If NEITHER store provided reviews (e.g. no new reviews or network errors):
       - Fallback: if reviews exist for both platforms in DB, keep up to max_reviews // 2 from each.
       - Otherwise, keep up to max_reviews newest reviews overall.
    """
    db = get_supabase_client()
    
    # Fetch all reviews for this app
    resp = (
        db.table("reviews")
        .select("id, platform, review_date")
        .eq("catalog_app_id", app_id)
        .execute()
    )
    all_reviews = resp.data or []
    
    play_reviews = [r for r in all_reviews if r["platform"] == "play_store"]
    ios_reviews = [r for r in all_reviews if r["platform"] == "app_store"]
    
    def get_date_key(r):
        return r.get("review_date") or ""
        
    play_reviews.sort(key=get_date_key, reverse=True)
    ios_reviews.sort(key=get_date_key, reverse=True)
    
    half_limit = max_reviews // 2
    keep_ids = set()
    
    if play_provided and ios_provided:
        # Keep top half_limit from each
        keep_ids.update(r["id"] for r in play_reviews[:half_limit])
        keep_ids.update(r["id"] for r in ios_reviews[:half_limit])
    elif play_provided and not ios_provided:
        # Only play store provided reviews. Keep up to max_reviews play store reviews.
        # Fill remaining slots with newest app store reviews.
        play_keep = play_reviews[:max_reviews]
        ios_keep = ios_reviews[:(max_reviews - len(play_keep))]
        keep_ids.update(r["id"] for r in play_keep)
        keep_ids.update(r["id"] for r in ios_keep)
    elif ios_provided and not play_provided:
        # Only app store provided reviews. Keep up to max_reviews app store reviews.
        # Fill remaining slots with newest play store reviews.
        ios_keep = ios_reviews[:max_reviews]
        play_keep = play_reviews[:(max_reviews - len(ios_keep))]
        keep_ids.update(r["id"] for r in ios_keep)
        keep_ids.update(r["id"] for r in play_keep)
    else:
        # Neither store provided reviews in this sync.
        # Check if both have reviews in the database.
        if play_reviews and ios_reviews:
            # Maintain balance: keep top half_limit from each
            keep_ids.update(r["id"] for r in play_reviews[:half_limit])
            keep_ids.update(r["id"] for r in ios_reviews[:half_limit])
        else:
            # Only one has reviews, or both empty. Keep top max_reviews overall.
            merged = play_reviews + ios_reviews
            merged.sort(key=get_date_key, reverse=True)
            keep_ids.update(r["id"] for r in merged[:max_reviews])
            
    delete_ids = [r["id"] for r in all_reviews if r["id"] not in keep_ids]
    
    if delete_ids:
        for i in range(0, len(delete_ids), 100):
            batch = delete_ids[i:i + 100]
            db.table("reviews").delete().in_("id", batch).execute()
            
    deleted = len(delete_ids)
    logger.info("Pruned %d reviews for app %s (kept %d)", deleted, app_id, len(keep_ids))
    return deleted


def _run_sentiment(app_id: str) -> int:
    """Run Gemini sentiment analysis on reviews that need it. Returns count processed."""
    db = get_supabase_client()
    
    # Get reviews with text but no sentiment score yet
    resp = (
        db.table("reviews")
        .select("id, title, body, rating, catalog_app_id, platform, platform_review_id")
        .eq("catalog_app_id", app_id)
        .is_("sentiment_score", "null")
        .execute()
    )
    
    # Process all reviews (even without text body) as we now calculate rating-based sentiment
    reviews_to_analyze = []
    review_lookup = {}
    for r in resp.data:
        text = f"{r.get('title', '')}. {r.get('body', '')}".strip().strip(".")
        reviews_to_analyze.append({
            "review_id": r["id"],
            "rating": r["rating"],
            "text": text,
        })
        review_lookup[r["id"]] = r
    
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
                "catalog_app_id": review_lookup[result.review_id]["catalog_app_id"],
                "platform": review_lookup[result.review_id]["platform"],
                "platform_review_id": review_lookup[result.review_id]["platform_review_id"],
                "rating": review_lookup[result.review_id]["rating"],
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
        
        # Determine scraper limits dynamically
        has_play = bool(app_data.get("play_package"))
        has_ios = bool(app_data.get("ios_app_id"))
        
        # On each sync run, try to get max_reviews_per_app // 2 reviews from each store
        play_limit = settings.max_reviews_per_app // 2 if has_play else 0
        ios_limit = settings.max_reviews_per_app // 2 if has_ios else 0
        
        # Step 2: Scrape Play Store
        play_reviews = []
        if has_play:
            try:
                play_reviews = scrape_play_reviews(
                    package_name=app_data["play_package"],
                    country=app_data.get("country", "in"),
                    max_reviews=play_limit,
                )
                all_reviews.extend(play_reviews)
                logger.info("Play Store reviews: %d | app_id=%s", len(play_reviews), app_id)
            except Exception as e:
                logger.error("Play Store scrape failed for app %s: %s", app_id, str(e), exc_info=True)
        
        # Step 3: Scrape App Store
        ios_reviews = []
        if has_ios:
            try:
                ios_reviews = scrape_ios_reviews(
                    app_name=app_data.get("display_name", ""),
                    app_id=app_data["ios_app_id"],
                    country=app_data.get("country", "in"),
                    max_reviews=ios_limit,
                )
                all_reviews.extend(ios_reviews)
                logger.info("App Store reviews: %d | app_id=%s", len(ios_reviews), app_id)
            except Exception as e:
                logger.error("App Store scrape failed for app %s: %s", app_id, str(e), exc_info=True)
        
        if not all_reviews:
            logger.warning("No reviews scraped for app %s", app_id)
        
        play_provided = len(play_reviews) > 0
        ios_provided = len(ios_reviews) > 0
        
        # Step 4: Upsert reviews
        upserted = _upsert_reviews(app_id, all_reviews)
        
        # Step 5: Prune to max
        pruned = _prune_reviews(
            app_id,
            max_reviews=settings.max_reviews_per_app,
            play_provided=play_provided,
            ios_provided=ios_provided,
        )
        
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
