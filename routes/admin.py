"""
routes/admin.py — the admin console.

Five tabs: Analytics, Students, Skills, Requests, Review moderation.

Every list is sorted and paged **in SQL** (ORDER BY / LIMIT / OFFSET), never
in Python, and every sortable column is looked up in a whitelist before it
reaches the statement — a sort key is an identifier, so it cannot be a bound
parameter, and anything not in the whitelist is discarded.

Deleting a student demonstrates ON DELETE CASCADE (their skills, requests,
sessions and reviews go with them). Deleting a skill an exchange request
still points at demonstrates ON DELETE RESTRICT — MySQL refuses.
"""

import csv
import io

from flask import (Blueprint, Response, redirect, render_template, request,
                   url_for)
from mysql.connector import IntegrityError

from db import execute, query, scalar
from helpers import categories, current_user, login_required, notify

bp = Blueprint('admin', __name__)

PER_PAGE = 12

# column key -> the SQL fragment it is allowed to become
SORTS = {
    'users': {
        'id': 'u.user_id', 'name': 'u.name', 'department': 'u.department',
        'teach': 'teach_n', 'exchanges': 'exchanges',
        'rating': 'COALESCE(v.avg_rating, 0)', 'joined': 'u.created_at',
    },
    'skills': {
        'id': 's.skill_id', 'name': 's.skill_name', 'category': 's.category',
        'teachers': 'teachers', 'learners': 'learners',
    },
    'requests': {
        'id': 'er.request_id', 'sender': 'sn.name', 'receiver': 'rc.name',
        'status': 'er.status', 'sessions': 'session_count', 'opened': 'er.created_at',
    },
    'reviews': {
        'id': 'r.review_id', 'reviewer': 'rv.name', 'reviewee': 're.name',
        'rating': 'r.rating', 'date': 'r.created_at',
    },
}
DEFAULT_SORT = {'users': 'id', 'skills': 'id', 'requests': 'opened', 'reviews': 'rating'}


def _order(tab, sort, direction):
    """Whitelist lookup -> a safe ORDER BY fragment."""
    table = SORTS[tab]
    key = sort if sort in table else DEFAULT_SORT[tab]
    way = 'DESC' if direction == 'desc' else 'ASC'
    return key, way, '%s %s' % (table[key], way)


def _page():
    try:
        return max(1, int(request.args.get('page', 1)))
    except ValueError:
        return 1


