"""Profile selection without copying or overwriting private working data."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def resolver_perfil(raiz: Path = RAIZ) -> Path:
    """Explicit override, then private profile, then the synthetic example.

    Relative overrides are resolved against the project root. An explicit
    missing path is never silently replaced by another profile.
    """
    override = os.environ.get("CV_PIPELINE_PROFILE", "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else raiz / path
    private = raiz / "master" / "perfil.yaml"
    return private if private.is_file() else raiz / "examples" / "perfil.example.yaml"


MASTER_PATH = resolver_perfil()
