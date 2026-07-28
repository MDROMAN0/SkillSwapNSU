"""
routes/auth.py — sign in, register, sign out.

Passwords never touch the database in plain text: registration stores a
Werkzeug pbkdf2 hash and sign-in compares against that hash.
"""

from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from db import query, transaction
from helpers import categories, current_user, departments, notify

bp = Blueprint('auth', __name__)

EMAIL_OK = lambda e: '@' in e and '.' in e.split('@')[-1] and ' ' not in e   # noqa: E731


# ------------------------------------------------------------------ sign in
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('main.dashboard'))

    errors, form = {}, {'email': ''}

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        form['email'] = email

        if not email:
            errors['email'] = 'Enter your email address.'
        elif not EMAIL_OK(email):
            errors['email'] = 'That does not look like an email address.'
        if not password:
            errors['password'] = 'Enter your password.'

        if not errors:
            # SELECT * FROM users WHERE email = %s
            user = query('SELECT * FROM users WHERE email = %s', (email,), one=True)
            if user is None:
                errors['email'] = 'No account uses that email address.'
            elif not check_password_hash(user['password'], password):
                errors['password'] = 'Wrong password. Every seeded account uses password123.'
            else:
                session.clear()
                session['user_id'] = user['user_id']
                session.permanent = bool(request.form.get('remember'))
                notify('Signed in as %s.' % user['name'],
                       'SELECT * FROM users WHERE email = %s', 'success')
                return redirect(request.args.get('next') or url_for('main.dashboard'))

    return render_template('login.html', errors=errors, form=form)


# ------------------------------------------------------------------ register
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user():
        return redirect(url_for('main.dashboard'))

    errors = {}
    form = {'name': '', 'dept': '', 'email': '', 'bio': '',
            'teach_skill': '', 'teach_level': 'Intermediate', 'learn_skill': ''}

    if request.method == 'POST':
        for key in form:
            form[key] = request.form.get(key, '').strip()
        form['email'] = form['email'].lower()
        password = request.form.get('pw', '')
        confirm = request.form.get('pw2', '')

        if len(form['name']) < 3:
            errors['name'] = 'Enter your full name.'
        if not form['dept']:
            errors['dept'] = 'Choose your department.'

        if not EMAIL_OK(form['email']):
            errors['email'] = 'Enter a valid email address.'
        elif query('SELECT user_id FROM users WHERE email = %s', (form['email'],), one=True):
            errors['email'] = 'That email is already registered. Try signing in instead.'

        if len(password) < 8:
            errors['pw'] = 'Use at least 8 characters.'
        if confirm != password:
            errors['pw2'] = 'The two passwords do not match.'

        if not form['teach_skill']:
            errors['teach_skill'] = 'Pick one skill you can teach.'
        if not form['learn_skill']:
            errors['learn_skill'] = 'Pick one skill you want to learn.'
        elif form['learn_skill'] == form['teach_skill']:
            errors['learn_skill'] = 'Choose a different skill from the one you teach.'

        if not request.form.get('agree'):
            errors['agree'] = 'Please confirm this before continuing.'

        if not errors:
            # One transaction: the account and its two skill rows commit together,
            # or nothing is written at all.
            with transaction() as cur:
                cur.execute(
                    """INSERT INTO users (name, email, password, department, bio, profile_picture)
                       VALUES (%s, %s, %s, %s, %s, 'default.png')""",
                    (form['name'], form['email'], generate_password_hash(password),
                     form['dept'], form['bio'] or None))
                new_id = cur.lastrowid
                cur.execute(
                    """INSERT INTO userskills (user_id, skill_id, skill_type, proficiency)
                       VALUES (%s, %s, 'Teach', %s)""",
                    (new_id, int(form['teach_skill']), form['teach_level'] or 'Intermediate'))
                cur.execute(
                    """INSERT INTO userskills (user_id, skill_id, skill_type, proficiency)
                       VALUES (%s, %s, 'Learn', 'Beginner')""",
                    (new_id, int(form['learn_skill'])))

            session.clear()
            session['user_id'] = new_id
            notify('Welcome to SkillSwap, %s.' % form['name'].split()[0],
                   'INSERT INTO users (...) VALUES (...); '
                   'INSERT INTO userskills (...) x2  -- one transaction', 'success')
            return redirect(url_for('main.dashboard'))

    return render_template('register.html', errors=errors, form=form,
                           departments=departments(), categories=categories())


# ------------------------------------------------------------------ sign out
@bp.route('/logout')
def logout():
    session.clear()
    notify('You have been signed out.', None, 'success')
    return redirect(url_for('auth.login'))
