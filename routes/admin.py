"""
routes/admin.py — the admin console.

Deleting a student demonstrates ON DELETE CASCADE (their skills, requests,
sessions and reviews disappear with them). Deleting a skill that an exchange
request still points at demonstrates ON DELETE RESTRICT — MySQL refuses.
"""

from flask import Blueprint, redirect, render_template, request, url_for
from mysql.connector import IntegrityError

from db import execute, query, scalar
from helpers import categories, current_user, login_required, notify

bp = Blueprint('admin', __name__)


@bp.route('/admin')
@login_required
def index():
    tab = request.args.get('tab', 'users')
    q = (request.args.get('q') or '').strip()
    like = '%' + q + '%'

    stats = {
        'students': scalar('SELECT COUNT(*) FROM users', (), 0),
        'skills':   scalar('SELECT COUNT(*) FROM skills', (), 0),
        'pending':  scalar("SELECT COUNT(*) FROM exchangerequests WHERE status = 'Pending'", (), 0),
        'upcoming': scalar("SELECT COUNT(*) FROM sessions WHERE status = 'Scheduled'", (), 0),
        'avg':      scalar('SELECT ROUND(AVG(rating), 2) FROM reviews', (), None),
        'flagged':  scalar('SELECT COUNT(*) FROM reviews WHERE rating <= 2', (), 0),
    }

    users = skills = requests_rows = reviews = []
    req_counts = {}

    if tab == 'users':
        users = query("""SELECT u.user_id, u.name, u.email, u.department, u.created_at,
                                (SELECT COUNT(*) FROM userskills us
                                  WHERE us.user_id = u.user_id AND us.skill_type = 'Teach') AS teach_n,
                                (SELECT COUNT(*) FROM userskills us
                                  WHERE us.user_id = u.user_id AND us.skill_type = 'Learn') AS learn_n,
                                (SELECT COUNT(*) FROM exchangerequests er
                                  WHERE er.sender_id = u.user_id
                                     OR er.receiver_id = u.user_id) AS exchanges,
                                COALESCE(v.total_reviews, 0) AS total_reviews, v.avg_rating
                         FROM users u
                         LEFT JOIN v_user_ratings v ON v.user_id = u.user_id
                         WHERE %s = '' OR u.name LIKE %s OR u.email LIKE %s
                            OR u.department LIKE %s
                         ORDER BY u.user_id""", (q, like, like, like))

    elif tab == 'skills':
        skills = query("""SELECT s.skill_id, s.skill_name, s.category, s.description,
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
                          ORDER BY s.skill_id""", (q, like, like))

    elif tab == 'requests':
        requests_rows = query("""SELECT er.request_id, er.status, er.created_at,
                                        sn.user_id AS s_id, sn.name AS s_name,
                                        rc.user_id AS r_id, rc.name AS r_name,
                                        ts.skill_name AS offered,
                                        ls.skill_name AS requested,
                                        (SELECT COUNT(*) FROM sessions se
                                          WHERE se.request_id = er.request_id) AS session_count
                                 FROM       exchangerequests er
                                 INNER JOIN users  sn ON sn.user_id  = er.sender_id
                                 INNER JOIN users  rc ON rc.user_id  = er.receiver_id
                                 INNER JOIN skills ts ON ts.skill_id = er.teach_skill
                                 INNER JOIN skills ls ON ls.skill_id = er.learn_skill
                                 ORDER BY er.created_at DESC, er.request_id DESC
                                 LIMIT 30""")
        for row in query("""SELECT status, COUNT(*) AS n
                            FROM exchangerequests GROUP BY status"""):
            req_counts[row['status']] = row['n']

    else:
        reviews = query("""SELECT r.review_id, r.rating, r.comment, r.created_at,
                                  rv.user_id AS rv_id, rv.name AS rv_name,
                                  re.user_id AS re_id, re.name AS re_name
                           FROM       reviews r
                           INNER JOIN users rv ON rv.user_id = r.reviewer_id
                           INNER JOIN users re ON re.user_id = r.reviewee_id
                           ORDER BY r.rating, r.review_id""")

    total_requests = scalar('SELECT COUNT(*) FROM exchangerequests', (), 0)
    total_reviews = scalar('SELECT COUNT(*) FROM reviews', (), 0)

    return render_template('admin.html', tab=tab, q=q, stats=stats,
                           users=users, skills=skills,
                           requests_rows=requests_rows, req_counts=req_counts,
                           reviews=reviews, categories=categories(),
                           total_requests=total_requests, total_reviews=total_reviews)


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
