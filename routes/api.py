from flask import Blueprint, request, jsonify, session
from services.db import get_db
from services.storage_service import save_uploaded_file
from utils.security import login_required
from bson import ObjectId
import datetime
import re
from werkzeug.utils import secure_filename

api_bp = Blueprint('api', __name__)

# Helper to enrich posts with author detail
def enrich_posts(db, posts, current_user_id=None):
    if not posts:
        return []
        
    author_ids = list(set([ObjectId(p['author_id']) for p in posts if p.get('author_id')]))
    users = list(db.users.find({'_id': {'$in': author_ids}}, {'password_hash': 0}))
    user_map = {str(u['_id']): u for u in users}
    
    # Check if current user liked/saved these posts
    liked_post_ids = set()
    saved_post_ids = set()
    if current_user_id:
        likes = db.likes.find({'user_id': current_user_id, 'post_id': {'$in': [str(p['_id']) for p in posts]}})
        liked_post_ids = set([l['post_id'] for l in likes])
        saves = db.saves.find({'user_id': current_user_id, 'post_id': {'$in': [str(p['_id']) for p in posts]}})
        saved_post_ids = set([s['post_id'] for s in saves])

    enriched = []
    for p in posts:
        p_id = str(p['_id'])
        author_id = p.get('author_id')
        author = user_map.get(author_id, {})
        
        # Engagement totals are derived from their source collections, not from
        # cached fields. This keeps every displayed count accurate even if old
        # posts were imported with stale totals.
        likes_count = db.likes.count_documents({'post_id': p_id})
        comments_count = db.comments.count_documents({'post_id': p_id})
        saves_count = db.saves.count_documents({'post_id': p_id})
        shares_count = db.posts.count_documents({'is_repost': True, 'reposted_from': p_id})
        
        # Format timestamps
        created_at = p.get('created_at')
        if isinstance(created_at, datetime.datetime):
            # Show a friendly time or ISO format
            created_at_str = created_at.isoformat()
        else:
            created_at_str = str(created_at)

        post_data = {
            'id': p_id,
            'content': p.get('content', ''),
            'media': p.get('media', []),
            'media_type': p.get('media_type', 'none'),
            'hashtags': p.get('hashtags', []),
            'mentions': p.get('mentions', []),
            'likes_count': likes_count,
            'comments_count': comments_count,
            'shares_count': shares_count,
            'saves_count': saves_count,
            'community_id': p.get('community_id'),
            'community_name': p.get('community_name'),
            'is_repost': p.get('is_repost', False),
            'reposted_from': p.get('reposted_from'),
            'created_at': created_at_str,
            'liked': p_id in liked_post_ids,
            'saved': p_id in saved_post_ids,
            'author': {
                'id': author_id,
                'name': author.get('name', 'Orvynian'),
                'username': author.get('username', 'anonymous'),
                'profile_image': author.get('profile_image', '/static/images/default-avatar.png')
            }
        }
        
        # If it's a repost, fetch original post details
        if post_data['is_repost'] and post_data['reposted_from']:
            orig = db.posts.find_one({'_id': ObjectId(post_data['reposted_from'])})
            if orig:
                orig_author = db.users.find_one({'_id': ObjectId(orig['author_id'])}, {'name': 1, 'username': 1, 'profile_image': 1})
                post_data['original_post'] = {
                    'id': str(orig['_id']),
                    'content': orig.get('content', ''),
                    'media': orig.get('media', []),
                    'media_type': orig.get('media_type', 'none'),
                    'author': {
                        'name': orig_author.get('name', 'Orvynian') if orig_author else 'Orvynian',
                        'username': orig_author.get('username', 'anonymous') if orig_author else 'anonymous',
                        'profile_image': orig_author.get('profile_image', '/static/images/default-avatar.png') if orig_author else '/static/images/default-avatar.png'
                    }
                }
                
        enriched.append(post_data)
    return enriched

# Helper to send system notifications
def add_notification(db, user_id, notification_type, actor_id, post_id=None, custom_message=""):
    if str(user_id) == str(actor_id):
        return
        
    actor = db.users.find_one({'_id': ObjectId(actor_id)}, {'name': 1})
    actor_name = actor.get('name', 'Someone') if actor else 'Someone'
    
    message = custom_message
    if not message:
        if notification_type == 'like':
            message = f"{actor_name} liked your post."
        elif notification_type == 'comment':
            message = f"{actor_name} commented on your post."
        elif notification_type == 'follow':
            message = f"{actor_name} started following you."
        elif notification_type == 'repost':
            message = f"{actor_name} reposted your post."
        elif notification_type == 'message':
            message = f"{actor_name} sent you a direct message."
            
    db.notifications.insert_one({
        'user_id': str(user_id),
        'type': notification_type,
        'actor_id': str(actor_id),
        'post_id': str(post_id) if post_id else None,
        'message': message,
        'read': False,
        'created_at': datetime.datetime.utcnow()
    })

