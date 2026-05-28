from __future__ import annotations

from app.config import Settings


DEFAULT_ALLOWED_SAVE_PATHS = (
    "/downloads/movies",
    "/downloads/movies-4k",
    "/downloads/tv",
)


def validate_save_path_override(save_path: str | None, settings: Settings) -> str | None:
    if save_path is None:
        return None

    normalized = _normalize_path(save_path)
    allowed_roots = [_normalize_path(path) for path in _allowed_save_paths(settings) if path]
    if any(_is_same_or_child(normalized, root) for root in allowed_roots):
        return normalized

    raise ValueError("save_path must be inside a configured qBitlarr save path")


def _allowed_save_paths(settings: Settings) -> list[str]:
    configured = [
        getattr(settings, "qbitlarr_save_path_movie", DEFAULT_ALLOWED_SAVE_PATHS[0]),
        getattr(settings, "qbitlarr_save_path_movie_4k", DEFAULT_ALLOWED_SAVE_PATHS[1]),
        getattr(settings, "qbitlarr_save_path_tv", DEFAULT_ALLOWED_SAVE_PATHS[2]),
    ]
    configured.extend(getattr(settings, "qbitlarr_extra_save_paths", None) or [])
    return configured


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized


def _is_same_or_child(path: str, root: str) -> bool:
    if path == root:
        return True
    return path.startswith(f"{root}/")
