"""
Local authentication for Summer of Simplex.
No external SSO — users are stored in the local database.
"""

from functools import wraps
from flask import session, redirect, url_for, request


def login_required(f):
    """Decorator: require an active login session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            session['next_page'] = request.url
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator: require login AND admin flag."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            session['next_page'] = request.url
            return redirect(url_for('main.login'))
        if not session.get('user_is_admin'):
            return "Access denied — admin only", 403
        return f(*args, **kwargs)
    return decorated_function


def setup_auth_routes(app):
    """
    Kept for __init__.py compatibility but nothing to register here —
    login/logout live in routing.py as regular blueprint routes.
    """
    pass