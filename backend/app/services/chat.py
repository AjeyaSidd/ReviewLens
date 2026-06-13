import json
import logging
import asyncio
import re
import dateparser
from datetime import date
from google import genai
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embeddings import generate_embeddings_batch

logger = logging.getLogger(__name__)


RAG_SYSTEM_PROMPT_HYBRID = """You are a mobile app review analyst. Synthesize the provided daily rollup metrics and user reviews into a clear, insightful answer.

THINKING: Before writing, identify the question type — diagnostic (what's broken?), quantitative (ratings/trends?), exploratory (what are users saying?), or simple (direct question?). Let the question type determine the structure naturally. Do not force a fixed template.

ANSWER FORMAT:
- Always markdown. Structure must fit the question — don't apply the same layout to every answer.
- Diagnostic → grouped bullet list by theme
- Quantitative → short narrative with inline numbers
- Exploratory → themed sections with a TL;DR opener
- Simple → 2-3 sentences + supporting bullets, no headers
- Bold key terms, versions, feature names. No walls of text.

METRICS: Populate only if the question asks for numbers/trends. Use only rollup data — never hallucinate. Return {} for qualitative questions.

CITATIONS: Every claim about a user experience, bug, or feature needs at least one citation. Prefer specific, recent reviews mentioning versions or devices.

OUTPUT — valid JSON only, no fences:
{
  "answer": "markdown answer",
  "metrics": {},
  "citations": [{"review_id": "uuid", "platform": "play_store or app_store", "rating": 0, "review_date": "YYYY-MM-DD", "snippet": "quote"}]
}

If data is insufficient, explain what's missing in "answer" and return empty citations and metrics."""


# ✅ Singleton Gemini client — created once, reused across all requests
_gemini_client: genai.Client | None = None

def get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        settings = get_settings()
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _parse_version(ver_str: str) -> str | None:
    """
    Keep version as a string to avoid float precision issues.
    e.g. "1.10" stays "1.10" not 1.1
    Validates it looks like a real version number (digits.digits).
    """
    ver_str = ver_str.strip()
    if re.match(r'^\d+\.\d+$', ver_str):
        return ver_str
    return None


def _extract_date(text: str) -> str | None:
    """
    Try to parse a natural language date string using dateparser.
    Returns ISO date string or None if parsing fails.
    Only accepts dates in the past (no future dates).
    """
    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DAY_OF_MONTH": "first",
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DATES_FROM": "past",
            "RELATIVE_BASE": __import__("datetime").datetime.now(),
        }
    )
    if parsed and parsed.date() <= date.today():
        return parsed.date().isoformat()
    return None


