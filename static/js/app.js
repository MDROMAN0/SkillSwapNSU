/* =============================================================
   SkillSwap NSU  —  app.js  (Flask build)
   -------------------------------------------------------------
   The browser side only. Every value on screen was rendered by
   Jinja from a SQL result; nothing here invents data.

     · theme switch (dark ⇄ light, remembered)
     · command palette  (Ctrl / Cmd + K) -> /api/search
     · debounced live search on the Find page
     · animated counters, toasts, star picker, modals
   ============================================================= */

'use strict';

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const IS_MAC  = /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent);

function esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/* ---------------------------------------------------------------
   Theme
   --------------------------------------------------------------- */
function setTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  try { localStorage.setItem('skillswap-theme', name); } catch (e) { /* ignore */ }
  document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: name } }));
}

function initTheme() {
  const btn = $('#themeToggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const now = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    setTheme(now);
  });
}

/* ---------------------------------------------------------------
   Command palette
   --------------------------------------------------------------- */
function initPalette() {
  const backdrop = $('#cmdkBackdrop');
  if (!backdrop) return;

  const input = $('#cmdkInput');
  const list = $('#cmdkResults');
  const url = document.currentScript?.dataset.searchUrl
            || $('script[data-search-url]')?.dataset.searchUrl
            || '/api/search';

  const PAGES = [
    ['Home', '/dashboard', 'house-door'],
    ['Find a partner', '/search', 'search'],
    ['Exchange requests', '/requests', 'arrow-left-right'],
    ['Sessions', '/sessions', 'calendar-event'],
    ['Reviews', '/reviews', 'star'],
    ['Edit profile & skills', '/edit-profile', 'pencil-square'],
    ['Analytics', '/admin?tab=analytics', 'bar-chart-line'],
    ['Admin console', '/admin', 'shield-lock']
  ];

  let items = [];
  let cursor = 0;

  function open() {
    backdrop.classList.add('open');
    input.value = '';
    render(null);
    setTimeout(() => input.focus(), 30);
    document.body.style.overflow = 'hidden';
  }
  function close() {
    backdrop.classList.remove('open');
    document.body.style.overflow = '';
  }

  function row(icon, title, meta, href) {
    return { icon, title, meta, href };
  }

  /* Build [{label, rows:[…]}, …], flatten to `items`, then paint once. */
  function render(data, q = '') {
    const sections = [];

    const pages = PAGES
      .filter(p => !q || p[0].toLowerCase().includes(q.toLowerCase()))
      .map(([label, href, icon]) => row(icon, label, '', href));
    if (pages.length) sections.push({ label: 'Go to', rows: pages });

    if (data) {
      if (data.students && data.students.length) {
        sections.push({
          label: 'Students — ' + data.students.length,
          rows: data.students.map(s => row(
            'person', s.name,
            s.department + ' · ' + s.teach_n + ' skills to teach',
            '/profile/' + s.user_id))
        });
      }
      if (data.skills && data.skills.length) {
        sections.push({
          label: 'Skills — ' + data.skills.length,
          rows: data.skills.map(s => row(
            'mortarboard', s.skill_name,
            s.category + ' · ' + s.teachers + ' can teach · ' + s.learners + ' want it',
            '/search?skill=' + encodeURIComponent(s.skill_name)))
        });
      }
      if (data.departments && data.departments.length) {
        sections.push({
          label: 'Departments',
          rows: data.departments.map(d => row(
            'building', d.department, d.n + ' students',
            '/search?department=' + encodeURIComponent(d.department)))
        });
      }
    }

    items = sections.flatMap(sec => sec.rows);

    if (!items.length) {
      list.innerHTML = '<div class="cmdk-empty">Nothing matches &ldquo;' + esc(q) + '&rdquo;.</div>';
      return;
    }

    let i = 0;
    list.innerHTML = sections.map(sec =>
      '<div class="cmdk-group">' + esc(sec.label) + '</div>' +
      sec.rows.map(it => {
        const idx = i++;
        return `<div class="cmdk-item" role="option" data-i="${idx}" data-href="${esc(it.href)}">
                  <span class="cmdk-ico"><i class="bi bi-${it.icon}"></i></span>
                  <span class="min-w-0">
                    <span class="d-block text-truncate">${hl(it.title, q)}</span>
                    ${it.meta ? `<span class="cmdk-meta">${esc(it.meta)}</span>` : ''}
                  </span>
                </div>`;
      }).join('')
    ).join('');

    cursor = 0;
    paint();
  }

  function hl(text, q) {
    if (!q) return esc(text);
    const i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return esc(text);
    return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) +
           '</mark>' + esc(text.slice(i + q.length));
  }

  function paint() {
    $$('.cmdk-item', list).forEach(el => {
      const on = Number(el.dataset.i) === cursor;
      el.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) el.scrollIntoView({ block: 'nearest' });
    });
  }

  const query = debounce(async q => {
    if (!q) { render(null); return; }
    try {
      const res = await fetch(url + '?q=' + encodeURIComponent(q));
      render(await res.json(), q);
    } catch (e) { render(null, q); }
  }, 160);

  input.addEventListener('input', e => query(e.target.value.trim()));

  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); cursor = Math.min(cursor + 1, items.length - 1); paint(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); cursor = Math.max(cursor - 1, 0); paint(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (items[cursor]) location.href = items[cursor].href; }
    else if (e.key === 'Escape') { close(); }
  });

  list.addEventListener('click', e => {
    const item = e.target.closest('.cmdk-item');
    if (item) location.href = item.dataset.href;
  });

  backdrop.addEventListener('click', e => { if (e.target === backdrop) close(); });

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); }
    else if (e.key === '/' && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      e.preventDefault(); open();
    }
  });

  const hint = $('#kbdHint');
  if (hint) hint.textContent = IS_MAC ? '⌘ K' : 'Ctrl K';
  $('#navSearch')?.addEventListener('focus', e => { e.target.blur(); open(); });
}

