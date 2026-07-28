"""
routes/sessions.py — booking and managing sessions.

A session belongs to exactly one ACCEPTED request. The UNIQUE key
(request_id, session_date, session_time) is what stops the same slot from
being booked twice, and duration is guarded by CHECK (15..480).
"""

from flask import Blueprint, redirect, render_template, request, url_for

from db import execute, query, time_to_str
from helpers import current_user, login_required, notify, today_iso

bp = Blueprint('sessions', __name__)

BASE_SQL = """
    SELECT se.session_id, se.request_id, se.session_date, se.session_time,
           se.duration, se.mode, se.location, se.meeting_link, se.status,
           er.sender_id, er.receiver_id,
           p.user_id AS p_id, p.name AS p_name, p.department AS p_dept,
           CASE WHEN er.sender_id = %s THEN ts.skill_name ELSE ls.skill_name END AS i_teach,
           CASE WHEN er.sender_id = %s THEN ls.skill_name ELSE ts.skill_name END AS i_learn,
           EXISTS (SELECT 1 FROM reviews r
                    WHERE r.session_id = se.session_id AND r.reviewer_id = %s) AS reviewed
    FROM       sessions se
    INNER JOIN exchangerequests er ON er.request_id = se.request_id
    INNER JOIN users  p  ON p.user_id = CASE WHEN er.sender_id = %s
                                             THEN er.receiver_id ELSE er.sender_id END
    INNER JOIN skills ts ON ts.skill_id = er.teach_skill
    INNER JOIN skills ls ON ls.skill_id = er.learn_skill
    WHERE er.sender_id = %s OR er.receiver_id = %s
    ORDER BY se.session_date, se.session_time
"""


def my_sessions(uid):
    rows = query(BASE_SQL, (uid,) * 6)
    for row in rows:
        row['time_str'] = time_to_str(row['session_time'])
    return rows


@bp.route('/sessions')
@login_required
def index():
    me = current_user()
    uid = me['user_id']
    tab = request.args.get('tab', 'upcoming')
    view = request.args.get('view', 'cards')

    rows = my_sessions(uid)

    wanted = {'upcoming': 'Scheduled', 'past': 'Completed', 'cancelled': 'Cancelled'}
    shown = [r for r in rows if r['status'] == wanted.get(tab, 'Scheduled')]
    if tab == 'past':
        shown = list(reversed(shown))

    minutes = sum(r['duration'] for r in rows if r['status'] == 'Completed')
    stats = {
        'upcoming':  sum(1 for r in rows if r['status'] == 'Scheduled'),
        'completed': sum(1 for r in rows if r['status'] == 'Completed'),
        'hours':     round(minutes / 60.0, 1),
        'online':    sum(1 for r in rows if r['mode'] == 'Online'),
        'offline':   sum(1 for r in rows if r['mode'] == 'Offline'),
    }

    # Only accepted requests can be booked — sessions.request_id is a FK.
    bookable = query("""SELECT er.request_id, p.name AS p_name,
                               ts.skill_name AS teach_name, ls.skill_name AS learn_name
                        FROM       exchangerequests er
                        INNER JOIN users  p  ON p.user_id = CASE WHEN er.sender_id = %s
                                                                 THEN er.receiver_id
                                                                 ELSE er.sender_id END
                        INNER JOIN skills ts ON ts.skill_id = er.teach_skill
                        INNER JOIN skills ls ON ls.skill_id = er.learn_skill
                        WHERE er.status = 'Accepted'
                          AND (er.sender_id = %s OR er.receiver_id = %s)
                        ORDER BY er.request_id""", (uid, uid, uid))

    return render_template('sessions.html', rows=shown, stats=stats, tab=tab,
                           view=view, bookable=bookable,
                           preset=request.args.get('book', ''),
                           today=today_iso())


