# Kitab Personality Self Map — Technical Documentation

> **Purpose:** This document explains every step of the logic that transforms a
> person's birth data into an 8-dimension personality Self Map, suitable for
> driving book recommendations on the Kitab platform.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Sources and API Calls](#2-data-sources-and-api-calls)
3. [The 8 Personality Dimensions](#3-the-8-personality-dimensions)
4. [Scoring Algorithm — Step by Step](#4-scoring-algorithm--step-by-step)
5. [Current Life Theme (Maha Dasa)](#5-current-life-theme-maha-dasa)
6. [Dimension → Book Recommendation Mapping](#6-dimension--book-recommendation-mapping)
7. [Output Structure](#7-output-structure)
8. [File Reference](#8-file-reference)
9. [Design Decisions & Rationale](#9-design-decisions--rationale)
10. [Known Limitations & Future Improvements](#10-known-limitations--future-improvements)

---

## 1. System Overview

```
Birth Data (date, time, location)
        │
        ▼
  freeastrologyapi.com  ──┬── Vedic Planets    (Lahiri ayanamsha)
                          ├── Shad Bala        (6-fold strength, Lahiri)
                          ├── Maha Dasa        (Vimsottari Dasa sequence)
                          ├── Western Planets  (Tropical)
                          ├── Western Houses   (Placidus, Tropical)
                          └── Western Aspects  (Tropical)
        │
        ▼
  ChartData object  (normalised, language-agnostic)
        │
        ▼
  Scoring Engine  ──► 8 dimension scores (0–100 each)
        │
        ▼
  Self Map JSON  ──► Radar chart PNG
        │
        ▼
  Kitab Book Recommendations
```

The system deliberately blends **Vedic (Jyotish) astrology** for placement and
strength data with **Western astrology** for aspect analysis. This hybrid
approach is intentional: Jyotish has a richer framework for planetary strength
(Shad Bala) and life timing (Dasa), while Western astrology's aspect orbs and
minor aspects are more nuanced for relational dynamics between planets.

---

## 2. Data Sources and API Calls

All calls go to `https://json.freeastrologyapi.com`. Authentication is via
the `x-api-key` HTTP header.

### 2.1 Vedic Planets — `POST /planets`

Config: `ayanamsha: "lahiri"`, `observation_point: "topocentric"`

**Why topocentric?** Topocentric positions account for the observer's position
on Earth's surface rather than its centre — a small but meaningful correction
for the Moon (can shift it ~1°).

**Why Lahiri?** The Lahiri (Chitrapaksha) ayanamsha is the Indian government's
official standard and is used by the vast majority of Jyotish practitioners.
It represents a ~23.86° offset from the tropical zodiac as of 2024.

**What we use from this response:**
- `current_sign` (1–12): Vedic zodiac sign the planet occupies
- `house_number`: Which of the 12 houses the planet falls in
- `isRetro`: Whether the planet is in apparent retrograde motion
- `fullDegree`: Absolute ecliptic longitude (0–360°)

### 2.2 Shad Bala Summary — `POST /shadbala/summary`

Config: same as above.

Shad Bala ("six strengths") is a comprehensive Vedic planetary strength
calculation developed by Parashara. It covers Sun, Moon, Mars, Mercury,
Jupiter, Venus, and Saturn.

**Components included in the summary:**
| Component | What it measures |
|-----------|-----------------|
| Sthana Bala | Positional strength (sign dignity, house) |
| Dig Bala | Directional strength (planet favoured directions) |
| Kaala Bala | Temporal strength (time of day/year, weekday rulership) |
| Cheshta Bala | Motional strength (orbital speed — slower = stronger) |
| Naisargika Bala | Natural/inherent strength (fixed hierarchy) |
| Drig Bala | Aspectual strength (net aspecting influences) |

**What we use:** `percentage_strength` — the total Shad Bala divided by the
required minimum strength, expressed as a percentage. 100% = exactly average.
Values above 150% indicate an exceptionally strong planet; below 75% is weak.

**Note:** Rahu and Ketu are not included in Shad Bala. They default to 100%
(neutral) in our system.

### 2.3 Vimsottari Maha Dasas — `POST /vimsottari/maha-dasas`

Vimsottari ("120 years") is the primary predictive timing system in Jyotish.
It divides life into sequential planetary periods ruled by the 9 Jyotish planets
(Sun, Moon, Mars, Rahu, Jupiter, Saturn, Mercury, Ketu, Venus) in that order,
totalling 120 years.

The starting planet is determined by the Moon's Nakshatra at birth.

| Planet | Duration |
|--------|----------|
| Sun    | 6 years  |
| Moon   | 10 years |
| Mars   | 7 years  |
| Rahu   | 18 years |
| Jupiter| 16 years |
| Saturn | 19 years |
| Mercury| 17 years |
| Ketu   | 7 years  |
| Venus  | 20 years |

**What we use:** We find which Maha Dasa period contains today's date
(`current_date`). The ruling planet of that period receives a **+8 bonus**
to any dimension where it is the primary planet.

**Why?** The Maha Dasa lord represents what area of life is cosmically
"switched on" right now. A person in Jupiter Dasa will be especially receptive
to wisdom, teaching, and philosophy — which maps directly to Kitab categories.

### 2.4 Western Planets — `POST /western/planets`

Config: `ayanamsha: "tropical"` (no ayanamsha offset — Western standard).

Provides tropical positions including **outer planets** (Uranus, Neptune, Pluto)
and **asteroids** (Chiron, Ceres, Vesta, Juno, Pallas, Lilith) which the Vedic
system doesn't use. We primarily use this endpoint for the aspect calculation
input — the planet positions themselves are used to verify the aspect list.

### 2.5 Western Houses — `POST /western/houses`

Config: `house_system: "Placidus"`, tropical.

Provides the 12 house cusp degrees in the Placidus system. **We do not use
these directly** in scoring — we rely on the Vedic `house_number` field instead.
The Western house data is fetched for completeness and future use (e.g., whole-
sign vs Placidus house comparison).

### 2.6 Western Aspects — `POST /western/aspects`

Config: tropical, default orbs.

Returns all significant aspects between planet pairs within standard orb ranges.

**Why Western aspects instead of Vedic aspects?**
Vedic (Drishti) aspects are full/partial and cast from a planet to specific
houses ahead — e.g., Mars casts full drishti to the 4th, 7th, and 8th houses
from its position. Western aspects are degree-based and bidirectional.

For the purpose of measuring **relational dynamics between planets**, Western
degree-based aspects are more precise and capture subtle interactions (Quintile,
Septile, Novile) that Vedic Drishti doesn't include.

---

## 3. The 8 Personality Dimensions

Each dimension has:
- A **primary planet** (contributes 1.5× weight)
- **Secondary planets** (each contributes 1.0× weight)
- **Power houses** (dimension-specific angular houses)
- **Resonant signs** (signs that amplify this dimension's energy)
- A **Kitab mapping** for both high scorers and growth-zone readers

| # | Dimension | Primary | Secondary | Power Houses | Resonant Signs |
|---|-----------|---------|-----------|-------------|----------------|
| 1 | Intellect & Curiosity | Mercury | Sun | 3, 6, 1 | Gemini, Virgo, Aquarius |
| 2 | Emotional Intelligence | Moon | Venus | 4, 12, 1 | Cancer, Scorpio, Pisces |
| 3 | Drive & Vitality | Mars | Sun | 1, 10, 3 | Aries, Leo, Sagittarius |
| 4 | Relational Harmony | Venus | Jupiter, Moon | 7, 11, 5 | Taurus, Libra, Pisces |
| 5 | Discipline & Structure | Saturn | Mars | 10, 6, 11 | Capricorn, Aquarius, Virgo |
| 6 | Philosophical Wisdom | Jupiter | Sun, Ketu | 9, 12, 5 | Sagittarius, Pisces, Cancer |
| 7 | Creativity & Expression | Sun | Venus, Moon | 5, 1, 3 | Leo, Taurus, Libra |
| 8 | Resilience & Transformation | Saturn | Mars, Rahu | 8, 12, 6 | Scorpio, Capricorn, Aries |

### Why these 8 dimensions?

These cover the key axes of the **human personality relevant to reading**:

- **Intellect** — which ideas a person can engage with and at what depth
- **Emotion** — what emotional themes resonate (psychology, poetry, memoir)
- **Drive** — appetite for action-oriented content (biography, leadership)
- **Relational** — interest in human dynamics and connection
- **Discipline** — affinity for structured, long-form, systems thinking
- **Wisdom** — philosophical and spiritual seeking (the Gita, Stoics)
- **Creativity** — aesthetic sensibility and narrative engagement
- **Resilience** — capacity for depth, shadow work, transformation narratives

They also map cleanly onto the **Purusharthas** (four aims of life in Vedic
philosophy):
- **Dharma** (righteous duty) → Discipline + Philosophical Wisdom
- **Artha** (wealth/achievement) → Drive + Intellect
- **Kama** (desire/pleasure) → Relational + Creativity
- **Moksha** (liberation) → Resilience + Emotional Intelligence

---

## 4. Scoring Algorithm — Step by Step

### Step 1: Dignity Score (weight = 40%)

The planet's sign placement is assessed against the **Parashara dignity table**:

| Dignity | Description | Score |
|---------|-------------|-------|
| Exalted (Uccha) | Planet at greatest strength in this sign | 100 |
| Own Sign (Swakshetra) | Planet rules this sign | 85 |
| Friendly Sign (Mitra) | Sign ruled by a friendly planet | 65 |
| Neutral (Sama) | No special relationship | 50 |
| Enemy Sign (Shatru) | Sign ruled by an enemy planet | 32 |
| Debilitated (Neecha) | Planet at weakest in this sign | 18 |

**Vedic dignity table used (Parashara standard):**

| Planet | Own | Exalted | Debilitated | Friendly Signs | Enemy Signs |
|--------|-----|---------|-------------|---------------|-------------|
| Sun | Leo | Aries | Libra | Aries, Sag, Cancer | Aquarius, Libra |
| Moon | Cancer | Taurus | Scorpio | Leo, Aries | — |
| Mars | Aries, Scorpio | Capricorn | Cancer | Leo, Sag, Pisces | Gemini, Virgo |
| Mercury | Gemini, Virgo | Virgo | Pisces | Leo, Libra, Taurus | Scorpio |
| Jupiter | Sag, Pisces | Cancer | Capricorn | Aries, Cancer, Leo | Gemini, Virgo |
| Venus | Taurus, Libra | Pisces | Virgo | Gemini, Scorpio, Cap | Leo, Sag |
| Saturn | Cap, Aquarius | Libra | Aries | Gemini, Virgo, Aqu | Leo, Cancer, Sag |
| Rahu | — | Gemini | Sag | Gemini, Virgo, Aqu | Sag, Leo, Cancer |
| Ketu | — | Sag | Gemini | Sag, Leo, Cancer | Gemini, Virgo, Aqu |

**Retrograde modifier:**
When a planet is retrograde (℞), it moves inward and becomes more introspective.
This does not reduce strength — it changes its *expression*:

| Planet | Retro modifier |
|--------|---------------|
| Mercury | +6 (deep thinking, research, internalized learning) |
| Saturn | +5 (crystallised inner discipline) |
| Mars | −5 (energy turns inward; reduced outward assertion) |
| Venus | −4 (relational energy withdrawn; introspective creativity) |
| Jupiter | +4 (deeper philosophical seeking) |
| Others | 0 |

### Step 2: Shad Bala Score (weight = 25%)

`percentage_strength` from the API ranges roughly 75–200%.

Mapping formula:
```
shad_bala_score = clamp((percentage_strength − 50) / 1.5, 0, 100)
```

Examples:
- 100% → score 33  (slightly below average due to asymmetric normalisation)
- 130% → score 53  (above average)
- 160% → score 73  (strong)
- 75%  → score 17  (weak)

This was chosen over a linear normalisation because most planets cluster between
100–160%, so this formula spreads the distribution more usefully.

### Step 3: House Score (weight = 25%)

Based on the `house_number` field from the Vedic planets endpoint.

**Jyotish house strength classification:**

| Houses | Type | Score | Notes |
|--------|------|-------|-------|
| 1, 10, 7, 4 | Kendra (Angular) | 100, 95, 90, 85 | Most powerful; action houses |
| 5, 11, 2, 8 | Panaphar (Succedent) | 75, 70, 65, 60 | Moderate strength |
| 9 | Trikona (Trine) | 68 | Technically cadent but highly benefic |
| 12, 3, 6 | Apoklima (Cadent) | 48, 42, 38 | Lower activity, but 12th has spiritual value |

**Dimension-specific power house bonus (+5):**
If the primary planet is in one of the dimension's designated power houses, an
additional +5 is added to the final dimension score. This captures specificity —
Mercury in the 3rd house is more *directly* relevant to intellect than Mercury
in the 10th house, even if the 10th house gives higher general strength.

### Step 4: Aspect Score (weight = 10%)

For each aspect involving the primary planet, apply the following weights:

| Aspect | Weight | Interpretation |
|--------|--------|---------------|
| Trine | +20 | Harmonious flow; planet expresses easily |
| Sextile | +12 | Opportunity; planet has support |
| Conjunction (with benefic) | +14 | Strengthened by aligned energy |
| Conjunction (with malefic) | −6 | Complicated by conflicting energy |
| Semi-Sextile | +4 | Minor support |
| Quintile | +6 | Creative talent aspect |
| Septile | +3 | Subtle, fate-linked |
| Novile | +3 | Spiritual gift |
| Quincunx | −5 | Adjustment needed; awkward angle |
| Octile (Semi-square) | −4 | Friction |
| Sesquiquadrate | −6 | Persistent internal tension |
| Opposition | −8 | Pulled in two directions; awareness through conflict |
| Square | −14 | Challenge, tension, friction — growth through difficulty |

Normalisation: raw average weight → score centred at 50.
```
aspect_score = 50 + (raw_avg / 20) × 30,   clipped to [0, 100]
```

Natural benefics (Jupiter, Venus, Moon, Mercury) in Conjunction boost the
target planet. Natural malefics (Saturn, Mars, Sun, Rahu, Ketu) in Conjunction
reduce it.

### Step 5: Planet Blending

```
dimension_score = (primary × 1.5 + secondary_1 × 1.0 + secondary_2 × 1.0 + …)
                  / (1.5 + number_of_secondaries)
```

Each planet's individual score is computed through Steps 1–4 before blending.

### Step 6: Resonant Sign Bonus (+4)

If the primary planet occupies one of the dimension's resonant signs,
+4 is added. This is a small but meaningful bonus reflecting that the planet
is operating in a sign that is thematically aligned with the dimension.
Example: Moon in Cancer for Emotional Intelligence — canonical resonance.

### Step 7: Power House Bonus (+5)

If the primary planet is in one of the dimension's designated power houses,
+5 is added. See Step 3 for the house list per dimension.

### Step 8: Maha Dasa Bonus (+8)

If the current Maha Dasa lord matches the primary planet, +8 is added.
This represents temporal activation — the planet is not only strong in the
chart but is actively ruling the current life phase.

### Final Formula

```
raw   = dignity×0.40 + shad_bala×0.25 + house×0.25 + aspects×0.10
blended  = weighted_blend(primary×1.5, secondaries×1.0)
final = blended + resonant_sign_bonus + power_house_bonus + dasa_bonus
final = clamp(final, 0, 100)
```

### Score Bands

| Score | Band | Meaning for Kitab |
|-------|------|------------------|
| 72–100 | Strength | Natural resonance; deep books in this area will land strongly |
| 45–71 | Balanced | Both enriching and developmental books work |
| 0–44 | Growth Zone | Highest leverage reading; can unlock blind spots |

---

## 5. Current Life Theme (Maha Dasa)

The current Maha Dasa lord is identified by checking which period in the
Vimsottari sequence contains today's date.

Each lord has an associated life theme and Kitab book focus:

| Dasa Lord | Theme | Kitab Focus |
|-----------|-------|-------------|
| Sun | Identity & Authority | Leadership, Biographies, Bhagavad Gita — Action |
| Moon | Emotional Nourishment | Psychology, Poetry, Memoir |
| Mars | Action & Courage | Strategy, Entrepreneurship, Warrior Philosophy |
| Rahu | Ambition & Worldly Expansion | Technology, Social Philosophy, Boundary-Pushing Ideas |
| Jupiter | Wisdom & Growth | Vedic Texts, Stoicism, World Philosophy |
| Saturn | Discipline & Karma | Habits & Systems, Stoicism, Long-form Nonfiction |
| Mercury | Communication & Learning | Logic, Writing & Rhetoric, Science |
| Ketu | Detachment & Liberation | Mysticism, Upanishads, Minimalism |
| Venus | Relationships & Creativity | Art & Aesthetics, Love & Intimacy, Literature |

This is surfaced separately from the dimension scores as the **"current life
theme"** — it tells Kitab which thematic lens is most active right now,
independent of the static personality traits.

---

## 6. Dimension → Book Recommendation Mapping

### High Score (Strength Zone) → Deepen and Enrich

| Dimension | Kitab Categories |
|-----------|-----------------|
| Intellect | Philosophy, Science & Technology, Logic & Critical Thinking, Linguistics |
| Emotional Intelligence | Psychology, Poetry & Literature, Memoir & Biography, Depth Psychology |
| Drive & Vitality | Leadership, Entrepreneurship, Biographies of Achievers, Strategy |
| Relational Harmony | Communication, Relationships & Love, Social Philosophy, Diplomacy |
| Discipline & Structure | Systems Thinking, Productivity, Health & Longevity, Stoicism |
| Philosophical Wisdom | Vedic Texts, Stoicism, World Religions, The Bhagavad Gita |
| Creativity & Expression | Art & Aesthetics, Literature, Creative Process, Music & Sound |
| Resilience & Transformation | Shadow Work, Mythology & Archetypes, Transformation Narratives |

### Low Score (Growth Zone) → Develop and Unlock

| Dimension | Kitab Categories |
|-----------|-----------------|
| Intellect | Mental Models, Clear Thinking, Cognitive Biases, Memory & Learning |
| Emotional Intelligence | Emotional Literacy, Self-Compassion, Attachment Theory, Mindfulness |
| Drive & Vitality | Motivation & Drive, Overcoming Inertia, Energy Management, Courage |
| Relational Harmony | Conflict Resolution, Vulnerability & Trust, Social Skills |
| Discipline & Structure | Habits & Routines, Time Management, Simplicity, Willpower |
| Philosophical Wisdom | Introduction to Philosophy, Meaning-Making, Vedanta Basics |
| Creativity & Expression | Unlocking Creativity, Play & Imagination, Artist's Way |
| Resilience & Transformation | Resilience & Grit, Coping, Growth Mindset, Crisis Navigation |

---

## 7. Output Structure

The `generate_self_map()` function returns:

```json
{
  "self_map": {
    "profile": {
      "birth_data": { "year": ..., "month": ..., ... },
      "ascendant":  "Cancer",
      "moon_sign":  "Sagittarius",
      "sun_sign":   "Taurus",
      "current_maha_dasa": "Rahu"
    },
    "dimensions": {
      "intellect": {
        "label": "Intellect & Curiosity",
        "icon": "🧠",
        "description": "Analytical depth...",
        "score": 71.4,
        "band": "balanced",
        "interpretation": "...",
        "primary_planet": "Mercury",
        "primary_planet_score": 68.2,
        "dasa_active": false,
        "dominant_factors": [
          "Mercury in Aries (enemy sign)℞, House H10, Shad Bala 127%",
          "Sun (supporting) in Taurus (neutral), House H11"
        ],
        "recommended_categories": ["Philosophy", "Science & Technology", ...]
      },
      ...  (7 more dimensions)
    },
    "growth_zones": [
      { "dimension": "discipline_structure", "label": "...", "score": 38.2, "focus": [...] },
      ...  (top 3 lowest)
    ],
    "strength_zones": [
      { "dimension": "philosophical_wisdom", "label": "...", "score": 79.1, "focus": [...] },
      ...  (top 3 highest)
    ],
    "current_theme": {
      "maha_dasa_lord": "Rahu",
      "theme": "Ambition & Worldly Expansion",
      "recommended_books": ["Technology", "Social Philosophy", "Boundary-Pushing Ideas"]
    },
    "metadata": {
      "generated_at": "2024-01-15T10:30:00",
      "system": "freeastrologyapi.com",
      "ayanamsha": "Lahiri (Vedic) + Tropical (Western aspects)",
      "house_system": "Equal houses (Jyotish) + Placidus (Western)",
      "version": "1.0"
    }
  },
  "chart_path": "./self_map_Arjun_Sharma.png",
  "raw_data": { ... }  // full API responses for debugging
}
```

---

## 8. File Reference

| File | Role |
|------|------|
| `astro_client.py` | HTTP wrapper for freeastrologyapi.com. All 6 API calls. |
| `scoring_engine.py` | All scoring logic: dignity tables, house weights, aspect weights, dimension definitions, `parse_chart()`, `build_self_map()`. |
| `self_map.py` | Orchestration pipeline. Calls `AstroClient`, then `parse_chart`, then `build_self_map`. CLI entry point. |
| `visualizer.py` | Matplotlib radar chart generation. Produces the spider-web PNG. |
| `example.py` | Three demo birth profiles; quick validation and demonstration. |
| `requirements.txt` | Python dependencies: `requests`, `matplotlib`, `numpy`. |

---

## 9. Design Decisions & Rationale

### Why not use only Vedic or only Western?

Vedic astrology has:
- More sophisticated **planetary strength** (Shad Bala — 6 components)
- **Life timing** (Dasa systems) that Western lacks
- A richer tradition around personality psychology (Jyotish texts)

Western astrology has:
- More **aspect variety** (12 aspects vs Vedic's 5 major aspects)
- **Outer planets** (Uranus/Neptune/Pluto — generational influences)
- More developed **psychological interpretation** language

The hybrid approach extracts the best of both.

### Why 8 dimensions?

- 8 is visually ideal for a radar chart (axes are evenly spaced at 45°)
- 8 maps cleanly onto the 4 Purusharthas × 2 = 8 sub-categories
- Fewer dimensions (e.g., 5) would be too coarse for useful book targeting
- More dimensions (e.g., 12) would be noisy given the data available

### Why Lahiri ayanamsha?

Lahiri is the official ayanamsha of the Indian government (N.C. Lahiri, 1955)
and is used by ~80% of Jyotish practitioners. It's the safe default.

### Why Placidus houses (Western)?

Placidus is the most widely used house system in Western astrology (~80% usage).
For the Vedic layer, the house numbers come directly from the API (which uses
Jyotish whole-sign-adjacent calculation) rather than from the Placidus cusps.

### Why not use Navamsa (D9) or other divisional charts?

The D1 (birth chart) + Shad Bala provides sufficient signal for personality
profiling. Navamsa (D9) is critical for marriage timing and dharma, and could
be added as a future layer — particularly for the Relational and Philosophical
Wisdom dimensions.

---

## 10. Known Limitations & Future Improvements

### Limitations

1. **No exact-degree dignity refinement.** We use sign-level dignity (exalted/
   own/friendly/neutral/enemy/debilitated) but not exact degree (e.g., deep
   exaltation at specific degrees like Sun at 10° Aries).

2. **Rahu/Ketu Shad Bala.** Rahu and Ketu are not included in Shad Bala.
   They default to 100% strength. In practice, Rahu is often very strong
   (it amplifies whatever it touches), so this is a conservative fallback.

3. **No Nakshatra personality layer.** The Moon's birth Nakshatra is one of
   the richest personality indicators in Jyotish (27 Nakshatras with distinct
   deities, qualities, and psychological profiles). Adding Nakshatra-based
   dimension modifiers would significantly improve accuracy.

4. **No Ashtakavarga.** Ashtakavarga assigns benefic/malefic points to each
   sign-house combination. High Ashtakavarga points in the relevant house would
   strengthen the score for that dimension.

5. **Aspect interpretation is aggregate.** We sum all aspects to the primary
   planet without weighting by aspect tightness (orb). A 1° orb square is much
   stronger than a 7° orb square.

### Planned Improvements

- [ ] Nakshatra personality layer (fetch `nakshatra-durations` and map
      `moon_nakshatra` → personality modifiers per dimension)
- [ ] Ashtakavarga integration (`/ashtakavarga` endpoint)
- [ ] Exact-degree dignity (deep exaltation/debilitation)
- [ ] Antar Dasa (sub-period) as secondary temporal layer
- [ ] User feedback loop — Kitab reading behaviour as signal to calibrate weights
- [ ] Ascendant-based house emphasis (e.g., Scorpio ascendant naturally emphasises
      the 8th house / Resilience dimension)
- [ ] D9 Navamsa for deeper Relational + Philosophical scoring
