"""
SkillSwap NSU  —  CSE311L Database Systems Lab
config.py — every setting the Flask build needs, in one place.

The defaults match a stock XAMPP install on Windows:
    host 127.0.0.1, port 3306, user 'root', empty password.
If your MySQL uses a password, either edit DB_PASSWORD below or set the
environment variable SKILLSWAP_DB_PASSWORD before starting the server.
"""

import os

# ---------------------------------------------------------------- database
DB_HOST     = os.environ.get('SKILLSWAP_DB_HOST',     '127.0.0.1')
DB_PORT     = int(os.environ.get('SKILLSWAP_DB_PORT', '3306'))
DB_USER     = os.environ.get('SKILLSWAP_DB_USER',     'root')
DB_PASSWORD = os.environ.get('SKILLSWAP_DB_PASSWORD', '')
DB_NAME     = os.environ.get('SKILLSWAP_DB_NAME',     'skillexchange')

DB = {
    'host':     DB_HOST,
    'port':     DB_PORT,
    'user':     DB_USER,
    'password': DB_PASSWORD,
    'database': DB_NAME,
    'charset':  'utf8mb4',
    'autocommit': False,          # we manage transactions by hand
}

# ---------------------------------------------------------------- flask
SECRET_KEY = os.environ.get('SKILLSWAP_SECRET', 'cse311l-skillswap-nsu-dev-key')

UPLOAD_FOLDER  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 2 * 1024 * 1024        # 2 MB profile pictures

# Show the SQL statement behind every write action in the toast.
# Handy while demonstrating the project; set to False for a clean UI.
SHOW_SQL_TOASTS = True
