/* =============================================================
   SkillSwap NSU  —  app.js  (Flask build)
   -------------------------------------------------------------
   Only the small things a browser should do: toasts fading out,
   a password eye, the star picker, and showing the right field
   when a session switches between Online and Offline.

   All data now comes from MySQL through Jinja, so there is no
   client side rendering left in this file.
   ============================================================= */

'use strict';

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

document.addEventListener('DOMContentLoaded', () => {

  /* ---------- footer year ---------- */
  $$('[data-year]').forEach(el => el.textContent = new Date().getFullYear());

  /* ---------- flash toasts fade away on their own ---------- */
  $$('.toast[data-auto-hide]').forEach(el => {
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 400);
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
      const id = btn.dataset.reviewSession;
      $('#revSessionId').value = id;
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
      const f = $('#reschedForm');
      f.action = btn.dataset.reschedule;
      $('#rsDate').value = btn.dataset.date || '';
      $('#rsTime').value = btn.dataset.time || '';
      new bootstrap.Modal($('#reschedModal')).show();
    });
  });

  /* ---------- propose-an-exchange modal (search results) ---------- */
  $$('[data-propose]').forEach(btn => {
    btn.addEventListener('click', () => {
      $('#propReceiver').value = btn.dataset.propose;
      $('#propName').textContent = btn.dataset.name || '';
      const give = $('#propGive'), take = $('#propTake');
      take.innerHTML = (JSON.parse(btn.dataset.theirTeach || '[]'))
        .map(s => `<option value="${s[0]}">${s[1]}</option>`).join('');
      if (btn.dataset.suggestGive) give.value = btn.dataset.suggestGive;
      if (btn.dataset.suggestTake) take.value = btn.dataset.suggestTake;
      new bootstrap.Modal($('#proposeModal')).show();
    });
  });

  /* ---------- confirm destructive actions ---------- */
  $$('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  /* ---------- filter form: re-run search when a select changes ---------- */
  $$('#filterForm select, #filterForm input[type=checkbox]').forEach(el => {
    el.addEventListener('change', () => $('#filterForm').submit());
  });
  const sortBy = $('#sortBy');
  if (sortBy) sortBy.addEventListener('change', () => sortBy.form.submit());
});
