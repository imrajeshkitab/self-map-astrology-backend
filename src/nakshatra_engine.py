"""
nakshatra_engine.py
-------------------
Vedic Nakshatra (lunar mansion) layer for the Self Map.

The 27 Nakshatras divide the 360° sidereal zodiac into equal 13°20' segments.
They are the most granular personality indicator in Jyotish — far more specific
than the 12 rasis (signs).

What this module does
---------------------
1. Compute which Nakshatra a planet occupies from its sidereal full-degree.
2. Apply personality dimension modifiers from the Moon's Nakshatra (Janma
   Nakshatra — the most important) and the Ascendant's Nakshatra.
3. Return rich Nakshatra metadata (name, deity, symbol, quality, traits) for
   display in the output JSON and radar chart.

Scoring contribution
--------------------
Moon Nakshatra modifiers  : weight 1.0  (primary personality imprint)
Ascendant Nakshatra mods  : weight 0.5  (outer personality / physical self)
Modifier range            : ±3 to ±5 per dimension (intentionally small so as
                            not to overwhelm the main 4-factor score)
"""

from __future__ import annotations
from typing import Optional

# Each Nakshatra spans 360/27 = 13.3333...°
NAKSHATRA_SPAN = 360.0 / 27.0

# ═══════════════════════════════════════════════════════════════════════════════
# 27 Nakshatra definitions
# ═══════════════════════════════════════════════════════════════════════════════
# dimension_modifiers maps Self Map dimension key → point delta (+/-)
# Only dimensions that are meaningfully influenced are listed (omitted = 0).
# Values kept in range ±3 to ±5 to stay a subtle but real influence.

