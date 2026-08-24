from flask import Blueprint, request, jsonify, session
from services.ai_service import AIService
from services.db import get_db
from services.storage_service import save_uploaded_file
from utils.security import login_required
from bson import ObjectId
import os

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/api/ai/write', methods=['POST'])
@login_required
def ai_write():
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    tone = data.get('tone', 'friendly').strip()
    style = data.get('style', 'engaging').strip()
    
    if not prompt:
        return jsonify({'error': 'A prompt idea is required.'}), 400
        
    generated = AIService.generate_post(prompt, tone, style)
    return jsonify({
        'success': True,
        'result': generated
    })

@ai_bp.route('/api/ai/improve', methods=['POST'])
@login_required
def ai_improve():
    data = request.get_json() or {}
    draft = data.get('draft', '').strip()
    tone = data.get('tone', 'friendly').strip()
    
    if not draft:
        return jsonify({'error': 'Draft text is required to improve.'}), 400
        
    improved = AIService.improve_post(draft, tone)
    return jsonify({
        'success': True,
        'result': improved
    })

@ai_bp.route('/api/ai/hashtags', methods=['POST'])
@login_required
def ai_hashtags():
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'error': 'Text is required to generate hashtags.'}), 400
        
    tags = AIService.generate_hashtags(text)
    return jsonify({
        'success': True,
        'result': tags
    })

@ai_bp.route('/api/ai/translate', methods=['POST'])
@login_required
def ai_translate():
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    target_lang = data.get('target_lang', 'spanish').strip()
    
    if not text:
        return jsonify({'error': 'Text is required to translate.'}), 400
        
    translated = AIService.translate_text(text, target_lang)
    return jsonify({
        'success': True,
        'result': translated
    })

@ai_bp.route('/api/ai/reply', methods=['POST'])
@login_required
def ai_reply():
    data = request.get_json() or {}
    comment_text = data.get('comment', '').strip()
    
    if not comment_text:
        return jsonify({'error': 'Comment text is required.'}), 400
        
    reply = AIService.suggest_comment_reply(comment_text)
    return jsonify({
        'success': True,
        'result': reply
    })

@ai_bp.route('/api/ai/caption', methods=['POST'])
@login_required
def ai_caption():
    """Accepts uploaded image file and returns AI analysis (caption, description, tags, alt_text)."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded.'}), 400
        
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'Empty filename.'}), 400
        
    user_id = session.get('user_id')
    
    try:
        # Save file to temp / uploads directory first
        relative_path = save_uploaded_file(image_file, user_id, 'image')
        # Resolve absolute path on server to pass to AI service
        absolute_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            relative_path.lstrip('/')
        )
        
        # Analyze image
        analysis = AIService.describe_image(absolute_path)
        
        # We can clean up the file afterwards if they cancel, or leave it as it was uploaded.
        # Let's keep it and return the saved path in the response so they can publish it directly!
        analysis['media_url'] = relative_path
        
        return jsonify({
            'success': True,
            'result': analysis
        })
    except Exception as e:
        return jsonify({'error': f"AI Image analysis failed: {str(e)}"}), 500

@ai_bp.route('/api/ai/assistant', methods=['POST'])
@login_required
def ai_assistant():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Ask me something!'}), 400
        
    # Inject simple session context for AI
    db = get_db()
    user_id = session.get('user_id')
    user = db.users.find_one({'_id': ObjectId(user_id)}, {'password_hash': 0})
    
    context = {
        'user': {
            'id': user_id,
            'name': user.get('name'),
            'username': user.get('username'),
            'interests': user.get('interests', [])
        }
    }
    
    response = AIService.get_assistant_response(query, context)
    return jsonify({
        'success': True,
        'result': response
    })

@ai_bp.route('/api/ai/profile-summary', methods=['POST'])
@login_required
def regenerate_profile_summary():
    """Generates and saves the user's AI summary profile insight."""
    db = get_db()
    user_id = session.get('user_id')
    
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found.'}), 404
        
    # Get user's recent posts for context
    recent_posts = list(db.posts.find({'author_id': user_id}).sort('created_at', -1).limit(5))
    
    summary = AIService.generate_profile_summary(user, recent_posts)
    
    # Save back to database
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'ai_summary': summary}})
    
    return jsonify({
        'success': True,
        'summary': summary
    })
