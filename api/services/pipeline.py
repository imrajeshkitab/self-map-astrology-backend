"""
api/services/pipeline.py
------------------------
Async bridge between FastAPI and the blocking generate_self_map() pipeline.

The core pipeline (freeastrologyapi.com HTTP calls + matplotlib rendering) is
synchronous and takes ~5-8 seconds. We offload it to FastAPI's thread pool via
run_in_threadpool so the event loop stays free for other requests.
"""

import os
import sys
from pathlib import Path

from starlette.concurrency import run_in_threadpool

# Ensure src/ is importable from anywhere
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from self_map import generate_self_map, make_output_dir


def _cache_exists(birth: dict) -> tuple[bool, Path, Path]:
    """
    Check if a cached result already exists for this birth data.
    Returns (is_cached, json_path, png_path).
    """
    out_dir   = make_output_dir(birth, base="output")
    json_path = out_dir / "self_map.json"
    png_path  = out_dir / "chart.png"
    return (json_path.exists() and png_path.exists()), json_path, png_path


async def run_pipeline(birth: dict) -> tuple[bytes, bytes, str, bool]:
    """
    Run the Self Map pipeline (or serve from cache).

    Returns
    -------
    (json_bytes, png_bytes, cache_key, was_cached)
    """
    api_key = os.environ.get("ASTRO_API_KEY", "")
    if not api_key:
        raise ValueError("ASTRO_API_KEY is not set in the environment.")

    is_cached, json_path, png_path = _cache_exists(birth)
    cache_key = json_path.parent.name   # e.g. "Rajesh_Kumar_Meena_2002-06-27_Dausa"

    if is_cached:
        return json_path.read_bytes(), png_path.read_bytes(), cache_key, True

    # Run blocking pipeline in thread pool
    await run_in_threadpool(
        generate_self_map,
        birth=birth,
        api_key=api_key,
        save_chart=True,
        output_base="output",
        verbose=False,
    )

    return json_path.read_bytes(), png_path.read_bytes(), cache_key, False
