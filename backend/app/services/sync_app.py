import logging
import asyncio
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


async def _set_scrape_status(app_id: str, status: str) -> None:
    """Update the scrape_status of a catalog app."""
    db = await get_supabase_client()
    update_data = {"scrape_status": status}
    if status == "ready":
        update_data["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    await db.table("catalog_apps").update(update_data).eq("id", app_id).execute()


async def _upsert_reviews(app_id: str, reviews: list[NormalizedReview]) -> int:
    """Upsert normalized reviews into Supabase. Returns count of upserted rows."""
    if not reviews:
        return 0

    db = await get_supabase_client()
    upserted = 0

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

        # ✅ Async upsert — yields control between chunks so chat stays responsive
        await db.table("reviews").upsert(
            rows,
            on_conflict="catalog_app_id,platform,platform_review_id",
        ).execute()
        upserted += len(chunk)

    logger.info("Upserted %d reviews for app %s", upserted, app_id)
    return upserted


async def _prune_reviews(
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
    db = await get_supabase_client()

    # ✅ Async fetch
    resp = await (
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
        keep_ids.update(r["id"] for r in play_reviews[:half_limit])
        keep_ids.update(r["id"] for r in ios_reviews[:half_limit])
    elif play_provided and not ios_provided:
        play_keep = play_reviews[:max_reviews]
        ios_keep = ios_reviews[:(max_reviews - len(play_keep))]
        keep_ids.update(r["id"] for r in play_keep)
        keep_ids.update(r["id"] for r in ios_keep)
    elif ios_provided and not play_provided:
        ios_keep = ios_reviews[:max_reviews]
        play_keep = play_reviews[:(max_reviews - len(ios_keep))]
        keep_ids.update(r["id"] for r in ios_keep)
        keep_ids.update(r["id"] for r in play_keep)
    else:
        if play_reviews and ios_reviews:
            keep_ids.update(r["id"] for r in play_reviews[:half_limit])
            keep_ids.update(r["id"] for r in ios_reviews[:half_limit])
        else:
            merged = play_reviews + ios_reviews
            merged.sort(key=get_date_key, reverse=True)
            keep_ids.update(r["id"] for r in merged[:max_reviews])

    delete_ids = [r["id"] for r in all_reviews if r["id"] not in keep_ids]

    if delete_ids:
        for i in range(0, len(delete_ids), 100):
            batch = delete_ids[i:i + 100]
            # ✅ Async delete — yields control between batches
            await db.table("reviews").delete().in_("id", batch).execute()

    deleted = len(delete_ids)
    logger.info("Pruned %d reviews for app %s (kept %d)", deleted, app_id, len(keep_ids))
    return deleted


async def _run_sentiment(app_id: str) -> int:
    """Run Gemini sentiment analysis on reviews that need it. Returns count processed."""
    db = await get_supabase_client()

    # ✅ Async fetch
    resp = await (
        db.table("reviews")
        .select("id, title, body, rating, catalog_app_id, platform, platform_review_id")
        .eq("catalog_app_id", app_id)
        .is_("sentiment_score", "null")
        .execute()
    )

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

    # ✅ analyze_sentiment_batch is sync (Gemini SDK) — run in thread
    results = await asyncio.to_thread(analyze_sentiment_batch, reviews_to_analyze)

    # ✅ Async upsert in chunks of 100
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
        await db.table("reviews").upsert(rows).execute()

    logger.info("Sentiment updated for %d reviews | app=%s", len(results), app_id)
    return len(results)


async def _update_review_count(app_id: str) -> int:
    """Update the review_count on catalog_apps. Returns the count."""
    db = await get_supabase_client()

    # ✅ Async fetch + update
    count_resp = await (
        db.table("reviews")
        .select("id", count="exact")
        .eq("catalog_app_id", app_id)
        .execute()
    )
    count = count_resp.count if count_resp.count else 0
    await db.table("catalog_apps").update({"review_count": count}).eq("id", app_id).execute()
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
    7. Run embeddings
    8. Recompute daily rollups
    9. Set scrape_status = 'ready', update counts
    """
    settings = get_settings()
    start_time = time.time()

    logger.info("=== Sync started | app_id=%s ===", app_id)

    try:
        # Step 1: Set status to running
        await _set_scrape_status(app_id, "running")

        # Get app details — ✅ async
        db = await get_supabase_client()
        app_resp = await (
            db.table("catalog_apps")
            .select("*")
            .eq("id", app_id)
            .single()
            .execute()
        )
        app_data = app_resp.data

        if not app_data:
            logger.error("App not found | app_id=%s", app_id)
            await _set_scrape_status(app_id, "failed")
            return

        all_reviews: list[NormalizedReview] = []

        has_play = bool(app_data.get("play_package"))
        has_ios = bool(app_data.get("ios_app_id"))

        play_limit = settings.max_reviews_per_app // 2 if has_play else 0
        ios_limit = settings.max_reviews_per_app // 2 if has_ios else 0

        # Step 2: Scrape Play Store
        # ✅ scrape_play_reviews is sync (third-party) — run in thread
        play_reviews = []
        if has_play:
            try:
                play_reviews = await asyncio.to_thread(
                    scrape_play_reviews,
                    package_name=app_data["play_package"],
                    country=app_data.get("country", "in"),
                    max_reviews=play_limit,
                )
                all_reviews.extend(play_reviews)
                logger.info("Play Store reviews: %d | app_id=%s", len(play_reviews), app_id)
            except Exception as e:
                logger.error("Play Store scrape failed for app %s: %s", app_id, str(e), exc_info=True)

        # Step 3: Scrape App Store
        # ✅ scrape_ios_reviews is sync (third-party) — run in thread
        ios_reviews = []
        if has_ios:
            try:
                ios_reviews = await asyncio.to_thread(
                    scrape_ios_reviews,
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
        upserted = await _upsert_reviews(app_id, all_reviews)

        # Step 5: Prune to max
        pruned = await _prune_reviews(
            app_id,
            max_reviews=settings.max_reviews_per_app,
            play_provided=play_provided,
            ios_provided=ios_provided,
        )

        # Step 6: Sentiment analysis
        sentiment_count = await _run_sentiment(app_id)

        # Step 7: Embeddings
        await run_embeddings(app_id)

        # Step 8: Rollups
        await recompute_daily_rollups(app_id)

        # Step 9: Finalize
        review_count = await _update_review_count(app_id)
        await _set_scrape_status(app_id, "ready")

        duration = time.time() - start_time
        logger.info(
            "=== Sync complete | app_id=%s | duration=%.1fs | upserted=%d | pruned=%d | sentiment=%d | total=%d ===",
            app_id, duration, upserted, pruned, sentiment_count, review_count,
        )

    except Exception as e:
        await _set_scrape_status(app_id, "failed")
        duration = time.time() - start_time
        logger.error(
            "=== Sync FAILED | app_id=%s | duration=%.1fs | error=%s ===",
            app_id, duration, str(e), exc_info=True,
        )