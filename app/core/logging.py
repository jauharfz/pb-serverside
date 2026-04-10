"""
core/logging.py
───────────────
Setup logging terpusat.
Dipanggil sekali saat aplikasi start via lifespan.
"""

import logging
import sys


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )
    # Kurangi noise dari library pihak ketiga
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.WARNING)