# ------------------------------------------------------------------ console
@bp.route('/admin')
@login_required
def index():
    tab = request.args.get('tab', 'analytics')
    q = (request.args.get('q') or '').strip()
    like = '%' + q + '%'
    direction = request.args.get('dir', 'asc')
    page = _page()
    offset = (page - 1) * PER_PAGE

    stats = {
        'students': scalar('SELECT COUNT(*) FROM users', (), 0),
        'skills':   scalar('SELECT COUNT(*) FROM skills', (), 0),
        'pending':  scalar("SELECT COUNT(*) FROM exchangerequests WHERE status = 'Pending'", (), 0),
        'upcoming': scalar("SELECT COUNT(*) FROM sessions WHERE status = 'Scheduled'", (), 0),
        'avg':      scalar('SELECT ROUND(AVG(rating), 2) FROM reviews', (), None),
        'flagged':  scalar('SELECT COUNT(*) FROM reviews WHERE rating <= 2', (), 0),
    }

    ctx = dict(tab=tab, q=q, stats=stats, categories=categories(),
               page=page, per_page=PER_PAGE, dir=direction,
               sort=DEFAULT_SORT.get(tab, 'id'), total=0, pages=1,
               users=[], skills=[], requests_rows=[], reviews=[], req_counts={},
               analytics=None,
               total_requests=scalar('SELECT COUNT(*) FROM exchangerequests', (), 0),
               total_reviews=scalar('SELECT COUNT(*) FROM reviews', (), 0))

    # ---------------------------------------------------------- analytics
    if tab == 'analytics':
        ctx['analytics'] = _analytics()
        return render_template('admin.html', **ctx)

    # ---------------------------------------------------------- students
    if tab == 'users':
        key, way, order = _order('users', request.args.get('sort'), direction)
        ctx['sort'] = key
        ctx['total'] = scalar("""SELECT COUNT(*) FROM users u
                                 WHERE %s = '' OR u.name LIKE %s OR u.email LIKE %s
                                    OR u.department LIKE %s""", (q, like, like, like), 0)
        ctx['users'] = query("""SELECT u.user_id, u.name, u.email, u.department, u.created_at,
                                       (SELECT COUNT(*) FROM userskills us
                                         WHERE us.user_id = u.user_id
                                           AND us.skill_type = 'Teach') AS teach_n,
                                       (SELECT COUNT(*) FROM userskills us
                                         WHERE us.user_id = u.user_id
                                           AND us.skill_type = 'Learn') AS learn_n,
                                       (SELECT COUNT(*) FROM exchangerequests er
                                         WHERE er.sender_id = u.user_id
                                            OR er.receiver_id = u.user_id) AS exchanges,
                                       COALESCE(v.total_reviews, 0) AS total_reviews, v.avg_rating
                                FROM users u
                                LEFT JOIN v_user_ratings v ON v.user_id = u.user_id
                                WHERE %s = '' OR u.name LIKE %s OR u.email LIKE %s
                                   OR u.department LIKE %s
                                ORDER BY """ + order + """
                                LIMIT %s OFFSET %s""",
                             (q, like, like, like, PER_PAGE, offset))

    # ---------------------------------------------------------- skills
    elif tab == 'skills':
        key, way, order = _order('skills', request.args.get('sort'), direction)
        ctx['sort'] = key
        ctx['total'] = scalar("""SELECT COUNT(*) FROM skills s
                                 WHERE %s = '' OR s.skill_name LIKE %s
                                    OR s.category LIKE %s""", (q, like, like), 0)
        ctx['skills'] = query("""SELECT s.skill_id, s.skill_name, s.category, s.description,
                                        (SELECT COUNT(*) FROM userskills us
                                          WHERE us.skill_id = s.skill_id
                                            AND us.skill_type = 'Teach') AS teachers,
                                        (SELECT COUNT(*) FROM userskills us
                                          WHERE us.skill_id = s.skill_id
                                            AND us.skill_type = 'Learn') AS learners,
                                        EXISTS (SELECT 1 FROM exchangerequests er
                                                 WHERE er.teach_skill = s.skill_id
                                                    OR er.learn_skill = s.skill_id) AS in_use
                                 FROM skills s
                                 WHERE %s = '' OR s.skill_name LIKE %s OR s.category LIKE %s
                                 ORDER BY """ + order + """
                                 LIMIT %s OFFSET %s""",
                              (q, like, like, PER_PAGE, offset))

    # ---------------------------------------------------------- requests
    elif tab == 'requests':
        key, way, order = _order('requests', request.args.get('sort'), direction)
        ctx['sort'] = key
        ctx['total'] = scalar('SELECT COUNT(*) FROM exchangerequests', (), 0)
        ctx['requests_rows'] = query("""
            SELECT er.request_id, er.status, er.created_at,
                   sn.user_id AS s_id, sn.name AS s_name,
                   rc.user_id AS r_id, rc.name AS r_name,
                   ts.skill_name AS offered, ls.skill_name AS requested,
                   (SELECT COUNT(*) FROM sessions se
                     WHERE se.request_id = er.request_id) AS session_count
            FROM       exchangerequests er
            INNER JOIN users  sn ON sn.user_id  = er.sender_id
            INNER JOIN users  rc ON rc.user_id  = er.receiver_id
            INNER JOIN skills ts ON ts.skill_id = er.teach_skill
            INNER JOIN skills ls ON ls.skill_id = er.learn_skill
            ORDER BY """ + order + """
            LIMIT %s OFFSET %s""", (PER_PAGE, offset))
        for row in query('SELECT status, COUNT(*) AS n FROM exchangerequests GROUP BY status'):
            ctx['req_counts'][row['status']] = row['n']

    # ---------------------------------------------------------- reviews
    else:
        key, way, order = _order('reviews', request.args.get('sort'), direction)
        ctx['sort'] = key
        ctx['total'] = scalar('SELECT COUNT(*) FROM reviews', (), 0)
        ctx['reviews'] = query("""SELECT r.review_id, r.rating, r.comment, r.created_at,
                                         rv.user_id AS rv_id, rv.name AS rv_name,
                                         re.user_id AS re_id, re.name AS re_name
                                  FROM       reviews r
                                  INNER JOIN users rv ON rv.user_id = r.reviewer_id
                                  INNER JOIN users re ON re.user_id = r.reviewee_id
                                  ORDER BY """ + order + """
                                  LIMIT %s OFFSET %s""", (PER_PAGE, offset))

    ctx['pages'] = max(1, -(-ctx['total'] // PER_PAGE))
    return render_template('admin.html', **ctx)


# ------------------------------------------------------------------ analytics
def _analytics():
    """
    Six aggregates, all straight SQL. Nothing here is computed in Python
    except assembling the shared month axis for the activity chart.
    """
    # 1. supply vs demand for the eight most wanted skills
    demand = query("""SELECT s.skill_name,
                             SUM(us.skill_type = 'Teach') AS teachers,
                             SUM(us.skill_type = 'Learn') AS learners
                      FROM       userskills us
                      INNER JOIN skills s ON s.skill_id = us.skill_id
                      GROUP BY s.skill_id, s.skill_name
                      ORDER BY learners DESC, teachers DESC, s.skill_name
                      LIMIT 8""")

    # 2. students per department
    depts = query("""SELECT department, COUNT(*) AS n
                     FROM users
                     GROUP BY department
                     ORDER BY n DESC, department""")

    # 3. the exchange funnel — five ordered stages
    funnel = [
        {'stage': 'Requests sent',
         'n': scalar('SELECT COUNT(*) FROM exchangerequests', (), 0)},
        {'stage': 'Accepted',
         'n': scalar("""SELECT COUNT(*) FROM exchangerequests
                        WHERE status IN ('Accepted', 'Completed')""", (), 0)},
        {'stage': 'Sessions booked',
         'n': scalar('SELECT COUNT(*) FROM sessions', (), 0)},
        {'stage': 'Sessions completed',
         'n': scalar("SELECT COUNT(*) FROM sessions WHERE status = 'Completed'", (), 0)},
        {'stage': 'Reviews written',
         'n': scalar('SELECT COUNT(*) FROM reviews', (), 0)},
    ]

    # 4. how the ratings are spread
    spread_rows = query("""SELECT rating, COUNT(*) AS n
                           FROM reviews GROUP BY rating ORDER BY rating""")
    by_rating = {r['rating']: r['n'] for r in spread_rows}
    ratings = [{'rating': n, 'n': by_rating.get(n, 0)} for n in (1, 2, 3, 4, 5)]

    # 5. activity per month — three series on ONE count axis
    req_m = query("""SELECT DATE_FORMAT(created_at, '%Y-%m') AS ym, COUNT(*) AS n
                     FROM exchangerequests GROUP BY ym ORDER BY ym""")
    ses_m = query("""SELECT DATE_FORMAT(session_date, '%Y-%m') AS ym, COUNT(*) AS n
                     FROM sessions GROUP BY ym ORDER BY ym""")
    rev_m = query("""SELECT DATE_FORMAT(created_at, '%Y-%m') AS ym, COUNT(*) AS n
                     FROM reviews GROUP BY ym ORDER BY ym""")
    months = sorted({r['ym'] for r in req_m} | {r['ym'] for r in ses_m} | {r['ym'] for r in rev_m})
    pick = lambda rows: {r['ym']: r['n'] for r in rows}          # noqa: E731
    activity = {
        'months': months,
        'requests': [int(pick(req_m).get(mth, 0)) for mth in months],
        'sessions': [int(pick(ses_m).get(mth, 0)) for mth in months],
        'reviews':  [int(pick(rev_m).get(mth, 0)) for mth in months],
    }

    # 6. the busiest students — GROUP BY … HAVING
    leaders = query("""SELECT u.user_id, u.name, u.department,
                              COUNT(DISTINCT se.session_id) AS sessions_done,
                              COALESCE(SUM(se.duration), 0) AS minutes,
                              COALESCE(v.avg_rating, 0) AS avg_rating,
                              COALESCE(v.total_reviews, 0) AS total_reviews
                       FROM       users u
                       INNER JOIN exchangerequests er
                               ON er.sender_id = u.user_id OR er.receiver_id = u.user_id
                       INNER JOIN sessions se
                               ON se.request_id = er.request_id AND se.status = 'Completed'
                       LEFT JOIN  v_user_ratings v ON v.user_id = u.user_id
                       GROUP BY u.user_id, u.name, u.department, v.avg_rating, v.total_reviews
                       HAVING COUNT(DISTINCT se.session_id) >= 2
                       ORDER BY sessions_done DESC, minutes DESC, u.name
                       LIMIT 8""")

    # MySQL hands SUM()/COUNT() back as Decimal; the chart payload is JSON,
    # so coerce to plain ints before it reaches |tojson.
    demand = [{'skill_name': d['skill_name'],
               'teachers': int(d['teachers'] or 0),
               'learners': int(d['learners'] or 0)} for d in demand]
    depts = [{'department': d['department'], 'n': int(d['n'])} for d in depts]
    funnel = [{'stage': f['stage'], 'n': int(f['n'])} for f in funnel]
    ratings = [{'rating': int(r['rating']), 'n': int(r['n'])} for r in ratings]

    return {
        'demand': demand,
        'depts': depts,
        'funnel': funnel,
        'ratings': ratings,
        'activity': activity,
        'leaders': leaders,
        'headline': {
            'exchanges': scalar("SELECT COUNT(*) FROM exchangerequests WHERE status = 'Completed'", (), 0),
            'hours': round((scalar("SELECT COALESCE(SUM(duration),0) FROM sessions "
                                   "WHERE status = 'Completed'", (), 0)) / 60),
            'avg': float(scalar('SELECT ROUND(AVG(rating), 2) FROM reviews', (), 0) or 0),
            'match_rate': round(100.0 * scalar(
                "SELECT COUNT(*) FROM exchangerequests WHERE status IN ('Accepted','Completed')", (), 0)
                / max(1, scalar('SELECT COUNT(*) FROM exchangerequests', (), 1))),
        },
    }


# ------------------------------------------------------------------ CSV export
EXPORTS = {
    'users': ('users.csv', """SELECT u.user_id, u.name, u.email, u.department, u.bio,
                                     u.created_at,
                                     (SELECT COUNT(*) FROM userskills x
                                       WHERE x.user_id = u.user_id AND x.skill_type='Teach') AS teaches,
                                     (SELECT COUNT(*) FROM userskills x
                                       WHERE x.user_id = u.user_id AND x.skill_type='Learn') AS learns,
                                     COALESCE(v.total_reviews,0) AS total_reviews, v.avg_rating
                              FROM users u
                              LEFT JOIN v_user_ratings v ON v.user_id = u.user_id
                              ORDER BY u.user_id"""),
    'skills': ('skills.csv', """SELECT s.skill_id, s.skill_name, s.category, s.description,
                                       (SELECT COUNT(*) FROM userskills x
                                         WHERE x.skill_id = s.skill_id AND x.skill_type='Teach') AS teachers,
                                       (SELECT COUNT(*) FROM userskills x
                                         WHERE x.skill_id = s.skill_id AND x.skill_type='Learn') AS learners
                                FROM skills s ORDER BY s.skill_id"""),
    'requests': ('exchangerequests.csv', 'SELECT * FROM v_request_details ORDER BY request_id'),
    'sessions': ('sessions.csv', 'SELECT * FROM v_session_overview ORDER BY session_id'),
    'reviews': ('reviews.csv', """SELECT r.review_id, r.session_id, rv.name AS reviewer,
                                         re.name AS reviewee, r.rating, r.comment, r.created_at
                                  FROM reviews r
                                  JOIN users rv ON rv.user_id = r.reviewer_id
                                  JOIN users re ON re.user_id = r.reviewee_id
                                  ORDER BY r.review_id"""),
}


@bp.route('/admin/export/<name>.csv')
@login_required
def export(name):
    if name not in EXPORTS:
        notify('Nothing to export under that name.', None, 'warning')
        return redirect(url_for('admin.index'))

    filename, sql = EXPORTS[name]
    rows = query(sql)

    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(['' if v is None else v for v in row.values()])

    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=' + filename})


# ------------------------------------------------------------------ students
@bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    me = current_user()
    if user_id == me['user_id']:
        notify('You cannot delete the account you are signed in with.', None, 'danger')
        return redirect(url_for('admin.index', tab='users'))

    victim = query('SELECT name FROM users WHERE user_id = %s', (user_id,), one=True)
    if not victim:
        notify('No such student.', None, 'warning')
        return redirect(url_for('admin.index', tab='users'))

    skills_n = scalar('SELECT COUNT(*) FROM userskills WHERE user_id = %s', (user_id,), 0)
    reqs_n = scalar("""SELECT COUNT(*) FROM exchangerequests
                       WHERE sender_id = %s OR receiver_id = %s""", (user_id, user_id), 0)

    execute('DELETE FROM users WHERE user_id = %s', (user_id,))
    notify('Deleted %s — ON DELETE CASCADE also removed %d skill rows and %d requests.'
           % (victim['name'], skills_n, reqs_n),
           'DELETE FROM users WHERE user_id = %s', 'success')
    return redirect(url_for('admin.index', tab='users'))


# ------------------------------------------------------------------ skills
@bp.route('/admin/skills/add', methods=['POST'])
@login_required
def add_skill():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()

    if len(name) < 2:
        notify('Enter a skill name.', None, 'danger')
    elif query('SELECT skill_id FROM skills WHERE skill_name = %s', (name,), one=True):
        notify('That skill already exists — UNIQUE (skill_name) blocks the duplicate.',
               None, 'danger')
    else:
        new_id, _ = execute("""INSERT INTO skills (skill_name, category, description)
                               VALUES (%s, %s, %s)""",
                            (name, category or 'Programming', description or None))
        notify('Skill #%d added.' % new_id,
               'INSERT INTO skills (skill_name, category, description) '
               'VALUES (%s, %s, %s)', 'success')
    return redirect(url_for('admin.index', tab='skills'))


@bp.route('/admin/skills/<int:skill_id>/delete', methods=['POST'])
@login_required
def delete_skill(skill_id):
    try:
        _, n = execute('DELETE FROM skills WHERE skill_id = %s', (skill_id,))
        if n:
            notify('Skill deleted — its userskills rows went with it (ON DELETE CASCADE).',
                   'DELETE FROM skills WHERE skill_id = %s', 'success')
        else:
            notify('No such skill.', None, 'warning')
    except IntegrityError:
        notify('An exchange request still points at this skill. ON DELETE RESTRICT '
               'blocks the DELETE until those requests are removed.', None, 'danger')
    return redirect(url_for('admin.index', tab='skills'))


# ------------------------------------------------------------------ reviews
@bp.route('/admin/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    _, n = execute('DELETE FROM reviews WHERE review_id = %s', (review_id,))
    if n:
        notify('Review #%d removed.' % review_id,
               'DELETE FROM reviews WHERE review_id = %s', 'success')
    else:
        notify('No such review.', None, 'warning')
    return redirect(url_for('admin.index', tab='reviews'))
