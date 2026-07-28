"""
routes/profile.py — public profile, edit profile, skill list, password.
"""

import os

from flask import (Blueprint, current_app, redirect, render_template, request,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from db import execute, query, scalar
from helpers import (current_user, departments, login_required, notify,
                     rating_of, skills_of)

bp = Blueprint('profile', __name__)


# ------------------------------------------------------------------ view
@bp.route('/profile/<int:user_id>')
@bp.route('/profile')
@login_required
def view(user_id=None):
    me = current_user()
    if user_id is None:
        user_id = int(request.args.get('id', me['user_id']))

    person = query('SELECT * FROM users WHERE user_id = %s', (user_id,), one=True)
    if person is None:
        person, user_id = me, me['user_id']
    is_me = person['user_id'] == me['user_id']

    teach = skills_of(user_id, 'Teach')
    learn = skills_of(user_id, 'Learn')
    rating = rating_of(user_id)

    my_teach_ids = {r['skill_id'] for r in skills_of(me['user_id'], 'Teach')}
    my_learn_ids = {r['skill_id'] for r in skills_of(me['user_id'], 'Learn')}

    header = {
        'done': scalar("""SELECT COUNT(*) FROM exchangerequests
                          WHERE (sender_id = %s OR receiver_id = %s)
                            AND status = 'Completed'""", (user_id, user_id), 0),
        'hours': round((scalar("""SELECT COALESCE(SUM(se.duration), 0)
                                  FROM sessions se
                                  JOIN exchangerequests er ON er.request_id = se.request_id
                                  WHERE se.status = 'Completed'
                                    AND (er.sender_id = %s OR er.receiver_id = %s)""",
                               (user_id, user_id), 0)) / 60),
    }

    # ---------------- reviews about this student ----------------
    reviews = query("""SELECT r.review_id, r.rating, r.comment, r.created_at,
                              u.user_id, u.name,
                              CASE WHEN er.sender_id = %s THEN ts.skill_name
                                   ELSE ls.skill_name END AS skill_name
                       FROM reviews r
                       INNER JOIN users u ON u.user_id = r.reviewer_id
                       LEFT JOIN sessions se ON se.session_id = r.session_id
                       LEFT JOIN exchangerequests er ON er.request_id = se.request_id
                       LEFT JOIN skills ts ON ts.skill_id = er.teach_skill
                       LEFT JOIN skills ls ON ls.skill_id = er.learn_skill
                       WHERE r.reviewee_id = %s
                       ORDER BY r.review_id DESC""", (user_id, user_id))

    spread = []
    for n in (5, 4, 3, 2, 1):
        count = sum(1 for r in reviews if r['rating'] == n)
        spread.append({'n': n, 'count': count,
                       'pct': (100.0 * count / len(reviews)) if reviews else 0})

    # ---------------- exchange history ----------------
    history = query("""SELECT er.request_id, er.status, er.created_at,
                              CASE WHEN er.sender_id = %s THEN 1 ELSE 0 END AS sent,
                              p.user_id AS p_id, p.name AS p_name,
                              CASE WHEN er.sender_id = %s THEN ts.skill_name
                                   ELSE ls.skill_name END AS gave,
                              CASE WHEN er.sender_id = %s THEN ls.skill_name
                                   ELSE ts.skill_name END AS got
                       FROM exchangerequests er
                       INNER JOIN users p ON p.user_id = CASE WHEN er.sender_id = %s
                                                              THEN er.receiver_id
                                                              ELSE er.sender_id END
                       INNER JOIN skills ts ON ts.skill_id = er.teach_skill
                       INNER JOIN skills ls ON ls.skill_id = er.learn_skill
                       WHERE er.sender_id = %s OR er.receiver_id = %s
                       ORDER BY er.created_at DESC""",
                    (user_id, user_id, user_id, user_id, user_id, user_id))

    # ---------------- proposal box (only when viewing somebody else) -------
    existing = they_teach_i_want = they_want_i_teach = None
    peers = []
    if not is_me:
        existing = query("""SELECT request_id, status FROM exchangerequests
                            WHERE (sender_id = %s AND receiver_id = %s)
                               OR (receiver_id = %s AND sender_id = %s)
                            ORDER BY request_id DESC LIMIT 1""",
                         (me['user_id'], user_id, me['user_id'], user_id), one=True)
        they_teach_i_want = [s for s in teach if s['skill_id'] in my_learn_ids]
        they_want_i_teach = [s for s in learn if s['skill_id'] in my_teach_ids]

        peers = query("""SELECT u.user_id, u.name,
                                COALESCE(v.total_reviews, 0) AS total_reviews, v.avg_rating,
                                (SELECT COUNT(*) FROM userskills us
                                  WHERE us.user_id = u.user_id AND us.skill_type = 'Teach') AS teach_n
                         FROM users u
                         LEFT JOIN v_user_ratings v ON v.user_id = u.user_id
                         WHERE u.department = %s AND u.user_id <> %s AND u.user_id <> %s
                         ORDER BY u.name LIMIT 5""",
                      (person['department'], user_id, me['user_id']))

    return render_template('profile.html',
                           person=person, is_me=is_me,
                           teach=teach, learn=learn, rating=rating,
                           my_teach_ids=my_teach_ids, my_learn_ids=my_learn_ids,
                           header=header, reviews=reviews, spread=spread,
                           history=history, existing=existing,
                           they_teach_i_want=they_teach_i_want,
                           they_want_i_teach=they_want_i_teach,
                           my_teach=skills_of(me['user_id'], 'Teach'),
                           peers=peers)


# ------------------------------------------------------------------ edit
@bp.route('/edit-profile')
@login_required
def edit():
    me = current_user()
    rows = query("""SELECT us.user_skill_id, us.skill_type, us.proficiency,
                           s.skill_id, s.skill_name, s.category
                    FROM userskills us
                    INNER JOIN skills s ON s.skill_id = us.skill_id
                    WHERE us.user_id = %s
                    ORDER BY us.skill_type, s.skill_name""", (me['user_id'],))
    return render_template('edit_profile.html', rows=rows, departments=departments())


@bp.route('/edit-profile/details', methods=['POST'])
@login_required
def save_details():
    me = current_user()
    name = request.form.get('name', '').strip()
    dept = request.form.get('dept', '').strip() or me['department']
    bio = request.form.get('bio', '').strip()

    if len(name) < 3:
        notify('Enter your full name.', None, 'danger')
        return redirect(url_for('profile.edit'))

    execute("""UPDATE users SET name = %s, department = %s, bio = %s
               WHERE user_id = %s""", (name, dept, bio or None, me['user_id']))
    notify('Profile updated.',
           'UPDATE users SET name = %s, department = %s, bio = %s WHERE user_id = %s',
           'success')
    return redirect(url_for('profile.edit'))


@bp.route('/edit-profile/picture', methods=['POST'])
@login_required
def save_picture():
    me = current_user()
    file = request.files.get('pic')
    if not file or not file.filename:
        notify('Choose an image first.', None, 'warning')
        return redirect(url_for('profile.edit'))

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in current_app.config['ALLOWED_IMAGES']:
        notify('Only JPG, PNG, GIF or WEBP images are accepted.', None, 'danger')
        return redirect(url_for('profile.edit'))

    filename = secure_filename('user%d.%s' % (me['user_id'], ext))
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

    execute('UPDATE users SET profile_picture = %s WHERE user_id = %s',
            (filename, me['user_id']))
    notify('Profile picture saved as %s.' % filename,
           'UPDATE users SET profile_picture = %s WHERE user_id = %s', 'success')
    return redirect(url_for('profile.edit'))


@bp.route('/edit-profile/picture/remove', methods=['POST'])
@login_required
def remove_picture():
    me = current_user()
    execute("UPDATE users SET profile_picture = 'default.png' WHERE user_id = %s",
            (me['user_id'],))
    notify('Profile picture removed.',
           "UPDATE users SET profile_picture = 'default.png' WHERE user_id = %s", 'success')
    return redirect(url_for('profile.edit'))


# ------------------------------------------------------------------ skills
@bp.route('/edit-profile/skills/add', methods=['POST'])
@login_required
def add_skill():
    me = current_user()
    skill_id = int(request.form.get('skill_id', 0) or 0)
    skill_type = request.form.get('skill_type', 'Teach')
    level = request.form.get('level', 'Beginner')

    if not skill_id:
        notify('Choose a skill first.', None, 'warning')
        return redirect(url_for('profile.edit'))

    # The UNIQUE (user_id, skill_id, skill_type) constraint would reject a
    # duplicate anyway; checking first turns a database error into a message.
    dup = query("""SELECT user_skill_id FROM userskills
                   WHERE user_id = %s AND skill_id = %s AND skill_type = %s""",
                (me['user_id'], skill_id, skill_type), one=True)
    if dup:
        notify('That skill is already on your %s list — UNIQUE '
               '(user_id, skill_id, skill_type) blocks the duplicate.'
               % skill_type.lower(), None, 'danger')
        return redirect(url_for('profile.edit'))

    execute("""INSERT INTO userskills (user_id, skill_id, skill_type, proficiency)
               VALUES (%s, %s, %s, %s)""", (me['user_id'], skill_id, skill_type, level))
    notify('Skill added.',
           'INSERT INTO userskills (user_id, skill_id, skill_type, proficiency) '
           'VALUES (%s, %s, %s, %s)', 'success')
    return redirect(url_for('profile.edit'))


@bp.route('/edit-profile/skills/<int:user_skill_id>/level', methods=['POST'])
@login_required
def change_level(user_skill_id):
    me = current_user()
    level = request.form.get('level', 'Beginner')
    _, n = execute("""UPDATE userskills SET proficiency = %s
                      WHERE user_skill_id = %s AND user_id = %s""",
                   (level, user_skill_id, me['user_id']))
    if n:
        notify('Level changed to %s.' % level,
               'UPDATE userskills SET proficiency = %s WHERE user_skill_id = %s', 'success')
    return redirect(url_for('profile.edit'))


@bp.route('/edit-profile/skills/<int:user_skill_id>/delete', methods=['POST'])
@login_required
def remove_skill(user_skill_id):
    me = current_user()
    _, n = execute('DELETE FROM userskills WHERE user_skill_id = %s AND user_id = %s',
                   (user_skill_id, me['user_id']))
    if n:
        notify('Skill removed.',
               'DELETE FROM userskills WHERE user_skill_id = %s', 'success')
    return redirect(url_for('profile.edit'))


# ------------------------------------------------------------------ password
@bp.route('/edit-profile/password', methods=['POST'])
@login_required
def change_password():
    me = current_user()
    old = request.form.get('old_pw', '')
    new = request.form.get('new_pw', '')
    confirm = request.form.get('new_pw2', '')

    if not check_password_hash(me['password'], old):
        notify('That is not your current password.', None, 'danger')
    elif len(new) < 8:
        notify('Use at least 8 characters.', None, 'danger')
    elif new != confirm:
        notify('The two passwords do not match.', None, 'danger')
    else:
        execute('UPDATE users SET password = %s WHERE user_id = %s',
                (generate_password_hash(new), me['user_id']))
        notify('Password updated — stored as a Werkzeug pbkdf2 hash.',
               'UPDATE users SET password = %s WHERE user_id = %s', 'success')
    return redirect(url_for('profile.edit'))
