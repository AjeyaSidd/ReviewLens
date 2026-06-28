import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.config import get_settings
from app.database import get_db
from app.dependencies import verify_admin_key
from app.services.models import CatalogAppCreate, SyncAppsRequest
from app.services.sync_app import sync_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/apps", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin_key)])
async def add_app(body: CatalogAppCreate, db=Depends(get_db)):
    """Add a new app to the catalog. Rejects if >= 15 active apps."""
    settings = get_settings()

    # ✅ await added
    count_resp = await (
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

    insert_data = {
        "display_name": body.display_name,
        "country": body.country,
        "play_package": body.play_package,
        "ios_app_id": body.ios_app_id,
        "app_icon_url": body.app_icon_url,
        "is_active": True,
        "scrape_status": "pending",
    }

    # ✅ await added
    result = await db.table("catalog_apps").insert(insert_data).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create app")

    logger.info("App created | id=%s | name=%s", result.data[0]["id"], body.display_name)
    return result.data[0]


@router.delete("/apps/{app_id}", dependencies=[Depends(verify_admin_key)])
async def delete_app(app_id: str, purge: bool = False, db=Depends(get_db)):
    """Delete an app. If purge=true, cascade delete reviews and rollups."""

    # ✅ await added
    app_resp = await db.table("catalog_apps").select("id").eq("id", app_id).execute()
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")

    if purge:
        # ✅ await added
        await db.table("catalog_apps").delete().eq("id", app_id).execute()
        logger.info("App purged | id=%s", app_id)
        return {"detail": f"App {app_id} and all related data purged"}
    else:
        # ✅ await added
        await db.table("catalog_apps").update({"is_active": False}).eq("id", app_id).execute()
        logger.info("App deactivated | id=%s", app_id)
        return {"detail": f"App {app_id} deactivated"}


@router.get("/apps", dependencies=[Depends(verify_admin_key)])
async def list_all_apps(db=Depends(get_db)):
    """List all apps (active and inactive) with scrape status."""

    # ✅ await added
    result = await db.table("catalog_apps").select("*").order("created_at", desc=True).execute()
    return result.data or []


@router.post("/apps/{app_id}/refresh", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_admin_key)])
async def refresh_app(app_id: str, db=Depends(get_db)):
    """Trigger background sync for one app. Returns 202 immediately."""

    # ✅ await added
    app_resp = await (
        db.table("catalog_apps")
        .select("id, is_active")
        .eq("id", app_id)
        .single()
        .execute()
    )
    if not app_resp.data:
        raise HTTPException(status_code=404, detail="App not found")
    if not app_resp.data.get("is_active"):
        raise HTTPException(status_code=400, detail="App is not active")

    asyncio.create_task(sync_app(app_id))
    logger.info("Refresh triggered | app_id=%s", app_id)
    return {"detail": f"Sync started for app {app_id}", "app_id": app_id}


@router.post("/sync-all", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_admin_key)])
async def sync_all_apps(limit: int = 1, db=Depends(get_db)):
    """Trigger background sync for active apps, starting with the oldest synced.

    Accepts a limit parameter (defaulting to 1) to prevent rate limits.
    """
    from datetime import datetime, timezone

    # Fetch all active apps with their last_synced_at timestamps
    result = await db.table("catalog_apps").select("id, last_synced_at").eq("is_active", True).execute()
    apps = result.data or []

    if not apps:
        return {"detail": "No active apps to sync", "count": 0, "synced_app_ids": [], "skipped_app_ids": []}

    # Sort in Python: Never synced (None) first, then oldest synced
    def get_sync_time(app):
        val = app.get("last_synced_at")
        if not val:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(val)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    apps.sort(key=get_sync_time)

    # Slice to limit
    selected_apps = apps[:limit]
    selected_app_ids = [app["id"] for app in selected_apps]
    skipped_app_ids = [app["id"] for app in apps[limit:]]

    async def _sync_selected():
        for aid in selected_app_ids:
            try:
                await sync_app(aid)
            except Exception as e:
                logger.error("Sync failed for app %s during sync-all: %s", aid, str(e))

    asyncio.create_task(_sync_selected())
    logger.info(
        "Sync-all triggered | limit=%d | syncing=%d | skipped=%d",
        limit, len(selected_app_ids), len(skipped_app_ids)
    )
    return {
        "detail": f"Sync started for {len(selected_app_ids)} apps ({len(skipped_app_ids)} skipped)",
        "count": len(selected_app_ids),
        "synced_app_ids": selected_app_ids,
        "skipped_app_ids": [app["id"] for app in apps[limit:]],
    }


@router.post("/sync-apps", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_admin_key)])
async def sync_selected_apps(body: SyncAppsRequest, db=Depends(get_db)):
    """Trigger background sync for specific apps by DB UUID, play package, or App Store ID."""
    app_identifiers = body.app_identifiers
    if not app_identifiers:
        raise HTTPException(status_code=400, detail="app_identifiers list cannot be empty")

    # ✅ await added
    result = await (
        db.table("catalog_apps")
        .select("id, play_package, ios_app_id")
        .eq("is_active", True)
        .execute()
    )
    active_apps = result.data or []

    matched_app_ids = []
    for identifier in app_identifiers:
        for app in active_apps:
            if app.get("id") == identifier:
                matched_app_ids.append(app["id"])
                break
            if app.get("play_package") == identifier:
                matched_app_ids.append(app["id"])
                break
            if app.get("ios_app_id") == identifier:
                matched_app_ids.append(app["id"])
                break

    matched_app_ids = list(set(matched_app_ids))

    if not matched_app_ids:
        raise HTTPException(status_code=400, detail="No active apps found matching the provided identifiers")

    async def _sync_selected():
        for aid in matched_app_ids:
            try:
                await sync_app(aid)
            except Exception as e:
                logger.error("Sync failed for app %s during sync-apps: %s", aid, str(e))

    asyncio.create_task(_sync_selected())
    logger.info("Sync-apps triggered | requested=%d | matched=%d", len(app_identifiers), len(matched_app_ids))
    return {"detail": f"Sync started for {len(matched_app_ids)} apps", "count": len(matched_app_ids)}