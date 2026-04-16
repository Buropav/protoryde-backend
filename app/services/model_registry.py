import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
REGISTRY_PATH = MODELS_DIR / "model_registry.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_registry() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "updated_at": _utc_now_iso(),
        "models": {},
    }


def _sha256(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_version(previous: Optional[str]) -> str:
    if not previous:
        return "v1.0.0"
    if previous.startswith("v"):
        parts = previous[1:].split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            major, minor, patch = (int(p) for p in parts)
            return f"v{major}.{minor}.{patch + 1}"
    return f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def load_registry() -> Dict[str, Any]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        return _default_registry()
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return _default_registry()
    data.setdefault("schema_version", "1.0")
    data.setdefault("updated_at", _utc_now_iso())
    data.setdefault("models", {})
    return data


def save_registry(registry: Dict[str, Any]) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = _utc_now_iso()
    with REGISTRY_PATH.open("w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, sort_keys=True)


def register_model(
    model_key: str,
    artifact_path: Path,
    framework: str,
    metrics: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    registry = load_registry()
    models = registry.setdefault("models", {})
    prev = models.get(model_key, {})
    current_version = version or _next_version(prev.get("version"))

    entry = {
        "model_key": model_key,
        "framework": framework,
        "version": current_version,
        "artifact_path": str(artifact_path),
        "artifact_exists": artifact_path.exists(),
        "artifact_sha256": _sha256(artifact_path),
        "metrics": metrics or {},
        "metadata": metadata or {},
        "updated_at": _utc_now_iso(),
    }
    models[model_key] = entry
    save_registry(registry)
    return entry


def sync_model_artifact(
    model_key: str,
    artifact_path: Path,
    framework: str,
    metrics: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    bump_version: bool = False,
) -> Dict[str, Any]:
    registry = load_registry()
    models = registry.setdefault("models", {})
    prev = models.get(model_key, {})
    if bump_version:
        current_version = _next_version(prev.get("version"))
    else:
        current_version = prev.get("version") or "v1.0.0"

    entry = {
        "model_key": model_key,
        "framework": framework,
        "version": current_version,
        "artifact_path": str(artifact_path),
        "artifact_exists": artifact_path.exists(),
        "artifact_sha256": _sha256(artifact_path),
        "metrics": metrics or prev.get("metrics", {}),
        "metadata": metadata or prev.get("metadata", {}),
        "updated_at": _utc_now_iso(),
    }
    models[model_key] = entry
    save_registry(registry)
    return entry


def get_model_entry(model_key: str) -> Dict[str, Any]:
    registry = load_registry()
    return registry.get("models", {}).get(model_key, {})


def bootstrap_registry_if_missing() -> Dict[str, Any]:
    registry = load_registry()
    models = registry.setdefault("models", {})

    defaults = {
        "premium_xgboost": (MODELS_DIR / "model.pkl", "xgboost"),
        "fraud_iforest": (
            MODELS_DIR / "isolation_forest.pkl",
            "sklearn_isolation_forest",
        ),
        "forecast_prophet": (MODELS_DIR / "forecast_cache.json", "prophet"),
    }

    changed = False
    for key, (path, framework) in defaults.items():
        if key in models:
            continue
        models[key] = {
            "model_key": key,
            "framework": framework,
            "version": "v0.0.0",
            "artifact_path": str(path),
            "artifact_exists": path.exists(),
            "artifact_sha256": _sha256(path),
            "metrics": {},
            "metadata": {},
            "updated_at": _utc_now_iso(),
        }
        changed = True

    if changed:
        save_registry(registry)
    return registry
