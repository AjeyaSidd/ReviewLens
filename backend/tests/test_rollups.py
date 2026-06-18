import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.services.rollups import recompute_daily_rollups


@pytest.fixture
def client(mock_settings, mock_db):
    """Create a test client with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with patch("app.config.get_settings", return_value=mock_settings), \
         patch("app.database.get_supabase_client", return_value=mock_db), \
         patch("app.logging_config.setup_logging"):
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_recompute_rollups_mathematical_accuracy(mock_db):
    """Verify daily rollups correctly average ratings/sentiments and sum stars by date."""
    mock_resp = MagicMock()
    mock_resp.data = [
        # 2026-05-20 reviews (mixed sentiment)
        {"review_date": "2026-05-20", "rating": 5, "sentiment_score": 0.8},
        {"review_date": "2026-05-20", "rating": 3, "sentiment_score": None},  # Rating-only review
        
        # 2026-05-19 reviews
        {"review_date": "2026-05-19", "rating": 1, "sentiment_score": -0.9},
    ]
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.rollups.get_supabase_client", return_value=mock_db):
        unique_dates = await recompute_daily_rollups("test-app-uuid")
        
        assert unique_dates == 2
        
        # Verify bulk upsert was executed
        assert mock_db.table("daily_rollups").upsert.call_count == 1
        
        upserted_rows = mock_db.table("daily_rollups").upsert.call_args[0][0]
        assert len(upserted_rows) == 2
        
        # Find rolled up rows
        row_20 = next(r for r in upserted_rows if r["date"] == "2026-05-20")
        row_19 = next(r for r in upserted_rows if r["date"] == "2026-05-19")
        
        # Assert math accuracy
        assert row_20["review_count"] == 2
        assert row_20["avg_rating"] == 4.0  # (5 + 3) / 2
        assert row_20["avg_sentiment"] == 0.8  # sentiment_score=None ignored from avg
        assert row_20["star_5"] == 1
        assert row_20["star_3"] == 1
        assert row_20["star_1"] == 0
        
        assert row_19["review_count"] == 1
        assert row_19["avg_rating"] == 1.0
        assert row_19["avg_sentiment"] == -0.9
        assert row_19["star_1"] == 1
        assert row_19["star_5"] == 0


@pytest.mark.asyncio
async def test_recompute_rollups_empty(mock_db):
    """Verify rollups gracefully skips calculations if no reviews exist."""
    mock_resp = MagicMock()
    mock_resp.data = []
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.rollups.get_supabase_client", return_value=mock_db):
        unique_dates = await recompute_daily_rollups("test-app-uuid")
        assert unique_dates == 0
        mock_db.table("daily_rollups").upsert.assert_not_called()


class TestTrendsEndpoint:
    """Test GET /apps/{app_id}/trends endpoint."""
    
    def test_trends_app_not_found(self, client, mock_db):
        """Should return 404 if app doesn't exist."""
        app_resp = MagicMock()
        app_resp.data = []
        mock_db.table("catalog_apps").select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        response = client.get("/apps/non-existent-uuid/trends")
        assert response.status_code == 404
        
    def test_trends_app_inactive(self, client, mock_db):
        """Should return 404 if app is deactivated."""
        app_resp = MagicMock()
        app_resp.data = {"id": "test-uuid", "is_active": False}
        mock_db.table("catalog_apps").select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        response = client.get("/apps/test-uuid/trends")
        assert response.status_code == 404

    def test_trends_success_filtering_and_sorting(self, client, mock_db):
        """Verify trends are correctly requested, filtered by query params, and ordered."""
        # Mock active app validation
        app_resp = MagicMock()
        app_resp.data = {"id": "test-uuid", "is_active": True}
        
        # Mock rollups return
        rollups_resp = MagicMock()
        rollups_resp.data = [
            {"date": "2026-05-19", "avg_rating": 3.0},
            {"date": "2026-05-20", "avg_rating": 4.5},
        ]
        
        # Setup mocks chain
        mock_db.table("catalog_apps").select.return_value.eq.return_value.single.return_value.execute.return_value = app_resp
        
        query_mock = mock_db.table("daily_rollups").select.return_value.eq.return_value
        query_mock.gte.return_value.lte.return_value.order.return_value.execute.return_value = rollups_resp
        
        response = client.get("/apps/test-uuid/trends?from_date=2026-05-19&to_date=2026-05-20")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["date"] == "2026-05-19"
        
        # Verify query parameters was mapped to date filters
        query_mock.gte.assert_called_with("date", "2026-05-19")
        query_mock.gte.return_value.lte.assert_called_with("date", "2026-05-20")
        query_mock.gte.return_value.lte.return_value.order.assert_called_with("date")
