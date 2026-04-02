"""
self_map.py
-----------
Main entry point for the Kitab Personality Self Map.

Usage (CLI)
-----------
    python self_map.py --year 2002 --month 6 --date 27 \\
        --hours 2 --minutes 0 \\
        --lat 26.8997 --lon 76.3324 --tz 5.5 \\
        --name "Rajesh Kumar Meena" --place "Dausa"

    # Optionally pass API key directly (otherwise reads from .env / ASTRO_API_KEY):
    python self_map.py --api-key YOUR_KEY ...

Output is written to:
    output/<Name>_<YYYY-MM-DD>_<Place>/
        self_map.json
        chart.png

Usage (programmatic)
--------------------
    from self_map import generate_self_map
    result = generate_self_map(birth, api_key="...")
    # result["self_map"]   → full dict
    # result["output_dir"] → path to output folder
    # result["chart_path"] → path to PNG
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from astro_client import AstroClient
from scoring_engine import parse_chart, build_self_map


# ─────────────────────────────────────────────────────────────────────
# Output path helper
# ─────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert arbitrary text to a safe filename component."""
    text = text.strip().replace(" ", "_")
    text = re.sub(r"[^\w\-]", "", text)
    return text


def make_output_dir(birth: dict, base: str = "output") -> Path:
    """
    Build a unique output directory path:
        output/<Name>_<YYYY-MM-DD>_<Place>/
    Falls back to a timestamp if name/place are missing.
    """
    name  = _slugify(birth.get("name", "unknown"))
    place = _slugify(birth.get("place", "unknown"))
    dob   = f"{birth['year']:04d}-{birth['month']:02d}-{birth['date']:02d}"
    folder_name = f"{name}_{dob}_{place}"
    out_dir = Path(base) / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# ─────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────

def generate_self_map(
    birth: dict,
    api_key: str,
    save_chart: bool = True,
    output_base: str = "output",
    current_date: Optional[datetime] = None,
    verbose: bool = False,
) -> dict:
    """
    Full pipeline: fetch → parse → score → Nakshatra → JSON + chart.

    Parameters
    ----------
    birth : dict
        Required: year, month, date, hours, minutes, latitude, longitude, timezone
        Optional: seconds, name, place
    api_key : str
    save_chart : bool
    output_base : str   Root folder for all outputs (default "output")
    current_date : datetime, optional
    verbose : bool

    Returns
    -------
    dict with keys:
        self_map    → complete Self Map dict
        output_dir  → Path of the output folder
        chart_path  → path to radar chart PNG (or None)
        raw_data    → raw API responses
    """
    if verbose:
        print("[1/4] Fetching chart data from freeastrologyapi.com ...")

    client = AstroClient(api_key)
    try:
        raw = client.get_full_chart_data(birth)
    except Exception as e:
        raise RuntimeError(f"API fetch failed: {e}") from e

    if verbose:
        print("      ✓ Vedic planets, Shad Bala, Maha Dasa, Western planets/houses/aspects fetched.")
        print("[2/4] Parsing chart data ...")

    chart = parse_chart(raw, current_date=current_date or datetime.now())

    if verbose:
        from scoring_engine import SIGN_NAMES
        asc  = SIGN_NAMES.get(chart.ascendant_sign, "?")
        moon = SIGN_NAMES.get(chart.moon_sign, "?")
        print(f"      Ascendant: {asc} | Moon: {moon} | Dasa lord: {chart.current_dasa_lord}")
        print("[3/4] Scoring 8 dimensions + Nakshatra layer ...")

    self_map = build_self_map(chart, birth)

    if verbose:
        moon_nak = self_map["profile"]["nakshatra"]["moon"]["nakshatra"]
        asc_nak  = self_map["profile"]["nakshatra"]["ascendant"]["nakshatra"]
        print(f"      Moon Nakshatra: {moon_nak}  |  Ascendant Nakshatra: {asc_nak}")
        print("      ✓ Scores computed:")
        for k, v in self_map["dimensions"].items():
            pre  = v["score_pre_nakshatra"]
            post = v["score"]
            diff = round(post - pre, 1)
            tag  = f"  [{'+' if diff >= 0 else ''}{diff} nak]" if diff != 0 else ""
            print(f"         {v['icon']}  {v['label']:<28} {post:5.1f}{tag}  [{v['band']}]")

    # Prepare output directory
    out_dir = make_output_dir(birth, output_base)

    # Save JSON
    json_path = out_dir / "self_map.json"
    with open(json_path, "w") as f:
        json.dump(self_map, f, indent=2, default=str)

    chart_path = None
    if save_chart:
        if verbose:
            print("[4/4] Generating radar chart ...")
        try:
            from visualizer import generate_radar_chart
            chart_path = str(out_dir / "chart.png")
            generate_radar_chart(self_map, output_path=chart_path)
            if verbose:
                print(f"      ✓ Chart saved.")
        except Exception as e:
            if verbose:
                print(f"      ⚠ Chart generation failed: {e}")
            chart_path = None

    if verbose:
        print(f"\n  Output folder: {out_dir}/")

    return {
        "self_map":   self_map,
        "output_dir": out_dir,
        "chart_path": chart_path,
        "raw_data":   raw,
    }


