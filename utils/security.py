import re
from functools import wraps
from flask import session, request, redirect, url_for, jsonify
import bcrypt

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    """Verify password against its hash."""
    if not password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def is_valid_email(email: str) -> bool:
    """Check if email matches regex standard."""
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email))

def is_valid_username(username: str) -> bool:
    """Check if username matches rules: 3-20 chars, alphanumeric, underscore, period."""
    username_regex = r'^[a-zA-Z0-9._]{3,20}$'
    return bool(re.match(username_regex, username))

def login_required(f):
    """Decorator to require login. Returns JSON for API requests and redirect for views."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if this is an API route or expects JSON
            if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Unauthorized. Please log in.'}), 401
            return redirect(url_for('views.login_view'))
        return f(*args, **kwargs)
    return decorated_function