def extract_metadata_filters(query: str) -> dict:
    """
    Extract filters (date range, version, rating) from natural language query.
    Uses dateparser for flexible date extraction, regex for ratings and versions.
    """
    filters = {}
    query_lower = query.lower()

    # ── 1. DATE EXTRACTION (dateparser handles most natural language) ────

    # Patterns that indicate a "from" date — capture the date expression after the keyword
    from_date_patterns = [
        # "last/past N days/weeks/months"
        r'(?:last|past)\s+\d+\s+(?:days?|weeks?|months?)',
        # "last/past week/month"
        r'(?:last|past)\s+(?:week|month)',
        # "since/after/from <date expression>"
        r'(?:since|after)\s+[\w\s,]+?(?=\s+(?:to|until|before)|$)',
        # ISO date
        r'(?:since|after|from)\s+\d{4}-\d{2}-\d{2}',
        # Named month + year: "in January 2025", "since March 2024"
        r'(?:in|since|after|from)\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}',
        # "N days/weeks/months ago"
        r'\d+\s+(?:days?|weeks?|months?)\s+ago',
    ]

    for pattern in from_date_patterns:
        match = re.search(pattern, query_lower)
        if match:
            parsed_date = _extract_date(match.group(0))
            if parsed_date:
                filters["filter_from_date"] = parsed_date
                break  # stop at first successful match

    # Patterns that indicate a "to/until" date
    to_date_patterns = [
        r'(?:before|until)\s+\d{4}-\d{2}-\d{2}',
        r'(?:before|until)\s+[\w\s,]+?(?=\s+(?:from|since|after)|$)',
    ]

    for pattern in to_date_patterns:
        match = re.search(pattern, query_lower)
        if match:
            parsed_date = _extract_date(match.group(0))
            if parsed_date:
                filters["filter_to_date"] = parsed_date
                break

    # ── 2. VERSION EXTRACTION (regex — kept as strings not floats) ───────

    # "above/since/after/from version X.X" or "above/since v X.X"
    ver_min_match = re.search(
        r'(?:since|after|above|from|starting)\s+(?:app\s+)?(?:version\s+|v\s*)?(\d+\.\d+)',
        query_lower
    )
    # "X.X and above/later/newer"
    ver_min_suffix = re.search(
        r'(\d+\.\d+)\s+(?:and\s+)?(?:above|later|newer|onwards?)',
        query_lower
    )

    if ver_min_match:
        ver = _parse_version(ver_min_match.group(1))
        if ver:
            filters["filter_min_version"] = ver
    elif ver_min_suffix:
        ver = _parse_version(ver_min_suffix.group(1))
        if ver:
            filters["filter_min_version"] = ver

    # "before/below/under version X.X"
    ver_max_match = re.search(
        r'(?:before|below|under|up\s+to)\s+(?:app\s+)?(?:version\s+|v\s*)?(\d+\.\d+)',
        query_lower
    )
    # "X.X and below/earlier/older"
    ver_max_suffix = re.search(
        r'(\d+\.\d+)\s+(?:and\s+)?(?:below|earlier|older)',
        query_lower
    )

    if ver_max_match:
        ver = _parse_version(ver_max_match.group(1))
        if ver:
            filters["filter_max_version"] = ver
    elif ver_max_suffix:
        ver = _parse_version(ver_max_suffix.group(1))
        if ver:
            filters["filter_max_version"] = ver

    # Exact version — only if no min/max already set
    # Handles: "version 20.96", "v20.96", "app version 20.96", "for v20.96"
    if "filter_min_version" not in filters and "filter_max_version" not in filters:
        ver_exact_match = re.search(
            r'(?:(?:app\s+)?version\s+|v\s*)(\d+\.\d+)',
            query_lower
        )
        if ver_exact_match:
            ver = _parse_version(ver_exact_match.group(1))
            if ver:
                filters["filter_min_version"] = ver
                filters["filter_max_version"] = ver

    # ── 3. RATING EXTRACTION (regex) ─────────────────────────────────────

    # "below/less than/under 3 stars" → max rating is N-1
    below_stars = re.search(
        r'(?:below|less than|under|lower than)\s+(\d)\s*(?:stars?|\*)',
        query_lower
    )
    if below_stars:
        filters["filter_max_rating"] = int(below_stars.group(1)) - 1

    # "above/more than/at least 3 stars" → min rating is N
    above_stars = re.search(
        r'(?:above|greater than|more than|at least|over)\s+(\d)\s*(?:stars?|\*)',
        query_lower
    )
    if above_stars:
        filters["filter_min_rating"] = int(above_stars.group(1))

    # Exact rating — only if no min/max already set
    # Handles: "2-star", "2 stars", "2*", "2 star rating", "2* rating"
    if "filter_min_rating" not in filters and "filter_max_rating" not in filters:
        exact_star = re.search(
            r'(\d)\s*-\s*stars?'           # 2-star, 2 - stars
            r'|\b(\d)\s*stars?\b'          # 2 stars, 2star
            r'|(\d)\s*\*'                  # 2*, 2 *
            r'|\b(\d)\s*star\s*rating\b',  # 2 star rating
            query_lower
        )
        if exact_star:
            # Only one group will match — use whichever is not None
            val = exact_star.group(1) or exact_star.group(2) or exact_star.group(3) or exact_star.group(4)
            if val:
                rating_val = int(val)
                # Sanity check — ratings are 1-5 only
                if 1 <= rating_val <= 5:
                    filters["filter_min_rating"] = rating_val
                    filters["filter_max_rating"] = rating_val

    return filters


