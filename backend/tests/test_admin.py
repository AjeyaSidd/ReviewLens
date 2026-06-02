import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

@pytest.fixture
def client(mock_settings, mock_db):
    """Create a test client with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.config.get_settings", return_value=mock_settings), \
         patch("app.database.get_supabase_client", return_value=mock_db), \
         patch("app.logging_config.setup_logging"):
        yield TestClient(app)
    app.dependency_overrides.clear()


class TestAdminAuth:
    """Test admin authentication."""
    
    def test_missing_admin_key_returns_422(self, client):
        """Request without X-Admin-Key header should return 422."""
        response = client.get("/admin/apps")
        assert response.status_code == 422
        
    def test_wrong_admin_key_returns_401(self, client):
        """Request with wrong X-Admin-Key should return 401."""
        response = client.get("/admin/apps", headers={"X-Admin-Key": "wrong-key"})
        assert response.status_code == 401


class TestAddApp:
    """Test POST /admin/apps."""
    
    def test_add_app_success(self, client, mock_db):
        """Adding an app with valid data should return 201."""
        # Mock active count = 5 (below limit)
        count_mock = MagicMock()
        count_mock.count = 5
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = count_mock
        
        # Mock insert returns created app
        insert_mock = MagicMock()
        insert_mock.data = [{"id": "test-uuid", "display_name": "Test App", "country": "in"}]
        mock_db.table.return_value.insert.return_value.execute.return_value = insert_mock
        
        response = client.post(
            "/admin/apps",
            json={"display_name": "Test App", "play_package": "com.test.app"},
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 201
        assert response.json()["display_name"] == "Test App"
        
    def test_add_app_no_store_id_returns_422(self, client):
        """Adding an app without play_package or ios_app_id should return 422."""
        response = client.post(
            "/admin/apps",
            json={"display_name": "Test App"},
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 422
        
    def test_add_app_at_limit_returns_409(self, client, mock_db):
        """Adding an app when 15 active apps exist should return 409."""
        count_mock = MagicMock()
        count_mock.count = 15
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = count_mock
        
        response = client.post(
            "/admin/apps",
            json={"display_name": "Test App", "play_package": "com.test.app"},
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 409
        assert "Maximum of" in response.json()["detail"]


class TestDeleteApp:
    """Test DELETE /admin/apps/{app_id}."""
    
    def test_delete_app_not_found(self, client, mock_db):
        """Deleting a non-existent app should return 404."""
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        
        response = client.delete(
            "/admin/apps/non-existent-uuid",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 404
        
    def test_delete_app_soft_delete(self, client, mock_db):
        """Soft deleting should set is_active to False."""
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "test-uuid"}]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        
        response = client.delete(
            "/admin/apps/test-uuid",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 200
        mock_db.table.return_value.update.assert_called_with({"is_active": False})
        
    def test_delete_app_purge(self, client, mock_db):
        """Hard deleting with purge=True should execute a delete query."""
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "test-uuid"}]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        
        response = client.delete(
            "/admin/apps/test-uuid?purge=true",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 200
        mock_db.table.return_value.delete.assert_called_once()


class TestListApps:
    """Test GET /admin/apps."""
    
    def test_list_all_apps_success(self, client, mock_db):
        """Should return list of apps."""
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "app-1", "display_name": "App 1"}]
        mock_db.table.return_value.select.return_value.order.return_value.execute.return_value = mock_resp
        
        response = client.get(
            "/admin/apps",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["display_name"] == "App 1"


class TestRefreshApp:
    """Test POST /admin/apps/{app_id}/refresh."""
    
    @patch("app.routers.admin.sync_app", new_callable=AsyncMock)
    def test_refresh_app_success(self, mock_sync_app, client, mock_db):
        """Refreshing active app should launch background task and return 202."""
        mock_resp = MagicMock()
        mock_resp.data = {"id": "test-uuid", "is_active": True}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_resp
        
        response = client.post(
            "/admin/apps/test-uuid/refresh",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 202
        assert "Sync started" in response.json()["detail"]
        
    def test_refresh_inactive_app_returns_400(self, client, mock_db):
        """Refreshing inactive app should return 400."""
        mock_resp = MagicMock()
        mock_resp.data = {"id": "test-uuid", "is_active": False}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_resp
        
        response = client.post(
            "/admin/apps/test-uuid/refresh",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 400
        assert "is not active" in response.json()["detail"]


class TestSyncAll:
    """Test POST /admin/sync-all."""
    
    @patch("app.routers.admin.sync_app", new_callable=AsyncMock)
    def test_sync_all_success(self, mock_sync_app, client, mock_db):
        """Should fetch all active apps and run sync for them."""
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "app-1"}, {"id": "app-2"}]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        
        response = client.post(
            "/admin/sync-all",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert response.status_code == 202
        assert response.json()["count"] == 2
