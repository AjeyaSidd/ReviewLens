import logging
from datetime import date
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.services.chat import run_hybrid_rag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])


@router.get("/catalog")
async def list_catalog(db=Depends(get_db)):
    """List active, ready apps for public consumption."""
    result = (
        db.table("catalog_apps")
        .select("id, display_name, country, play_package, ios_app_id, review_count, last_synced_at")
        .eq("is_active", True)
        .eq("scrape_status", "ready")
        .order("display_name")
        .execute()
    )
    return result.data or []


@router.get("/apps/{app_id}")
async def get_app(app_id: str, db=Depends(get_db)):
    """Get a single app's metadata (only if active and ready)."""
    result = (
        db.table("catalog_apps")
        .select("*")
        .eq("id", app_id)
        .eq("is_active", True)
        .eq("scrape_status", "ready")
        .execute()
    )
    
    if not result.data:
        raise HTTPException(status_code=404, detail="App not found or not ready")
    
    return result.data[0]


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
    app_resp = db.table("catalog_apps").select("id, is_active").eq("id", app_id).single().execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=404, detail="App is not active")

    try:
        response = run_hybrid_rag(app_id, body.message)
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
        # Fetch reviews
        result = (
            db.table("reviews")
            .select("id, platform, rating, title, body, sentiment, review_date")
            .eq("catalog_app_id", app_id)
            .order("review_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("Failed to retrieve recent reviews | app_id=%s | error=%s", app_id, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent reviews")