NAKSHATRAS: dict[int, dict] = {
    1: {
        "name": "Ashwini",
        "deity": "Ashwini Kumars (divine healers)",
        "symbol": "Horse's Head",
        "ruling_planet": "Ketu",
        "quality": "Sharp & Swift",
        "element": "Fire",
        "core_traits": ["speed", "initiative", "healing instinct", "adventure"],
        "dimension_modifiers": {
            "drive_vitality":            +5,
            "intellect":                 +3,
        },
    },
    2: {
        "name": "Bharani",
        "deity": "Yama (god of death & dharma)",
        "symbol": "Yoni (womb)",
        "ruling_planet": "Venus",
        "quality": "Fixed & Fierce",
        "element": "Earth",
        "core_traits": ["transformation", "intensity", "willpower", "deep creativity"],
        "dimension_modifiers": {
            "resilience_transformation": +5,
            "creativity_expression":     +3,
            "drive_vitality":            +2,
        },
    },
    3: {
        "name": "Krittika",
        "deity": "Agni (fire god)",
        "symbol": "Razor / Flame",
        "ruling_planet": "Sun",
        "quality": "Mixed",
        "element": "Fire",
        "core_traits": ["critical mind", "precision", "courage", "purification"],
        "dimension_modifiers": {
            "intellect":                 +4,
            "discipline_structure":      +3,
            "drive_vitality":            +2,
        },
    },
    4: {
        "name": "Rohini",
        "deity": "Brahma (creator)",
        "symbol": "Chariot / Ox Cart",
        "ruling_planet": "Moon",
        "quality": "Fixed",
        "element": "Earth",
        "core_traits": ["creativity", "sensuality", "fertility", "beauty", "groundedness"],
        "dimension_modifiers": {
            "creativity_expression":     +5,
            "relational_harmony":        +4,
            "emotional_intelligence":    +3,
        },
    },
    5: {
        "name": "Mrigashira",
        "deity": "Soma (Moon god)",
        "symbol": "Deer's Head",
        "ruling_planet": "Mars",
        "quality": "Soft",
        "element": "Air",
        "core_traits": ["curiosity", "seeking", "restlessness", "gentle mind"],
        "dimension_modifiers": {
            "intellect":                 +5,
            "philosophical_wisdom":      +3,
        },
    },
    6: {
        "name": "Ardra",
        "deity": "Rudra (storm god)",
        "symbol": "Teardrop / Diamond",
        "ruling_planet": "Rahu",
        "quality": "Sharp",
        "element": "Water",
        "core_traits": ["intensity", "emotional storms", "empathy through suffering", "research depth"],
        "dimension_modifiers": {
            "emotional_intelligence":    +5,
            "resilience_transformation": +4,
            "intellect":                 +2,
        },
    },
    7: {
        "name": "Punarvasu",
        "deity": "Aditi (mother of gods)",
        "symbol": "Quiver of Arrows",
        "ruling_planet": "Jupiter",
        "quality": "Moveable",
        "element": "Air",
        "core_traits": ["renewal", "optimism", "generosity", "returning home"],
        "dimension_modifiers": {
            "relational_harmony":        +4,
            "philosophical_wisdom":      +4,
            "emotional_intelligence":    +2,
        },
    },
    8: {
        "name": "Pushya",
        "deity": "Brihaspati (Jupiter, teacher of gods)",
        "symbol": "Flower / Circle",
        "ruling_planet": "Saturn",
        "quality": "Moveable",
        "element": "Water",
        "core_traits": ["nurturing", "discipline", "dharma", "nourishment of others"],
        "dimension_modifiers": {
            "emotional_intelligence":    +4,
            "discipline_structure":      +4,
            "philosophical_wisdom":      +2,
        },
    },
    9: {
        "name": "Ashlesha",
        "deity": "Nagas (serpent deities)",
        "symbol": "Serpent",
        "ruling_planet": "Mercury",
        "quality": "Sharp",
        "element": "Water",
        "core_traits": ["penetrating insight", "secrecy", "intuition", "kundalini energy"],
        "dimension_modifiers": {
            "resilience_transformation": +5,
            "emotional_intelligence":    +3,
            "intellect":                 +3,
        },
    },
    10: {
        "name": "Magha",
        "deity": "Pitrus (ancestral spirits)",
        "symbol": "Throne / Palanquin",
        "ruling_planet": "Ketu",
        "quality": "Fierce",
        "element": "Fire",
        "core_traits": ["nobility", "ancestral power", "authority", "pride"],
        "dimension_modifiers": {
            "drive_vitality":            +4,
            "philosophical_wisdom":      +3,
            "discipline_structure":      +2,
        },
    },
    11: {
        "name": "Purva Phalguni",
        "deity": "Bhaga (god of pleasure & union)",
        "symbol": "Front legs of a Bed",
        "ruling_planet": "Venus",
        "quality": "Fierce",
        "element": "Water",
        "core_traits": ["pleasure", "creativity", "romance", "relaxation", "generosity"],
        "dimension_modifiers": {
            "creativity_expression":     +5,
            "relational_harmony":        +4,
        },
    },
    12: {
        "name": "Uttara Phalguni",
        "deity": "Aryaman (god of contracts & unions)",
        "symbol": "Back legs of a Bed",
        "ruling_planet": "Sun",
        "quality": "Fixed",
        "element": "Fire",
        "core_traits": ["duty", "patronage", "partnerships", "stability", "generosity"],
        "dimension_modifiers": {
            "relational_harmony":        +4,
            "discipline_structure":      +3,
        },
    },
    13: {
        "name": "Hasta",
        "deity": "Savitar (sun of skill)",
        "symbol": "Hand / Fist",
        "ruling_planet": "Moon",
        "quality": "Light",
        "element": "Earth",
        "core_traits": ["craftsmanship", "dexterity", "wit", "resourcefulness"],
        "dimension_modifiers": {
            "intellect":                 +4,
            "creativity_expression":     +4,
        },
    },
    14: {
        "name": "Chitra",
        "deity": "Vishwakarma (divine architect)",
        "symbol": "Bright Jewel / Pearl",
        "ruling_planet": "Mars",
        "quality": "Soft",
        "element": "Fire",
        "core_traits": ["artistry", "brilliance", "perfectionism", "charm"],
        "dimension_modifiers": {
            "creativity_expression":     +5,
            "intellect":                 +3,
            "relational_harmony":        +2,
        },
    },
    15: {
        "name": "Swati",
        "deity": "Vayu (wind god)",
        "symbol": "Sword / Young Sprout",
        "ruling_planet": "Rahu",
        "quality": "Moveable",
        "element": "Air",
        "core_traits": ["independence", "balance", "diplomacy", "flexibility"],
        "dimension_modifiers": {
            "relational_harmony":        +4,
            "philosophical_wisdom":      +3,
            "drive_vitality":            +2,
        },
    },
    16: {
        "name": "Vishakha",
        "deity": "Indra & Agni",
        "symbol": "Decorated Gateway",
        "ruling_planet": "Jupiter",
        "quality": "Mixed",
        "element": "Fire",
        "core_traits": ["focus", "determination", "ambition", "goal-orientation"],
        "dimension_modifiers": {
            "drive_vitality":            +4,
            "discipline_structure":      +4,
        },
    },
    17: {
        "name": "Anuradha",
        "deity": "Mitra (god of friendship)",
        "symbol": "Lotus / Umbrella",
        "ruling_planet": "Saturn",
        "quality": "Soft",
        "element": "Water",
        "core_traits": ["devotion", "friendship", "teamwork", "travel toward success"],
        "dimension_modifiers": {
            "relational_harmony":        +5,
            "emotional_intelligence":    +3,
        },
    },
    18: {
        "name": "Jyeshtha",
        "deity": "Indra (king of gods)",
        "symbol": "Circular Amulet / Umbrella",
        "ruling_planet": "Mercury",
        "quality": "Sharp",
        "element": "Water",
        "core_traits": ["leadership", "seniority", "power", "responsibility"],
        "dimension_modifiers": {
            "drive_vitality":            +4,
            "philosophical_wisdom":      +3,
            "discipline_structure":      +2,
        },
    },
    19: {
        "name": "Mula",
        "deity": "Nirriti (goddess of dissolution)",
        "symbol": "Bunch of Roots / Tied Reins",
        "ruling_planet": "Ketu",
        "quality": "Sharp",
        "element": "Fire",
        "core_traits": ["investigation", "getting to roots", "liberation", "destruction of illusion"],
        "dimension_modifiers": {
            "philosophical_wisdom":      +5,
            "resilience_transformation": +4,
        },
    },
    20: {
        "name": "Purva Ashadha",
        "deity": "Apas (water goddess)",
        "symbol": "Fan / Winnowing Basket",
        "ruling_planet": "Venus",
        "quality": "Fierce",
        "element": "Air",
        "core_traits": ["invincibility", "perseverance", "pride", "purification"],
        "dimension_modifiers": {
            "drive_vitality":            +4,
            "resilience_transformation": +3,
        },
    },
    21: {
        "name": "Uttara Ashadha",
        "deity": "Vishvadevas (universal gods)",
        "symbol": "Elephant Tusk / Small Bed",
        "ruling_planet": "Sun",
        "quality": "Fixed",
        "element": "Earth",
        "core_traits": ["ultimate victory", "dharma", "ethics", "introspection", "integrity"],
        "dimension_modifiers": {
            "philosophical_wisdom":      +5,
            "discipline_structure":      +4,
            "resilience_transformation": +2,
        },
    },
    22: {
        "name": "Shravana",
        "deity": "Vishnu (preserver)",
        "symbol": "Ear / Three Footprints",
        "ruling_planet": "Moon",
        "quality": "Moveable",
        "element": "Air",
        "core_traits": ["learning by listening", "wisdom", "connecting", "steady progress"],
        "dimension_modifiers": {
            "intellect":                 +4,
            "philosophical_wisdom":      +4,
        },
    },
    23: {
        "name": "Dhanishtha",
        "deity": "Ashta Vasus (elemental gods)",
        "symbol": "Drum / Flute",
        "ruling_planet": "Mars",
        "quality": "Moveable",
        "element": "Air",
        "core_traits": ["wealth", "music", "rhythm", "Mars energy", "social connections"],
        "dimension_modifiers": {
            "creativity_expression":     +4,
            "drive_vitality":            +3,
        },
    },
    24: {
        "name": "Shatabhisha",
        "deity": "Varuna (god of cosmic order)",
        "symbol": "Circle / 1000 Stars",
        "ruling_planet": "Rahu",
        "quality": "Moveable",
        "element": "Air",
        "core_traits": ["healing", "mystery", "independence", "scientific thinking"],
        "dimension_modifiers": {
            "resilience_transformation": +4,
            "intellect":                 +4,
        },
    },
    25: {
        "name": "Purva Bhadrapada",
        "deity": "Aja Ekapada (one-footed goat)",
        "symbol": "Swords / Front of Funeral Cot",
        "ruling_planet": "Jupiter",
        "quality": "Fierce",
        "element": "Fire",
        "core_traits": ["intensity", "otherworldly", "transformation", "spiritual fire"],
        "dimension_modifiers": {
            "resilience_transformation": +5,
            "drive_vitality":            +3,
        },
    },
    26: {
        "name": "Uttara Bhadrapada",
        "deity": "Ahir Budhnya (serpent of the deep)",
        "symbol": "Twins / Back of Funeral Cot",
        "ruling_planet": "Saturn",
        "quality": "Fixed",
        "element": "Water",
        "core_traits": ["depth", "wisdom", "ethics", "hidden knowledge", "compassion"],
        "dimension_modifiers": {
            "philosophical_wisdom":      +5,
            "emotional_intelligence":    +3,
        },
    },
    27: {
        "name": "Revati",
        "deity": "Pushan (nurturer of flocks)",
        "symbol": "Fish / Drum",
        "ruling_planet": "Mercury",
        "quality": "Soft",
        "element": "Water",
        "core_traits": ["completion", "compassion", "spirituality", "journeys", "abundance"],
        "dimension_modifiers": {
            "philosophical_wisdom":      +4,
            "emotional_intelligence":    +4,
            "relational_harmony":        +2,
        },
    },
}

