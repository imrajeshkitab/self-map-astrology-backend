"""
api/routes/self_map.py
----------------------
Endpoints:

    POST /api/v1/self-map
        → Compute (or serve cached) Self Map.
        → Returns multipart/form-data with two parts:
              self_map_json  (application/json)
              chart_png      (image/png)
        → Header:  X-Cache-Key: <cache_key>
        → Header:  X-Cached: true | false

    GET  /api/v1/self-map/{cache_key}
        → Same multipart response from cache (404 if not found).

    GET  /api/v1/self-map/{cache_key}/json
        → Returns only the self_map.json.

    GET  /api/v1/self-map/{cache_key}/chart
        → Returns only the chart.png.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse

from api.models.birth_request import BirthRequest
from api.services.pipeline import run_pipeline

router = APIRouter()

OUTPUT_DIR = Path("output")
BOUNDARY   = "----SelfMapBoundary"


# ─────────────────────────────────────────────────────────────────────
# Multipart body builder
# ─────────────────────────────────────────────────────────────────────

def _build_multipart(json_bytes: bytes, png_bytes: bytes) -> bytes:
    """
    Construct an RFC 2046 multipart/form-data body with two named parts:
      1. self_map_json  — application/json
      2. chart_png      — image/png

    No external library needed; the format is straightforward bytes assembly.
    """
    crlf  = b"\r\n"
    delim = f"--{BOUNDARY}".encode()
    close = f"--{BOUNDARY}--".encode()

    parts = [
        delim,
        b'Content-Disposition: form-data; name="self_map_json"',
        b"Content-Type: application/json",
        b"",
        json_bytes,

        delim,
        b'Content-Disposition: form-data; name="chart_png"; filename="chart.png"',
        b"Content-Type: image/png",
        b"",
        png_bytes,

        close,
        b"",
    ]
    return crlf.join(parts)


def _multipart_response(
    json_bytes: bytes,
    png_bytes: bytes,
    cache_key: str,
    cached: bool,
) -> Response:
    body = _build_multipart(json_bytes, png_bytes)
    return Response(
        content=body,
        media_type=f"multipart/form-data; boundary={BOUNDARY}",
        headers={
            "X-Cache-Key": cache_key,
            "X-Cached":    "true" if cached else "false",
        },
    )


def _resolve_cache(cache_key: str) -> tuple[Path, Path]:
    """Resolve and validate cache paths. Raises 404 if not found."""
    out_dir   = OUTPUT_DIR / cache_key
    json_path = out_dir / "self_map.json"
    png_path  = out_dir / "chart.png"
    if not json_path.exists() or not png_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No cached Self Map found for key '{cache_key}'. "
                   "Generate it first via POST /api/v1/self-map."
        )
    return json_path, png_path


# ─────────────────────────────────────────────────────────────────────
# POST — generate (or serve cached) Self Map
# ─────────────────────────────────────────────────────────────────────

@router.post(
    "/self-map",
    summary="Generate a Personality Self Map",
    description=(
        "Accepts birth data, calls freeastrologyapi.com, runs the scoring engine "
        "with Nakshatra layer, and returns a multipart response with:\n"
        "- **self_map_json**: full Self Map as application/json\n"
        "- **chart_png**: radar chart as image/png\n\n"
        "Results are cached by birth identity (Name + DOB + Place). "
        "Identical requests return instantly from cache."
    ),
    response_class=Response,
    responses={
        200: {"description": "multipart/form-data with self_map_json + chart_png"},
        503: {"description": "Upstream astrology API failed"},
        422: {"description": "Validation error"},
    },
)
async def generate_self_map(request: BirthRequest) -> Response:
    birth = request.model_dump()
    try:
        json_bytes, png_bytes, cache_key, cached = await run_pipeline(birth)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Upstream API error: {e}")

    return _multipart_response(json_bytes, png_bytes, cache_key, cached)


# ─────────────────────────────────────────────────────────────────────
# GET — retrieve from cache by key
# ─────────────────────────────────────────────────────────────────────

@router.get(
    "/self-map/{cache_key}",
    summary="Retrieve cached Self Map (both files)",
    response_class=Response,
)
async def get_self_map(cache_key: str) -> Response:
    json_path, png_path = _resolve_cache(cache_key)
    return _multipart_response(
        json_path.read_bytes(), png_path.read_bytes(), cache_key, cached=True
    )


@router.get(
    "/self-map/{cache_key}/json",
    summary="Retrieve cached Self Map JSON only",
)
async def get_self_map_json(cache_key: str) -> JSONResponse:
    json_path, _ = _resolve_cache(cache_key)
    return JSONResponse(
        content=json.loads(json_path.read_bytes()),
        headers={"X-Cache-Key": cache_key},
    )


@router.get(
    "/self-map/{cache_key}/chart",
    summary="Retrieve cached radar chart PNG only",
    response_class=Response,
)
async def get_self_map_chart(cache_key: str) -> Response:
    _, png_path = _resolve_cache(cache_key)
    return Response(
        content=png_path.read_bytes(),
        media_type="image/png",
        headers={"X-Cache-Key": cache_key},
    )
