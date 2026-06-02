import logging
from collections import defaultdict
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def recompute_daily_rollups(app_id: str) -> int:
    """Calculate daily aggregates for reviews of an app and bulk upsert them into daily_rollups.
    
    Groups all existing reviews for app_id by date and aggregates:
    - total review count
    - mathematical average rating
    - mathematical average sentiment score (excluding rating-only NULL sentiment reviews)
    - star rating breakouts (star_1 through star_5)
    
    Returns the number of unique dates aggregated and upserted.
    """
    db = get_supabase_client()

    # Fetch all reviews associated with the app to perform an in-memory aggregation
    resp = (
        db.table("reviews")
        .select("review_date, rating, sentiment_score")
        .eq("catalog_app_id", app_id)
        .execute()
    )
    
    if not resp.data:
        logger.info("No reviews found for app %s, skipping rollups", app_id)
        return 0

    # Group metrics by date_str
    daily_groups = defaultdict(lambda: {
        "rating_sum": 0,
        "rating_count": 0,
        "sentiment_sum": 0.0,
        "sentiment_count": 0,
        "stars": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    })

    for review in resp.data:
        date_str = review.get("review_date")
        if not date_str:
            continue  # Skip reviews without a valid date
            
        rating = review.get("rating")
        sentiment_score = review.get("sentiment_score")

        group = daily_groups[date_str]
        
        # Rating counts and star breakdown
        if rating is not None and 1 <= int(rating) <= 5:
            r_int = int(rating)
            group["rating_sum"] += r_int
            group["rating_count"] += 1
            group["stars"][r_int] += 1
            
        # Sentiment aggregates (ignore reviews without sentiment text scores)
        if sentiment_score is not None:
            group["sentiment_sum"] += float(sentiment_score)
            group["sentiment_count"] += 1

    # Format the rows for database ingestion
    rollup_rows = []
    for date_str, group in daily_groups.items():
        count = group["rating_count"]
        if count == 0:
            continue
            
        avg_rating = group["rating_sum"] / count
        
        sent_count = group["sentiment_count"]
        avg_sentiment = (group["sentiment_sum"] / sent_count) if sent_count > 0 else None

        row = {
            "catalog_app_id": app_id,
            "date": date_str,
            "review_count": count,
            "avg_rating": round(avg_rating, 2),
            "avg_sentiment": round(avg_sentiment, 4) if avg_sentiment is not None else None,
            "star_1": group["stars"][1],
            "star_2": group["stars"][2],
            "star_3": group["stars"][3],
            "star_4": group["stars"][4],
            "star_5": group["stars"][5],
        }
        rollup_rows.append(row)

    if not rollup_rows:
        return 0

    # Bulk upsert rollups in chunks of 100
    chunk_size = 100
    for i in range(0, len(rollup_rows), chunk_size):
        chunk = rollup_rows[i:i + chunk_size]
        db.table("daily_rollups").upsert(
            chunk,
            on_conflict="catalog_app_id,date",
        ).execute()

    logger.info(
        "Recomputed daily rollups | app_id=%s | total_dates=%d",
        app_id, len(rollup_rows)
    )
    return len(rollup_rows)
