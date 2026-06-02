import json
import logging
import time
from google import genai
from app.config import get_settings
from app.services.models import SentimentResult

logger = logging.getLogger(__name__)

SENTIMENT_SYSTEM_PROMPT = """You are a sentiment analysis engine. Analyze the TONE of the review text provided.
Do NOT simply copy or mirror the star rating — judge sentiment purely from the text content.
For each review, return a JSON object with:
- "review_id": the provided review ID
- "sentiment_score": a float from -1.0 (very negative) to 1.0 (very positive), with 0.0 being neutral
- "sentiment_label": one of "positive", "neutral", or "negative"

Return a JSON array of results. Output ONLY valid JSON, no markdown fences or extra text."""


def _build_batch_prompt(batch: list[dict]) -> str:
    """Build the user prompt for a batch of reviews."""
    reviews_text = json.dumps(batch, indent=2)
    return f"Analyze the sentiment of these reviews:\n\n{reviews_text}"


def _parse_sentiment_response(response_text: str) -> list[SentimentResult]:
    """Parse Gemini response into SentimentResult objects."""
    # Strip markdown fences if present
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    
    results = []
    parsed = json.loads(text)
    
    for item in parsed:
        score = float(item["sentiment_score"])
        score = max(-1.0, min(1.0, score))  # Clamp to valid range
        
        label = item.get("sentiment_label", "neutral")
        if label not in ("positive", "neutral", "negative"):
            # Derive label from score if invalid
            if score > 0.1:
                label = "positive"
            elif score < -0.1:
                label = "negative"
            else:
                label = "neutral"
        
        results.append(SentimentResult(
            review_id=str(item["review_id"]),
            sentiment_score=score,
            sentiment_label=label,
        ))
    
    return results


def analyze_sentiment_batch(
    reviews_for_sentiment: list[dict],
    max_retries: int = 3,
) -> list[SentimentResult]:
    """Analyze sentiment for a batch of reviews using Gemini.
    
    Each item in reviews_for_sentiment should have:
        - review_id: str
        - rating: int (context only)
        - text: str (title + body)
    
    Returns list of SentimentResult.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    batch_size = settings.gemini_sentiment_batch_size
    all_results: list[SentimentResult] = []
    
    # Split into batches
    batches = [
        reviews_for_sentiment[i:i + batch_size]
        for i in range(0, len(reviews_for_sentiment), batch_size)
    ]
    
    logger.info(
        "Sentiment analysis starting | total_reviews=%d | batches=%d | batch_size=%d",
        len(reviews_for_sentiment), len(batches), batch_size,
    )
    
    for batch_idx, batch in enumerate(batches):
        retries = 0
        while retries <= max_retries:
            try:
                prompt = _build_batch_prompt(batch)
                
                response = client.models.generate_content(
                    model=settings.gemini_sentiment_model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SENTIMENT_SYSTEM_PROMPT,
                        temperature=0.1,
                    ),
                )
                
                response_text = response.text
                batch_results = _parse_sentiment_response(response_text)
                all_results.extend(batch_results)
                
                logger.info(
                    "Sentiment batch %d/%d complete | results=%d",
                    batch_idx + 1, len(batches), len(batch_results),
                )
                break  # Success, move to next batch
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(
                    "Sentiment parse error batch %d | error=%s",
                    batch_idx + 1, str(e), exc_info=True,
                )
                retries += 1
                if retries > max_retries:
                    logger.error("Sentiment batch %d failed after %d retries, skipping", batch_idx + 1, max_retries)
                    break
                time.sleep(2 ** retries)  # Exponential backoff
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "500" in error_str or "503" in error_str:
                    retries += 1
                    wait_time = 2 ** retries
                    logger.warning(
                        "Sentiment rate limit/server error batch %d | retry %d/%d | waiting %ds | error=%s",
                        batch_idx + 1, retries, max_retries, wait_time, error_str,
                    )
                    if retries > max_retries:
                        logger.error("Sentiment batch %d failed after %d retries, skipping", batch_idx + 1, max_retries)
                        break
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Sentiment unexpected error batch %d | error=%s",
                        batch_idx + 1, error_str, exc_info=True,
                    )
                    break  # Don't retry unexpected errors
    
    logger.info("Sentiment analysis complete | total_results=%d", len(all_results))
    return all_results
