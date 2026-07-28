"""
SkillSwap NSU  —  helpers.py
Session handling, small formatters and the shared bits every page needs
(the navigation counters and the left rail card).
"""

import datetime
import functools
import os

from flask import current_app, flash, g, redirect, session, url_for

from db import date_to_str, query, scalar, time_to_str

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

AV_TINTS = ['#0A66C2', '#1B5E9E', '#2E7DBE', '#134E7A',
            '#3D6FA5', '#0F5C8C', '#4A7FB5', '#26689F']

LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Expert']


# ------------------------------------------------------------------ formatting
def fmt_date(value):
    """'2026-07-25' -> '25 Jul 2026'"""
    iso = date_to_str(value)
    if not iso:
        return ''
    y, m, d = iso.split('-')
    return '%d %s %s' % (int(d), MONTHS[int(m) - 1], y)


def fmt_time(value):
    """'15:30' -> '3:30 PM'"""
    hm = time_to_str(value)
    if not hm:
        return ''
    h, m = (int(x) for x in hm.split(':')[:2])
    ap = 'PM' if h >= 12 else 'AM'
    h = h % 12 or 12
    return '%d:%02d %s' % (h, m, ap)


def initials(name):
    parts = str(name or '?').strip().split()
    first = parts[0][0] if parts else ''
    last = parts[-1][0] if len(parts) > 1 else ''
    return (first + last).upper()


def month_abbr(value):
    iso = date_to_str(value)
    return MONTHS[int(iso[5:7]) - 1] if iso else ''


def day_num(value):
    iso = date_to_str(value)
    return int(iso[8:10]) if iso else ''


def year_num(value):
    iso = date_to_str(value)
    return iso[:4] if iso else ''


def has_upload(filename):
    if not filename or filename == 'default.png':
        return False
    return os.path.isfile(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))


def today_iso():
    return datetime.date.today().strftime('%Y-%m-%d')


# ------------------------------------------------------------------ auth
def current_user():
    """The signed-in student, or None. Cached for the length of the request."""
    if 'user' not in g:
        uid = session.get('user_id')
        g.user = query('SELECT * FROM users WHERE user_id = %s', (uid,), one=True) if uid else None
        if uid and g.user is None:          # account was deleted mid-session
            session.clear()
    return g.user


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash('Please sign in first.', 'warning')
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ feedback
def notify(message, sql=None, category='info'):
    """
    Flash a message. When SHOW_SQL_TOASTS is on, the SQL statement that
    actually ran is shown underneath it — useful when demonstrating the
    project to the lab instructor.
    """
    if sql and current_app.config.get('SHOW_SQL_TOASTS', True):
        flash(message + '||' + ' '.join(sql.split()), category)
    else:
        flash(message, category)


# ------------------------------------------------------------------ shell data
def shell_context(user):
    """
    Counters used by the top navigation and the left rail on every
    signed-in page. Four small aggregate queries.
    """
    uid = user['user_id']

    pending = scalar("""SELECT COUNT(*) FROM exchangerequests
                        WHERE receiver_id = %s AND status = 'Pending'""", (uid,), 0)

    upcoming = scalar("""SELECT COUNT(*)
                         FROM sessions se
                         JOIN exchangerequests er ON er.request_id = se.request_id
                         WHERE se.status = 'Scheduled'
                           AND (er.sender_id = %s OR er.receiver_id = %s)""", (uid, uid), 0)

    exchanges = scalar("""SELECT COUNT(*) FROM exchangerequests
                          WHERE sender_id = %s OR receiver_id = %s""", (uid, uid), 0)

    teach_n = scalar("""SELECT COUNT(*) FROM userskills
                        WHERE user_id = %s AND skill_type = 'Teach'""", (uid,), 0)
    learn_n = scalar("""SELECT COUNT(*) FROM userskills
                        WHERE user_id = %s AND skill_type = 'Learn'""", (uid,), 0)

    rating = rating_of(uid)

    return {
        'pending_count':   pending,
        'upcoming_count':  upcoming,
        'exchange_count':  exchanges,
        'teach_count':     teach_n,
        'learn_count':     learn_n,
        'my_rating':       rating,
    }


# ------------------------------------------------------------------ shared queries
def rating_of(user_id):
    """
    Review count and average for one student, read from the v_user_ratings
    VIEW rather than recomputing the aggregate here.
    """
    row = query("""SELECT total_reviews, avg_rating
                   FROM v_user_ratings WHERE user_id = %s""", (user_id,), one=True)
    if not row or not row['total_reviews']:
        return {'count': 0, 'avg': None}
    return {'count': int(row['total_reviews']), 'avg': float(row['avg_rating'])}


def skills_of(user_id, skill_type):
    """Every skill a student teaches (or wants to learn), alphabetically."""
    return query("""SELECT s.skill_id, s.skill_name, s.category, s.description,
                           us.proficiency, us.user_skill_id
                    FROM userskills us
                    INNER JOIN skills s ON s.skill_id = us.skill_id
                    WHERE us.user_id = %s AND us.skill_type = %s
                    ORDER BY s.skill_name""", (user_id, skill_type))


def departments():
    return [r['department'] for r in
            query('SELECT DISTINCT department FROM users ORDER BY department')]


def categories():
    return [r['category'] for r in
            query('SELECT DISTINCT category FROM skills ORDER BY category')]


def all_skills():
    return query('SELECT skill_id, skill_name, category, description '
                 'FROM skills ORDER BY category, skill_name')
