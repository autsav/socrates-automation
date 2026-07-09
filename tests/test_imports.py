"""Smoke test — imports every module to catch syntax and import errors."""

import importlib
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
MODULES = [
    "config",
    "src.core.excel_reader",
    "src.content.generate_quotes_excel",
    "src.visual.image_composer",
    "src.visual.image_generator",
    "src.core.instagram_poster",
    "pipeline",
    "src.content.quote_generator",
    "refresh_token",
]


def test_all_modules_import_cleanly():
    for name in MODULES:
        module_path = PROJECT_ROOT / (name.replace(".", "/") + ".py")
        if module_path.exists():
            importlib.import_module(name)
