/* =============================================================
   SkillSwap NSU  —  charts.js
   -------------------------------------------------------------
   Draws the analytics tab. Every number comes from a SQL
   aggregate rendered into #analyticsData by Jinja — this file
   never computes a statistic, it only draws one.

   Colour rules follow the project's data-viz tokens:
     · nominal categories (departments)  -> ONE hue, slot 1
     · ordered stages (funnel, ratings)  -> the ordinal ramp
     · true series (teach vs learn, activity) -> categorical slots
   Both palettes were checked with the palette validator against
   the exact dark (#151B2E) and light (#FFFFFF) chart surfaces.
   ============================================================= */

'use strict';

(function () {
  const holder = document.getElementById('analyticsData');
  if (!holder || typeof Chart === 'undefined') return;

  const DATA = JSON.parse(holder.textContent);
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let charts = [];

  const css = name => getComputedStyle(document.documentElement)
    .getPropertyValue(name).trim();

  function tokens() {
    return {
      c1: css('--c-1'), c2: css('--c-2'), c3: css('--c-3'),
      ordinal: [css('--c-o1'), css('--c-o2'), css('--c-o3'), css('--c-o4'), css('--c-o5')],
      grid: css('--c-grid'),
      axis: css('--c-axis'),
      ink: css('--ink'),
      ink2: css('--ink-2'),
      muted: css('--muted'),
      surface: css('--c-surface'),
    };
  }

  /* ---- direct value labels: selective, at the data end ---- */
  const directLabels = {
    id: 'directLabels',
    afterDatasetsDraw(chart, _args, opts) {
      const { ctx } = chart;
      ctx.save();
      ctx.font = '600 11px Inter, system-ui, sans-serif';
      ctx.fillStyle = opts.color;
      chart.data.datasets.forEach((ds, di) => {
        const meta = chart.getDatasetMeta(di);
        if (meta.hidden) return;
        meta.data.forEach((el, i) => {
          const v = ds.data[i];
          if (v === null || v === undefined || v === 0) return;
          if (opts.horizontal) {
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(v, el.x + 7, el.y);
          } else {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(v, el.x, el.y - 6);
          }
        });
      });
      ctx.restore();
    }
  };

  /* ---- shared options ---- */
  function base(t, horizontal) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: REDUCED ? false : { duration: 620, easing: 'easeOutQuart' },
      layout: { padding: { right: horizontal ? 34 : 8, top: 14 } },
      interaction: { mode: horizontal ? 'nearest' : 'index', intersect: false },
      plugins: {
        legend: { display: false },           /* an HTML legend is rendered instead */
        tooltip: {
          backgroundColor: t.surface,
          titleColor: t.ink,
          bodyColor: t.ink2,
          borderColor: t.axis,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          displayColors: true,
          boxWidth: 9, boxHeight: 9, boxPadding: 4,
          titleFont: { family: 'Inter', size: 12, weight: '700' },
          bodyFont: { family: 'Inter', size: 12 },
        },
        directLabels: { color: t.muted, horizontal: !!horizontal },
      },
    };
  }

  function scale(t, opts) {
    return Object.assign({
      grid: { color: t.grid, drawTicks: false, drawBorder: false },
      border: { display: false },
      ticks: {
        color: t.muted,
        font: { family: 'Inter', size: 11 },
        padding: 8,
      },
    }, opts || {});
  }

  /* ---- the five charts ---- */
  function build() {
    const t = tokens();
    charts.forEach(c => c.destroy());
    charts = [];

    /* 1 — supply vs demand: two real series, categorical slots 1 & 2 */
    const el1 = document.getElementById('chartDemand');
    if (el1) charts.push(new Chart(el1, {
      type: 'bar',
      data: {
        labels: DATA.demand.map(d => d.skill_name),
        datasets: [
          { label: 'Can teach', data: DATA.demand.map(d => Number(d.teachers)),
            backgroundColor: t.c1, borderRadius: 4, borderSkipped: 'start',
            barPercentage: .82, categoryPercentage: .74 },
          { label: 'Want to learn', data: DATA.demand.map(d => Number(d.learners)),
            backgroundColor: t.c2, borderRadius: 4, borderSkipped: 'start',
            barPercentage: .82, categoryPercentage: .74 },
        ]
      },
      options: Object.assign(base(t, true), {
        indexAxis: 'y',
        scales: {
          x: scale(t, { beginAtZero: true, ticks: { display: false }, grid: { display: false } }),
          y: scale(t, { grid: { display: false }, ticks: { color: t.ink2, font: { family: 'Inter', size: 11.5, weight: '600' } } }),
        }
      }),
      plugins: [directLabels]
    }));

    /* 2 — departments: nominal categories, so ONE hue for every bar */
    const el2 = document.getElementById('chartDepts');
    if (el2) charts.push(new Chart(el2, {
      type: 'bar',
      data: {
        labels: DATA.depts.map(d => d.department),
        datasets: [{ label: 'Students', data: DATA.depts.map(d => Number(d.n)),
                     backgroundColor: t.c1, borderRadius: 4, borderSkipped: 'start',
                     barPercentage: .72, categoryPercentage: .86 }]
      },
      options: Object.assign(base(t, true), {
        indexAxis: 'y',
        scales: {
          x: scale(t, { beginAtZero: true, ticks: { display: false }, grid: { display: false } }),
          y: scale(t, { grid: { display: false }, ticks: { color: t.ink2, font: { family: 'Inter', size: 11.5, weight: '600' } } }),
        }
      }),
      plugins: [directLabels]
    }));

    /* 3 — the exchange funnel: five ORDERED stages, so the ordinal ramp */
    const el3 = document.getElementById('chartFunnel');
    if (el3) charts.push(new Chart(el3, {
      type: 'bar',
      data: {
        labels: DATA.funnel.map(f => f.stage),
        datasets: [{ label: 'Rows', data: DATA.funnel.map(f => Number(f.n)),
                     backgroundColor: t.ordinal.slice().reverse(),
                     borderRadius: 4, borderSkipped: 'start',
                     barPercentage: .74, categoryPercentage: .88 }]
      },
      options: Object.assign(base(t, true), {
        indexAxis: 'y',
        scales: {
          x: scale(t, { beginAtZero: true, ticks: { display: false }, grid: { display: false } }),
          y: scale(t, { grid: { display: false }, ticks: { color: t.ink2, font: { family: 'Inter', size: 11.5, weight: '600' } } }),
        }
      }),
      plugins: [directLabels]
    }));

    /* 4 — rating spread: 1..5 is an ordered scale, so the ordinal ramp */
    const el4 = document.getElementById('chartRatings');
    if (el4) charts.push(new Chart(el4, {
      type: 'bar',
      data: {
        labels: DATA.ratings.map(r => r.rating + '★'),
        datasets: [{ label: 'Reviews', data: DATA.ratings.map(r => Number(r.n)),
                     backgroundColor: t.ordinal,
                     borderRadius: 4, borderSkipped: 'start',
                     barPercentage: .62, categoryPercentage: .82 }]
      },
      options: Object.assign(base(t, false), {
        scales: {
          x: scale(t, { grid: { display: false }, ticks: { color: t.ink2, font: { family: 'Inter', size: 12, weight: '700' } } }),
          y: scale(t, { beginAtZero: true, ticks: { precision: 0 } }),
        }
      }),
      plugins: [directLabels]
    }));

    /* 5 — activity over time: three series on ONE count axis (never two scales) */
    const el5 = document.getElementById('chartActivity');
    if (el5) {
      const line = (label, data, colour) => ({
        label, data, borderColor: colour, backgroundColor: colour,
        borderWidth: 2, tension: .32,
        pointRadius: 0, pointHoverRadius: 5,
        pointBackgroundColor: colour,
        pointBorderColor: t.surface, pointBorderWidth: 2,
        pointHitRadius: 24,
      });
      charts.push(new Chart(el5, {
        type: 'line',
        data: {
          labels: DATA.activity.months,
          datasets: [
            line('Requests', DATA.activity.requests, t.c1),
            line('Sessions', DATA.activity.sessions, t.c2),
            line('Reviews',  DATA.activity.reviews,  t.c3),
          ]
        },
        options: Object.assign(base(t, false), {
          plugins: Object.assign(base(t, false).plugins, { directLabels: false }),
          scales: {
            x: scale(t, { grid: { display: false } }),
            y: scale(t, { beginAtZero: true, ticks: { precision: 0 } }),
          }
        })
      }));
    }
  }

  build();
  document.addEventListener('themechange', () => setTimeout(build, 60));
})();