/* ---------------------------------------------------------------
   Animated counters
   --------------------------------------------------------------- */
function initCounters() {
  const tiles = $$('[data-count]');
  if (!tiles.length) return;

  const run = el => {
    const target = parseFloat(el.dataset.count);
    if (!isFinite(target)) return;
    const decimals = (el.dataset.count.split('.')[1] || '').length;
    if (REDUCED) { el.textContent = target.toFixed(decimals); return; }
    const dur = 700;
    const t0 = performance.now();
    const step = now => {
      const p = Math.min((now - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = target.toFixed(decimals);
    };
    requestAnimationFrame(step);
  };

  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (en.isIntersecting) { run(en.target); io.unobserve(en.target); }
    });
  }, { threshold: .4 });
  tiles.forEach(t => io.observe(t));
}

/* ---------------------------------------------------------------
   Everything else
   --------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {

  initTheme();
  initPalette();
  initCounters();

  $$('[data-year]').forEach(el => el.textContent = new Date().getFullYear());

  /* ---------- flash toasts fade away on their own ---------- */
  $$('.toast[data-auto-hide]').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s, transform .4s';
      el.style.opacity = '0';
      el.style.transform = 'translateX(24px)';
      setTimeout(() => el.remove(), 420);
    }, 7000);
  });

  /* ---------- show / hide password ---------- */
  const toggle = $('#togglePw');
  if (toggle) {
    toggle.addEventListener('click', e => {
      const inp = $('#password');
      const show = inp.type === 'password';
      inp.type = show ? 'text' : 'password';
      e.currentTarget.innerHTML = `<i class="bi bi-eye${show ? '-slash' : ''}"></i>`;
    });
  }

  /* ---------- fill the demo credentials ---------- */
  const fill = $('#fillDemo');
  if (fill) {
    fill.addEventListener('click', () => {
      $('#email').value = fill.dataset.email || '';
      $('#password').value = 'password123';
    });
  }

  /* ---------- character counters ---------- */
  $$('[data-counter]').forEach(box => {
    const out = $('#' + box.dataset.counter);
    const paint = () => out.textContent = box.value.length;
    box.addEventListener('input', paint);
    paint();
  });

  /* ---------- booking modal: Online link vs Offline place ---------- */
  const mode = $('#bMode');
  if (mode) {
    const sync = () => {
      const online = mode.value === 'Online';
      $('#linkWrap').classList.toggle('d-none', !online);
      $('#locWrap').classList.toggle('d-none', online);
      $('#bLink').required = online;
      $('#bLoc').required = !online;
    };
    mode.addEventListener('change', sync);
    sync();
  }

  /* ---------- star picker in the review modal ---------- */
  const starBox = $('#starInput');
  if (starBox) {
    const hints = {
      1: 'Poor — it did not work out.',
      2: 'Below expectations.',
      3: 'Fine, but there is room to improve.',
      4: 'Good session, would repeat.',
      5: 'Excellent — clear, prepared and generous with time.'
    };
    const field = $('#ratingValue');
    const paint = n => $$('i', starBox).forEach(el =>
      el.classList.toggle('on', Number(el.dataset.star) <= n));

    $$('i', starBox).forEach(el => {
      el.addEventListener('mouseenter', () => paint(Number(el.dataset.star)));
      el.addEventListener('click', () => {
        field.value = el.dataset.star;
        paint(Number(field.value));
        $('#ratingHint').textContent = hints[field.value];
        $$('i', starBox).forEach(x =>
          x.setAttribute('aria-checked', x.dataset.star === field.value));
      });
      el.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
      });
    });
    starBox.addEventListener('mouseleave', () => paint(Number(field.value || 0)));
  }

  /* ---------- open the review modal for one session ---------- */
  $$('[data-review-session]').forEach(btn => {
    btn.addEventListener('click', () => {
      $('#revSessionId').value = btn.dataset.reviewSession;
      $('#revPartner').textContent = btn.dataset.partner || '';
      $('#revMeta').textContent = btn.dataset.meta || '';
      $('#ratingValue').value = '';
      $('#revText').value = '';
      $('#revCount').textContent = '0';
      $('#ratingHint').textContent = 'Pick a score from 1 to 5.';
      $$('#starInput i').forEach(el => el.classList.remove('on'));
      new bootstrap.Modal($('#revModal')).show();
    });
  });

  /* ---------- reschedule modal ---------- */
  $$('[data-reschedule]').forEach(btn => {
    btn.addEventListener('click', () => {
      $('#reschedForm').action = btn.dataset.reschedule;
      $('#rsDate').value = btn.dataset.date || '';
      $('#rsTime').value = btn.dataset.time || '';
      new bootstrap.Modal($('#reschedModal')).show();
    });
  });

  /* ---------- confirm destructive actions ---------- */
  $$('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  /* ---------- Find page: filters re-run the query ---------- */
  $$('#filterForm select, #filterForm input[type=checkbox]').forEach(el => {
    el.addEventListener('change', () => $('#filterForm').submit());
  });
  /* debounced so a five-letter name is one request, not five */
  $$('#filterForm input[type=text]').forEach(el => {
    el.addEventListener('input', debounce(() => $('#filterForm').submit(), 500));
  });
  $('#sortBy')?.addEventListener('change', e => e.target.form.submit());

  /* ---------- admin search boxes ---------- */
  $$('form[data-live] input[name=q]').forEach(el => {
    el.addEventListener('input', debounce(() => el.form.submit(), 450));
  });
});
