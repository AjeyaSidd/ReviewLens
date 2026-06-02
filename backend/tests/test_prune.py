import pytest
from unittest.mock import MagicMock, patch
from app.services.sync_app import _prune_reviews


def test_prune_skipped_when_under_limit(mock_db):
    """Verify prune does nothing if review count is below or equal to max limit."""
    # Mock count response: 50 reviews
    count_resp = MagicMock()
    count_resp.count = 50
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = count_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = _prune_reviews("test-app-id", 2000)
        assert deleted == 0
        mock_db.table.return_value.delete.assert_not_called()


def test_prune_deletes_excess_reviews(mock_db):
    """Verify prune correctly deletes reviews outside the newest max_reviews."""
    # Mock count response: 2002 reviews (2 excess)
    count_resp = MagicMock()
    count_resp.count = 2002
    
    # Cutoff response: return the Nth (index 2000) review
    cutoff_resp = MagicMock()
    cutoff_resp.data = [{"id": "r-cutoff", "review_date": "2026-05-01"}]
    
    # Keep response: list of newest reviews to keep (index 0 to 1999)
    keep_resp = MagicMock()
    keep_resp.data = [{"id": f"keep-{i}"} for i in range(2000)]
    
    # All response: all existing reviews for this app
    all_resp = MagicMock()
    all_resp.data = [{"id": f"keep-{i}"} for i in range(2000)] + [{"id": "old-1"}, {"id": "old-2"}]
    
    # Setup chain calls
    mock_db.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
        count_resp,  # First query: count
        all_resp     # Fourth query: select id for all
    ]
    
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = cutoff_resp
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = keep_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = _prune_reviews("test-app-id", 2000)
        
        # Verify 2 excess reviews were deleted
        assert deleted == 2
        mock_db.table.return_value.delete.assert_called_once()
        mock_db.table.return_value.delete.return_value.in_.assert_called_with("id", ["old-1", "old-2"])
