import json
import logging
from google import genai
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embeddings import generate_embeddings_batch

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are a query classifier for a product manager dashboard.
Classify the user's question into one of the following three categories:
- "METRIC_TRENDS": if the user is asking *only* about numerical trends, ratings averages, daily count totals, star splits, or aggregates over time (e.g., "What was my rating last week?", "How many reviews did we get on Monday?").
- "SEMANTIC_FEEDBACK": if the user is asking *only* about user experiences, specific bugs, logins, crashes, feature requests, dark mode, or written feedback comments (e.g., "Why are users complaining?", "What do they think of logins?").
- "HYBRID": if the user is asking *both* about numerical stats/averages and specific qualitative experiences/complaints (e.g., "What was our rating last week and what specific bugs did users complain about?", "Show me the average rating trend and the top features users want").

Respond with exactly one of these three strings: "METRIC_TRENDS", "SEMANTIC_FEEDBACK", or "HYBRID". Output ONLY that string, no extra text or markdown fences."""

RAG_SYSTEM_PROMPT_SEMANTIC = """You are an expert product support assistant. Use the provided user review text context to synthesize a concise, helpful answer to the user's question.
For every claim or point you make in your answer, you MUST link it to one or more of the provided reviews.
Return your response as a JSON object with:
- "answer": the natural-language answer text (concise and professional)
- "metrics": null or an empty object
- "citations": an array of objects representing the reviews you cited. Each citation MUST have:
  - "review_id": the exact UUID of the review
  - "platform": the platform of the review ("play_store" or "app_store")
  - "rating": the star rating (integer)
  - "review_date": the review date (string)
  - "snippet": a short text snippet from the review supporting the claim

Output ONLY valid JSON. Do not include any markdown backticks or markdown fences."""

RAG_SYSTEM_PROMPT_TRENDS = """You are an expert financial and metric analysis assistant. Use the provided daily rollup metric context to synthesize a mathematically accurate, professional answer to the user's trend-based question.
Do NOT hallucinate averages or ratings. Use only the figures provided.
Return your response as a JSON object with:
- "answer": a natural-language summary of the trends (e.g., average rating, total volume)
- "metrics": a dictionary summarizing the key aggregated calculations (e.g., {"avg_rating": 4.2, "total_reviews": 120})
- "citations": an empty array []

Output ONLY valid JSON. Do not include any markdown backticks or markdown fences."""

RAG_SYSTEM_PROMPT_HYBRID = """You are an expert product intelligence assistant. Use BOTH the daily rollup metrics AND the specific user review context to synthesize a mathematically accurate, comprehensive, and helpful answer to the user's multi-part question.
You MUST:
1. Link any claims about specific user experiences, bugs, or features to one or more of the provided reviews inside "citations".
2. Summarize key numerical or rating calculations using the provided daily rollup data inside "metrics". Do NOT hallucinate averages or ratings.
Return your response as a JSON object with:
- "answer": the natural-language answer text (concise, professional, and answering both parts of the question)
- "metrics": a dictionary summarizing the key aggregated calculations (e.g., {"avg_rating": 4.2, "total_reviews": 120})
- "citations": an array of objects representing the reviews you cited. Each citation MUST have:
  - "review_id": the exact UUID of the review
  - "platform": the platform of the review ("play_store" or "app_store")
  - "rating": the star rating (integer)
  - "review_date": the review date (string)
  - "snippet": a short text snippet from the review supporting the claim

Output ONLY valid JSON. Do not include any markdown backticks or markdown fences."""


def detect_query_intent(query: str) -> str:
    """Classify user query into METRIC_TRENDS, SEMANTIC_FEEDBACK, or HYBRID using Gemini."""
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    response = client.models.generate_content(
        model=settings.gemini_sentiment_model,
        contents=query,
        config=genai.types.GenerateContentConfig(
            system_instruction=INTENT_SYSTEM_PROMPT,
            temperature=0.1,
        ),
    )
    
    intent = response.text.strip().upper()
    if intent not in ("METRIC_TRENDS", "SEMANTIC_FEEDBACK", "HYBRID"):
        # Fallback to semantic if classification fails
        intent = "SEMANTIC_FEEDBACK"
        
    logger.info("Query intent classified | query='%s' | intent=%s", query, intent)
    return intent



def retrieve_semantic_context(app_id: str, query: str, limit: int = 5) -> list[dict]:
    """Retrieve top K reviews matching query semantic vector embedding."""
    try:
        # Generate embedding for user query
        query_vectors = generate_embeddings_batch([query])
        if not query_vectors:
            return []
        query_vector = query_vectors[0]
        
        db = get_supabase_client()
        
        # Invoke the match_reviews database RPC function
        resp = db.rpc("match_reviews", {
            "query_embedding": query_vector,
            "match_threshold": 0.0,
            "match_count": limit,
            "filter_app_id": app_id,
        }).execute()
        
        return resp.data or []
    except Exception as e:
        logger.error("Failed to retrieve semantic vector context | error=%s", str(e), exc_info=True)
        return []


def retrieve_trends_context(app_id: str, limit: int = 30) -> list[dict]:
    """Retrieve daily rollup historical logs for app_id (last 30 days)."""
    try:
        db = get_supabase_client()
        resp = (
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


def run_hybrid_rag(app_id: str, query: str) -> dict:
    """Coordinate intent classification, query retrieval, and answer synthesis."""
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    # 1. Detect Intent
    intent = detect_query_intent(query)
    
    # 2. Retrieve Context & Format Prompt
    if intent == "METRIC_TRENDS":
        context_data = retrieve_trends_context(app_id)
        context_str = json.dumps(context_data, indent=2)
        system_instruction = RAG_SYSTEM_PROMPT_TRENDS
        prompt = f"Question: {query}\n\nDaily Rollups Context:\n{context_str}"
    elif intent == "HYBRID":
        trends_data = retrieve_trends_context(app_id)
        reviews_data = retrieve_semantic_context(app_id, query)
        
        clean_reviews = [
            {
                "review_id": r.get("id"),
                "platform": r.get("platform"),
                "rating": r.get("rating"),
                "review_date": str(r.get("review_date")),
                "title": r.get("title", ""),
                "body": r.get("body", ""),
            }
            for r in reviews_data
        ]
        
        trends_str = json.dumps(trends_data, indent=2)
        reviews_str = json.dumps(clean_reviews, indent=2)
        
        system_instruction = RAG_SYSTEM_PROMPT_HYBRID
        prompt = f"Question: {query}\n\nDaily Rollups Context:\n{trends_str}\n\nReviews Context:\n{reviews_str}"
    else:
        context_data = retrieve_semantic_context(app_id, query)
        # Format reviews context for Gemini, stripping embeddings or internal dates
        clean_context = [
            {
                "review_id": r.get("id"),
                "platform": r.get("platform"),
                "rating": r.get("rating"),
                "review_date": str(r.get("review_date")),
                "title": r.get("title", ""),
                "body": r.get("body", ""),
            }
            for r in context_data
        ]
        context_str = json.dumps(clean_context, indent=2)
        system_instruction = RAG_SYSTEM_PROMPT_SEMANTIC
        prompt = f"Question: {query}\n\nReviews Context:\n{context_str}"

    # 3. Generate Answer
    logger.info("Executing Gemini RAG | intent=%s | prompt_length=%d", intent, len(prompt))
    
    response = client.models.generate_content(
        model=settings.gemini_sentiment_model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
        ),
    )
    
    # 4. Parse & Return
    return _parse_rag_response(response.text)
