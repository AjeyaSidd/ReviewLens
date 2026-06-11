import logging
import time
from google import genai
from app.config import get_settings
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def generate_embeddings_batch(
    texts: list[str],
    max_retries: int = 1,
) -> list[list[float]]:
    """Generate 1536-dimensional embeddings for a list of texts using Gemini API.
    
    Splits texts into batches of up to 1000 texts to prevent API overload.
    Enforces a strict Requests-Per-Minute (RPM) ceiling of 5 requests/min.
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
                # Call Gemini embedding API with 1536 output dimension to match Supabase schema
                response = client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=batch,
                    config=genai.types.EmbedContentConfig(output_dimensionality=1536),
                )
                
                # Check response has embeddings list
                if not response.embeddings:
                    raise ValueError("No embeddings returned in response")
                
                # Extract values (list of floats of size 1536) for each content
                batch_embeddings = [emb.values for emb in response.embeddings]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(
                    "Embedding batch %d/%d complete | items=%d",
                    batch_idx + 1, len(batches), len(batch)
                )
                
                # Enforce RPM ceiling: space every request by 12 seconds (protect limit across apps)
                logger.info("Enforcing RPM ceiling: sleeping 12s...")
                time.sleep(12.0)
                break  # Success, move to the next batch
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "500" in error_str or "503" in error_str:
                    retries += 1
                    if retries > max_retries:
                        logger.error("Embedding batch %d failed after single retry", batch_idx + 1)
                        raise
                    
                    # If rate limited (429), wait for a full minute. For server errors, wait 5s.
                    if "429" in error_str:
                        wait_time = 60.0
                        logger.warning("Embedding rate limit 429 hit. Sleeping 60s before retry...")
                    else:
                        wait_time = 5.0
                        logger.warning("Embedding server error %s. Sleeping 5s before retry...", error_str)
                    
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Embedding unexpected failure batch %d | error=%s",
                        batch_idx + 1, error_str, exc_info=True,
                    )
                    raise  # Propagate unexpected errors immediately

    return all_embeddings


def run_embeddings(app_id: str) -> int:
    """Generate and save Gemini vector embeddings for all reviews of an app that need it.
    
    Fetches reviews with text where embedding is still NULL, generates embeddings,
    and updates them individually in Supabase.
    """
    db = get_supabase_client()
    
    # Query reviews that have body text but no embedding vector yet
    resp = (
        db.table("reviews")
        .select("id, title, body, catalog_app_id, platform, platform_review_id, rating")
        .eq("catalog_app_id", app_id)
        .is_("embedding", "null")
        .execute()
    )
    
    # Filter and construct clean review texts, enforcing 8000-character safety truncation
    reviews_to_embed = []
    for r in resp.data:
        text = f"{r.get('title', '')}. {r.get('body', '')}".strip().strip(" .")
        if text:
            # Safe truncation: keep only the first 8000 chars to fit within the 2048-token limit
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

    # Extract clean texts list
    texts = [item["text"] for item in reviews_to_embed]
    
    # Generate embeddings
    embeddings = generate_embeddings_batch(texts)
    
    if len(embeddings) != len(reviews_to_embed):
        raise ValueError(
            f"Embedding length mismatch | expected={len(reviews_to_embed)} | received={len(embeddings)}"
        )
        
    # Update Supabase reviews with their corresponding float vector list in chunks of 100
    chunk_size = 100
    for i in range(0, len(reviews_to_embed), chunk_size):
        chunk = reviews_to_embed[i:i + chunk_size]
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
        db.table("reviews").upsert(rows).execute()
    updated_count = len(reviews_to_embed)
        
    logger.info("Successfully updated %d reviews with vectors | app=%s", updated_count, app_id)
    return updated_count
