import os
import shutil
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MODELS_BASE_DIR   = os.getenv("MODELS_BASE_DIR", "/app/models")
CACHE_TTL_DAYS    = float(os.getenv("CACHE_TTL_DAYS", "7"))
CACHE_MAX_SIZE_GB = float(os.getenv("CACHE_MAX_SIZE_GB", "10"))
CACHE_MAX_MODELS  = int(os.getenv("CACHE_MAX_MODELS", "20"))

@dataclass(order=True)
class ModelEntry:
    last_used: float
    run_id:    str  = field(compare=False)
    size_bytes: int = field(compare=False)
    path:      Path = field(compare=False)

    @property
    def age_days(self) -> float:
        return (time.time() - self.last_used) / 86_400

def touch_model(mlflow_run_id: str) -> None:
    base = Path(MODELS_BASE_DIR) / mlflow_run_id
    pkl  = _find_pkl(base)
    if pkl:
        pkl.touch()
        logger.debug(f"Touched model for LRU: {pkl}")

def _find_pkl(directory: Path) -> Path | None:
    for pkl_file in directory.rglob("*.pkl"):
        return pkl_file
    return None

def _dir_size(directory: Path) -> int:
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())

def _scan_models() -> list[ModelEntry]:
    base = Path(MODELS_BASE_DIR)
    entries = []
    if not base.exists(): return entries
    for run_dir in base.iterdir():
        if not run_dir.is_dir(): continue
        pkl = _find_pkl(run_dir)
        if not pkl: continue
        entries.append(ModelEntry(pkl.stat().st_mtime, run_dir.name, _dir_size(run_dir), run_dir))
    return entries

def _delete(entry: ModelEntry, dry_run: bool) -> None:
    if dry_run: return
    try: shutil.rmtree(entry.path)
    except Exception as e: logger.error(f"Failed to delete {entry.path}: {e}")

def evict_unused_models(ttl_days=None, max_size_gb=None, max_models=None, dry_run=False) -> list[str]:
    ttl_days = ttl_days if ttl_days is not None else CACHE_TTL_DAYS
    max_size_gb = max_size_gb if max_size_gb is not None else CACHE_MAX_SIZE_GB
    max_models = max_models if max_models is not None else CACHE_MAX_MODELS
    
    entries = _scan_models()
    evicted = []
    
    # TTL Logic
    survivors = []
    for e in entries:
        if e.age_days > ttl_days:
            _delete(e, dry_run)
            evicted.append(e.run_id)
        else: survivors.append(e)
        
    # LRU/Size/Count Logic
    survivors.sort()
    max_bytes = max_size_gb * 1024 ** 3
    total_bytes = sum(e.size_bytes for e in survivors)
    
    # Evict by size
    for e in survivors[:]:
        if total_bytes <= max_bytes: break
        _delete(e, dry_run)
        evicted.append(e.run_id)
        total_bytes -= e.size_bytes
        survivors.remove(e)
        
    # Evict by count
    for e in survivors[:]:
        if len(survivors) <= max_models: break
        _delete(e, dry_run)
        evicted.append(e.run_id)
        survivors.remove(e)
        
    return evicted