# Feed API
@api_bp.route('/api/feed', methods=['GET'])
@login_required
def get_feed():
    db = get_db()
    current_user_id = session.get('user_id')
    
    feed_type = request.args.get('type', 'for_you').lower()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    skip = (page - 1) * limit
    
    query = {}
    sort_criteria = [('created_at', -1)]
    
    # Fetch user data for personalized recommendations
    user = db.users.find_one({'_id': ObjectId(current_user_id)})
    
    # 1. FOLLOWING
    if feed_type == 'following':
        following_docs = list(db.follows.find({'follower_id': current_user_id}))
        following_ids = [f['following_id'] for f in following_docs]
        # Include self in following feed
        following_ids.append(current_user_id)
        query = {'author_id': {'$in': following_ids}}
        
    # 2. TRENDING
    elif feed_type == 'trending':
        # Sort by popularity (likes + comments)
        # For simplicity in MongoDB Atlas free tier, sort by likes_count then date
        sort_criteria = [('likes_count', -1), ('created_at', -1)]
        
    # 3. TAG CATEGORIES (Tech, Creative, AI)
    elif feed_type in ['tech', 'creative', 'ai']:
        tag = f"#{feed_type}"
        # Case insensitive regex match for tag or hashtag array
        query = {
            '$or': [
                {'hashtags': feed_type},
                {'content': {'$regex': f'#{feed_type}\\b', '$options': 'i'}}
            ]
        }
        
    # 4. FOR YOU (Recommendations algorithm)
    else: # for_you
        # Personalized sorting:
        # Show posts from people they follow AND posts matching user's interests
        following_docs = list(db.follows.find({'follower_id': current_user_id}))
        following_ids = [f['following_id'] for f in following_docs]
        
        interests = user.get('interests', []) if user else []
        interest_regexes = []
        for interest in interests:
            interest_regexes.append({'hashtags': interest.lower()})
            interest_regexes.append({'content': {'$regex': f'#{interest.lower()}\\b', '$options': 'i'}})
            
        if following_ids or interest_regexes:
            or_conditions = []
            if following_ids:
                or_conditions.append({'author_id': {'$in': following_ids}})
            if interest_regexes:
                or_conditions.extend(interest_regexes)
                
            query = {'$or': or_conditions}
            
    # Execute query
    posts = list(db.posts.find(query).sort(sort_criteria).skip(skip).limit(limit))
    
    # If For You didn't yield enough posts, pad it with latest public posts
    if feed_type == 'for_you' and len(posts) < 5:
        existing_ids = [p['_id'] for p in posts]
        pad_posts = list(db.posts.find({'_id': {'$nin': existing_ids}}).sort('created_at', -1).limit(limit - len(posts)))
        posts.extend(pad_posts)
        
    enriched = enrich_posts(db, posts, current_user_id)
    return jsonify({
        'success': True,
        'page': page,
        'posts': enriched
    })

# Post creation
@api_bp.route('/api/posts', methods=['POST'])
@login_required
def create_post():
    db = get_db()
    current_user_id = session.get('user_id')
    
    content = request.form.get('content', '').strip()
    community_id = request.form.get('community_id')
    
    if not content and 'media' not in request.files:
        return jsonify({'error': 'Post content cannot be empty.'}), 400
        
    # Parse hashtags and mentions
    hashtags = list(set([tag.lower() for tag in re.findall(r'#(\w+)', content)]))
    mentions = list(set([m.lower() for m in re.findall(r'@(\w+)', content)]))
    
    # Upload media files (supports multiple images/video)
    media_urls = []
    media_type = 'none'
    
    if 'media' in request.files:
        uploaded_files = request.files.getlist('media')
        for file in uploaded_files:
            if file and file.filename != '':
                try:
                    # Check extension to determine type
                    filename = file.filename.lower()
                    file_ext = filename.rsplit('.', 1)[1] if '.' in filename else ''
                    
                    is_video = file_ext in ['mp4', 'mov', 'avi', 'webm']
                    m_type = 'video' if is_video else 'image'
                    
                    url = save_uploaded_file(file, current_user_id, m_type)
                    media_urls.append(url)
                    media_type = m_type # Sets post media type to the last uploaded file type
                except Exception as e:
                    return jsonify({'error': f"File upload failed: {str(e)}"}), 400
                    
    # Validate community name
    community_name = None
    if community_id:
        comm = db.communities.find_one({'_id': ObjectId(community_id)})
        if comm:
            community_name = comm.get('name')

    post_doc = {
        'author_id': current_user_id,
        'content': content,
        'media': media_urls,
        'media_type': media_type,
        'hashtags': hashtags,
        'mentions': mentions,
        'likes_count': 0,
        'comments_count': 0,
        'shares_count': 0,
        'saves_count': 0,
        'community_id': community_id,
        'community_name': community_name,
        'is_repost': False,
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }
    
    result = db.posts.insert_one(post_doc)
    post_id = str(result.inserted_id)
    
    # Process mentions to notify users
    for username in mentions:
        mentioned_user = db.users.find_one({'username': username})
        if mentioned_user:
            add_notification(db, mentioned_user['_id'], 'mention', current_user_id, post_id, 
                             custom_message=f"{session.get('name')} mentioned you in a post.")
                             
    return jsonify({
        'success': True,
        'message': 'Post created successfully!',
        'post': enrich_posts(db, [post_doc], current_user_id)[0]
    }), 201

