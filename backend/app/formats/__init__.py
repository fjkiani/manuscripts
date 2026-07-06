"""
Journal format plugin registry.
Auto-discovers all format modules in this directory.
Each module must expose: FORMAT_NAME, FORMAT_SUFFIX, build(items, output_path, ris_data, zotero_enabled)
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Protocol


class FormatPlugin(Protocol):
    FORMAT_NAME: str
    FORMAT_SUFFIX: str

    def build(self, items: list, output_path: str, ris_data: list | None, zotero_enabled: bool) -> str:
        ...


_REGISTRY: dict[str, object] = {}


def _load_plugins():
    pkg_dir = Path(__file__).parent
    for finder, name, ispkg in pkgutil.iter_modules([str(pkg_dir)]):
        if name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"app.formats.{name}")
            if hasattr(mod, "FORMAT_NAME") and hasattr(mod, "build"):
                _REGISTRY[name] = mod
        except Exception as e:
            import structlog
            structlog.get_logger().warning("format_plugin_load_failed", name=name, error=str(e))


_load_plugins()


def get_formatter(style: str):
    """Get a format plugin by style key (e.g. 'ieee', 'apa')."""
    if style not in _REGISTRY:
        raise ValueError(f"Unknown style '{style}'. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[style]


def list_formats() -> list[dict]:
    """List all available format plugins."""
    return [
        {"id": key, "name": mod.FORMAT_NAME, "suffix": mod.FORMAT_SUFFIX}
        for key, mod in _REGISTRY.items()
    ]
