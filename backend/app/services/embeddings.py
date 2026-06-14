import logging
import asyncio
import time
from google import genai
from app.config import get_settings
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def generate_embeddings_batch(
    texts: list[str],
    max_retries: int = 2,
    enforce_rpm: bool = True,
) -> list[list[float]]:
    """Generate 1536-dimensional embeddings for a list of texts using Gemini API.

    Splits texts into batches of up to 1000 texts to prevent API overload.
    Enforces a strict Requests-Per-Minute (RPM) ceiling of 5 requests/min.
    This function is sync — callers should wrap with asyncio.to_thread.
    """
    if not texts:
        return []

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_embedding_api_key)

    batch_size = settings.gemini_embedding_batch_size
    batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
    all_embeddings: list[list[float]] = []

    logger.info(
        "Embedding starting | total_texts=%d | batches=%d | batch_size=%d",
        len(texts), len(batches), batch_size,
    )

    for batch_idx, batch in enumerate(batches):
        retries = 0
        while retries <= max_retries:
            try:
                response = client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=batch,
                    config=genai.types.EmbedContentConfig(output_dimensionality=1536),
                )

                if not response.embeddings:
                    raise ValueError("No embeddings returned in response")

                batch_embeddings = [emb.values for emb in response.embeddings]
                all_embeddings.extend(batch_embeddings)

                logger.info(
                    "Embedding batch %d/%d complete | items=%d",
                    batch_idx + 1, len(batches), len(batch)
                )

                if enforce_rpm and batch_idx < len(batches) - 1:
                    logger.info("Enforcing RPM ceiling: sleeping 12s...")
                    time.sleep(15.0)
                break

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "500" in error_str or "503" in error_str:
                    retries += 1
                    if retries > max_retries:
                        logger.error("Embedding batch %d failed after retry. Returning successful embeddings so far.", batch_idx + 1)
                        return all_embeddings

                    if "429" in error_str:
                        wait_time = 75.0
                        logger.warning("Embedding rate limit 429 hit. Sleeping 60s before retry...")
                    else:
                        wait_time = 5.0
                        logger.warning("Embedding server error %s. Sleeping 5s before retry...", error_str)

                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Embedding unexpected failure batch %d | error=%s. Returning successful embeddings so far.",
                        batch_idx + 1, error_str, exc_info=True,
                    )
                    return all_embeddings

    return all_embeddings


async def run_embeddings(app_id: str) -> int:
    """Generate and save Gemini vector embeddings for all reviews of an app that need it.

    Fetches reviews with text where embedding is still NULL, generates embeddings,
    and updates them individually in Supabase.
    """
    # ✅ Async Supabase client
    db = await get_supabase_client()

    # ✅ Async DB fetch
    resp = await (
        db.table("reviews")
        .select("id, title, body, catalog_app_id, platform, platform_review_id, rating")
        .eq("catalog_app_id", app_id)
        .is_("embedding", "null")
        .neq("body", "")
        .execute()
    )

    reviews_to_embed = []
    for r in resp.data:
        text = f"{r.get('title', '')}. {r.get('body', '')}".strip().strip(" .")
        if text:
            safe_text = text[:8000]
            reviews_to_embed.append({
                "id": r["id"],
                "text": safe_text,
                "catalog_app_id": r["catalog_app_id"],
                "platform": r["platform"],
                "platform_review_id": r["platform_review_id"],
                "rating": r["rating"],
            })

    if not reviews_to_embed:
        logger.info("No reviews need vector embedding for app %s", app_id)
        return 0

    logger.info("Running embeddings for %d reviews | app=%s", len(reviews_to_embed), app_id)

    texts = [item["text"] for item in reviews_to_embed]

    # ✅ generate_embeddings_batch is sync (Gemini SDK) — run in thread so event loop stays free
    embeddings = await asyncio.to_thread(generate_embeddings_batch, texts)

    if not embeddings:
        logger.warning("No embeddings successfully generated for app %s", app_id)
        return 0

    successful_reviews = reviews_to_embed[:len(embeddings)]

    # ✅ Async upsert in chunks of 100
    chunk_size = 100
    for i in range(0, len(successful_reviews), chunk_size):
        chunk = successful_reviews[i:i + chunk_size]
        rows = [
            {
                "id": item["id"],
                "catalog_app_id": item["catalog_app_id"],
                "platform": item["platform"],
                "platform_review_id": item["platform_review_id"],
                "rating": item["rating"],
                "embedding": embeddings[i + idx],
            }
            for idx, item in enumerate(chunk)
        ]
        await db.table("reviews").upsert(rows).execute()

    updated_count = len(successful_reviews)

    if updated_count < len(reviews_to_embed):
        logger.warning(
            "Partial embedding completion | requested=%d | successful=%d | app=%s",
            len(reviews_to_embed), updated_count, app_id
        )
    else:
        logger.info("Successfully updated all %d reviews with vectors | app=%s", updated_count, app_id)

    return updated_count