# ------------------------------------------------------------------ book
@bp.route('/sessions/book', methods=['POST'])
@login_required
def book():
    me = current_user()
    uid = me['user_id']
    back = url_for('sessions.index')

    try:
        request_id = int(request.form.get('request_id', 0) or 0)
        duration = int(request.form.get('duration', 60) or 60)
    except ValueError:
        notify('Invalid booking details.', None, 'danger')
        return redirect(back)

    date = request.form.get('date', '').strip()
    time_v = request.form.get('time', '').strip()
    mode = request.form.get('mode', 'Online')
    link = request.form.get('link', '').strip()
    location = request.form.get('location', '').strip()

    owned = query("""SELECT request_id FROM exchangerequests
                     WHERE request_id = %s AND status = 'Accepted'
                       AND (sender_id = %s OR receiver_id = %s)""",
                  (request_id, uid, uid), one=True)
    if not owned:
        notify('Accept a request before booking a session against it.', None, 'warning')
        return redirect(back)
    if not date or date < today_iso():
        notify('Choose today or a later date.', None, 'danger')
        return redirect(back)
    if not time_v:
        notify('Pick a start time.', None, 'danger')
        return redirect(back)
    if not 15 <= duration <= 480:
        notify('Duration must be between 15 and 480 minutes — CHECK constraint.',
               None, 'danger')
        return redirect(back)
    if mode == 'Online' and not link.startswith(('http://', 'https://')):
        notify('Online sessions need a meeting link.', None, 'danger')
        return redirect(back)
    if mode == 'Offline' and not location:
        notify('Offline sessions need a place on campus.', None, 'danger')
        return redirect(back)

    clash = query("""SELECT session_id FROM sessions
                     WHERE request_id = %s AND session_date = %s AND session_time = %s""",
                  (request_id, date, time_v), one=True)
    if clash:
        notify('That exact slot is already booked — UNIQUE '
               '(request_id, session_date, session_time).', None, 'danger')
        return redirect(back)

    new_id, _ = execute("""INSERT INTO sessions
                             (request_id, session_date, session_time, duration,
                              mode, location, meeting_link, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, 'Scheduled')""",
                        (request_id, date, time_v, duration, mode,
                         location or None, link or None))
    notify('Session #%d booked for %s at %s.' % (new_id, date, time_v),
           'INSERT INTO sessions (request_id, session_date, session_time, duration, '
           "mode, location, meeting_link) VALUES (%s, %s, %s, %s, %s, %s, %s)", 'success')
    return redirect(back)


# ------------------------------------------------------------------ status
def _owned(session_id, uid):
    return query("""SELECT se.session_id, se.request_id, se.status
                    FROM sessions se
                    JOIN exchangerequests er ON er.request_id = se.request_id
                    WHERE se.session_id = %s AND (er.sender_id = %s OR er.receiver_id = %s)""",
                 (session_id, uid, uid), one=True)


@bp.route('/sessions/<int:session_id>/complete', methods=['POST'])
@login_required
def complete(session_id):
    me = current_user()
    row = _owned(session_id, me['user_id'])
    if not row or row['status'] != 'Scheduled':
        notify('That session cannot be completed.', None, 'warning')
        return redirect(url_for('sessions.index'))

    execute("UPDATE sessions SET status = 'Completed' WHERE session_id = %s", (session_id,))
    # Once every session on a request is finished the exchange itself is done.
    left = query("""SELECT COUNT(*) AS n FROM sessions
                    WHERE request_id = %s AND status = 'Scheduled'""",
                 (row['request_id'],), one=True)['n']
    if left == 0:
        execute("""UPDATE exchangerequests SET status = 'Completed'
                   WHERE request_id = %s AND status = 'Accepted'""", (row['request_id'],))

    notify('Session #%d completed — you can review your partner now.' % session_id,
           "UPDATE sessions SET status = 'Completed' WHERE session_id = %s", 'success')
    return redirect(url_for('sessions.index', tab='past'))


@bp.route('/sessions/<int:session_id>/cancel', methods=['POST'])
@login_required
def cancel(session_id):
    me = current_user()
    row = _owned(session_id, me['user_id'])
    if not row or row['status'] != 'Scheduled':
        notify('That session cannot be cancelled.', None, 'warning')
        return redirect(url_for('sessions.index'))

    execute("UPDATE sessions SET status = 'Cancelled' WHERE session_id = %s", (session_id,))
    notify('Session #%d cancelled.' % session_id,
           "UPDATE sessions SET status = 'Cancelled' WHERE session_id = %s", 'success')
    return redirect(url_for('sessions.index'))


@bp.route('/sessions/<int:session_id>/reschedule', methods=['POST'])
@login_required
def reschedule(session_id):
    me = current_user()
    row = _owned(session_id, me['user_id'])
    date = request.form.get('date', '').strip()
    time_v = request.form.get('time', '').strip()

    if not row or row['status'] != 'Scheduled':
        notify('That session cannot be rescheduled.', None, 'warning')
    elif not date or not time_v:
        notify('Pick both a new date and a new time.', None, 'danger')
    elif date < today_iso():
        notify('Choose today or a later date.', None, 'danger')
    else:
        clash = query("""SELECT session_id FROM sessions
                         WHERE request_id = %s AND session_date = %s
                           AND session_time = %s AND session_id <> %s""",
                      (row['request_id'], date, time_v, session_id), one=True)
        if clash:
            notify('That slot is already taken for this exchange.', None, 'danger')
        else:
            execute("""UPDATE sessions SET session_date = %s, session_time = %s
                       WHERE session_id = %s""", (date, time_v, session_id))
            notify('Session #%d moved to %s at %s.' % (session_id, date, time_v),
                   'UPDATE sessions SET session_date = %s, session_time = %s '
                   'WHERE session_id = %s', 'success')
    return redirect(url_for('sessions.index'))
