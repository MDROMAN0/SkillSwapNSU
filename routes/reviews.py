"""
routes/reviews.py — write, read and delete reviews.

A review can only follow a COMPLETED session, and UNIQUE (session_id,
reviewer_id) means each partner writes at most one review per session.
"""

from flask import Blueprint, redirect, render_template, request, url_for

from db import execute, query, time_to_str
from helpers import current_user, login_required, notify, rating_of

bp = Blueprint('reviews', __name__)


@bp.route('/reviews')
@login_required
def index():
    me = current_user()
    uid = me['user_id']
    tab = request.args.get('tab', 'received')

    # ---------- completed sessions I have not reviewed yet ----------
    to_review = query("""
        SELECT se.session_id, se.session_date, se.session_time, se.duration, se.mode,
               p.user_id AS p_id, p.name AS p_name,
               CASE WHEN er.sender_id = %s THEN ls.skill_name ELSE ts.skill_name END AS skill_name
        FROM       sessions se
        INNER JOIN exchangerequests er ON er.request_id = se.request_id
        INNER JOIN users  p  ON p.user_id = CASE WHEN er.sender_id = %s
                                                 THEN er.receiver_id ELSE er.sender_id END
        INNER JOIN skills ts ON ts.skill_id = er.teach_skill
        INNER JOIN skills ls ON ls.skill_id = er.learn_skill
        WHERE se.status = 'Completed'
          AND (er.sender_id = %s OR er.receiver_id = %s)
          AND NOT EXISTS (SELECT 1 FROM reviews r
                           WHERE r.session_id = se.session_id AND r.reviewer_id = %s)
        ORDER BY se.session_date DESC""", (uid, uid, uid, uid, uid))
    for row in to_review:
        row['time_str'] = time_to_str(row['session_time'])

    received = query("""SELECT r.review_id, r.session_id, r.rating, r.comment, r.created_at,
                               u.user_id, u.name,
                               ts.skill_name AS skill_name
                        FROM reviews r
                        INNER JOIN users u ON u.user_id = r.reviewer_id
                        LEFT JOIN sessions se ON se.session_id = r.session_id
                        LEFT JOIN exchangerequests er ON er.request_id = se.request_id
                        LEFT JOIN skills ts ON ts.skill_id = er.teach_skill
                        WHERE r.reviewee_id = %s
                        ORDER BY r.review_id DESC""", (uid,))

    given = query("""SELECT r.review_id, r.session_id, r.rating, r.comment, r.created_at,
                            u.user_id, u.name,
                            ts.skill_name AS skill_name
                     FROM reviews r
                     INNER JOIN users u ON u.user_id = r.reviewee_id
                     LEFT JOIN sessions se ON se.session_id = r.session_id
                     LEFT JOIN exchangerequests er ON er.request_id = se.request_id
                     LEFT JOIN skills ts ON ts.skill_id = er.teach_skill
                     WHERE r.reviewer_id = %s
                     ORDER BY r.review_id DESC""", (uid,))

    my_rating = rating_of(uid)
    spread = []
    for n in (5, 4, 3, 2, 1):
        count = sum(1 for r in received if r['rating'] == n)
        spread.append({'n': n, 'count': count,
                       'pct': (100.0 * count / len(received)) if received else 0})

    return render_template('reviews.html', tab=tab, to_review=to_review,
                           received=received, given=given, my_rating=my_rating,
                           spread=spread, preset=request.args.get('session', ''))


@bp.route('/reviews/add', methods=['POST'])
@login_required
def add():
    me = current_user()
    uid = me['user_id']
    try:
        session_id = int(request.form.get('session_id', 0) or 0)
        rating = int(request.form.get('rating', 0) or 0)
    except ValueError:
        notify('Invalid review.', None, 'danger')
        return redirect(url_for('reviews.index'))
    comment = request.form.get('comment', '').strip()

    row = query("""SELECT se.session_id, se.status,
                          CASE WHEN er.sender_id = %s THEN er.receiver_id
                               ELSE er.sender_id END AS partner_id
                   FROM sessions se
                   JOIN exchangerequests er ON er.request_id = se.request_id
                   WHERE se.session_id = %s AND (er.sender_id = %s OR er.receiver_id = %s)""",
                (uid, session_id, uid, uid), one=True)

    if not row:
        notify('That session is not yours to review.', None, 'danger')
    elif row['status'] != 'Completed':
        notify('Only a completed session can be reviewed.', None, 'warning')
    elif not 1 <= rating <= 5:
        notify('Choose a rating between 1 and 5 — CHECK (rating BETWEEN 1 AND 5).',
               None, 'danger')
    elif len(comment) < 10:
        notify('Write at least a short sentence.', None, 'danger')
    elif query("""SELECT review_id FROM reviews
                  WHERE session_id = %s AND reviewer_id = %s""",
               (session_id, uid), one=True):
        notify('You already reviewed this session — UNIQUE (session_id, reviewer_id).',
               None, 'warning')
    else:
        new_id, _ = execute("""INSERT INTO reviews
                                 (session_id, reviewer_id, reviewee_id, rating, comment)
                               VALUES (%s, %s, %s, %s, %s)""",
                            (session_id, uid, row['partner_id'], rating, comment[:200]))
        notify('Review #%d published.' % new_id,
               'INSERT INTO reviews (session_id, reviewer_id, reviewee_id, rating, '
               'comment) VALUES (%s, %s, %s, %s, %s)', 'success')
    return redirect(url_for('reviews.index'))


@bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
def delete(review_id):
    me = current_user()
    _, n = execute('DELETE FROM reviews WHERE review_id = %s AND reviewer_id = %s',
                   (review_id, me['user_id']))
    if n:
        notify('Review deleted.', 'DELETE FROM reviews WHERE review_id = %s', 'success')
    else:
        notify('You can only delete a review you wrote.', None, 'warning')
    return redirect(url_for('reviews.index', tab='given'))