# Post Detail
@api_bp.route('/api/posts/<post_id>', methods=['GET'])
@login_required
def get_post_detail(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    enriched = enrich_posts(db, [post], current_user_id)[0]
    
    # Fetch comments
    comments = list(db.comments.find({'post_id': post_id}).sort('created_at', 1))
    
    # Enrich comments with author details
    comment_author_ids = [ObjectId(c['author_id']) for c in comments]
    comment_users = {str(u['_id']): u for u in db.users.find({'_id': {'$in': comment_author_ids}})}
    
    enriched_comments = []
    for c in comments:
        c_author = comment_users.get(c['author_id'], {})
        enriched_comments.append({
            'id': str(c['_id']),
            'content': c.get('content', ''),
            'created_at': c.get('created_at').isoformat() if isinstance(c.get('created_at'), datetime.datetime) else str(c.get('created_at')),
            'author': {
                'id': c['author_id'],
                'name': c_author.get('name', 'Anonymous'),
                'username': c_author.get('username', 'anonymous'),
                'profile_image': c_author.get('profile_image', '/static/images/default-avatar.png')
            }
        })
        
    return jsonify({
        'success': True,
        'post': enriched,
        'comments': enriched_comments
    })

@api_bp.route('/api/posts/<post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    if post['author_id'] != current_user_id:
        return jsonify({'error': 'You are not authorized to delete this post.'}), 403
        
    db.posts.delete_one({'_id': ObjectId(post_id)})
    db.likes.delete_many({'post_id': post_id})
    db.saves.delete_many({'post_id': post_id})
    db.comments.delete_many({'post_id': post_id})
    
    return jsonify({
        'success': True,
        'message': 'Post deleted successfully!'
    })

# Post Actions: Like, Comment, Repost, Save
@api_bp.route('/api/posts/<post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    existing_like = db.likes.find_one({'user_id': current_user_id, 'post_id': post_id})
    
    if existing_like:
        # Unlike
        db.likes.delete_one({'_id': existing_like['_id']})
        db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes_count': -1}})
        liked = False
    else:
        # Like
        db.likes.insert_one({
            'user_id': current_user_id,
            'post_id': post_id,
            'created_at': datetime.datetime.utcnow()
        })
        db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes_count': 1}})
        liked = True
        
        # Send Notification
        add_notification(db, post['author_id'], 'like', current_user_id, post_id)
        
    return jsonify({
        'success': True,
        'liked': liked,
        'likes_count': db.likes.count_documents({'post_id': post_id})
    })

@api_bp.route('/api/posts/<post_id>/comment', methods=['POST'])
@login_required
def comment_post(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'error': 'Comment content cannot be empty.'}), 400
        
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    comment_doc = {
        'post_id': post_id,
        'author_id': current_user_id,
        'content': content,
        'likes_count': 0,
        'created_at': datetime.datetime.utcnow()
    }
    
    result = db.comments.insert_one(comment_doc)
    db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'comments_count': 1}})
    
    # Notify post owner
    add_notification(db, post['author_id'], 'comment', current_user_id, post_id)
    
    # Fetch author info for response
    author = db.users.find_one({'_id': ObjectId(current_user_id)}, {'name': 1, 'username': 1, 'profile_image': 1})
    
    return jsonify({
        'success': True,
        'comments_count': db.comments.count_documents({'post_id': post_id}),
        'comment': {
            'id': str(result.inserted_id),
            'content': content,
            'created_at': comment_doc['created_at'].isoformat(),
            'author': {
                'id': current_user_id,
                'name': author.get('name', 'Anonymous'),
                'username': author.get('username', 'anonymous'),
                'profile_image': author.get('profile_image', '/static/images/default-avatar.png')
            }
        }
    }), 201

@api_bp.route('/api/posts/<post_id>/save', methods=['POST'])
@login_required
def save_post(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    existing_save = db.saves.find_one({'user_id': current_user_id, 'post_id': post_id})
    
    if existing_save:
        db.saves.delete_one({'_id': existing_save['_id']})
        db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'saves_count': -1}})
        saved = False
    else:
        db.saves.insert_one({
            'user_id': current_user_id,
            'post_id': post_id,
            'created_at': datetime.datetime.utcnow()
        })
        db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'saves_count': 1}})
        saved = True
        
    return jsonify({
        'success': True,
        'saved': saved,
        'saves_count': db.saves.count_documents({'post_id': post_id})
    })

