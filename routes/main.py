"""
routes/main.py — the public landing page and the signed-in dashboard.

The dashboard is where the matching query lives: a self-join on userskills
that finds students who teach something I want to learn AND want to learn
something I teach.
"""

import datetime

from flask import Blueprint, redirect, render_template, url_for

from db import query, scalar
from helpers import current_user, login_required, rating_of, skills_of

bp = Blueprint('main', __name__)


# ------------------------------------------------------------------ landing
@bp.route('/')
def index():
    if current_user():
        return redirect(url_for('main.dashboard'))

    stats = {
        'students':  scalar('SELECT COUNT(*) FROM users', (), 0),
        'skills':    scalar('SELECT COUNT(*) FROM skills', (), 0),
        'completed': scalar("SELECT COUNT(*) FROM exchangerequests WHERE status = 'Completed'", (), 0),
        'minutes':   scalar("SELECT COALESCE(SUM(duration), 0) FROM sessions WHERE status = 'Completed'", (), 0),
        'avg':       scalar('SELECT ROUND(AVG(rating), 2) FROM reviews', (), None),
    }
    stats['hours'] = round(stats['minutes'] / 60)

    # One real exchange, shown in the hero — the v_request_details VIEW gives
    # readable names instead of raw foreign keys.
    hero = query("""SELECT er.request_id, er.created_at,
                           sn.name AS sender_name, sn.department AS sender_dept,
                           rc.name AS receiver_name, rc.department AS receiver_dept,
                           ts.skill_name AS teach_name, ts.category AS teach_cat,
                           ls.skill_name AS learn_name, ls.category AS learn_cat,
                           (SELECT COUNT(*) FROM sessions se
                             WHERE se.request_id = er.request_id) AS session_count,
                           (SELECT ROUND(AVG(rv.rating), 1) FROM reviews rv
                             JOIN sessions se2 ON se2.session_id = rv.session_id
                            WHERE se2.request_id = er.request_id) AS avg_rating
                    FROM exchangerequests er
                    INNER JOIN users  sn ON sn.user_id  = er.sender_id
                    INNER JOIN users  rc ON rc.user_id  = er.receiver_id
                    INNER JOIN skills ts ON ts.skill_id = er.teach_skill
                    INNER JOIN skills ls ON ls.skill_id = er.learn_skill
                    WHERE er.status = 'Completed'
                    ORDER BY er.request_id
                    LIMIT 1""", one=True)

    # GROUP BY + ORDER BY COUNT: the six most wanted skills.
    demand = query("""SELECT s.skill_id, s.skill_name, s.category, s.description,
                             COUNT(*) AS learners,
                             (SELECT COUNT(*) FROM userskills t
                               WHERE t.skill_id = s.skill_id AND t.skill_type = 'Teach') AS teachers
                      FROM userskills us
                      INNER JOIN skills s ON s.skill_id = us.skill_id
                      WHERE us.skill_type = 'Learn'
                      GROUP BY s.skill_id, s.skill_name, s.category, s.description
                      ORDER BY learners DESC, s.skill_name
                      LIMIT 6""")

    dept_counts = query("""SELECT department, COUNT(*) AS n
                           FROM users GROUP BY department
                           ORDER BY n DESC, department""")

    table_counts = [
        ('users',            scalar('SELECT COUNT(*) FROM users', (), 0)),
        ('skills',           scalar('SELECT COUNT(*) FROM skills', (), 0)),
        ('userskills',       scalar('SELECT COUNT(*) FROM userskills', (), 0)),
        ('exchangerequests', scalar('SELECT COUNT(*) FROM exchangerequests', (), 0)),
        ('sessions',         scalar('SELECT COUNT(*) FROM sessions', (), 0)),
        ('reviews',          scalar('SELECT COUNT(*) FROM reviews', (), 0)),
    ]

    return render_template('index.html', stats=stats, hero=hero, demand=demand,
                           dept_counts=dept_counts, table_counts=table_counts)


