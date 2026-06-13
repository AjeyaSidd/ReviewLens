import json
import logging
import asyncio
import re
from datetime import date, timedelta
from google import genai
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embeddings import generate_embeddings_batch

logger = logging.getLogger(__name__)


RAG_SYSTEM_PROMPT_HYBRID = """You are an expert product intelligence analyst specializing in mobile app review analysis, with deep expertise in UX research, sentiment analysis, and product feedback synthesis.

You will be given:
- A user's question about an app
- Daily rollup metrics (aggregated rating/review counts per day)
- A set of semantically relevant user reviews

---

## THINKING APPROACH

Before writing your answer, internally ask yourself:
- What is the user actually trying to understand or decide?
- Is this a diagnostic question (what's broken?), an exploratory question (what are users saying?), a quantitative question (how are ratings trending?), or a comparative question (how did version X perform vs Y)?
- What structure would make this answer easiest to read — a short punchy list? A narrative with data? A theme-by-theme breakdown? A direct yes/no with evidence?

Let the question shape the structure. Do not force a template onto every answer.

---

## ANSWER QUALITY RULES

1. **Be specific, not generic.** Don't say "users are unhappy" — say "reviews from the last 30 days frequently mention login failures, mostly on Android."
2. **Identify patterns.** Group similar complaints or praises into themes. Surface the top 2-3 signals.
3. **Lead with the most important insight.** Don't bury the key finding at the end.
4. **Use evidence.** Every claim about user experience MUST be backed by a citation.
5. **Acknowledge data limits.** If the reviews don't have enough signal to answer confidently, say so clearly instead of guessing.

---

## FORMATTING RULES

- Always use markdown
- **Match structure to the question:**
  - Diagnostic/bug questions → bullet list of issues grouped by theme
  - Trend/quantitative questions → short narrative with inline numbers, optionally a metrics summary at the end
  - Exploratory/open-ended questions → themed sections with a brief TL;DR opener
  - Simple/direct questions → 2-3 sentences + supporting bullets, no unnecessary headers
- Use **bold** for key terms, version numbers, feature names, and critical metrics
- Keep bullets to 1-2 sentences max
- Only use `##` headers if the answer genuinely has multiple distinct sections worth separating
- Never write a wall of text — break up anything longer than 3 lines

---

## METRICS RULES

- Only populate "metrics" if the question asks for numbers, ratings, counts, or trends
- For qualitative questions, return "metrics": {}
- Only use numbers present in the daily rollup data — never calculate or hallucinate
- Useful keys: "avg_rating", "total_reviews", "reviews_this_week", "rating_trend", "positive_pct", "negative_pct"

---

## CITATION RULES

- Every factual claim about a user experience, bug, or feature MUST have at least one citation
- Prefer reviews that mention a specific version, device, or exact error over vague ones
- Prefer more recent reviews when multiple say the same thing
- Do NOT cite a review unless its snippet directly supports the claim

---

## OUTPUT FORMAT

Return ONLY valid JSON — no markdown fences, no backticks, no preamble:

{
  "answer": "markdown answer shaped naturally by the question",
  "metrics": {},
  "citations": [
    {
      "review_id": "exact UUID",
      "platform": "play_store or app_store",
      "rating": <integer>,
      "review_date": "YYYY-MM-DD",
      "snippet": "short direct quote supporting the claim"
    }
  ]
}

If the data is insufficient to answer, return valid JSON with "answer" explaining what's missing and "citations": [], "metrics": {}."""