@api_bp.route('/api/posts/<post_id>/repost', methods=['POST'])
@login_required
def repost_post(post_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    post = db.posts.find_one({'_id': ObjectId(post_id)})
    if not post:
        return jsonify({'error': 'Post not found.'}), 404
        
    # Check if they already reposted this post to avoid duplicates
    existing_repost = db.posts.find_one({'author_id': current_user_id, 'is_repost': True, 'reposted_from': post_id})
    if existing_repost:
        return jsonify({'error': 'You have already reposted this.'}), 400

    repost_doc = {
        'author_id': current_user_id,
        'content': f"Shared a post from @{db.users.find_one({'_id': ObjectId(post['author_id'])})['username']}",
        'media': [],
        'media_type': 'none',
        'hashtags': post.get('hashtags', []),
        'mentions': [],
        'likes_count': 0,
        'comments_count': 0,
        'shares_count': 0,
        'saves_count': 0,
        'is_repost': True,
        'reposted_from': post_id,
        'created_at': datetime.datetime.utcnow(),
        'updated_at': datetime.datetime.utcnow()
    }
    
    db.posts.insert_one(repost_doc)
    db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'shares_count': 1}})
    
    # Notify author
    add_notification(db, post['author_id'], 'repost', current_user_id, post_id)
    
    return jsonify({
        'success': True,
        'message': 'Reposted successfully!',
        'shares_count': db.posts.count_documents({'is_repost': True, 'reposted_from': post_id})
    })

# Profiles & Follow Network
@api_bp.route('/api/trends', methods=['GET'])
@login_required
def get_trends():
    """Return live hashtag counts calculated from real posts."""
    db = get_db()
    pipeline = [
        {'$unwind': '$hashtags'},
        {'$group': {'_id': {'$toLower': '$hashtags'}, 'count': {'$sum': 1}}},
        {'$sort': {'count': -1, '_id': 1}},
        {'$limit': 8}
    ]
    tags = [
        {'tag': item['_id'].lstrip('#'), 'count': item['count']}
        for item in db.posts.aggregate(pipeline)
        if item.get('_id')
    ]
    return jsonify({'success': True, 'trends': tags})

@api_bp.route('/api/users/search', methods=['GET'])
@login_required
def search_users():
    """Search actual registered users for discovery and direct messaging."""
    db = get_db()
    current_user_id = session.get('user_id')
    query = request.args.get('q', '').strip()
    limit = min(max(int(request.args.get('limit', 8)), 1), 30)

    criteria = {'_id': {'$ne': ObjectId(current_user_id)}}
    if query:
        escaped = re.escape(query)
        criteria['$or'] = [
            {'name': {'$regex': escaped, '$options': 'i'}},
            {'username': {'$regex': escaped, '$options': 'i'}},
            {'bio': {'$regex': escaped, '$options': 'i'}}
        ]

    users = list(db.users.find(criteria, {'password_hash': 0}).sort('created_at', -1).limit(limit))
    results = []
    for user in users:
        user_id = str(user['_id'])
        results.append({
            'id': user_id,
            'name': user.get('name', 'Orvyn member'),
            'username': user.get('username', ''),
            'profile_image': user.get('profile_image', '/static/images/default-avatar.png'),
            'bio': user.get('bio', ''),
            'is_following': db.follows.find_one({'follower_id': current_user_id, 'following_id': user_id}) is not None
        })
    return jsonify({'success': True, 'users': results})

@api_bp.route('/api/users/<username>', methods=['GET'])
@login_required
def get_user_profile(username):
    db = get_db()
    current_user_id = session.get('user_id')
    
    user = db.users.find_one({'username': username.lower()})
    if not user:
        return jsonify({'error': 'User not found.'}), 404
        
    user_id = str(user['_id'])
    
    # Calculate counts dynamically to stay robust
    followers_count = db.follows.count_documents({'following_id': user_id})
    following_count = db.follows.count_documents({'follower_id': user_id})
    posts_count = db.posts.count_documents({'author_id': user_id})
    
    is_following = db.follows.find_one({'follower_id': current_user_id, 'following_id': user_id}) is not None
    
    # Fetch posts
    posts = list(db.posts.find({'author_id': user_id}).sort('created_at', -1))
    enriched_posts = enrich_posts(db, posts, current_user_id)
    
    # Fetch saved posts if requesting their own profile
    saved_posts = []
    if user_id == current_user_id:
        saves = list(db.saves.find({'user_id': current_user_id}))
        save_post_ids = [ObjectId(s['post_id']) for s in saves]
        saved_docs = list(db.posts.find({'_id': {'$in': save_post_ids}}).sort('created_at', -1))
        saved_posts = enrich_posts(db, saved_docs, current_user_id)
        
    return jsonify({
        'success': True,
        'profile': {
            'id': user_id,
            'name': user.get('name'),
            'username': user.get('username'),
            'profile_image': user.get('profile_image'),
            'cover_image': user.get('cover_image'),
            'bio': user.get('bio', ''),
            'location': user.get('location', ''),
            'website': user.get('website', ''),
            'interests': user.get('interests', []),
            'ai_summary': user.get('ai_summary', ''),
            'followers_count': followers_count,
            'following_count': following_count,
            'posts_count': posts_count,
            'is_following': is_following,
            'is_self': user_id == current_user_id
        },
        'posts': enriched_posts,
        'saved_posts': saved_posts
    })

