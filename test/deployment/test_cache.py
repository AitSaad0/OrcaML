import os  # <--- THIS WAS MISSING
import time
import shutil
from pathlib import Path
from unittest.mock import patch
from src.deployments.cache_manager import (
    evict_unused_models, touch_model, ModelEntry
)

# Use a temporary directory for testing
TEST_MODELS_DIR = "/tmp/orcaml_test_models"

@patch("src.deployments.cache_manager.MODELS_BASE_DIR", TEST_MODELS_DIR)
class TestCacheManager:
    
    def setup_method(self):
        if Path(TEST_MODELS_DIR).exists():
            shutil.rmtree(TEST_MODELS_DIR)
        Path(TEST_MODELS_DIR).mkdir(parents=True, exist_ok=True)

    def _create_mock_model(self, run_id: str, age_seconds: float):
        run_dir = Path(TEST_MODELS_DIR) / run_id
        run_dir.mkdir(exist_ok=True)
        pkl = run_dir / "model.pkl"
        pkl.touch()
        # Set access/modify time in the past
        past_time = time.time() - age_seconds
        os.utime(pkl, (past_time, past_time))
        return run_dir

    def test_touch_model_updates_mtime(self):
        run_dir = self._create_mock_model("run1", 1000)
        pkl = run_dir / "model.pkl"
        old_mtime = pkl.stat().st_mtime
        
        touch_model("run1")
        
        assert pkl.stat().st_mtime > old_mtime

    def test_evict_by_ttl(self):
        self._create_mock_model("old_run", 10 * 86400)
        
        evicted = evict_unused_models(ttl_days=7)
        
        assert "old_run" in evicted
        assert not (Path(TEST_MODELS_DIR) / "old_run").exists()

    def test_evict_by_count_cap(self):
        self._create_mock_model("newest", 10)
        self._create_mock_model("middle", 100)
        self._create_mock_model("oldest", 1000)
        
        evicted = evict_unused_models(max_models=2)
        
        assert "oldest" in evicted
        assert len(evicted) == 1

    def test_evict_by_size_cap(self):
        # We patch _scan_models to simulate disk usage without creating real files
        with patch("src.deployments.cache_manager._scan_models") as mock_scan:
            mock_scan.return_value = [
                ModelEntry(last_used=time.time(), run_id="small", size_bytes=100, path=Path("/tmp/a")),
                ModelEntry(last_used=time.time()-10000, run_id="big", size_bytes=2*1024**3, path=Path("/tmp/b"))
            ]
            evicted = evict_unused_models(max_size_gb=1.0)
            assert "big" in evicted