# ------------------------------------------------------------------ dashboard
@bp.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    uid = user['user_id']

    my_teach = skills_of(uid, 'Teach')
    my_learn = skills_of(uid, 'Learn')
    my_rating = rating_of(uid)

    stats = {
        'pending': scalar("""SELECT COUNT(*) FROM exchangerequests
                             WHERE receiver_id = %s AND status = 'Pending'""", (uid,), 0),
        'upcoming': scalar("""SELECT COUNT(*) FROM sessions se
                              JOIN exchangerequests er ON er.request_id = se.request_id
                              WHERE se.status = 'Scheduled'
                                AND (er.sender_id = %s OR er.receiver_id = %s)""", (uid, uid), 0),
        'done': scalar("""SELECT COUNT(*) FROM exchangerequests
                          WHERE (sender_id = %s OR receiver_id = %s)
                            AND status = 'Completed'""", (uid, uid), 0),
        'rating': my_rating['avg'],
    }

    # ---------------- suggested matches ----------------
    # Self-join on userskills: they teach something on my learn list AND
    # want something on my teach list, and I have no request with them yet.
    match_rows = query("""
        SELECT  o.user_id, o.name, o.department,
                COUNT(DISTINCT t.skill_id) + COUNT(DISTINCT w.skill_id) AS score
        FROM        users      o
        INNER JOIN  userskills t ON t.user_id = o.user_id AND t.skill_type = 'Teach'
        INNER JOIN  userskills w ON w.user_id = o.user_id AND w.skill_type = 'Learn'
        WHERE o.user_id <> %s
          AND t.skill_id IN (SELECT skill_id FROM userskills
                              WHERE user_id = %s AND skill_type = 'Learn')
          AND w.skill_id IN (SELECT skill_id FROM userskills
                              WHERE user_id = %s AND skill_type = 'Teach')
          AND NOT EXISTS (SELECT 1 FROM exchangerequests er
                           WHERE (er.sender_id = %s AND er.receiver_id = o.user_id)
                              OR (er.receiver_id = %s AND er.sender_id = o.user_id))
        GROUP BY o.user_id, o.name, o.department
        ORDER BY score DESC, o.name
        LIMIT 3""", (uid, uid, uid, uid, uid))

    matches = []
    for row in match_rows:
        give = query("""SELECT s.skill_id, s.skill_name
                        FROM userskills us
                        INNER JOIN skills s ON s.skill_id = us.skill_id
                        WHERE us.user_id = %s AND us.skill_type = 'Learn'
                          AND us.skill_id IN (SELECT skill_id FROM userskills
                                               WHERE user_id = %s AND skill_type = 'Teach')
                        ORDER BY s.skill_name LIMIT 1""", (row['user_id'], uid), one=True)
        take = query("""SELECT s.skill_id, s.skill_name, us.proficiency
                        FROM userskills us
                        INNER JOIN skills s ON s.skill_id = us.skill_id
                        WHERE us.user_id = %s AND us.skill_type = 'Teach'
                          AND us.skill_id IN (SELECT skill_id FROM userskills
                                               WHERE user_id = %s AND skill_type = 'Learn')
                        ORDER BY s.skill_name LIMIT 1""", (row['user_id'], uid), one=True)
        if give and take:
            matches.append({'other': row, 'give': give, 'take': take,
                            'rating': rating_of(row['user_id'])})

    # ---------------- requests waiting for my answer ----------------
    pending = query("""SELECT er.request_id, er.created_at,
                              u.user_id, u.name, u.department,
                              ts.skill_name AS teach_name,
                              ls.skill_name AS learn_name
                       FROM exchangerequests er
                       INNER JOIN users  u  ON u.user_id  = er.sender_id
                       INNER JOIN skills ts ON ts.skill_id = er.teach_skill
                       INNER JOIN skills ls ON ls.skill_id = er.learn_skill
                       WHERE er.receiver_id = %s AND er.status = 'Pending'
                       ORDER BY er.created_at DESC""", (uid,))

    # ---------------- next three sessions ----------------
    next_sessions = query("""
        SELECT se.session_id, se.session_date, se.session_time, se.duration,
               se.mode, se.location, se.meeting_link, se.status,
               p.user_id AS p_id, p.name AS p_name,
               CASE WHEN er.sender_id = %s THEN ts.skill_name ELSE ls.skill_name END AS skill_name
        FROM sessions se
        INNER JOIN exchangerequests er ON er.request_id = se.request_id
        INNER JOIN users p ON p.user_id = CASE WHEN er.sender_id = %s
                                               THEN er.receiver_id ELSE er.sender_id END
        INNER JOIN skills ts ON ts.skill_id = er.teach_skill
        INNER JOIN skills ls ON ls.skill_id = er.learn_skill
        WHERE se.status = 'Scheduled' AND (er.sender_id = %s OR er.receiver_id = %s)
        ORDER BY se.session_date, se.session_time
        LIMIT 3""", (uid, uid, uid, uid))

    # ---------------- three most recent reviews about me ----------------
    recent_reviews = query("""SELECT r.review_id, r.rating, r.comment, r.created_at,
                                     u.user_id, u.name
                              FROM reviews r
                              INNER JOIN users u ON u.user_id = r.reviewer_id
                              WHERE r.reviewee_id = %s
                              ORDER BY r.review_id DESC
                              LIMIT 3""", (uid,))

    # ---------------- right rail ----------------
    top_rated = query("""SELECT user_id, name, department, avg_rating, total_reviews
                         FROM v_user_ratings
                         WHERE total_reviews >= 2 AND user_id <> %s
                         ORDER BY avg_rating DESC, total_reviews DESC
                         LIMIT 5""", (uid,))

    demand = query("""SELECT s.skill_id, s.skill_name, COUNT(*) AS learners
                      FROM userskills us
                      INNER JOIN skills s ON s.skill_id = us.skill_id
                      WHERE us.skill_type = 'Learn'
                      GROUP BY s.skill_id, s.skill_name
                      ORDER BY learners DESC, s.skill_name
                      LIMIT 8""")

    hour = datetime.datetime.now().hour
    greeting = 'Good morning' if hour < 12 else ('Good afternoon' if hour < 17 else 'Good evening')

    return render_template('dashboard.html',
                           greeting=greeting, stats=stats,
                           my_teach=my_teach, my_learn=my_learn,
                           matches=matches, pending=pending,
                           next_sessions=next_sessions,
                           recent_reviews=recent_reviews,
                           top_rated=top_rated, demand=demand)
