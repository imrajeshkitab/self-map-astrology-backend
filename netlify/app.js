/* ── Self Map Frontend ────────────────────────────────────────────── *
 * Flow:
 *   1. POST /api/v1/self-map  → triggers backend computation
 *   2. Read X-Cache-Key header from response
 *   3. GET  /api/v1/{key}/json → personality scores + profile
 *   4. Show chart as <img src="/api/v1/{key}/chart">
 * ──────────────────────────────────────────────────────────────────── */

// LOCAL DEV: point to your running FastAPI backend
// PRODUCTION (Netlify): change back to '' — the netlify.toml proxy takes over
const API_BASE = 'http://localhost:8000';

// ── View helpers ────────────────────────────────────────────────────

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

// ── Geolocation ─────────────────────────────────────────────────────

document.getElementById('geo-btn').addEventListener('click', () => {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(pos => {
    document.getElementById('lat').value = pos.coords.latitude.toFixed(4);
    document.getElementById('lon').value = pos.coords.longitude.toFixed(4);
    // Best-guess tz from browser
    const offsetMins = -new Date().getTimezoneOffset();
    document.getElementById('tz').value = (offsetMins / 60).toFixed(1);
  });
});

// ── Form submit ─────────────────────────────────────────────────────

document.getElementById('birth-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const errBanner = document.getElementById('form-error');
  errBanner.classList.add('hidden');

  // Parse date + time fields
  const dobVal = document.getElementById('dob').value;   // "YYYY-MM-DD"
  const tobVal = document.getElementById('tob').value;   // "HH:MM"

  if (!dobVal || !tobVal) {
    showError('Please fill in both date and time of birth.');
    return;
  }

  const [year, month, day] = dobVal.split('-').map(Number);
  const [hour, minute]     = tobVal.split(':').map(Number);

  const payload = {
    name:      document.getElementById('name').value.trim(),
    place:     document.getElementById('city').value.trim(),
    year, month,
    date:      day,
    hours:     hour,
    minutes:   minute,
    seconds:   0,
    latitude:  parseFloat(document.getElementById('lat').value),
    longitude: parseFloat(document.getElementById('lon').value),
    timezone:  parseFloat(document.getElementById('tz').value),
  };

  // Basic client-side validation
  const missing = ['name','place'].filter(k => !payload[k]);
  if (missing.length || isNaN(payload.latitude) || isNaN(payload.longitude) || isNaN(payload.timezone)) {
    showError('Please fill in all fields before submitting.');
    return;
  }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  showView('view-loading');

  try {
    // Step 1 — trigger computation
    const postRes = await fetch(`${API_BASE}/api/v1/self-map`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!postRes.ok) {
      const txt = await postRes.text();
      throw new Error(`API error ${postRes.status}: ${txt}`);
    }

    const cacheKey = postRes.headers.get('X-Cache-Key');
    if (!cacheKey) throw new Error('No cache key returned from server.');

    // Step 2 — fetch JSON data
    const jsonRes = await fetch(`${API_BASE}/api/v1/self-map/${cacheKey}/json`);
    if (!jsonRes.ok) throw new Error(`Failed to fetch results (${jsonRes.status})`);
    const data = await jsonRes.json();

    // Step 3 — render results
    renderResults(data, cacheKey);
    showView('view-results');

  } catch (err) {
    showView('view-form');
    showError(err.message || 'Something went wrong. Please try again.');
  } finally {
    btn.disabled = false;
  }
});