async def retrieve_semantic_context(
    app_id: str,
    query: str,
    limit: int = 20,
    filter_from_date: str | None = None,
    filter_to_date: str | None = None,
    filter_min_version: str | None = None,
    filter_max_version: str | None = None,
    filter_min_rating: int | None = None,
    filter_max_rating: int | None = None,
) -> list[dict]:
    """Retrieve top K reviews via semantic vector search with metadata filters."""
    try:
        # Embedding generation is still sync (Google SDK) — kept on thread
        query_vectors = await asyncio.to_thread(
            generate_embeddings_batch,
            [query],
            enforce_rpm=False,
        )
        if not query_vectors:
            return []
        query_vector = query_vectors[0]

        # ✅ Async Supabase client
        db = await get_supabase_client()

        rpc_params = {
            "query_embedding": query_vector,
            "match_threshold": 0.3,
            "match_count": limit,
            "filter_app_id": app_id,
        }

        if filter_from_date is not None:
            rpc_params["filter_from_date"] = filter_from_date
        if filter_to_date is not None:
            rpc_params["filter_to_date"] = filter_to_date
        if filter_min_version is not None:
            rpc_params["filter_min_version"] = filter_min_version
        if filter_max_version is not None:
            rpc_params["filter_max_version"] = filter_max_version
        if filter_min_rating is not None:
            rpc_params["filter_min_rating"] = filter_min_rating
        if filter_max_rating is not None:
            rpc_params["filter_max_rating"] = filter_max_rating

        resp = await db.rpc("match_reviews", rpc_params).execute()
        return resp.data or []

    except Exception as e:
        logger.error("Failed to retrieve semantic vector context | error=%s", str(e), exc_info=True)
        return []


async def retrieve_trends_context(app_id: str, limit: int = 30) -> list[dict]:
    """Retrieve daily rollup historical logs for app_id (last 30 days)."""
    try:
        db = await get_supabase_client()

        resp = await (
            db.table("daily_rollups")
            .select("*")
            .eq("catalog_app_id", app_id)
            .order("date", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    except Exception as e:
        logger.error("Failed to retrieve trends SQL context | error=%s", str(e), exc_info=True)
        return []


def _parse_rag_response(response_text: str) -> dict:
    """Safely strip markdown blocks and parse JSON answer payload."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("RAG response failed to parse as JSON | raw=%s", response_text)
        return {
            "answer": "I'm sorry, I was unable to format the response correctly. Here was the raw output: " + response_text,
            "metrics": {},
            "citations": []
        }


async def run_hybrid_rag(app_id: str, query: str) -> dict:
    """Coordinate async parallel context retrieval and Gemini answer synthesis."""
    try:
        settings = get_settings()
        client = get_gemini_client()

        # 1. Extract metadata filters
        filters = extract_metadata_filters(query)
        logger.info("Extracted metadata filters | query='%s' | filters=%s", query, filters)

        # 2. Retrieve contexts concurrently
        trends_data, reviews_data = await asyncio.gather(
            retrieve_trends_context(app_id),
            retrieve_semantic_context(
                app_id=app_id,
                query=query,
                limit=20,
                **filters,
            ),
        )

        # 3. Format context string
        clean_reviews = [
            {
                "review_id": r.get("id"),
                "platform": r.get("platform"),
                "rating": r.get("rating"),
                "review_date": str(r.get("review_date")),
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "app_version": r.get("app_version"),
            }
            for r in reviews_data
        ]

        trends_str = json.dumps(trends_data, indent=2)
        reviews_str = json.dumps(clean_reviews, indent=2)

        prompt = (
            f"Question: {query}\n\n"
            f"Daily Rollups Context:\n{trends_str}\n\n"
            f"Reviews Context:\n{reviews_str}"
        )

        # 4. Gemini is still sync SDK — kept on thread, reuses singleton client
        logger.info("Executing Gemini RAG | prompt_length=%d", len(prompt))

        def _generate():
            return client.models.generate_content(
                model=settings.gemini_sentiment_model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=RAG_SYSTEM_PROMPT_HYBRID,
                    temperature=0.2,
                ),
            )

        response = await asyncio.to_thread(_generate)

        # 5. Parse & return
        return _parse_rag_response(response.text)

    except Exception as e:
        error_msg = str(e)
        logger.error("RAG execution failed | error=%s", error_msg, exc_info=True)

        if "503" in error_msg or "temporary" in error_msg or "high demand" in error_msg or "UNAVAILABLE" in error_msg:
            return {
                "answer": "ReviewLens is currently experiencing high demand from the AI service. This is usually temporary—please wait a moment and try sending your question again.",
                "metrics": {},
                "citations": []
            }
        elif "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
            return {
                "answer": "We have temporarily hit a rate limit with the AI service. Please wait a short moment and try again.",
                "metrics": {},
                "citations": []
            }
        else:
            return {
                "answer": f"I encountered a server issue while processing your request: {error_msg}. Please try again.",
                "metrics": {},
                "citations": []
            }