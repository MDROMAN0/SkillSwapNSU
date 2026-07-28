/* =============================================================
   SkillSwap NSU  —  ui.js
   -------------------------------------------------------------
   Shared navigation shell + data lookup helpers.

   Everything here reads from the arrays in data.js. In the final
   Flask build the lookups below are replaced by raw SQL queries
   (the comment above each helper names the query it stands in for)
   and the markup moves into Jinja templates unchanged.
   ============================================================= */

'use strict';

/* ---------------------------------------------------------------
   Tiny utilities
   --------------------------------------------------------------- */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function param(name, fallback = null) {
  const v = new URLSearchParams(location.search).get(name);
  return v === null || v === '' ? fallback : v;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/* '2026-07-25' -> '25 Jul 2026' */
function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

/* '15:30' -> '3:30 PM' */
function fmtTime(t) {
  if (!t) return '';
  let [h, m] = t.split(':').map(Number);
  const ap = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${h}:${String(m).padStart(2, '0')} ${ap}`;
}

const TODAY = '2026-07-28';

/* ---------------------------------------------------------------
   Lookups
   --------------------------------------------------------------- */

/* SQL: SELECT * FROM users WHERE user_id = %s */
const userById  = id => USERS.find(u => u.user_id === Number(id));

/* SQL: SELECT * FROM skills WHERE skill_id = %s */
const skillById = id => SKILLS.find(s => s.skill_id === Number(id));

const me = () => userById(DEMO_USER_ID);

/* SQL: SELECT s.*, us.proficiency FROM userskills us
        JOIN skills s USING(skill_id)
        WHERE us.user_id = %s AND us.skill_type = %s          */
function skillsOf(userId, type) {
  return USERSKILLS
    .filter(us => us.user_id === Number(userId) && us.skill_type === type)
    .map(us => ({ ...skillById(us.skill_id), proficiency: us.proficiency }))
    .sort((a, b) => a.skill_name.localeCompare(b.skill_name));
}

/* SQL: SELECT COUNT(*), AVG(rating) FROM reviews WHERE reviewee_id = %s */
function ratingOf(userId) {
  const rows = REVIEWS.filter(r => r.reviewee_id === Number(userId));
  if (!rows.length) return { count: 0, avg: null };
  const avg = rows.reduce((t, r) => t + r.rating, 0) / rows.length;
  return { count: rows.length, avg: Math.round(avg * 100) / 100 };
}

/* SQL: SELECT * FROM exchangerequests WHERE sender_id = %s OR receiver_id = %s */
function requestsOf(userId) {
  const id = Number(userId);
  return {
    sent:     REQUESTS.filter(r => r.sender_id === id),
    received: REQUESTS.filter(r => r.receiver_id === id)
  };
}

/* SQL: SELECT se.* FROM sessions se JOIN exchangerequests er USING(request_id)
        WHERE er.sender_id = %s OR er.receiver_id = %s                        */
function sessionsOf(userId) {
  const id = Number(userId);
  return SESSIONS.filter(se => {
    const req = REQUESTS.find(r => r.request_id === se.request_id);
    return req && (req.sender_id === id || req.receiver_id === id);
  });
}

/* The other person in a session, as seen from `userId` */
function partnerOf(session, userId) {
  const req = REQUESTS.find(r => r.request_id === session.request_id);
  if (!req) return null;
  return userById(req.sender_id === Number(userId) ? req.receiver_id : req.sender_id);
}

function requestOfSession(session) {
  return REQUESTS.find(r => r.request_id === session.request_id);
}

/* ---------------------------------------------------------------
   Render helpers
   --------------------------------------------------------------- */
function initials(name) {
  const p = String(name || '?').trim().split(/\s+/);
  return ((p[0]?.[0] || '') + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
}

/* Deterministic avatar tint so each student keeps the same colour */
const AV_TINTS = ['#0A66C2', '#1B5E9E', '#2E7DBE', '#134E7A',
                  '#3D6FA5', '#0F5C8C', '#4A7FB5', '#26689F'];

function avatar(user, size = 40) {
  if (!user) return '';
  const tint = AV_TINTS[user.user_id % AV_TINTS.length];
  return `<span class="avatar avatar-${size}" style="background:${tint}"
                title="${esc(user.name)}" aria-hidden="true">${initials(user.name)}</span>`;
}

const PILL_ICON = {
  Pending: 'hourglass-split', Accepted: 'check-circle', Completed: 'patch-check',
  Rejected: 'x-circle', Cancelled: 'slash-circle', Scheduled: 'calendar-check'
};

function pill(status) {
  const key = String(status).toLowerCase();
  return `<span class="pill pill-${key}"><i class="bi bi-${PILL_ICON[status] || 'circle'}"></i>${esc(status)}</span>`;
}

function modePill(mode) {
  const icon = mode === 'Online' ? 'camera-video' : 'geo-alt';
  return `<span class="pill pill-${mode.toLowerCase()}"><i class="bi bi-${icon}"></i>${mode}</span>`;
}

function stars(rating) {
  if (rating === null || rating === undefined) return '<span class="text-muted-2 small">No rating yet</span>';
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  let out = '';
  for (let i = 1; i <= 5; i++) {
    if (i <= full)            out += '<i class="bi bi-star-fill"></i>';
    else if (i === full + 1 && half) out += '<i class="bi bi-star-half"></i>';
    else                      out += '<i class="bi bi-star"></i>';
  }
  return `<span class="stars">${out}</span>`;
}

function skillChip(skill, kind) {
  const cls = kind === 'Teach' ? 'chip-teach' : 'chip-learn';
  const lvl = skill.proficiency ? `<span class="lvl">${esc(skill.proficiency)}</span>` : '';
  return `<a class="chip ${cls}" href="search.html?skill=${encodeURIComponent(skill.skill_name)}">
            ${esc(skill.skill_name)} ${lvl}</a>`;
}

/* THE SIGNATURE COMPONENT — one skill trade, both directions */
function swapCard(giveLabel, giveSkill, giveMeta, takeLabel, takeSkill, takeMeta) {
  return `
  <div class="swap">
    <div class="swap-side give">
      <div class="small-label">${esc(giveLabel)}</div>
      <div class="swap-skill">${esc(giveSkill)}</div>
      <div class="swap-meta">${giveMeta || ''}</div>
    </div>
    <div class="swap-badge" aria-hidden="true"><i class="bi bi-arrow-left-right"></i></div>
    <div class="swap-side take">
      <div class="small-label">${esc(takeLabel)}</div>
      <div class="swap-skill">${esc(takeSkill)}</div>
      <div class="swap-meta">${takeMeta || ''}</div>
    </div>
  </div>`;
}

function empty(icon, text, ctaHtml = '') {
  return `<div class="empty"><i class="bi bi-${icon}"></i><p>${text}</p>${ctaHtml}</div>`;
}

/* ---------------------------------------------------------------
   Demo-only feedback.
   The static build has no server, so write actions explain
   themselves instead of pretending to work.
   --------------------------------------------------------------- */
function demoAction(what) {
  const host = $('#toastHost') || (() => {
    const d = document.createElement('div');
    d.id = 'toastHost';
    d.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    d.style.zIndex = 1080;
    document.body.appendChild(d);
    return d;
  })();
  const el = document.createElement('div');
  el.className = 'toast align-items-center text-bg-dark border-0 show';
  el.innerHTML = `<div class="d-flex">
      <div class="toast-body"><i class="bi bi-info-circle me-1"></i>${esc(what)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast" aria-label="Close"></button></div>`;
  host.appendChild(el);
  setTimeout(() => el.remove(), 5200);
}

/* ---------------------------------------------------------------
   Navigation shell
   Injected into <div id="shellNav"></div> on every signed-in page.
   In Flask this whole block lives in templates/base.html.
   --------------------------------------------------------------- */
const NAV = [
  { key: 'dashboard', href: 'dashboard.html', icon: 'house-door',    label: 'Home' },
  { key: 'search',    href: 'search.html',    icon: 'search',        label: 'Find' },
  { key: 'requests',  href: 'requests.html',  icon: 'arrow-left-right', label: 'Requests' },
  { key: 'sessions',  href: 'sessions.html',  icon: 'calendar-event', label: 'Sessions' },
  { key: 'reviews',   href: 'reviews.html',   icon: 'star',          label: 'Reviews' }
];

function pendingCount() {
  return requestsOf(DEMO_USER_ID).received.filter(r => r.status === 'Pending').length;
}

function mountShell(active) {
  const u = me();
  const pend = pendingCount();

  const links = NAV.map(n => {
    const dot = (n.key === 'requests' && pend)
      ? `<span class="badge-dot">${pend}</span>` : '';
    return `<a class="topnav-link position-relative ${n.key === active ? 'active' : ''}"
               href="${n.href}"><i class="bi bi-${n.icon}"></i>${dot}<span>${n.label}</span></a>`;
  }).join('');

  $('#shellNav').innerHTML = `
  <div class="demo-note">
    <div class="container d-flex flex-wrap gap-2 justify-content-between align-items-center">
      <span><i class="bi bi-display me-1"></i>Static preview for GitHub Pages &mdash;
        signed in as <strong>${esc(u.name)}</strong>. Data is the real
        <code>seed.sql</code> export; saving is disabled until the Flask build.</span>
      <a href="index.html" class="text-decoration-underline">About this project</a>
    </div>
  </div>

  <nav class="topbar">
    <div class="container d-flex align-items-center gap-3 py-1">
      <a class="brand-mark" href="dashboard.html">
        <span class="brand-glyph"><i class="bi bi-arrow-left-right"></i></span>
        SkillSwap <span class="brand-tag">NSU</span>
      </a>

      <form class="nav-search flex-grow-1 d-none d-md-block" role="search"
            onsubmit="event.preventDefault(); goSearch(this.q.value);">
        <div class="input-group input-group-sm">
          <span class="input-group-text bg-transparent border-0 pe-1"
                style="background:var(--brand-050)!important"><i class="bi bi-search text-muted-2"></i></span>
          <input class="form-control border-0" name="q" type="search"
                 placeholder="Search students, skills or departments" aria-label="Search">
        </div>
      </form>

      <div class="d-flex align-items-center ms-auto">
        ${links}
        <div class="dropdown ms-2">
          <a class="topnav-link" href="#" data-bs-toggle="dropdown" aria-expanded="false">
            ${avatar(u, 24)}<span>Me <i class="bi bi-caret-down-fill" style="font-size:.55rem"></i></span>
          </a>
          <ul class="dropdown-menu dropdown-menu-end shadow-sm" style="min-width:230px">
            <li class="px-3 py-2 d-flex gap-2 align-items-center">
              ${avatar(u, 40)}
              <div class="lh-sm">
                <div class="fw-semibold">${esc(u.name)}</div>
                <div class="small text-muted-2">${esc(u.department)}</div>
              </div>
            </li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item" href="profile.html?id=${u.user_id}">
                  <i class="bi bi-person me-2"></i>View profile</a></li>
            <li><a class="dropdown-item" href="edit-profile.html">
                  <i class="bi bi-pencil-square me-2"></i>Edit profile &amp; skills</a></li>
            <li><a class="dropdown-item" href="admin.html">
                  <i class="bi bi-shield-lock me-2"></i>Admin console</a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item text-danger" href="login.html">
                  <i class="bi bi-box-arrow-right me-2"></i>Sign out</a></li>
          </ul>
        </div>
      </div>
    </div>
  </nav>`;
}

function goSearch(q) {
  location.href = 'search.html?q=' + encodeURIComponent(q || '');
}

/* Left rail: mini profile card + section navigation */
function profileRail(active) {
  const u = me();
  const r = ratingOf(u.user_id);
  const teach = skillsOf(u.user_id, 'Teach').length;
  const learn = skillsOf(u.user_id, 'Learn').length;
  const req = requestsOf(u.user_id);
  const upcoming = sessionsOf(u.user_id).filter(s => s.status === 'Scheduled').length;

  const items = [
    ['dashboard', 'dashboard.html', 'house-door', 'Home', ''],
    ['search', 'search.html', 'search', 'Find a partner', ''],
    ['requests', 'requests.html', 'arrow-left-right', 'Requests',
      req.received.filter(x => x.status === 'Pending').length || ''],
    ['sessions', 'sessions.html', 'calendar-event', 'Sessions', upcoming || ''],
    ['reviews', 'reviews.html', 'star', 'Reviews', r.count || ''],
    ['profile', `profile.html?id=${u.user_id}`, 'person', 'My profile', ''],
    ['edit', 'edit-profile.html', 'pencil-square', 'Edit profile', ''],
    ['admin', 'admin.html', 'shield-lock', 'Admin console', '']
  ].map(([k, href, icon, label, count]) => `
      <a class="nav-link ${k === active ? 'active' : ''}" href="${href}">
        <i class="bi bi-${icon}"></i><span>${label}</span>
        ${count ? `<span class="count">${count}</span>` : ''}
      </a>`).join('');

  return `
  <div class="panel overflow-hidden">
    <div class="profile-card-cover"></div>
    <div class="profile-card-body">
      ${avatar(u, 88)}
      <h3 class="mt-2 mb-0" style="font-size:1.02rem">${esc(u.name)}</h3>
      <div class="small text-muted-2">${esc(u.department)} &middot; NSU</div>
      <div class="mt-2 d-flex justify-content-center align-items-center gap-1">
        ${stars(r.avg)} <span class="small text-muted-2">${r.count ? r.avg + ' (' + r.count + ')' : ''}</span>
      </div>
      <div class="d-flex justify-content-center gap-3 mt-3 pt-3 border-top">
        <div><div class="fw-bold" style="color:var(--brand-700)">${teach}</div>
             <div class="small text-muted-2" style="font-size:11.5px">Teaching</div></div>
        <div><div class="fw-bold" style="color:var(--brand-700)">${learn}</div>
             <div class="small text-muted-2" style="font-size:11.5px">Learning</div></div>
        <div><div class="fw-bold" style="color:var(--brand-700)">${req.sent.length + req.received.length}</div>
             <div class="small text-muted-2" style="font-size:11.5px">Exchanges</div></div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-body tight">
      <nav class="side-nav d-grid gap-1">${items}</nav>
    </div>
  </div>`;
}

/* Call once per page: mountShell + left rail + footer year */
function bootPage(active, railActive = active) {
  if ($('#shellNav')) mountShell(active);
  if ($('#shellRail')) $('#shellRail').innerHTML = profileRail(railActive);
  $$('[data-year]').forEach(el => el.textContent = new Date().getFullYear());
}