# ─────────────────────────────────────────────────────────────────────
# Console summary printer
# ─────────────────────────────────────────────────────────────────────

def print_summary(self_map: dict) -> None:
    profile = self_map["profile"]
    dims    = self_map["dimensions"]
    theme   = self_map["current_theme"]
    nak     = profile.get("nakshatra", {})
    moon_nak = nak.get("moon", {})
    asc_nak  = nak.get("ascendant", {})

    BAR = 30
    print("\n" + "═" * 65)
    print("  KITAB PERSONALITY SELF MAP")
    print("═" * 65)

    name  = profile["birth_data"].get("name", "—")
    place = profile["birth_data"].get("place", "—")
    bd    = profile["birth_data"]
    print(f"  Name  : {name}")
    print(f"  Place : {place}")
    print(f"  Born  : {bd['date']}/{bd['month']}/{bd['year']}  "
          f"{bd['hours']:02d}:{bd['minutes']:02d}")
    print()
    print(f"  ♑ Ascendant      : {profile['ascendant']}  "
          f"(Nakshatra: {asc_nak.get('nakshatra', '—')} pada {asc_nak.get('pada', '—')})")
    print(f"  ☽ Moon Sign      : {profile['moon_sign']}  "
          f"(Nakshatra: {moon_nak.get('nakshatra', '—')} pada {moon_nak.get('pada', '—')})")
    print(f"  ☀  Sun Sign      : {profile['sun_sign']}")
    print(f"  ⏳ Maha Dasa     : {profile['current_maha_dasa']}")
    if moon_nak:
        print(f"  ✨ Core Traits   : {', '.join(moon_nak.get('core_traits', []))}")
    print()

    print("─" * 65)
    print(f"  {'DIMENSION':<28}  {'SCORE':>5}  {'BAND':<12}  BAR")
    print("─" * 65)

    for key, val in sorted(dims.items(), key=lambda x: x[1]["score"], reverse=True):
        score = val["score"]
        bar   = "█" * int(score / 100 * BAR) + "░" * (BAR - int(score / 100 * BAR))
        dasa  = " ★" if val["dasa_active"] else "  "
        print(f"  {val['icon']} {val['label']:<27}{dasa}  {score:>5.1f}  {val['band']:<12}  {bar}")

    print()
    print("─" * 65)
    print("  ★ = current Maha Dasa lord is primary planet for this dimension")
    print()

    print("─" * 65)
    print("  STRENGTH ZONES")
    print("─" * 65)
    for sz in self_map["strength_zones"]:
        print(f"  {sz['label']:<28}  → {', '.join(sz['focus'][:3])}")

    print()
    print("─" * 65)
    print("  GROWTH ZONES  (highest leverage reading)")
    print("─" * 65)
    for gz in self_map["growth_zones"]:
        print(f"  {gz['label']:<28}  → {', '.join(gz['focus'][:3])}")

    print()
    print("─" * 65)
    print(f"  CURRENT LIFE THEME: {theme['maha_dasa_lord']} Maha Dasa — {theme['theme']}")
    print(f"  Recommended Kitab focus: {', '.join(theme['recommended_books'])}")
    print("═" * 65)
    print()


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a Kitab Personality Self Map.",
    )
    p.add_argument("--api-key", default=os.environ.get("ASTRO_API_KEY", ""),
                   help="API key (or set ASTRO_API_KEY in .env)")
    p.add_argument("--year",    type=int, required=True)
    p.add_argument("--month",   type=int, required=True)
    p.add_argument("--date",    type=int, required=True)
    p.add_argument("--hours",   type=int, required=True)
    p.add_argument("--minutes", type=int, required=True)
    p.add_argument("--seconds", type=int, default=0)
    p.add_argument("--lat",     type=float, required=True, dest="latitude")
    p.add_argument("--lon",     type=float, required=True, dest="longitude")
    p.add_argument("--tz",      type=float, required=True, dest="timezone")
    p.add_argument("--name",    default="")
    p.add_argument("--place",   default="")
    p.add_argument("--no-chart", action="store_true")
    p.add_argument("--output",  default="output", help="Base output directory")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if not args.api_key:
        sys.exit("Error: provide --api-key or set ASTRO_API_KEY in your .env file.")

    birth = {
        "year": args.year, "month": args.month, "date": args.date,
        "hours": args.hours, "minutes": args.minutes, "seconds": args.seconds,
        "latitude": args.latitude, "longitude": args.longitude, "timezone": args.timezone,
        "name": args.name, "place": args.place,
    }

    result = generate_self_map(
        birth=birth,
        api_key=args.api_key,
        save_chart=not args.no_chart,
        output_base=args.output,
        verbose=True,
    )

    print_summary(result["self_map"])
    print(f"Output folder : {result['output_dir']}/")
    if result["chart_path"]:
        print(f"Radar chart   : {result['chart_path']}")
    print(f"Self Map JSON : {result['output_dir']}/self_map.json")
