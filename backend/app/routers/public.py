import logging
import asyncio
from datetime import date
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.services.chat import run_hybrid_rag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])

@router.get("/health")
async def health():
    return {"status": "healthy"}
    
    
@router.get("/catalog")
async def list_catalog(db=Depends(get_db)):
    """List active apps for public consumption."""
    result = (
        db.table("catalog_apps")
        .select("id, display_name, country, play_package, ios_app_id, review_count, last_synced_at, app_icon_url, scrape_status")
        .eq("is_active", True)
        .gt("review_count", 0)
        .order("display_name")
        .execute()
    )
    apps = result.data or []
    if not apps:
        return []

    # Get app_id + platform from reviews table where body is not empty
    reviews_resp = db.table("reviews").select("catalog_app_id, platform").neq("body", "").execute()
    reviews_data = reviews_resp.data or []
    
    app_platforms = {}
    for r in reviews_data:
        aid = r["catalog_app_id"]
        platform = r["platform"]
        if aid not in app_platforms:
            app_platforms[aid] = set()
        app_platforms[aid].add(platform)
        
    for app in apps:
        platforms = app_platforms.get(app["id"], set())
        app["has_play_store"] = "play_store" in platforms
        app["has_app_store"] = "app_store" in platforms
        
    return apps


@router.get("/apps/{app_id}")
async def get_app(app_id: str, db=Depends(get_db)):
    """Get a single app's metadata (only if active)."""
    result = (
        db.table("catalog_apps")
        .select("*")
        .eq("id", app_id)
        .eq("is_active", True)
        .execute()
    )
    
    if not result.data:
        raise HTTPException(status_code=404, detail="App not found or not ready")
        
    app = result.data[0]
    
    # Check platforms having reviews with body not empty
    reviews_resp = db.table("reviews").select("platform").eq("catalog_app_id", app_id).neq("body", "").execute()
    platforms = {r["platform"] for r in (reviews_resp.data or [])}
    
    app["has_play_store"] = "play_store" in platforms
    app["has_app_store"] = "app_store" in platforms
    
    return app


@router.get("/apps/{app_id}/trends")
async def get_app_trends(
    app_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db=Depends(get_db),
):
    """Retrieve pre-aggregated daily rollups for an app, optionally filtered by date range."""
    # First verify that the app exists and is active
    app_resp = db.table("catalog_apps").select("id, is_active").eq("id", app_id).single().execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=404, detail="App is not active")

    # Fetch rollups
    query = db.table("daily_rollups").select("*").eq("catalog_app_id", app_id)
    
    if from_date:
        query = query.gte("date", from_date.isoformat())
    if to_date:
        query = query.lte("date", to_date.isoformat())
        
    result = query.order("date").execute()
    return result.data or []


class ChatMessageRequest(BaseModel):
    message: str


@router.post("/apps/{app_id}/chat")
async def chat_with_reviews(
    app_id: str,
    body: ChatMessageRequest,
    db=Depends(get_db),
):
    """Ask a natural-language question about review trends or user experiences."""
    # First verify that the app exists and is active
    app_resp = await asyncio.to_thread(
        db.table("catalog_apps").select("id, is_active").eq("id", app_id).single().execute
    )
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=404, detail="App is not active")

    try:
        response = await run_hybrid_rag(app_id, body.message)
        return response
    except Exception as e:
        logger.error("Chat RAG pipeline failed | app_id=%s | error=%s", app_id, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process chat query")


@router.get("/apps/{app_id}/reviews")
async def get_recent_reviews(
    app_id: str,
    limit: int = 50,
    offset: int = 0,
    db=Depends(get_db),
):
    """Retrieve recent reviews for an app sorted by date descending."""
    # First verify that the app exists and is active
    app_resp = db.table("catalog_apps").select("id, is_active").eq("id", app_id).single().execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=404, detail="App is inactive")

    try:
        result = (
            db.table("reviews")
            .select("id, platform, rating, title, body, sentiment_label, sentiment_score, review_date")
            .eq("catalog_app_id", app_id)
            .neq("body", "")
            .order("review_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        # Map sentiment_label/sentiment key to uppercase sentiment format expected by the frontend
        reviews = []
        for r in (result.data or []):
            label = r.get("sentiment_label") or r.get("sentiment")
            sentiment_upper = label.upper() if label else None
            reviews.append({
                "id": r["id"],
                "platform": r["platform"],
                "rating": r["rating"],
                "title": r["title"],
                "body": r["body"],
                "sentiment": sentiment_upper,
                "review_date": r["review_date"],
            })
        return reviews
    except Exception as e:
        logger.error("Failed to retrieve recent reviews | app_id=%s | error=%s", app_id, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent reviews")
