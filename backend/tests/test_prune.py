import pytest
from unittest.mock import MagicMock, patch
from app.services.sync_app import _prune_reviews


@pytest.mark.asyncio
async def test_prune_under_limit(mock_db):
    """Verify prune does nothing if total reviews is below max_reviews."""
    # DB has 50 reviews (all play_store)
    mock_resp = MagicMock()
    mock_resp.data = [{"id": f"r-{i}", "platform": "play_store", "review_date": "2026-06-01"} for i in range(50)]
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = await _prune_reviews("test-app-id", max_reviews=500, play_provided=True, ios_provided=False)
        assert deleted == 0
        mock_db.table("reviews").delete.assert_not_called()


@pytest.mark.asyncio
async def test_prune_both_stores_provided(mock_db):
    """Verify that when both stores provide reviews, we prune to 250 from each."""
    # DB has 300 from play_store and 300 from app_store
    play_list = [{"id": f"play-{i}", "platform": "play_store", "review_date": f"2026-06-{i:04d}"} for i in range(1, 301)]
    ios_list = [{"id": f"ios-{i}", "platform": "app_store", "review_date": f"2026-06-{i:04d}"} for i in range(1, 301)]
    
    mock_resp = MagicMock()
    mock_resp.data = play_list + ios_list
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = await _prune_reviews("test-app-id", max_reviews=500, play_provided=True, ios_provided=True)
        
        # We should delete the oldest 50 from each store (total 100)
        assert deleted == 100
        
        # Expected deleted play ids: play-1 to play-50 (earliest dates)
        expected_deleted = [f"play-{i}" for i in range(1, 51)] + [f"ios-{i}" for i in range(1, 51)]
        
        # Verify deletion calls
        mock_db.table("reviews").delete.assert_called()
        in_calls = mock_db.table("reviews").delete.return_value.in_.call_args_list
        deleted_ids = []
        for call in in_calls:
            deleted_ids.extend(call[0][1])
            
        assert set(deleted_ids) == set(expected_deleted)


@pytest.mark.asyncio
async def test_prune_only_play_store_provided(mock_db):
    """Verify that when only play_store provides reviews, it can keep up to 500."""
    # DB has 550 play reviews and 50 ios reviews
    play_list = [{"id": f"play-{i}", "platform": "play_store", "review_date": f"2026-06-{i:04d}"} for i in range(1, 551)]
    ios_list = [{"id": f"ios-{i}", "platform": "app_store", "review_date": "2026-05-01"} for i in range(1, 51)]
    
    mock_resp = MagicMock()
    mock_resp.data = play_list + ios_list
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = await _prune_reviews("test-app-id", max_reviews=500, play_provided=True, ios_provided=False)
        
        assert deleted == 100
        expected_deleted = [f"play-{i}" for i in range(1, 51)] + [f"ios-{i}" for i in range(1, 51)]
        
        in_calls = mock_db.table("reviews").delete.return_value.in_.call_args_list
        deleted_ids = []
        for call in in_calls:
            deleted_ids.extend(call[0][1])
            
        assert set(deleted_ids) == set(expected_deleted)


@pytest.mark.asyncio
async def test_prune_neither_store_provided_balanced(mock_db):
    """Verify fallback to balanced 250/250 when neither store provides reviews but both exist."""
    # DB has 300 play reviews and 300 ios reviews
    play_list = [{"id": f"play-{i}", "platform": "play_store", "review_date": f"2026-06-{i:04d}"} for i in range(1, 301)]
    ios_list = [{"id": f"ios-{i}", "platform": "app_store", "review_date": f"2026-06-{i:04d}"} for i in range(1, 301)]
    
    mock_resp = MagicMock()
    mock_resp.data = play_list + ios_list
    mock_db.table.return_value.execute.return_value = mock_resp
    
    with patch("app.services.sync_app.get_supabase_client", return_value=mock_db):
        deleted = await _prune_reviews("test-app-id", max_reviews=500, play_provided=False, ios_provided=False)
        
        assert deleted == 100
        expected_deleted = [f"play-{i}" for i in range(1, 51)] + [f"ios-{i}" for i in range(1, 51)]
        
        in_calls = mock_db.table("reviews").delete.return_value.in_.call_args_list
        deleted_ids = []
        for call in in_calls:
            deleted_ids.extend(call[0][1])
            
        assert set(deleted_ids) == set(expected_deleted)
