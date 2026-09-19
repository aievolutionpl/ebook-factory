"""Standard ASGI entrypoint for local runners and deployment probes."""

from __future__ import annotations

import os
from pathlib import Path

from ebook_factory.app import create_app

DATA_DIR = Path(os.environ.get("EBOOK_FACTORY_DATA_DIR", ".data"))
app = create_app(DATA_DIR)
