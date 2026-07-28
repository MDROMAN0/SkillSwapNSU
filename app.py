"""
SkillSwap NSU  —  CSE311L Database Systems Lab
app.py — application factory.

Run it with:      python app.py
Then open:        http://127.0.0.1:5000
"""

import os
import sys

from flask import Flask, render_template, send_from_directory

import config
from db import close_db
from helpers import (AV_TINTS, LEVELS, all_skills, categories, current_user,
                     day_num, departments, fmt_date, fmt_time, has_upload,
                     initials, month_abbr, shell_context, today_iso, year_num)


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    # ---------------------------------------------------------- teardown
    app.teardown_appcontext(close_db)

    # ---------------------------------------------------------- blueprints
    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.search import bp as search_bp
    from routes.profile import bp as profile_bp
    from routes.exchange import bp as exchange_bp
    from routes.sessions import bp as sessions_bp
    from routes.reviews import bp as reviews_bp
    from routes.admin import bp as admin_bp

    for bp in (auth_bp, main_bp, search_bp, profile_bp,
               exchange_bp, sessions_bp, reviews_bp, admin_bp):
        app.register_blueprint(bp)

    # ---------------------------------------------------------- jinja helpers
    app.jinja_env.filters['fmt_date']  = fmt_date
    app.jinja_env.filters['fmt_time']  = fmt_time
    app.jinja_env.filters['initials']  = initials
    app.jinja_env.filters['month']     = month_abbr
    app.jinja_env.filters['day']       = day_num
    app.jinja_env.filters['year']      = year_num

    app.jinja_env.globals.update(
        AV_TINTS=AV_TINTS,
        LEVELS=LEVELS,
        has_upload=has_upload,
        today_iso=today_iso,
    )

    # Available in every template without each view passing it in.
    @app.context_processor
    def inject_shell():
        user = current_user()
        ctx = {'me': user, 'DEPARTMENTS': departments, 'CATEGORIES': categories,
               'ALL_SKILLS': all_skills}
        if user:
            ctx.update(shell_context(user))
        return ctx

    # ---------------------------------------------------------- cache busting
    @app.url_defaults
    def stamp_static(endpoint, values):
        """Append ?v=ASSET_V to every static URL, so a stale cached
        stylesheet is never what the browser shows."""
        if endpoint == 'static' and 'filename' in values:
            values['v'] = app.config['ASSET_V']

    # ---------------------------------------------------------- uploads
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # ---------------------------------------------------------- errors
    @app.errorhandler(404)
    def not_found(_e):
        return render_template('error.html', code=404,
                               message='That page does not exist.'), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template('error.html', code=500,
                               message='Something went wrong on the server.'), 500

    return app


app = create_app()


def _check_database():
    """Fail loudly and helpfully instead of throwing a stack trace at a student."""
    import mysql.connector
    try:
        conn = mysql.connector.connect(**config.DB)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        n = cur.fetchone()[0]
        cur.close()
        conn.close()
        print('  Database  : connected to "%s" on %s:%s  (%d students)'
              % (config.DB_NAME, config.DB_HOST, config.DB_PORT, n))
        return True
    except Exception as exc:                                  # noqa: BLE001
        print('\n  !! Could not reach MySQL.\n')
        print('     %s\n' % exc)
        print('     Checklist:')
        print('       1. Is MySQL running?  Start it from the XAMPP Control Panel.')
        print('       2. Has the database been imported?')
        print('          Import database\\skillexchange_full.sql through phpMyAdmin,')
        print('          or double click setup-db.bat.')
        print('       3. If your MySQL root user has a password, set it in config.py.\n')
        return False


if __name__ == '__main__':
    print('\n  SkillSwap NSU  -  CSE311L Database Systems Lab')
    print('  ' + '-' * 52)
    if not _check_database():
        sys.exit(1)
    print('  Open now  : http://127.0.0.1:5000')
    print('  Demo login: roman.ahmed01@northsouth.edu / password123')
    print('  Stop it   : press Ctrl+C in this window\n')
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)),
            debug=True, use_reloader=True)