# Pada (quarter) names — each Nakshatra has 4 padas of 3°20' each
PADA_NAVAMSA = ["Aries", "Taurus", "Gemini", "Cancer",
                "Leo", "Virgo", "Libra", "Scorpio",
                "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


# ═══════════════════════════════════════════════════════════════════════════════
# Core calculation
# ═══════════════════════════════════════════════════════════════════════════════

def get_nakshatra(sidereal_degree: float) -> dict:
    """
    Given a planet's sidereal full degree (0–360), return its Nakshatra data.

    Returns
    -------
    dict with keys: number (1-27), name, pada (1-4), pada_sign,
                    and all fields from NAKSHATRAS[number]
    """
    degree = sidereal_degree % 360.0
    index = int(degree / NAKSHATRA_SPAN)          # 0-based index → 0-26
    number = index + 1                             # 1-27

    # Pada (quarter): each Nakshatra is divided into 4 equal parts
    position_within = degree - index * NAKSHATRA_SPAN
    pada = int(position_within / (NAKSHATRA_SPAN / 4.0)) + 1  # 1-4
    pada = min(pada, 4)  # clamp for floating-point edge cases

    # The Navamsa sign for this pada cycles through all 12 signs
    # starting from Aries for Ashwini pada 1.
    pada_navamsa_index = ((number - 1) * 4 + (pada - 1)) % 12
    pada_sign = PADA_NAVAMSA[pada_navamsa_index]

    result = dict(NAKSHATRAS[number])   # shallow copy
    result["number"] = number
    result["pada"] = pada
    result["pada_sign"] = pada_sign
    result["degree_in_nakshatra"] = round(position_within, 4)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Dimension modifier application
# ═══════════════════════════════════════════════════════════════════════════════

def apply_nakshatra_modifiers(
    dimension_scores: dict[str, float],
    moon_degree: float,
    ascendant_degree: float,
) -> tuple[dict[str, float], dict]:
    """
    Apply Nakshatra-based dimension modifiers and return updated scores
    plus Nakshatra metadata.

    Parameters
    ----------
    dimension_scores : dict[str, float]
        Pre-computed dimension scores from the main scoring engine.
    moon_degree : float
        Moon's sidereal full degree (0-360).
    ascendant_degree : float
        Ascendant's sidereal full degree (0-360).

    Returns
    -------
    (updated_scores, nakshatra_meta)
        updated_scores : dict[str, float] — scores with Nakshatra modifiers applied
        nakshatra_meta : dict — rich Nakshatra info for output / display
    """
    moon_nak  = get_nakshatra(moon_degree)
    asc_nak   = get_nakshatra(ascendant_degree)

    updated = dict(dimension_scores)

    # Moon Nakshatra modifiers — full weight (1.0)
    for dim, delta in moon_nak.get("dimension_modifiers", {}).items():
        if dim in updated:
            updated[dim] = max(0.0, min(100.0, updated[dim] + delta * 1.0))

    # Ascendant Nakshatra modifiers — half weight (0.5)
    for dim, delta in asc_nak.get("dimension_modifiers", {}).items():
        if dim in updated:
            updated[dim] = max(0.0, min(100.0, updated[dim] + delta * 0.5))

    nakshatra_meta = {
        "moon": {
            "nakshatra":     moon_nak["name"],
            "number":        moon_nak["number"],
            "pada":          moon_nak["pada"],
            "pada_sign":     moon_nak["pada_sign"],
            "ruling_planet": moon_nak["ruling_planet"],
            "deity":         moon_nak["deity"],
            "symbol":        moon_nak["symbol"],
            "quality":       moon_nak["quality"],
            "element":       moon_nak["element"],
            "core_traits":   moon_nak["core_traits"],
            "boosted_dimensions": [
                k for k, v in moon_nak.get("dimension_modifiers", {}).items() if v > 0
            ],
        },
        "ascendant": {
            "nakshatra":     asc_nak["name"],
            "number":        asc_nak["number"],
            "pada":          asc_nak["pada"],
            "pada_sign":     asc_nak["pada_sign"],
            "ruling_planet": asc_nak["ruling_planet"],
            "deity":         asc_nak["deity"],
            "symbol":        asc_nak["symbol"],
            "quality":       asc_nak["quality"],
            "element":       asc_nak["element"],
            "core_traits":   asc_nak["core_traits"],
        },
    }

    return updated, nakshatra_meta