function showError(msg) {
  const el = document.getElementById('form-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ── Back button ─────────────────────────────────────────────────────

document.getElementById('back-btn').addEventListener('click', () => {
  showView('view-form');
});

// ── Render results ───────────────────────────────────────────────────

function renderResults(data, cacheKey) {
  renderProfile(data.profile);
  renderChart(cacheKey);
  renderScores(data.dimensions);
  renderZones(data.strength_zones, data.growth_zones);
  renderTheme(data.current_theme);
}

// Profile header
function renderProfile(profile) {
  const bd = profile.birth_data;
  const dob = `${bd.year}-${String(bd.month).padStart(2,'0')}-${String(bd.date).padStart(2,'0')}`;

  const moon = profile.nakshatra?.moon;
  const asc  = profile.nakshatra?.ascendant;

  const nakshatraHtml = (moon || asc) ? `
    <div class="nakshatra-block">
      ${moon ? `
        <div class="nakshatra-item">
          <strong>${moon.nakshatra} (Moon)</strong>
          Pada ${moon.pada} · ${moon.pada_sign}<br>
          Ruled by ${moon.ruling_planet} · ${moon.element}
          ${moon.core_traits ? `<div class="nakshatra-traits">${moon.core_traits.join(', ')}</div>` : ''}
        </div>` : ''}
      ${asc ? `
        <div class="nakshatra-item">
          <strong>${asc.nakshatra} (Ascendant)</strong>
          Pada ${asc.pada} · ${asc.pada_sign}<br>
          Ruled by ${asc.ruling_planet} · ${asc.element}
          ${asc.core_traits ? `<div class="nakshatra-traits">${asc.core_traits.join(', ')}</div>` : ''}
        </div>` : ''}
    </div>` : '';

  document.getElementById('profile-header').innerHTML = `
    <div class="profile-name">${bd.name}</div>
    <div class="profile-meta">${dob} · ${bd.place} · ${bd.hours}:${String(bd.minutes).padStart(2,'0')}</div>
    <div class="profile-pills">
      <span class="pill">Ascendant: ${profile.ascendant}</span>
      <span class="pill">Moon: ${profile.moon_sign}</span>
      <span class="pill">Sun: ${profile.sun_sign}</span>
      <span class="pill dasa">Maha Dasa: ${profile.current_maha_dasa}</span>
    </div>
    ${nakshatraHtml}
  `;
}

// Radar chart
function renderChart(cacheKey) {
  document.getElementById('chart-img').src = `${API_BASE}/api/v1/self-map/${cacheKey}/chart`;
}

// Dimension score cards
const BAND_CLASS = { strength: 'band-strength', balanced: 'band-balanced', growth: 'band-growth' };
const BAND_LABEL = { strength: 'Strength Zone', balanced: 'Balanced', growth: 'Growth Zone' };

function renderScores(dimensions) {
  const grid = document.getElementById('scores-grid');
  grid.innerHTML = '';

  // Sort by score descending
  const sorted = Object.entries(dimensions).sort((a, b) => b[1].score - a[1].score);

  for (const [, dim] of sorted) {
    const bandClass = BAND_CLASS[dim.band] || 'band-balanced';
    const bandLabel = BAND_LABEL[dim.band] || dim.band;
    const dasaTag   = dim.dasa_active ? '<span class="score-dasa-tag">★ Dasa Active</span>' : '';
    const cats = (dim.recommended_categories || [])
      .map(c => `<span class="cat-tag">${c}</span>`).join('');

    const card = document.createElement('div');
    card.className = `score-card ${bandClass}`;
    card.innerHTML = `
      <div class="score-card-top">
        <div class="score-label">
          <span class="score-label-icon">${dim.icon || ''}</span>${dim.label}${dasaTag}
        </div>
        <div class="score-value">${dim.score.toFixed(1)}</div>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${dim.score}%"></div>
      </div>
      <span class="score-band-badge">${bandLabel}</span>
      ${cats ? `<div class="score-categories">${cats}</div>` : ''}
    `;
    grid.appendChild(card);
  }
}

// Strength + growth zone lists
function renderZones(strengthZones, growthZones) {
  function renderList(zones, listId) {
    const el = document.getElementById(listId);
    el.innerHTML = '';
    if (!zones || zones.length === 0) {
      el.innerHTML = '<li style="color:var(--text-muted);font-size:0.85rem">None in this range</li>';
      return;
    }
    for (const z of zones) {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>${z.label}</span>
        <span class="zone-score">${z.score.toFixed(1)}</span>
      `;
      el.appendChild(li);
    }
  }
  renderList(strengthZones, 'strength-list');
  renderList(growthZones,   'growth-list');
}

// Current theme card
function renderTheme(theme) {
  if (!theme) return;
  const books = (theme.recommended_books || [])
    .map(b => `<span class="theme-book-tag">${b}</span>`).join('');

  document.getElementById('theme-card').innerHTML = `
    <h3>Current Life Theme</h3>
    <div class="theme-name">${theme.theme}</div>
    <div class="theme-dasa">Maha Dasa Lord: ${theme.maha_dasa_lord}</div>
    ${books ? `<div class="theme-books">${books}</div>` : ''}
  `;
}
