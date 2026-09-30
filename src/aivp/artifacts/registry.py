from pathlib import Path
from typing import Dict, Optional


class ArtifactRegistry:
    def __init__(self) -> None:
        self._artifacts: Dict[str, Path] = {}

    def register(
        self,
        name: str,
        path: Path,
    ) -> Path:
        self._artifacts[name] = path
        return path

    def get(
        self,
        name: str,
    ) -> Optional[Path]:
        return self._artifacts.get(name)

    def all(
        self,
    ) -> Dict[str, Path]:
        return dict(self._artifacts)
