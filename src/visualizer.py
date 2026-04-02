"""
visualizer.py
-------------
Generates the Personality Self Map as a radar (spider-web) chart.

Produces a publication-quality PNG with:
  - 8-axis radar polygon for the dimension scores
  - Colour-coded zones (strength / balanced / growth)
  - Annotations for the current Maha Dasa
  - Kitab branding aesthetic

Requires: matplotlib, numpy
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")   # headless rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np


# ─────────────────────────────────────────────────────────────────────
# Colour palette (Kitab-inspired: warm parchment + ink tones)
# ─────────────────────────────────────────────────────────────────────
COLORS = {
    "background":   "#FAF7F0",   # warm parchment
    "grid":         "#DDD5C3",   # soft grid lines
    "axis":         "#B5A99A",   # axis spoke lines
    "polygon_fill": "#C17D3C",   # terracotta amber (main polygon)
    "polygon_edge": "#8B5320",   # dark brown edge
    "strength":     "#6B9E5E",   # muted green
    "balanced":     "#C17D3C",   # terracotta
    "growth_zone":  "#C05050",   # muted red
    "text_dark":    "#2C1F0E",   # deep ink
    "text_mid":     "#6B5744",   # medium brown
    "text_light":   "#A89880",   # light taupe
    "star":         "#E8B84B",   # gold star for dasa
    "overlay_bg":   "#F0EAE0",
}

BAND_COLORS = {
    "strength":   COLORS["strength"],
    "balanced":   COLORS["balanced"],
    "growth_zone": COLORS["growth_zone"],
}


def generate_radar_chart(
    self_map: dict,
    output_path: str = "self_map.png",
    figsize: tuple = (14, 11),
    dpi: int = 150,
) -> str:
    """
    Generate and save the Self Map radar chart.

    Parameters
    ----------
    self_map : dict
        Output of scoring_engine.build_self_map()
    output_path : str
        File path to save the PNG.
    figsize : tuple
        Matplotlib figure size in inches.
    dpi : int
        Output resolution.

    Returns
    -------
    str : absolute path of the saved file.
    """
    dims = self_map["dimensions"]
    profile = self_map["profile"]
    theme = self_map["current_theme"]

    # Ordered labels and values
    keys   = list(dims.keys())
    labels = [dims[k]["label"] for k in keys]
    icons  = [dims[k]["icon"]  for k in keys]
    scores = [dims[k]["score"] for k in keys]
    bands  = [dims[k]["band"]  for k in keys]
    dasa_active = [dims[k]["dasa_active"] for k in keys]

    N = len(keys)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles_closed = angles + [angles[0]]
    scores_closed = scores + [scores[0]]

    # ── Figure setup ──────────────────────────────────────────────────
    fig = plt.figure(figsize=figsize, facecolor=COLORS["background"])

    # Main radar axis
    ax_radar = fig.add_axes([0.05, 0.12, 0.55, 0.78], polar=True)
    ax_radar.set_facecolor(COLORS["background"])

    # ── Grid rings ────────────────────────────────────────────────────
    ring_values = [25, 50, 75, 100]
    for rv in ring_values:
        ring_angles = np.linspace(0, 2 * math.pi, 200)
        ring_r      = [rv] * 200
        ax_radar.plot(ring_angles, ring_r, color=COLORS["grid"],
                      linewidth=0.6, linestyle="--", alpha=0.7, zorder=1)
        # Label the 50 ring at top
        if rv == 50:
            ax_radar.text(math.pi / 2, rv + 3, "50", fontsize=7,
                          color=COLORS["text_light"], ha="center", va="bottom")

    # Zone fill: strength ring (>=72) in faint green
    strength_ring = np.linspace(0, 2 * math.pi, 200)
    ax_radar.fill_between(strength_ring, 72, 100,
                          alpha=0.06, color=COLORS["strength"], zorder=0)

    # ── Spokes ────────────────────────────────────────────────────────
    for angle in angles:
        ax_radar.plot([angle, angle], [0, 100],
                      color=COLORS["axis"], linewidth=0.8, alpha=0.6, zorder=1)

    # ── Main polygon (score area) ─────────────────────────────────────
    ax_radar.plot(angles_closed, scores_closed,
                  color=COLORS["polygon_edge"], linewidth=2.2, zorder=5)
    ax_radar.fill(angles_closed, scores_closed,
                  alpha=0.35, color=COLORS["polygon_fill"], zorder=4)

    # ── Score dots ────────────────────────────────────────────────────
    for i, (angle, score, band, is_dasa) in enumerate(
            zip(angles, scores, bands, dasa_active)):
        dot_color = BAND_COLORS.get(band, COLORS["polygon_fill"])
        ax_radar.scatter([angle], [score], s=55, color=dot_color,
                         zorder=6, edgecolors=COLORS["polygon_edge"], linewidth=1.2)
        if is_dasa:
            ax_radar.scatter([angle], [score + 6], s=80, color=COLORS["star"],
                             marker="*", zorder=7)

    # ── Axis labels ───────────────────────────────────────────────────
    ax_radar.set_xticks(angles)
    ax_radar.set_xticklabels([])   # we draw custom labels below
    ax_radar.set_yticks([])
    ax_radar.set_ylim(0, 115)
    ax_radar.spines["polar"].set_visible(False)

    # Draw dimension labels + icons outside the polygon
    for i, (angle, label, icon, score, band) in enumerate(
            zip(angles, labels, icons, scores, bands)):
        label_r = 108
        x = label_r * math.cos(angle - math.pi / 2)
        y = label_r * math.sin(angle - math.pi / 2)

        # Convert polar to figure coords manually for text annotation
        ha = "center"
        if abs(x) > 0.1 * label_r:
            ha = "left" if x > 0 else "right"

        short_label = _shorten_label(label)
        color = BAND_COLORS.get(band, COLORS["text_dark"])

        ax_radar.text(
            angle, label_r,
            f"{icon}\n{short_label}\n{score:.0f}",
            ha="center", va="center",
            fontsize=8.5, color=COLORS["text_dark"],
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=COLORS["overlay_bg"],
                      edgecolor=color, linewidth=1.2, alpha=0.85),
            zorder=8,
        )

    # ── Right panel: info cards ────────────────────────────────────────
    ax_info = fig.add_axes([0.62, 0.12, 0.36, 0.78])
    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.axis("off")
    ax_info.set_facecolor(COLORS["background"])

    name  = profile["birth_data"].get("name", "")
    place = profile["birth_data"].get("place", "")
    bd    = profile["birth_data"]
    nak      = profile.get("nakshatra", {})
    moon_nak = nak.get("moon", {})
    asc_nak  = nak.get("ascendant", {})

    ypos = 0.97
    ax_info.text(0.5, ypos, "Kitab Self Map", fontsize=15,
                 fontweight="bold", ha="center", va="top",
                 color=COLORS["text_dark"])
    ypos -= 0.05
    if name:
        ax_info.text(0.5, ypos, name, fontsize=11, ha="center", va="top",
                     color=COLORS["text_mid"], style="italic")
        ypos -= 0.04
    if place:
        ax_info.text(0.5, ypos, place, fontsize=9, ha="center", va="top",
                     color=COLORS["text_light"])
        ypos -= 0.03
    birth_str = f"{bd['date']}/{bd['month']}/{bd['year']}  {bd['hours']:02d}:{bd['minutes']:02d}"
    ax_info.text(0.5, ypos, birth_str, fontsize=9, ha="center", va="top",
                 color=COLORS["text_light"])
    ypos -= 0.05

    # Vedic profile card — includes Nakshatra
    nak_lines = []
    if moon_nak:
        nak_lines.append(
            f"Moon Nak  : {moon_nak.get('nakshatra','—')} "
            f"p{moon_nak.get('pada','—')} "
            f"({moon_nak.get('ruling_planet','—')})"
        )
        traits = moon_nak.get("core_traits", [])[:3]
        if traits:
            nak_lines.append(f"Traits     : {', '.join(traits)}")
    if asc_nak:
        nak_lines.append(
            f"Asc Nak   : {asc_nak.get('nakshatra','—')} "
            f"p{asc_nak.get('pada','—')}"
        )

    vedic_lines = [
        f"Ascendant : {profile['ascendant']}",
        f"Moon Sign  : {profile['moon_sign']}",
        f"Sun Sign   : {profile['sun_sign']}",
    ] + nak_lines
    _draw_card(ax_info, ypos - 0.01, 0.12, title="Vedic Profile", lines=vedic_lines)
    ypos -= 0.04 + len(vedic_lines) * 0.036 + 0.04

    # Current Dasa card
    _draw_card(ax_info, ypos - 0.01, 0.12,
               title=f"★ Current Maha Dasa: {theme['maha_dasa_lord']}",
               lines=[theme["theme"]] + [f"• {b}" for b in theme["recommended_books"][:3]])
    ypos -= 0.22

    # Strength zones
    _draw_zone_card(ax_info, ypos - 0.01, 0.12,
                    title="Strength Zones",
                    zones=self_map["strength_zones"],
                    color=COLORS["strength"])
    ypos -= 0.20

    # Growth zones
    _draw_zone_card(ax_info, ypos - 0.01, 0.12,
                    title="Growth Zones (highest leverage reading)",
                    zones=self_map["growth_zones"],
                    color=COLORS["growth_zone"])
    ypos -= 0.21

    # Legend
    _draw_legend(ax_info, ypos)

    # ── Footer ────────────────────────────────────────────────────────
    fig.text(0.5, 0.03,
             "Scoring: Vedic dignities (40%) · Shad Bala strength (25%) · "
             "House placement (25%) · Western aspects (10%) + Dasa bonus",
             ha="center", fontsize=7.5, color=COLORS["text_light"],
             style="italic")
    fig.text(0.5, 0.01,
             f"Generated: {self_map['metadata']['generated_at'][:10]}  |  "
             f"Ayanamsha: Lahiri  |  freeastrologyapi.com",
             ha="center", fontsize=6.5, color=COLORS["text_light"])

    plt.savefig(output_path, dpi=dpi, bbox_inches="tight",
                facecolor=COLORS["background"])
    plt.close(fig)

    return str(Path(output_path).resolve())


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _shorten_label(label: str) -> str:
    """Shorten long dimension labels for the radar axis."""
    mapping = {
        "Philosophical Wisdom":    "Wisdom",
        "Emotional Intelligence":  "Emotion",
        "Discipline & Structure":  "Discipline",
        "Resilience & Transformation": "Resilience",
        "Creativity & Expression": "Creativity",
        "Relational Harmony":      "Relational",
        "Drive & Vitality":        "Drive",
        "Intellect & Curiosity":   "Intellect",
    }
    return mapping.get(label, label)


def _draw_card(ax, y: float, x: float, title: str, lines: list[str],
               bg_color: str = None) -> None:
    """Draw a small info card on the info axis."""
    bg = bg_color or COLORS["overlay_bg"]
    card_h = 0.04 + len(lines) * 0.035
    rect = FancyBboxPatch((x, y - card_h), 0.88, card_h,
                          boxstyle="round,pad=0.01",
                          facecolor=bg, edgecolor=COLORS["grid"],
                          linewidth=0.8, transform=ax.transData)
    ax.add_patch(rect)
    ax.text(x + 0.03, y - 0.01, title, fontsize=8.5, fontweight="bold",
            color=COLORS["text_dark"], va="top")
    for i, line in enumerate(lines):
        ax.text(x + 0.03, y - 0.04 - i * 0.034, line, fontsize=7.5,
                color=COLORS["text_mid"], va="top")


def _draw_zone_card(ax, y: float, x: float, title: str,
                    zones: list[dict], color: str) -> None:
    """Draw strength/growth zone card."""
    n = len(zones)
    card_h = 0.04 + n * 0.055
    rect = FancyBboxPatch((x, y - card_h), 0.88, card_h,
                          boxstyle="round,pad=0.01",
                          facecolor=COLORS["overlay_bg"], edgecolor=color,
                          linewidth=1.2, transform=ax.transData)
    ax.add_patch(rect)
    ax.text(x + 0.03, y - 0.01, title, fontsize=8.5, fontweight="bold",
            color=color, va="top")
    for i, zone in enumerate(zones):
        ax.text(x + 0.03, y - 0.045 - i * 0.052,
                f"{zone['label']}  ({zone['score']:.0f})",
                fontsize=7.5, fontweight="semibold",
                color=COLORS["text_dark"], va="top")
        focus_str = "  " + ", ".join(zone["focus"][:2])
        ax.text(x + 0.03, y - 0.068 - i * 0.052,
                focus_str, fontsize=6.8,
                color=COLORS["text_mid"], va="top", style="italic")


def _draw_legend(ax, y: float) -> None:
    """Draw the band colour legend."""
    ax.text(0.12, y, "Score bands:", fontsize=7.5, fontweight="bold",
            color=COLORS["text_mid"], va="top")
    entries = [
        ("■", COLORS["strength"],   "Strength  (≥72)"),
        ("■", COLORS["balanced"],   "Balanced  (45–71)"),
        ("■", COLORS["growth_zone"], "Growth Zone  (<45)"),
        ("★", COLORS["star"],        "Maha Dasa active"),
    ]
    for j, (sym, col, txt) in enumerate(entries):
        ax.text(0.14 + j * 0.22, y - 0.04, sym, fontsize=11,
                color=col, va="top")
        ax.text(0.14 + j * 0.22 + 0.025, y - 0.04, txt,
                fontsize=7, color=COLORS["text_mid"], va="top")