@api_bp.route('/api/users/<user_id>/follow', methods=['POST'])
@login_required
def follow_user(user_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    if user_id == current_user_id:
        return jsonify({'error': 'You cannot follow yourself.'}), 400
        
    target_user = db.users.find_one({'_id': ObjectId(user_id)})
    if not target_user:
        return jsonify({'error': 'User not found.'}), 404
        
    existing_follow = db.follows.find_one({'follower_id': current_user_id, 'following_id': user_id})
    if existing_follow:
        return jsonify({'error': 'You are already following this user.'}), 400
        
    db.follows.insert_one({
        'follower_id': current_user_id,
        'following_id': user_id,
        'created_at': datetime.datetime.utcnow()
    })
    
    # Update counters
    db.users.update_one({'_id': ObjectId(current_user_id)}, {'$inc': {'following_count': 1}})
    db.users.update_one({'_id': ObjectId(user_id)}, {'$inc': {'followers_count': 1}})
    
    # Notify target user
    add_notification(db, user_id, 'follow', current_user_id)
    
    return jsonify({
        'success': True,
        'message': 'Following user successfully!'
    })

@api_bp.route('/api/users/<user_id>/follow', methods=['DELETE'])
@login_required
def unfollow_user(user_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    existing_follow = db.follows.find_one({'follower_id': current_user_id, 'following_id': user_id})
    if not existing_follow:
        return jsonify({'error': 'You are not following this user.'}), 400
        
    db.follows.delete_one({'_id': existing_follow['_id']})
    
    # Update counters
    db.users.update_one({'_id': ObjectId(current_user_id)}, {'$inc': {'following_count': -1}})
    db.users.update_one({'_id': ObjectId(user_id)}, {'$inc': {'followers_count': -1}})
    
    return jsonify({
        'success': True,
        'message': 'Unfollowed user successfully!'
    })

# Notifications
@api_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    db = get_db()
    current_user_id = session.get('user_id')
    
    notifications = list(db.notifications.find({'user_id': current_user_id}).sort('created_at', -1).limit(50))
    
    # Format notifications
    formatted = []
    for n in notifications:
        formatted.append({
            'id': str(n['_id']),
            'type': n.get('type'),
            'actor_id': n.get('actor_id'),
            'post_id': n.get('post_id'),
            'message': n.get('message'),
            'read': n.get('read', False),
            'created_at': n.get('created_at').isoformat() if isinstance(n.get('created_at'), datetime.datetime) else str(n.get('created_at'))
        })
        
    # Mark as read
    db.notifications.update_many({'user_id': current_user_id, 'read': False}, {'$set': {'read': True}})
    
    return jsonify({
        'success': True,
        'notifications': formatted
    })

# Messaging API (DMs)
@api_bp.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    db = get_db()
    current_user_id = session.get('user_id')
    
    # Fetch active chats (grouped conversations)
    # Fetch all DMs where user is sender or receiver
    messages = list(db.messages.find({
        '$or': [{'sender_id': current_user_id}, {'receiver_id': current_user_id}]
    }).sort('created_at', -1))
    
    # Group by chat partner
    threads = {}
    for m in messages:
        partner_id = m['receiver_id'] if m['sender_id'] == current_user_id else m['sender_id']
        if partner_id not in threads:
            partner = db.users.find_one({'_id': ObjectId(partner_id)}, {'name': 1, 'username': 1, 'profile_image': 1})
            if partner:
                threads[partner_id] = {
                    'partner': {
                        'id': partner_id,
                        'name': partner.get('name'),
                        'username': partner.get('username'),
                        'profile_image': partner.get('profile_image', '/static/images/default-avatar.png')
                    },
                    'last_message': {
                        'content': m.get('content', ''),
                        'media': m.get('media'),
                        'read': m.get('read', False),
                        'sender_id': m['sender_id'],
                        'created_at': m['created_at'].isoformat() if isinstance(m['created_at'], datetime.datetime) else str(m['created_at'])
                    },
                    'unread_count': 0
                }
        if m['receiver_id'] == current_user_id and not m.get('read', False):
            threads[partner_id]['unread_count'] += 1
            
    return jsonify({
        'success': True,
        'threads': list(threads.values())
    })

@api_bp.route('/api/messages/<partner_id>', methods=['GET'])
@login_required
def get_thread(partner_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    # Fetch conversation
    messages = list(db.messages.find({
        '$or': [
            {'sender_id': current_user_id, 'receiver_id': partner_id},
            {'sender_id': partner_id, 'receiver_id': current_user_id}
        ]
    }).sort('created_at', 1))
    
    # Mark messages as read
    db.messages.update_many({
        'sender_id': partner_id,
        'receiver_id': current_user_id,
        'read': False
    }, {'$set': {'read': True}})
    
    formatted = []
    for m in messages:
        formatted.append({
            'id': str(m['_id']),
            'sender_id': m['sender_id'],
            'receiver_id': m['receiver_id'],
            'content': m.get('content', ''),
            'media': m.get('media'),
            'created_at': m['created_at'].isoformat() if isinstance(m['created_at'], datetime.datetime) else str(m['created_at'])
        })
        
    # Fetch partner info
    partner = db.users.find_one({'_id': ObjectId(partner_id)}, {'name': 1, 'username': 1, 'profile_image': 1})
    
    return jsonify({
        'success': True,
        'partner': {
            'id': partner_id,
            'name': partner.get('name') if partner else 'User',
            'username': partner.get('username') if partner else 'user',
            'profile_image': partner.get('profile_image', '/static/images/default-avatar.png') if partner else '/static/images/default-avatar.png'
        },
        'messages': formatted
    })

@api_bp.route('/api/messages', methods=['POST'])
@login_required
def send_message():
    db = get_db()
    current_user_id = session.get('user_id')
    
    # Can be JSON or Multipart for media files
    receiver_id = request.form.get('receiver_id') or request.json.get('receiver_id') if request.is_json else request.form.get('receiver_id')
    content = request.form.get('content', '').strip() or request.json.get('content', '').strip() if request.is_json else request.form.get('content', '').strip()
    
    if not receiver_id:
        return jsonify({'error': 'Receiver ID is required.'}), 400
        
    media_url = None
    if 'media' in request.files:
        try:
            media_url = save_uploaded_file(request.files['media'], current_user_id, 'image')
        except Exception as e:
            return jsonify({'error': f"Failed uploading image: {str(e)}"}), 400
            
    if not content and not media_url:
        return jsonify({'error': 'Message content cannot be empty.'}), 400
        
    msg_doc = {
        'sender_id': current_user_id,
        'receiver_id': receiver_id,
        'content': content,
        'media': media_url,
        'read': False,
        'created_at': datetime.datetime.utcnow()
    }
    
    result = db.messages.insert_one(msg_doc)
    
    # Notify receiver
    add_notification(db, receiver_id, 'message', current_user_id, custom_message=f"{session.get('name')} sent you a message.")
    
    return jsonify({
        'success': True,
        'message': {
            'id': str(result.inserted_id),
            'sender_id': current_user_id,
            'receiver_id': receiver_id,
            'content': content,
            'media': media_url,
            'created_at': msg_doc['created_at'].isoformat()
        }
    }), 201

# Communities
@api_bp.route('/api/communities', methods=['GET'])
@login_required
def get_communities():
    db = get_db()
    query = {}
    
    search_q = request.args.get('q', '').strip()
    if search_q:
        query = {'$text': {'$search': search_q}}
        
    comms = list(db.communities.find(query).sort('members_count', -1))
    
    formatted = []
    current_user_id = session.get('user_id')
    for c in comms:
        c_id = str(c['_id'])
        is_member = db.community_members.find_one({'community_id': c_id, 'user_id': current_user_id}) is not None
        formatted.append({
            'id': c_id,
            'name': c.get('name'),
            'description': c.get('description'),
            'image': c.get('image', '/static/images/default-community.png'),
            'members_count': c.get('members_count', 1),
            'category': c.get('category', 'General'),
            'is_member': is_member
        })
        
    return jsonify({
        'success': True,
        'communities': formatted
    })

@api_bp.route('/api/communities', methods=['POST'])
@login_required
def create_community():
    db = get_db()
    current_user_id = session.get('user_id')
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', 'General').strip()
    rules = request.form.get('rules', '').strip()
    
    if not name or not description:
        return jsonify({'error': 'Community name and description are required.'}), 400
        
    # Check unique community name
    if db.communities.find_one({'name': {'$regex': f'^{name}$', '$options': 'i'}}):
        return jsonify({'error': 'A community with this name already exists.'}), 400
        
    # Community image upload
    image_url = '/static/images/default-community.png'
    image_file = request.files.get('image')
    if image_file and image_file.filename:
        try:
            image_url = save_uploaded_file(image_file, 'comm_' + secure_filename(name), 'image')
        except Exception as e:
            return jsonify({'error': f"Image upload failed: {str(e)}"}), 400
            
    comm_doc = {
        'name': name,
        'description': description,
        'image': image_url,
        'creator_id': current_user_id,
        'members_count': 1,
        'category': category,
        'rules': rules,
        'created_at': datetime.datetime.utcnow()
    }
    
    result = db.communities.insert_one(comm_doc)
    comm_id = str(result.inserted_id)
    
    # Add creator as Admin member
    db.community_members.insert_one({
        'community_id': comm_id,
        'user_id': current_user_id,
        'role': 'admin',
        'joined_at': datetime.datetime.utcnow()
    })
    
    return jsonify({
        'success': True,
        'message': 'Community created successfully!',
        'community': {
            'id': comm_id,
            'name': name,
            'description': description,
            'image': image_url,
            'members_count': 1,
            'category': category
        }
    }), 201

@api_bp.route('/api/communities/<comm_id>/join', methods=['POST'])
@login_required
def join_community(comm_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    comm = db.communities.find_one({'_id': ObjectId(comm_id)})
    if not comm:
        return jsonify({'error': 'Community not found.'}), 404
        
    existing_membership = db.community_members.find_one({'community_id': comm_id, 'user_id': current_user_id})
    if existing_membership:
        return jsonify({'error': 'You are already a member of this community.'}), 400
        
    db.community_members.insert_one({
        'community_id': comm_id,
        'user_id': current_user_id,
        'role': 'member',
        'joined_at': datetime.datetime.utcnow()
    })
    
    db.communities.update_one({'_id': ObjectId(comm_id)}, {'$inc': {'members_count': 1}})
    
    return jsonify({
        'success': True,
        'message': 'Joined community successfully!'
    })

@api_bp.route('/api/communities/<comm_id>/leave', methods=['POST'])
@login_required
def leave_community(comm_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    comm = db.communities.find_one({'_id': ObjectId(comm_id)})
    if not comm:
        return jsonify({'error': 'Community not found.'}), 404
        
    existing_membership = db.community_members.find_one({'community_id': comm_id, 'user_id': current_user_id})
    if not existing_membership:
        return jsonify({'error': 'You are not a member of this community.'}), 400
        
    if existing_membership['role'] == 'admin':
        # Creator leaving community: find another admin or prevent if they are the only member
        if comm['members_count'] == 1:
            # Delete community entirely
            db.communities.delete_one({'_id': ObjectId(comm_id)})
            db.community_members.delete_many({'community_id': comm_id})
            return jsonify({'success': True, 'message': 'Community deleted since you were the last member.'})
            
    db.community_members.delete_one({'_id': existing_membership['_id']})
    db.communities.update_one({'_id': ObjectId(comm_id)}, {'$inc': {'members_count': -1}})
    
    return jsonify({
        'success': True,
        'message': 'Left community successfully!'
    })

@api_bp.route('/api/communities/<comm_id>/posts', methods=['GET'])
@login_required
def get_community_posts(comm_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    comm = db.communities.find_one({'_id': ObjectId(comm_id)})
    if not comm:
        return jsonify({'error': 'Community not found.'}), 404
        
    posts = list(db.posts.find({'community_id': comm_id}).sort('created_at', -1))
    enriched = enrich_posts(db, posts, current_user_id)
    
    return jsonify({
        'success': True,
        'posts': enriched
    })

# Stories
@api_bp.route('/api/stories', methods=['GET'])
@login_required
def get_stories():
    db = get_db()
    current_user_id = session.get('user_id')
    
    # Active stories: expires_at > now
    now = datetime.datetime.utcnow()
    active_stories = list(db.stories.find({'expires_at': {'$gt': now}}).sort('created_at', -1))
    
    # Group stories by user
    user_stories = {}
    for s in active_stories:
        u_id = s['user_id']
        if u_id not in user_stories:
            user = db.users.find_one({'_id': ObjectId(u_id)}, {'name': 1, 'username': 1, 'profile_image': 1})
            if user:
                user_stories[u_id] = {
                    'user': {
                        'id': u_id,
                        'name': user.get('name'),
                        'username': user.get('username'),
                        'profile_image': user.get('profile_image', '/static/images/default-avatar.png')
                    },
                    'stories': []
                }
        if u_id in user_stories:
            user_stories[u_id]['stories'].append({
                'id': str(s['_id']),
                'media': s.get('media'),
                'media_type': s.get('media_type', 'image'),
                'created_at': s['created_at'].isoformat()
            })
            
    return jsonify({
        'success': True,
        'threads': list(user_stories.values())
    })

@api_bp.route('/api/stories', methods=['POST'])
@login_required
def create_story():
    db = get_db()
    current_user_id = session.get('user_id')
    
    if 'media' not in request.files:
        return jsonify({'error': 'No story media file uploaded.'}), 400
        
    media_file = request.files['media']
    
    try:
        # Determine media type (image or video)
        filename = media_file.filename.lower()
        file_ext = filename.rsplit('.', 1)[1] if '.' in filename else ''
        is_video = file_ext in ['mp4', 'mov', 'avi', 'webm']
        media_type = 'video' if is_video else 'image'
        
        media_url = save_uploaded_file(media_file, current_user_id, media_type)
        
        # Stories automatically expire in 24 hours
        created_at = datetime.datetime.utcnow()
        expires_at = created_at + datetime.timedelta(hours=24)
        
        story_doc = {
            'user_id': current_user_id,
            'media': media_url,
            'media_type': media_type,
            'created_at': created_at,
            'expires_at': expires_at
        }
        
        result = db.stories.insert_one(story_doc)
        
        return jsonify({
            'success': True,
            'message': 'Story created successfully!',
            'story': {
                'id': str(result.inserted_id),
                'media': media_url,
                'media_type': media_type,
                'created_at': created_at.isoformat()
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f"Failed to post story: {str(e)}"}), 400

@api_bp.route('/api/stories/<story_id>', methods=['DELETE'])
@login_required
def delete_story(story_id):
    db = get_db()
    current_user_id = session.get('user_id')
    
    try:
        story = db.stories.find_one({'_id': ObjectId(story_id)})
        if not story:
            return jsonify({'error': 'Story not found.'}), 404
            
        if str(story['user_id']) != current_user_id:
            return jsonify({'error': 'You are not authorized to delete this story.'}), 403
            
        db.stories.delete_one({'_id': ObjectId(story_id)})
        
        return jsonify({
            'success': True,
            'message': 'Story deleted successfully!'
        })
    except Exception as e:
        return jsonify({'error': f"Failed to delete story: {str(e)}"}), 400

# Creator Analytics
@api_bp.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    db = get_db()
    current_user_id = session.get('user_id')
    
    # Calculate simple real statistics for the user's posts
    my_posts = list(db.posts.find({'author_id': current_user_id}))
    
    total_posts = len(my_posts)
    total_likes = sum([p.get('likes_count', 0) for p in my_posts])
    total_comments = sum([p.get('comments_count', 0) for p in my_posts])
    total_saves = sum([p.get('saves_count', 0) for p in my_posts])
    total_shares = sum([p.get('shares_count', 0) for p in my_posts])
    
    # Simulate views: view is approx likes * 5 + comments * 12 + 15
    total_views = sum([p.get('likes_count', 0)*5 + p.get('comments_count', 0)*12 + 15 for p in my_posts])
    
    # Engagement rate: (interactions / views) * 100
    engagement_rate = 0.0
    if total_views > 0:
        engagement_rate = round(((total_likes + total_comments + total_saves) / total_views) * 100, 1)
        
    # Get follower counts
    user = db.users.find_one({'_id': ObjectId(current_user_id)})
    followers_count = db.follows.count_documents({'following_id': current_user_id})
    
    # AI insights generator based on actual statistics
    ai_insights = "Your posts are showing healthy steady engagement! Share more interactive updates to increase follow rates."
    if total_posts > 0:
        image_posts = [p for p in my_posts if p.get('media_type') == 'image']
        video_posts = [p for p in my_posts if p.get('media_type') == 'video']
        text_posts = [p for p in my_posts if p.get('media_type') == 'none']
        
        # Analyze category performance
        avg_img_likes = sum([p.get('likes_count',0) for p in image_posts])/len(image_posts) if image_posts else 0
        avg_text_likes = sum([p.get('likes_count',0) for p in text_posts])/len(text_posts) if text_posts else 0
        
        if avg_img_likes > avg_text_likes and len(image_posts) > 0:
            ai_insights = "AI Suggestion: Your photo posts are getting higher engagement than text posts. Focus on sharing more high-quality graphics and mockup screenshots."
        elif avg_text_likes > avg_img_likes and len(text_posts) > 0:
            ai_insights = "AI Suggestion: Your text-based posts are generating deeper discussions. Leverage short text thoughts and conversational questions to build community relationships."
        elif total_saves > total_likes * 0.5:
            ai_insights = "AI Suggestion: Your project updates are getting saved frequently! Keep building in public and posting step-by-step guides; users value bookmarking your code setups."
            
    return jsonify({
        'success': True,
        'stats': {
            'total_posts': total_posts,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_saves': total_saves,
            'total_shares': total_shares,
            'total_views': total_views,
            'engagement_rate': f"{engagement_rate}%",
            'follower_growth': followers_count
        },
        'ai_insights': ai_insights
    })
