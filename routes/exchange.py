"""
routes/exchange.py — exchange requests (send, accept, decline, cancel).

The status column is the whole state machine:
    Pending -> Accepted -> Completed
    Pending -> Rejected
    Pending / Accepted -> Cancelled
"""

from flask import Blueprint, redirect, render_template, request, url_for

from db import execute, query
from helpers import current_user, login_required, notify

bp = Blueprint('exchange', __name__)


# ------------------------------------------------------------------ list
@bp.route('/requests')
@login_required
def index():
    me = current_user()
    uid = me['user_id']
    direction = request.args.get('dir', 'received')
    status_f = request.args.get('status', '')

    rows = query("""
        SELECT er.request_id, er.sender_id, er.receiver_id, er.status, er.created_at,
               CASE WHEN er.sender_id = %s THEN 'sent' ELSE 'received' END AS dir,
               CASE WHEN er.sender_id = %s THEN ts.skill_name ELSE ls.skill_name END AS i_give,
               CASE WHEN er.sender_id = %s THEN ts.category   ELSE ls.category   END AS i_give_cat,
               CASE WHEN er.sender_id = %s THEN ls.skill_name ELSE ts.skill_name END AS i_get,
               CASE WHEN er.sender_id = %s THEN ls.category   ELSE ts.category   END AS i_get_cat,
               p.user_id AS p_id, p.name AS p_name, p.department AS p_dept,
               COALESCE(v.total_reviews, 0) AS total_reviews, v.avg_rating,
               (SELECT COUNT(*) FROM sessions se
                 WHERE se.request_id = er.request_id AND se.status <> 'Cancelled') AS booked
        FROM       exchangerequests er
        INNER JOIN skills ts ON ts.skill_id = er.teach_skill
        INNER JOIN skills ls ON ls.skill_id = er.learn_skill
        INNER JOIN users  p  ON p.user_id = CASE WHEN er.sender_id = %s
                                                 THEN er.receiver_id ELSE er.sender_id END
        LEFT JOIN  v_user_ratings v ON v.user_id = p.user_id
        WHERE er.sender_id = %s OR er.receiver_id = %s
        ORDER BY er.created_at DESC, er.request_id DESC
    """, (uid, uid, uid, uid, uid, uid, uid, uid))

    counts = {s: 0 for s in ('Pending', 'Accepted', 'Completed', 'Rejected', 'Cancelled')}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1

    shown = [r for r in rows
             if (direction == 'all' or r['dir'] == direction)
             and (not status_f or r['status'] == status_f)]

    return render_template('requests.html', rows=shown, counts=counts,
                           dir=direction, status_f=status_f)


# ------------------------------------------------------------------ send
@bp.route('/requests/send', methods=['POST'])
@login_required
def send():
    me = current_user()
    uid = me['user_id']
    receiver_id = int(request.form.get('receiver_id', 0) or 0)
    teach_skill = int(request.form.get('teach_skill', 0) or 0)
    learn_skill = int(request.form.get('learn_skill', 0) or 0)
    back = request.form.get('next') or url_for('exchange.index')

    if not (receiver_id and teach_skill and learn_skill):
        notify('Pick both skills before sending the request.', None, 'warning')
        return redirect(back)
    if receiver_id == uid:
        notify('You cannot send a request to yourself — CHECK (sender_id <> receiver_id).',
               None, 'danger')
        return redirect(back)
    if teach_skill == learn_skill:
        notify('The two skills must differ — CHECK (teach_skill <> learn_skill).',
               None, 'danger')
        return redirect(back)

    open_one = query("""SELECT request_id FROM exchangerequests
                        WHERE ((sender_id = %s AND receiver_id = %s)
                            OR (sender_id = %s AND receiver_id = %s))
                          AND status IN ('Pending', 'Accepted')""",
                     (uid, receiver_id, receiver_id, uid), one=True)
    if open_one:
        notify('You already have an open request with that student (#%d).'
               % open_one['request_id'], None, 'warning')
        return redirect(back)

    new_id, _ = execute("""INSERT INTO exchangerequests
                             (sender_id, receiver_id, teach_skill, learn_skill, status)
                           VALUES (%s, %s, %s, %s, 'Pending')""",
                        (uid, receiver_id, teach_skill, learn_skill))
    notify('Request #%d sent.' % new_id,
           'INSERT INTO exchangerequests (sender_id, receiver_id, teach_skill, '
           "learn_skill, status) VALUES (%s, %s, %s, %s, 'Pending')", 'success')
    return redirect(back)


# ------------------------------------------------------------------ status
def _set_status(request_id, new_status, allowed_from, role):
    """
    role = 'receiver' (accept / decline) or 'either' (cancel).
    Ownership is enforced in the WHERE clause, so a crafted request_id
    belonging to somebody else simply updates zero rows.
    """
    me = current_user()
    uid = me['user_id']
    who = ('receiver_id = %s' if role == 'receiver'
           else '(sender_id = %s OR receiver_id = %s)')
    params = [new_status, request_id, uid] + ([uid] if role != 'receiver' else [])

    sql = ("""UPDATE exchangerequests SET status = %s
              WHERE request_id = %s AND """ + who +
           " AND status IN (" + ','.join(["'" + s + "'" for s in allowed_from]) + ")")

    _, n = execute(sql, tuple(params))
    return n


@bp.route('/requests/<int:request_id>/accept', methods=['POST'])
@login_required
def accept(request_id):
    if _set_status(request_id, 'Accepted', ['Pending'], 'receiver'):
        notify('Request #%d accepted — you can book a session now.' % request_id,
               "UPDATE exchangerequests SET status = 'Accepted' WHERE request_id = %s",
               'success')
    else:
        notify('That request can no longer be accepted.', None, 'warning')
    return redirect(request.form.get('next') or url_for('exchange.index'))


@bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject(request_id):
    if _set_status(request_id, 'Rejected', ['Pending'], 'receiver'):
        notify('Request #%d declined.' % request_id,
               "UPDATE exchangerequests SET status = 'Rejected' WHERE request_id = %s",
               'success')
    else:
        notify('That request can no longer be declined.', None, 'warning')
    return redirect(request.form.get('next') or url_for('exchange.index'))


@bp.route('/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel(request_id):
    if _set_status(request_id, 'Cancelled', ['Pending', 'Accepted'], 'either'):
        notify('Request #%d cancelled.' % request_id,
               "UPDATE exchangerequests SET status = 'Cancelled' WHERE request_id = %s",
               'success')
    else:
        notify('That request can no longer be cancelled.', None, 'warning')
    return redirect(request.form.get('next') or url_for('exchange.index'))


@bp.route('/requests/<int:request_id>/complete', methods=['POST'])
@login_required
def complete(request_id):
    if _set_status(request_id, 'Completed', ['Accepted'], 'either'):
        notify('Exchange #%d marked completed.' % request_id,
               "UPDATE exchangerequests SET status = 'Completed' WHERE request_id = %s",
               'success')
    else:
        notify('Only an accepted exchange can be completed.', None, 'warning')
    return redirect(request.form.get('next') or url_for('exchange.index'))
