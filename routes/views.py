from flask import Blueprint, render_template, session, redirect, url_for
from services.db import get_db
from utils.security import login_required
from bson import ObjectId

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
@login_required
def home_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    
    # Render home.html passing user details
    return render_template('home.html', user=user, active_tab='home')

@views_bp.route('/discover')
@login_required
def discover_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    return render_template('discover.html', user=user, active_tab='discover')

@views_bp.route('/communities')
@login_required
def communities_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    return render_template('communities.html', user=user, active_tab='communities')

@views_bp.route('/messages')
@login_required
def messages_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    return render_template('messages.html', user=user, active_tab='messages')

@views_bp.route('/profile')
@login_required
def self_profile_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    # Redirects to profile page by username
    return redirect(url_for('views.profile_view', username=user['username']))

@views_bp.route('/profile/<username>')
@login_required
def profile_view(username):
    db = get_db()
    user_id = session.get('user_id')
    current_user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    
    # Retrieve target user profile
    target_user = db.users.find_one({'username': username.lower()}, {'password_hash': 0})
    if not target_user:
        # Fallback to current profile or 404
        return render_template('404.html', user=current_user), 404
        
    return render_template('profile.html', user=current_user, target_user=target_user, active_tab='profile')

@views_bp.route('/settings')
@login_required
def settings_view():
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    return render_template('settings.html', user=user, active_tab='settings')

@views_bp.route('/login')
def login_view():
    if 'user_id' in session:
        return redirect(url_for('views.home_view'))
    return render_template('login.html')

@views_bp.route('/register')
def register_view():
    if 'user_id' in session:
        return redirect(url_for('views.home_view'))
    return render_template('register.html')
