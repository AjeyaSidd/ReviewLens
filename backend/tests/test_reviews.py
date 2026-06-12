import pytest
from unittest.mock import MagicMock, patch
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


class TestReviewsEndpoint:
    """Test GET /apps/{app_id}/reviews endpoint."""
    
    def test_reviews_app_not_found(self, client, mock_db):
        """Should return 404 if app doesn't exist."""
        app_resp = MagicMock()
        app_resp.data = {}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        response = client.get("/apps/non-existent-uuid/reviews")
        assert response.status_code == 404
        
    def test_reviews_app_inactive(self, client, mock_db):
        """Should return 404 if app is deactivated."""
        app_resp = MagicMock()
        app_resp.data = {"id": "test-uuid", "is_active": False}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        response = client.get("/apps/test-uuid/reviews")
        assert response.status_code == 404

    def test_reviews_success_filtering_and_sorting(self, client, mock_db):
        """Verify reviews are correctly requested with range limit parameters and sorted by date."""
        # Mock active app validation
        app_resp = MagicMock()
        app_resp.data = {"id": "test-uuid", "is_active": True}
        
        # Mock reviews return
        reviews_resp = MagicMock()
        reviews_resp.data = [
            {"id": "uuid-1", "platform": "play_store", "rating": 5, "title": "Good", "body": "Great app", "sentiment": "POSITIVE", "review_date": "2026-05-20"},
            {"id": "uuid-2", "platform": "app_store", "rating": 2, "title": "Bad", "body": "Crashes on login", "sentiment": "NEGATIVE", "review_date": "2026-05-19"},
        ]
        
        # Setup mocks chain
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        query_mock = mock_db.table.return_value.select.return_value.eq.return_value
        query_mock.order.return_value.range.return_value.execute.return_value = reviews_resp
        
        response = client.get("/apps/test-uuid/reviews?limit=10&offset=0")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["title"] == "Good"
        assert response.json()[1]["title"] == "Bad"
        
        # Verify query parameters were correctly applied
        query_mock.order.assert_called_with("review_date", desc=True)
        query_mock.order.return_value.range.assert_called_with(0, 9)  # 0 to (0 + 10 - 1)


class TestCatalogEndpoint:
    """Test GET /catalog endpoint."""
    
    def test_catalog_hides_zero_review_apps(self, client, mock_db):
        """Should filter catalog to only return apps with review_count > 0."""
        mock_resp = MagicMock()
        mock_resp.data = [
            {"id": "app-1", "display_name": "App 1", "review_count": 5},
            {"id": "app-3", "display_name": "App 3", "review_count": 10},
        ]
        
        table_mock = mock_db.table.return_value
        select_mock = table_mock.select.return_value
        eq_mock = select_mock.eq.return_value
        gt_mock = eq_mock.gt.return_value
        order_mock = gt_mock.order.return_value
        order_mock.execute.return_value = mock_resp
        
        response = client.get("/catalog")
        
        assert response.status_code == 200
        eq_mock.gt.assert_called_once_with("review_count", 0)
        assert len(response.json()) == 2

