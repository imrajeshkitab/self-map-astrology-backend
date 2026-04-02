"""
scoring_engine.py
-----------------
Converts raw API chart data into an 8-dimension personality Self Map.

Architecture
============
raw API data
    → parse_chart()        normalise into a flat ChartData object
    → score_dimension()    score each of 8 dimensions 0–100
    → build_self_map()     assemble the final Self Map dict

Scoring formula (per dimension)
================================
  dignity_score   × 0.40   (Vedic sign dignity of primary planet)
  shad_bala_score × 0.25   (Parashara six-fold strength, Sun–Saturn only)
  house_score     × 0.25   (Vedic house placement: angular / succedent / cadent)
  aspect_score    × 0.10   (Western benefic vs malefic aspects to primary planet)
  ─────────────────────────
  base_score               (0–100)
  + dasa_bonus             (+8 if primary planet lords the current Maha Dasa)
  = final_score            (clipped to 0–100)

Each secondary planet contributes a weighted partial score that is blended
into the dimension at a 1.5 : 1.0 primary-to-secondary ratio.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 1. STATIC TABLES
# ═══════════════════════════════════════════════════════════════════════════════

# Sign numbers follow Vedic convention: 1=Aries … 12=Pisces
SIGN_NAMES = {
    1: "Aries", 2: "Taurus", 3: "Gemini", 4: "Cancer",
    5: "Leo",   6: "Virgo",  7: "Libra",  8: "Scorpio",
    9: "Sagittarius", 10: "Capricorn", 11: "Aquarius", 12: "Pisces",
}

ELEMENT_MAP = {
    1: "fire", 5: "fire", 9: "fire",
    2: "earth", 6: "earth", 10: "earth",
    3: "air",  7: "air",  11: "air",
    4: "water", 8: "water", 12: "water",
}

MODALITY_MAP = {
    1: "cardinal", 4: "cardinal", 7: "cardinal", 10: "cardinal",
    2: "fixed",    5: "fixed",    8: "fixed",    11: "fixed",
    3: "mutable",  6: "mutable",  9: "mutable",  12: "mutable",
}

# Vedic (Parashara) dignity table
# Keys: planet name as returned by the API
VEDIC_DIGNITIES: dict[str, dict] = {
    "Sun":     {"own": [5],      "exalted": 1,  "debilitated": 7,  "friendly": [1, 9, 4],    "enemy": [11, 7]},
    "Moon":    {"own": [4],      "exalted": 2,  "debilitated": 8,  "friendly": [5, 1],        "enemy": []},
    "Mars":    {"own": [1, 8],   "exalted": 10, "debilitated": 4,  "friendly": [5, 9, 12],    "enemy": [3, 6]},
    "Mercury": {"own": [3, 6],   "exalted": 6,  "debilitated": 12, "friendly": [5, 7, 2],     "enemy": [8]},
    "Jupiter": {"own": [9, 12],  "exalted": 4,  "debilitated": 10, "friendly": [1, 4, 5],     "enemy": [3, 6]},
    "Venus":   {"own": [2, 7],   "exalted": 12, "debilitated": 6,  "friendly": [3, 8, 10],    "enemy": [5, 9]},
    "Saturn":  {"own": [10, 11], "exalted": 7,  "debilitated": 1,  "friendly": [3, 6, 11],    "enemy": [5, 4, 9]},
    "Rahu":    {"own": [],       "exalted": 3,  "debilitated": 9,  "friendly": [3, 6, 11],    "enemy": [9, 5, 4]},
    "Ketu":    {"own": [],       "exalted": 9,  "debilitated": 3,  "friendly": [9, 5, 4],     "enemy": [3, 6, 11]},
}

DIGNITY_SCORE = {
    "exalted":     100,
    "own":          85,
    "friendly":     65,
    "neutral":      50,
    "enemy":        32,
    "debilitated":  18,
}

# House strength in Jyotish: Kendra (angular) > Panaphar (succedent) > Apoklima (cadent)
HOUSE_STRENGTH: dict[int, int] = {
    1: 100, 10: 95, 7: 90, 4: 85,   # Angular (Kendra)
    5: 75,  11: 70, 2: 65, 8: 60,   # Succedent (Panaphar)
    9: 68,  3: 42, 6: 38, 12: 48,   # Cadent (Apoklima) — 9th elevated for dharma
}

# Aspect weights for the aspect_score calculation
ASPECT_WEIGHT: dict[str, int] = {
    "Trine":          +20,
    "Sextile":        +12,
    "Conjunction":    +8,    # net neutral; benefic if with a benefic planet
    "Opposition":     -8,
    "Square":         -14,
    "Quincunx":       -5,
    "Sesquiquadrate": -6,
    "Semi-Sextile":   +4,
    "Quintile":       +6,
    "Septile":        +3,
    "Octile":         -4,
    "Novile":         +3,
}

# Natural benefics / malefics for Conjunction bonus adjustment
NATURAL_BENEFICS  = {"Jupiter", "Venus", "Moon", "Mercury"}   # Mercury benefic when alone
NATURAL_MALEFICS  = {"Saturn", "Mars", "Sun", "Rahu", "Ketu"} # Sun malefic to other planets


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DIMENSION DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

DIMENSIONS: dict[str, dict] = {
    "intellect": {
        "label": "Intellect & Curiosity",
        "icon":  "🧠",
        "primary_planet":    "Mercury",
        "secondary_planets": ["Sun"],          # Sun gives mental clarity
        "power_houses":      [3, 6, 1],        # 3rd = learning, 6th = analysis, 1st = self
        "resonant_signs":    [3, 6, 11],       # Gemini, Virgo, Aquarius
        "retro_modifier":    +6,               # Retro Mercury = deep, inward thinking
        "kitab_high":  ["Philosophy", "Science & Technology", "Logic & Critical Thinking",
                        "Linguistics", "Mathematics"],
        "kitab_low":   ["Mental Models", "Clear Thinking", "Cognitive Biases",
                        "Epistemology", "Memory & Learning"],
        "description": "Analytical depth, pattern recognition, and intellectual curiosity.",
    },
    "emotional_intelligence": {
        "label": "Emotional Intelligence",
        "icon":  "🌊",
        "primary_planet":    "Moon",
        "secondary_planets": ["Venus"],
        "power_houses":      [4, 12, 1],       # 4th = inner world, 12th = depth
        "resonant_signs":    [4, 8, 12],       # Cancer, Scorpio, Pisces (water)
        "retro_modifier":    0,
        "kitab_high":  ["Psychology", "Poetry & Literature", "Memoir & Biography",
                        "Relationships", "Depth Psychology"],
        "kitab_low":   ["Emotional Literacy", "Self-Compassion", "Attachment Theory",
                        "Therapy & Healing", "Mindfulness"],
        "description": "Empathy, emotional depth, and attunement to the inner world.",
    },
    "drive_vitality": {
        "label": "Drive & Vitality",
        "icon":  "🔥",
        "primary_planet":    "Mars",
        "secondary_planets": ["Sun"],
        "power_houses":      [1, 10, 3],       # 1st = body/self, 10th = ambition
        "resonant_signs":    [1, 5, 9],        # Aries, Leo, Sagittarius (fire)
        "retro_modifier":    -5,               # Retro Mars = blocked/redirected energy
        "kitab_high":  ["Leadership", "Entrepreneurship", "Biographies of Achievers",
                        "Strategy & War", "Sports & Performance"],
        "kitab_low":   ["Motivation & Drive", "Overcoming Inertia", "Energy Management",
                        "Starting & Doing", "Courage"],
        "description": "Life-force, ambition, competitive drive, and physical vitality.",
    },
    "relational_harmony": {
        "label": "Relational Harmony",
        "icon":  "🤝",
        "primary_planet":    "Venus",
        "secondary_planets": ["Jupiter", "Moon"],
        "power_houses":      [7, 11, 5],       # 7th = partnerships, 11th = community
        "resonant_signs":    [2, 7, 12],       # Taurus, Libra, Pisces
        "retro_modifier":    -4,               # Retro Venus = withdrawn relational energy
        "kitab_high":  ["Communication & Negotiation", "Relationships & Love",
                        "Social Philosophy", "Community & Belonging", "Diplomacy"],
        "kitab_low":   ["Conflict Resolution", "Vulnerability & Trust",
                        "Attachment & Love Languages", "Social Skills"],
        "description": "Capacity for meaningful bonds, cooperation, and social grace.",
    },
    "discipline_structure": {
        "label": "Discipline & Structure",
        "icon":  "⚖️",
        "primary_planet":    "Saturn",
        "secondary_planets": ["Mars"],
        "power_houses":      [10, 6, 11],      # 10th = duty/career, 6th = work ethic
        "resonant_signs":    [10, 11, 6],      # Capricorn, Aquarius, Virgo
        "retro_modifier":    +5,               # Retro Saturn = deep internalised discipline
        "kitab_high":  ["Systems Thinking", "Productivity & Focus", "Health & Longevity",
                        "Economics & Finance", "Stoicism"],
        "kitab_low":   ["Habits & Routines", "Time Management", "Simplicity & Minimalism",
                        "Consistency & Willpower", "Getting Things Done"],
        "description": "Long-range planning, self-mastery, reliability, and structured effort.",
    },
    "philosophical_wisdom": {
        "label": "Philosophical Wisdom",
        "icon":  "📿",
        "primary_planet":    "Jupiter",
        "secondary_planets": ["Sun", "Ketu"],
        "power_houses":      [9, 12, 5],       # 9th = dharma/higher learning, 12th = moksha
        "resonant_signs":    [9, 12, 4],       # Sagittarius, Pisces, Cancer
        "retro_modifier":    +4,               # Retro Jupiter = deeper philosophical seeking
        "kitab_high":  ["Vedic Texts & Upanishads", "Stoicism & Ancient Philosophy",
                        "World Religions & Mysticism", "Comparative Philosophy",
                        "The Bhagavad Gita"],
        "kitab_low":   ["Introduction to Philosophy", "Meaning-Making",
                        "Vedanta Basics", "Existentialism", "Ethics & Morality"],
        "description": "Quest for meaning, higher knowledge, spiritual depth, and dharmic clarity.",
    },
    "creativity_expression": {
        "label": "Creativity & Expression",
        "icon":  "🎨",
        "primary_planet":    "Sun",
        "secondary_planets": ["Venus", "Moon"],
        "power_houses":      [5, 1, 3],        # 5th = creativity/art, 1st = self-expression
        "resonant_signs":    [5, 2, 7],        # Leo, Taurus, Libra (aesthetic signs)
        "retro_modifier":    0,                # Sun is never retrograde
        "kitab_high":  ["Art, Aesthetics & Design", "Literature & Fiction",
                        "Creative Process & Craft", "Music & Sound", "Storytelling"],
        "kitab_low":   ["Unlocking Creativity", "Play & Imagination",
                        "Artist's Way", "Artisan Crafts", "Finding Your Voice"],
        "description": "Self-expression, aesthetic sensibility, and the joy of making.",
    },
    "resilience_transformation": {
        "label": "Resilience & Transformation",
        "icon":  "🦋",
        "primary_planet":    "Saturn",
        "secondary_planets": ["Mars", "Rahu"],
        "power_houses":      [8, 12, 6],       # 8th = transformation, 12th = dissolution/rebirth
        "resonant_signs":    [8, 10, 1],       # Scorpio, Capricorn, Aries (intensity/endurance)
        "retro_modifier":    +5,
        "kitab_high":  ["Shadow Work & Depth Psychology", "Mythology & Archetypes",
                        "Transformation Narratives", "Existential Crisis & Growth",
                        "Near-Death & Rebirth Stories"],
        "kitab_low":   ["Resilience & Grit", "Coping & Adaptation",
                        "Growth Mindset", "Crisis Navigation", "Post-Traumatic Growth"],
        "description": "Capacity to metabolise hardship, undergo change, and emerge renewed.",
    },
}

DASA_LORDS = {
    "Sun": "Sun", "Moon": "Moon", "Mars": "Mars",
    "Rahu": "Rahu", "Jupiter": "Jupiter", "Saturn": "Saturn",
    "Mercury": "Mercury", "Ketu": "Ketu", "Venus": "Venus",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CHART DATA CONTAINER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlanetData:
    name: str
    full_degree: float
    norm_degree: float
    is_retro: bool
    vedic_sign: int            # 1-12
    vedic_house: Optional[int] # None for Ascendant
    shad_bala_pct: float       # 0-200+; 100 = average; 0 if not in Shad Bala table


@dataclass
class ChartData:
    # Indexed by planet name (title-cased)
    planets: dict[str, PlanetData] = field(default_factory=dict)
    # Western aspects: list of (planet_1, planet_2, aspect_type)
    aspects: list[tuple[str, str, str]] = field(default_factory=list)
    # Current Maha Dasa lord (e.g. "Jupiter")
    current_dasa_lord: str = ""
    # Birth meta
    ascendant_sign: int = 0       # 1-12
    moon_sign: int = 0
    sun_sign: int = 0
    moon_nakshatra: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHART DATA PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_chart(raw: dict, current_date: Optional[datetime] = None) -> ChartData:
    """
    Normalise the six raw API dicts (from AstroClient.get_full_chart_data)
    into a ChartData object.
    """
    if current_date is None:
        current_date = datetime.now()

    chart = ChartData()

    # --- Shad Bala lookup (Sun–Saturn) ------------------------------------
    sb_map: dict[str, float] = {}
    for name, vals in raw["shad_bala"]["output"].items():
        sb_map[name] = float(vals.get("percentage_strength", 100.0))

    # --- Vedic planets ----------------------------------------------------
    # API returns output as a list[dict, dict]:
    #   [0] = numbered-key dict  {"0": {...}, "1": {...}, ...}
    #   [1] = name-key dict      {"Sun": {...}, "Moon": {...}, ...}
    # We use the name-key variant for cleaner access.
    raw_vedic_out = raw["vedic_planets"]["output"]
    vedic_out = raw_vedic_out[1] if isinstance(raw_vedic_out, list) else raw_vedic_out
    for planet_name, pdata in vedic_out.items():
        # planet_name is the key from the name-keyed dict (e.g. "Sun", "Moon")
        # pdata may or may not have a redundant "name" field
        name = planet_name
        is_retro = str(pdata.get("isRetro", "false")).lower() == "true"
        vedic_sign = int(pdata.get("current_sign", 0))
        vedic_house = int(pdata["house_number"]) if "house_number" in pdata else None
        planet = PlanetData(
            name=name,
            full_degree=float(pdata.get("fullDegree", 0)),
            norm_degree=float(pdata.get("normDegree", 0)),
            is_retro=is_retro,
            vedic_sign=vedic_sign,
            vedic_house=vedic_house,
            shad_bala_pct=sb_map.get(name, 100.0),
        )
        chart.planets[name] = planet
        if name == "Ascendant":
            chart.ascendant_sign = vedic_sign
        elif name == "Moon":
            chart.moon_sign = vedic_sign
        elif name == "Sun":
            chart.sun_sign = vedic_sign

    # --- Western aspects --------------------------------------------------
    for asp in raw["western_aspects"]["output"]:
        p1 = asp["planet_1"]["en"]
        p2 = asp["planet_2"]["en"]
        atype = asp["aspect"]["en"]
        chart.aspects.append((p1, p2, atype))

    # --- Current Maha Dasa ------------------------------------------------
    dasas = raw["maha_dasas"]["output"]  # already parsed to dict by AstroClient
    for _, dasa in dasas.items():
        start = datetime.fromisoformat(dasa["start_time"])
        end   = datetime.fromisoformat(dasa["end_time"])
        if start <= current_date <= end:
            chart.current_dasa_lord = dasa["Lord"]
            break

    return chart


# ═══════════════════════════════════════════════════════════════════════════════
# 5. INDIVIDUAL SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _dignity_score(planet_name: str, vedic_sign: int) -> float:
    """
    Returns 0–100 based on the planet's Vedic sign dignity.
    Planets not in VEDIC_DIGNITIES table default to 50 (neutral).
    """
    table = VEDIC_DIGNITIES.get(planet_name)
    if table is None:
        return 50.0

    if vedic_sign == table["exalted"]:
        return float(DIGNITY_SCORE["exalted"])
    if vedic_sign in table["own"]:
        return float(DIGNITY_SCORE["own"])
    if vedic_sign in table["enemy"]:
        return float(DIGNITY_SCORE["enemy"])
    if vedic_sign == table["debilitated"]:
        return float(DIGNITY_SCORE["debilitated"])
    if vedic_sign in table["friendly"]:
        return float(DIGNITY_SCORE["friendly"])
    return float(DIGNITY_SCORE["neutral"])


def _shad_bala_score(pct: float) -> float:
    """
    Map percentage_strength (typically 75–200) to 0–100.
    100% = average strength → maps to 50.
    Formula: score = (pct - 50) / 1.50, clipped to [0, 100].
    """
    score = (pct - 50.0) / 1.50
    return max(0.0, min(100.0, score))


def _house_score(house: Optional[int]) -> float:
    """Returns the base house strength score (0–100) for the given house number."""
    if house is None:
        return 50.0
    return float(HOUSE_STRENGTH.get(house, 50))


def _aspect_score(planet_name: str, aspects: list[tuple[str, str, str]]) -> float:
    """
    Aggregate aspect influence on planet_name.
    Returns a score centred at 50 (neutral).
    """
    cumulative = 0
    count = 0
    for p1, p2, atype in aspects:
        other = None
        if p1 == planet_name:
            other = p2
        elif p2 == planet_name:
            other = p1
        else:
            continue

        weight = ASPECT_WEIGHT.get(atype, 0)

        # Conjunction: refine sign based on whether the other planet is benefic/malefic
        if atype == "Conjunction":
            if other in NATURAL_BENEFICS:
                weight = +14
            elif other in NATURAL_MALEFICS:
                weight = -6

        cumulative += weight
        count += 1

    if count == 0:
        return 50.0  # no aspects → neutral

    # Normalise: ±40 raw → ±30 score shift from neutral 50
    raw_avg = cumulative / count
    score = 50.0 + (raw_avg / 20.0) * 30.0
    return max(0.0, min(100.0, score))


def _planet_raw_score(
    planet: PlanetData,
    aspects: list[tuple[str, str, str]],
    retro_mod: int,
) -> float:
    """
    Compute the weighted raw score (0–100) for a single planet.
    """
    dignity  = _dignity_score(planet.name, planet.vedic_sign)
    shad_b   = _shad_bala_score(planet.shad_bala_pct)
    house    = _house_score(planet.vedic_house)
    aspect   = _aspect_score(planet.name, aspects)

    base = dignity * 0.40 + shad_b * 0.25 + house * 0.25 + aspect * 0.10

    # Apply retrograde modifier
    if planet.is_retro:
        base = max(0.0, min(100.0, base + retro_mod))

    return base


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DIMENSION SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def score_dimension(dim_key: str, chart: ChartData) -> dict:
    """
    Score a single personality dimension and return a rich result dict.

    Returns
    -------
    {
        score: float (0–100),
        primary_planet_score: float,
        factors: list[str],   # human-readable explanations
        dasa_active: bool,
    }
    """
    dim = DIMENSIONS[dim_key]
    primary_name = dim["primary_planet"]
    secondary_names = dim["secondary_planets"]
    retro_mod = dim["retro_modifier"]
    power_houses = dim["power_houses"]
    resonant_signs = dim["resonant_signs"]

    factors: list[str] = []

    # --- Score primary planet ---
    primary = chart.planets.get(primary_name)
    if primary is None:
        primary_score = 50.0
        factors.append(f"{primary_name}: not found in chart (defaulting to 50)")
    else:
        primary_score = _planet_raw_score(primary, chart.aspects, retro_mod)

        sign_name = SIGN_NAMES.get(primary.vedic_sign, str(primary.vedic_sign))
        dignity_label = _get_dignity_label(primary_name, primary.vedic_sign)
        retro_tag = " ℞" if primary.is_retro else ""
        house_tag = f"H{primary.vedic_house}" if primary.vedic_house else "—"

        factors.append(
            f"{primary_name} in {sign_name} ({dignity_label}){retro_tag}, "
            f"House {house_tag}, Shad Bala {primary.shad_bala_pct:.0f}%"
        )

    # --- Score secondary planets and blend ---
    secondary_scores: list[float] = []
    for sec_name in secondary_names:
        sec = chart.planets.get(sec_name)
        if sec is None:
            secondary_scores.append(50.0)
            continue
        sec_score = _planet_raw_score(sec, chart.aspects, 0)  # retro_mod not applied to secondaries
        secondary_scores.append(sec_score)

        sign_name = SIGN_NAMES.get(sec.vedic_sign, str(sec.vedic_sign))
        dignity_label = _get_dignity_label(sec_name, sec.vedic_sign)
        retro_tag = " ℞" if sec.is_retro else ""
        house_tag = f"H{sec.vedic_house}" if sec.vedic_house else "—"
        factors.append(
            f"{sec_name} (supporting) in {sign_name} ({dignity_label}){retro_tag}, "
            f"House {house_tag}"
        )

    # Weighted average: primary = 1.5 parts, each secondary = 1.0 part
    total_weight = 1.5 + len(secondary_scores)
    blended = (primary_score * 1.5 + sum(secondary_scores)) / total_weight

    # --- Resonant sign bonus (+4 per primary planet in a resonant sign) ---
    if primary and primary.vedic_sign in resonant_signs:
        blended = min(100.0, blended + 4.0)
        factors.append(f"Resonant sign bonus: {primary_name} in {SIGN_NAMES[primary.vedic_sign]}")

    # --- Power house bonus (+5 if primary planet is in a dimension-specific power house) ---
    if primary and primary.vedic_house in power_houses:
        blended = min(100.0, blended + 5.0)
        factors.append(f"Power house bonus: {primary_name} in H{primary.vedic_house} (key house for this dimension)")

    # --- Current Maha Dasa bonus ---
    dasa_active = (chart.current_dasa_lord == primary_name)
    if dasa_active:
        blended = min(100.0, blended + 8.0)
        factors.append(f"Dasa bonus: {primary_name} Maha Dasa is currently active (+8)")

    return {
        "score": round(blended, 1),
        "primary_planet_score": round(primary_score, 1),
        "factors": factors,
        "dasa_active": dasa_active,
    }


def _get_dignity_label(planet_name: str, sign: int) -> str:
    """Return a human-readable dignity label for a planet/sign pair."""
    table = VEDIC_DIGNITIES.get(planet_name)
    if table is None:
        return "neutral"
    if sign == table["exalted"]:
        return "exalted"
    if sign in table["own"]:
        return "own sign"
    if sign == table["debilitated"]:
        return "debilitated"
    if sign in table["enemy"]:
        return "enemy sign"
    if sign in table["friendly"]:
        return "friendly sign"
    return "neutral"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. FULL SELF MAP BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_self_map(chart: ChartData, birth: dict) -> dict:
    """
    Score all 8 dimensions and assemble the complete Self Map dictionary.
    Includes Nakshatra layer on top of the main 4-factor scoring.
    This is the main entry point called by self_map.py.
    """
    from nakshatra_engine import apply_nakshatra_modifiers

    # --- Step 1: compute raw dimension scores ---
    raw_scores: dict[str, float] = {}
    dim_details: dict[str, dict] = {}
    for dim_key, dim_def in DIMENSIONS.items():
        result = score_dimension(dim_key, chart)
        raw_scores[dim_key] = result["score"]
        dim_details[dim_key] = result

    # --- Step 2: apply Nakshatra modifiers ---
    moon = chart.planets.get("Moon")
    asc  = chart.planets.get("Ascendant")
    moon_degree = moon.full_degree if moon else 0.0
    asc_degree  = asc.full_degree  if asc  else 0.0

    adjusted_scores, nakshatra_meta = apply_nakshatra_modifiers(
        raw_scores, moon_degree, asc_degree
    )

    # --- Step 3: assemble dimension result objects ---
    dimension_results = {}
    for dim_key, dim_def in DIMENSIONS.items():
        score = round(adjusted_scores[dim_key], 1)
        result = dim_details[dim_key]

        if score >= 72:
            band = "strength"
            interpretation = (
                f"Strong {dim_def['label'].lower()} is a natural asset. "
                "Books in this area will resonate deeply and reinforce existing capacity."
            )
            book_pool = dim_def["kitab_high"]
        elif score >= 45:
            band = "balanced"
            interpretation = (
                f"{dim_def['label']} is present and developing. "
                "A mix of enriching and developmental reading works best."
            )
            book_pool = dim_def["kitab_high"][:2] + dim_def["kitab_low"][:2]
        else:
            band = "growth_zone"
            interpretation = (
                f"{dim_def['label']} is an active growth area. "
                "Reading here can unlock significant potential and address blind spots."
            )
            book_pool = dim_def["kitab_low"]

        # Note when Nakshatra boosted this dimension
        nakshatra_boost = round(score - result["score"], 1)
        if nakshatra_boost != 0:
            sign = "+" if nakshatra_boost > 0 else ""
            result["factors"].append(
                f"Nakshatra modifier ({sign}{nakshatra_boost}): "
                f"Moon in {nakshatra_meta['moon']['nakshatra']}"
            )

        dimension_results[dim_key] = {
            "label":                  dim_def["label"],
            "icon":                   dim_def["icon"],
            "description":            dim_def["description"],
            "score":                  score,
            "score_pre_nakshatra":    result["score"],
            "band":                   band,
            "interpretation":         interpretation,
            "primary_planet":         dim_def["primary_planet"],
            "primary_planet_score":   result["primary_planet_score"],
            "dasa_active":            result["dasa_active"],
            "dominant_factors":       result["factors"],
            "recommended_categories": book_pool,
        }

    # Rank growth / strength zones
    sorted_dims = sorted(dimension_results.items(), key=lambda x: x[1]["score"])
    growth_zones = [
        {"dimension": k, "label": v["label"], "score": v["score"],
         "focus": v["recommended_categories"]}
        for k, v in sorted_dims[:3]
    ]
    strength_zones = [
        {"dimension": k, "label": v["label"], "score": v["score"],
         "focus": v["recommended_categories"]}
        for k, v in sorted_dims[-3:][::-1]
    ]

    # Current Dasa theme
    dasa_lord = chart.current_dasa_lord
    dasa_themes = {
        "Sun":     ("Identity & Authority",      ["Leadership", "Biographies of Achievers", "Bhagavad Gita — Action"]),
        "Moon":    ("Emotional Nourishment",     ["Psychology", "Poetry", "Memoir"]),
        "Mars":    ("Action & Courage",          ["Strategy", "Entrepreneurship", "Warrior Philosophy"]),
        "Rahu":    ("Ambition & Worldly Expansion", ["Technology", "Social Philosophy", "Boundary-Pushing Ideas"]),
        "Jupiter": ("Wisdom & Growth",           ["Vedic Texts", "Stoicism", "World Philosophy"]),
        "Saturn":  ("Discipline & Karma",        ["Habits & Systems", "Stoicism", "Long-form Nonfiction"]),
        "Mercury": ("Communication & Learning",  ["Logic & Critical Thinking", "Writing & Rhetoric", "Science"]),
        "Ketu":    ("Detachment & Liberation",   ["Mysticism", "Upanishads", "Minimalism"]),
        "Venus":   ("Relationships & Creativity", ["Art & Aesthetics", "Love & Intimacy", "Literature"]),
    }
    dasa_theme, dasa_books = dasa_themes.get(dasa_lord, ("Life Transition", ["Philosophy", "Self-reflection"]))

    asc_sign       = SIGN_NAMES.get(chart.ascendant_sign, "Unknown")
    moon_sign_name = SIGN_NAMES.get(chart.moon_sign, "Unknown")
    sun_sign_name  = SIGN_NAMES.get(chart.sun_sign, "Unknown")

    return {
        "profile": {
            "birth_data":        birth,
            "ascendant":         asc_sign,
            "moon_sign":         moon_sign_name,
            "sun_sign":          sun_sign_name,
            "current_maha_dasa": dasa_lord,
            "nakshatra":         nakshatra_meta,
        },
        "dimensions":     dimension_results,
        "growth_zones":   growth_zones,
        "strength_zones": strength_zones,
        "current_theme": {
            "maha_dasa_lord":    dasa_lord,
            "theme":             dasa_theme,
            "recommended_books": dasa_books,
        },
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "system":        "freeastrologyapi.com",
            "ayanamsha":     "Lahiri (Vedic) + Tropical (Western aspects)",
            "house_system":  "Equal houses (Jyotish whole-sign-adjacent) + Placidus (Western)",
            "version":       "1.1",
        },
    }
