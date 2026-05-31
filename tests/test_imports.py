"""Smoke test — imports every module to catch syntax and import errors."""

import importlib
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
MODULES = [
    "config",
    "excel_reader",
    "generate_quotes_excel",
    "image_composer",
    "image_generator",
    "instagram_poster",
    "pipeline",
    "quote_generator",
    "refresh_token",
]


def test_all_modules_import_cleanly():
    for name in MODULES:
        module_path = PROJECT_ROOT / f"{name}.py"
        if module_path.exists():
            importlib.import_module(name)