def extract_metadata_filters(query: str) -> dict:
    """Extract filters (date range, version, rating) from natural language query using regex."""
    filters = {}
    query_lower = query.lower()
    today = date.today()
    
    # 1. Date Range extraction
    # last \d+ days
    days_match = re.search(r'last\s+(\d+)\s+days?', query_lower)
    if days_match:
        num_days = int(days_match.group(1))
        from_date = today - timedelta(days=num_days)
        filters["filter_from_date"] = from_date.isoformat()
    elif "last week" in query_lower:
        from_date = today - timedelta(days=7)
        filters["filter_from_date"] = from_date.isoformat()
    elif "last month" in query_lower:
        from_date = today - timedelta(days=30)
        filters["filter_from_date"] = from_date.isoformat()
        
    # ISO date match: since 2024-01-01 / after 2024-01-01
    iso_from_match = re.search(r'(?:since|after|from)\s+(\d{4}-\d{2}-\d{2})', query_lower)
    if iso_from_match:
        filters["filter_from_date"] = iso_from_match.group(1)
        
    # before 2024-01-01 / until 2024-01-01 / to 2024-01-01
    iso_to_match = re.search(r'(?:before|until|to)\s+(\d{4}-\d{2}-\d{2})', query_lower)
    if iso_to_match:
        filters["filter_to_date"] = iso_to_match.group(1)
        
    # Named months: after Jan 1 2024 / since February 15, 2024
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }
    month_pattern = r'(since|after|from)\s+([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(\d{4})'
    month_match = re.search(month_pattern, query_lower)
    if month_match:
        m_name = month_match.group(2)
        day = int(month_match.group(3))
        year = int(month_match.group(4))
        if m_name in months:
            month_num = months[m_name]
            try:
                filters["filter_from_date"] = date(year, month_num, day).isoformat()
            except ValueError:
                pass
                
    # 2. Version extraction (major.minor format, e.g. 20.96)
    # since version 20.96 / after v20.96
    ver_min_match = re.search(r'(?:since|after|above|from)\s+(?:version\s+|v)?(\d+\.\d+)', query_lower)
    if ver_min_match:
        try:
            filters["filter_min_version"] = float(ver_min_match.group(1))
        except ValueError:
            pass
        
    # before version 20.96 / below v20.96
    ver_max_match = re.search(r'(?:before|below|under|to)\s+(?:version\s+|v)?(\d+\.\d+)', query_lower)
    if ver_max_match:
        try:
            filters["filter_max_version"] = float(ver_max_match.group(1))
        except ValueError:
            pass
        
    # version 20.99 (exact matching)
    ver_exact_match = re.search(r'(?:version\s+|v)(\d+\.\d+)', query_lower)
    if ver_exact_match and "filter_min_version" not in filters and "filter_max_version" not in filters:
        try:
            ver = float(ver_exact_match.group(1))
            filters["filter_min_version"] = ver
            filters["filter_max_version"] = ver
        except ValueError:
            pass
        
    # 3. Rating extraction
    # below 3 stars
    below_stars_match = re.search(r'(?:below|less than|under|lower than)\s+(\d)\s*star', query_lower)
    if below_stars_match:
        rating_val = int(below_stars_match.group(1))
        filters["filter_max_rating"] = rating_val - 1
        
    # above 3 stars
    above_stars_match = re.search(r'(?:above|greater than|more than|at least|since)\s+(\d)\s*star', query_lower)
    if above_stars_match:
        rating_val = int(above_stars_match.group(1))
        filters["filter_min_rating"] = rating_val
        
    # exact rating match: 1-star reviews / 5 star
    star_match = re.search(r'(\d)\s*-\s*stars?|\b(\d)\s*stars?\b', query_lower)
    if star_match and "filter_min_rating" not in filters and "filter_max_rating" not in filters:
        rating_val = int(star_match.group(1) or star_match.group(2))
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
    """Retrieve top K reviews matching query semantic vector embedding, applying metadata filters.
    Offloads synchronous Supabase and Gemini calls using asyncio.to_thread."""
    try:
        # Generate embedding for user query on a background thread
        query_vectors = await asyncio.to_thread(
            generate_embeddings_batch,
            [query],
            enforce_rpm=False,
        )
        if not query_vectors:
            return []
        query_vector = query_vectors[0]
        
        db = get_supabase_client()
        
        # Build RPC params
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

        # Execute Supabase RPC call on background thread
        resp = await asyncio.to_thread(
            db.rpc("match_reviews", rpc_params).execute
        )
        
        return resp.data or []
    except Exception as e:
        logger.error("Failed to retrieve semantic vector context | error=%s", str(e), exc_info=True)
        return []


async def retrieve_trends_context(app_id: str, limit: int = 30) -> list[dict]:
    """Retrieve daily rollup historical logs for app_id (last 30 days) on a background thread."""
    try:
        db = get_supabase_client()
        
        def _execute_query():
            return (
                db.table("daily_rollups")
                .select("*")
                .eq("catalog_app_id", app_id)
                .order("date", desc=True)
                .limit(limit)
                .execute()
            )
            
        resp = await asyncio.to_thread(_execute_query)
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
        client = genai.Client(api_key=settings.gemini_api_key)
        
        # 1. Extract metadata filters from natural language query
        filters = extract_metadata_filters(query)
        logger.info("Extracted metadata filters | query='%s' | filters=%s", query, filters)
        
        # 2. Retrieve contexts concurrently using asyncio.gather
        trends_task = retrieve_trends_context(app_id)
        semantic_task = retrieve_semantic_context(
            app_id=app_id,
            query=query,
            limit=20,
            **filters
        )
        
        trends_data, reviews_data = await asyncio.gather(trends_task, semantic_task)
        
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
        
        # 4. Generate Answer using Gemini API via asyncio.to_thread
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
        
        # 5. Parse & Return
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
