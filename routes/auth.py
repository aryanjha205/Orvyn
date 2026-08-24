from flask import Blueprint, request, jsonify, session
from services.db import get_db
from utils.security import hash_password, check_password, is_valid_email, is_valid_username, login_required
from services.storage_service import save_uploaded_file
from bson import ObjectId
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    db = get_db()
    
    # Form data or JSON
    # Registration supports multipart/form-data for profile image upload
    name = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    bio = request.form.get('bio', '').strip()
    location = request.form.get('location', '').strip()
    website = request.form.get('website', '').strip()
    
    # Parse interests from form (can be comma-separated or multiple fields)
    interests_raw = request.form.get('interests', '')
    interests = [i.strip().lower() for i in interests_raw.split(',') if i.strip()] if interests_raw else []

    # Validation
    if not name or not username or not email or not password:
        return jsonify({'error': 'Name, username, email, and password are required.'}), 400
        
    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email address.'}), 400
        
    if not is_valid_username(username):
        return jsonify({'error': 'Username must be between 3 and 20 characters and contain only letters, numbers, underscores, or periods.'}), 400
        
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400

    # Check unique username/email
    if db.users.find_one({'username': username}):
        return jsonify({'error': 'Username is already taken.'}), 400
        
    if db.users.find_one({'email': email}):
        return jsonify({'error': 'Email is already registered.'}), 400

    # Handle profile image upload
    profile_image_url = '/static/images/default-avatar.png'
    if 'profile_image' in request.files:
        try:
            profile_image_url = save_uploaded_file(request.files['profile_image'], username, 'image')
        except Exception as e:
            return jsonify({'error': f"Profile image upload failed: {str(e)}"}), 400

    # Default cover image
    cover_image_url = '/static/images/default-cover.png'

    # Hash password
    pw_hash = hash_password(password)

    # User document
    user_doc = {
        'name': name,
        'username': username,
        'email': email,
        'password_hash': pw_hash,
        'profile_image': profile_image_url,
        'cover_image': cover_image_url,
        'bio': bio,
        'location': location,
        'website': website,
        'interests': interests,
        'followers_count': 0,
        'following_count': 0,
        'ai_summary': '', # Will be generated when they build posts
        'created_at': datetime.datetime.utcnow()
    }

    try:
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        # Log user in
        session['user_id'] = user_id
        session['username'] = username
        session['name'] = name
        
        # Return user details without password hash
        user_doc['_id'] = user_id
        user_doc.pop('password_hash')
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully!',
            'user': {
                'id': user_id,
                'name': name,
                'username': username,
                'email': email,
                'profile_image': profile_image_url
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f"Failed to save user: {str(e)}"}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    db = get_db()
    
    # Can be JSON or URL-encoded form
    data = request.get_json() if request.is_json else request.form
    
    login_input = data.get('username_or_email', '').strip().lower()
    password = data.get('password', '')

    if not login_input or not password:
        return jsonify({'error': 'Username/email and password are required.'}), 400

    # Find user (match username or email)
    user = db.users.find_one({
        '$or': [
            {'username': login_input},
            {'email': login_input}
        ]
    })

    if not user or not check_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid username/email or password.'}), 401

    # Login session
    user_id = str(user['_id'])
    session['user_id'] = user_id
    session['username'] = user['username']
    session['name'] = user['name']

    return jsonify({
        'success': True,
        'message': 'Logged in successfully!',
        'user': {
            'id': user_id,
            'name': user['name'],
            'username': user['username'],
            'email': user['email'],
            'profile_image': user.get('profile_image', '/static/images/default-avatar.png')
        }
    }), 200

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully!'
    }), 200

@auth_bp.route('/api/auth/profile', methods=['POST'])
@login_required
def update_profile():
    """Update the signed-in user's editable profile fields and images."""
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    updates = {}
    for field in ('name', 'bio', 'location', 'website'):
        if field in request.form:
            updates[field] = request.form.get(field, '').strip()

    if 'name' in updates and not updates['name']:
        return jsonify({'error': 'Your name cannot be empty.'}), 400

    for upload_field, stored_field in (('profile_image', 'profile_image'), ('cover_image', 'cover_image')):
        image = request.files.get(upload_field)
        if image and image.filename:
            try:
                updates[stored_field] = save_uploaded_file(image, user_id, 'image')
            except Exception as e:
                return jsonify({'error': f'Image upload failed: {str(e)}'}), 400

    if not updates:
        return jsonify({'error': 'No profile changes were provided.'}), 400

    updates['updated_at'] = datetime.datetime.utcnow()
    db.users.update_one({'_id': user['_id']}, {'$set': updates})
    if 'name' in updates:
        session['name'] = updates['name']

    updated_user = db.users.find_one({'_id': user['_id']})
    return jsonify({
        'success': True,
        'message': 'Profile updated successfully.',
        'user': {
            'name': updated_user.get('name'),
            'bio': updated_user.get('bio', ''),
            'location': updated_user.get('location', ''),
            'website': updated_user.get('website', ''),
            'profile_image': updated_user.get('profile_image', '/static/images/default-avatar.png'),
            'cover_image': updated_user.get('cover_image', '/static/images/default-cover.png')
        }
    }), 200

@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    email = data.get('email', '').strip().lower()
    
    if not email or not is_valid_email(email):
        return jsonify({'error': 'Please provide a valid registered email.'}), 400
        
    user = db.users.find_one({'email': email})
    if not user:
        # Avoid user enumeration in production, but let's be explicit here for easy demo
        return jsonify({'error': 'No user found with that email address.'}), 404
        
    # Simulate sending reset link
    return jsonify({
        'success': True,
        'message': 'Password reset instructions have been sent to your email.'
    }), 200

@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip().lower()
    new_password = data.get('password', '')
    
    if not username or not new_password or len(new_password) < 6:
        return jsonify({'error': 'Invalid request parameters. Password must be >= 6 characters.'}), 400
        
    user = db.users.find_one({'username': username})
    if not user:
        return jsonify({'error': 'User not found.'}), 404
        
    pw_hash = hash_password(new_password)
    db.users.update_one({'_id': user['_id']}, {'$set': {'password_hash': pw_hash}})
    
    return jsonify({
        'success': True,
        'message': 'Password has been reset successfully! You can now log in.'
    }), 200
