import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.config import get_settings
from app.database import get_db
from app.dependencies import verify_admin_key
from app.services.models import CatalogAppCreate
from app.services.sync_app import sync_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/apps", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin_key)])
async def add_app(body: CatalogAppCreate, db=Depends(get_db)):
    """Add a new app to the catalog. Rejects if >= 15 active apps."""
    settings = get_settings()
    
    # Check active app count
    count_resp = (
        db.table("catalog_apps")
        .select("id", count="exact")
        .eq("is_active", True)
        .execute()
    )
    active_count = count_resp.count if count_resp.count is not None else 0
    
    if active_count >= settings.max_active_apps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum of {settings.max_active_apps} active apps reached. Delete an app before adding a new one.",
        )
    
    # Insert new app
    insert_data = {
        "display_name": body.display_name,
        "country": body.country,
        "play_package": body.play_package,
        "ios_app_id": body.ios_app_id,
        "app_icon_url": body.app_icon_url,
        "is_active": True,
        "scrape_status": "pending",
    }
    
    result = db.table("catalog_apps").insert(insert_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create app")
    
    logger.info("App created | id=%s | name=%s", result.data[0]["id"], body.display_name)
    return result.data[0]


@router.delete("/apps/{app_id}", dependencies=[Depends(verify_admin_key)])
async def delete_app(app_id: str, purge: bool = False, db=Depends(get_db)):
    """Delete an app. If purge=true, cascade delete reviews and rollups."""
    # Check app exists
    app_resp = db.table("catalog_apps").select("id").eq("id", app_id).execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    
    if purge:
        # Cascade delete is handled by DB foreign keys, just delete the app
        db.table("catalog_apps").delete().eq("id", app_id).execute()
        logger.info("App purged | id=%s", app_id)
        return {"detail": f"App {app_id} and all related data purged"}
    else:
        # Soft delete: set is_active to false
        db.table("catalog_apps").update({"is_active": False}).eq("id", app_id).execute()
        logger.info("App deactivated | id=%s", app_id)
        return {"detail": f"App {app_id} deactivated"}


@router.get("/apps", dependencies=[Depends(verify_admin_key)])
async def list_all_apps(db=Depends(get_db)):
    """List all apps (active and inactive) with scrape status."""
    result = db.table("catalog_apps").select("*").order("created_at", desc=True).execute()
    return result.data or []


@router.post("/apps/{app_id}/refresh", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_admin_key)])
async def refresh_app(app_id: str, db=Depends(get_db)):
    """Trigger background sync for one app. Returns 202 immediately."""
    # Verify app exists and is active
    app_resp = db.table("catalog_apps").select("id, is_active").eq("id", app_id).single().execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=400, detail="App is not active")
    
    # Launch sync in background
    asyncio.create_task(sync_app(app_id))
    logger.info("Refresh triggered | app_id=%s", app_id)
    return {"detail": f"Sync started for app {app_id}", "app_id": app_id}


@router.post("/sync-all", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_admin_key)])
async def sync_all_apps(db=Depends(get_db)):
    """Trigger background sync for all active apps. Returns 202 immediately."""
    result = db.table("catalog_apps").select("id").eq("is_active", True).execute()
    app_ids = [app["id"] for app in (result.data or [])]
    
    if not app_ids:
        return {"detail": "No active apps to sync", "count": 0}
    
    # Launch sync for each app sequentially in a single background task
    async def _sync_all():
        for aid in app_ids:
            try:
                await sync_app(aid)
            except Exception as e:
                logger.error("Sync failed for app %s during sync-all: %s", aid, str(e))
    
    asyncio.create_task(_sync_all())
    logger.info("Sync-all triggered | apps=%d", len(app_ids))
    return {"detail": f"Sync started for {len(app_ids)} apps", "count": len(app_ids)}
