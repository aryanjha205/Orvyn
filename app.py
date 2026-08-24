import os
import datetime
from flask import Flask, send_from_directory, make_response
from config import Config
from services.db import init_db
from routes.auth import auth_bp
from routes.api import api_bp
from routes.ai import ai_bp
from routes.views import views_bp
from utils.security import hash_password
from PIL import Image, ImageDraw

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure Uploads Directory exists
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'images'), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'icons'), exist_ok=True)
        
        # 1. Generate Placeholder assets if missing
        generate_placeholder_assets(app.root_path)
    except Exception as e:
        app.logger.warning(f"Skipping folder creation/placeholders in read-only environment: {e}")

    # 2. Connect Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(views_bp)

    # 3. PWA Root Route Handlers (Ensures Service Worker Scope is root-level)
    @app.route('/service-worker.js')
    def service_worker():
        response = make_response(send_from_directory(os.path.join(app.root_path, 'pwa'), 'service-worker.js'))
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Service-Worker-Allowed'] = '/'
        return response

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(os.path.join(app.root_path, 'pwa'), 'manifest.json')

    # Serve static uploads, falling back to /tmp/ for serverless environments
    @app.route('/static/uploads/<filename>')
    def serve_upload(filename):
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(local_path):
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        # Fallback to serving from /tmp in read-only environments
        return send_from_directory('/tmp', filename)

    # 4. Database Initialization & Seeding
    try:
        db = init_db()
        seed_database_if_empty(db)
    except Exception as e:
        app.logger.error(f"Database initialization failed: {e}")

    return app

def generate_placeholder_assets(root_path):
    """Generate basic assets to prevent 404 image errors on startup."""
    images_dir = os.path.join(root_path, 'static', 'images')
    icons_dir = os.path.join(root_path, 'static', 'icons')
    
    # 1. Default Avatar
    avatar_path = os.path.join(images_dir, 'default-avatar.png')
    if not os.path.exists(avatar_path):
        img = Image.new('RGB', (150, 150), color='#72C924')
        draw = ImageDraw.Draw(img)
        # Draw a simple smiley face avatar
        draw.ellipse([35, 35, 115, 115], fill='#FFFFFF')
        draw.ellipse([50, 55, 60, 65], fill='#1E2022')
        draw.ellipse([90, 55, 100, 65], fill='#1E2022')
        draw.arc([60, 75, 90, 95], 0, 180, fill='#1E2022', width=4)
        img.save(avatar_path)

    # 2. Default Cover Banner
    cover_path = os.path.join(images_dir, 'default-cover.png')
    if not os.path.exists(cover_path):
        img = Image.new('RGB', (800, 250), color='#F4F6F8')
        draw = ImageDraw.Draw(img)
        # Draw elegant color stripes
        draw.rectangle([0, 0, 800, 40], fill='#72C924')
        draw.rectangle([0, 40, 800, 45], fill='#F52887')
        img.save(cover_path)

    # 3. Default Community Icon
    comm_path = os.path.join(images_dir, 'default-community.png')
    if not os.path.exists(comm_path):
        img = Image.new('RGB', (150, 150), color='#F52887')
        draw = ImageDraw.Draw(img)
        # Draw group symbols
        draw.ellipse([30, 40, 70, 80], fill='#FFFFFF')
        draw.ellipse([80, 40, 120, 80], fill='#FFFFFF')
        draw.rectangle([20, 90, 130, 130], fill='#FFFFFF')
        img.save(comm_path)

    # 4. Floating AI Assistant Icon
    bot_path = os.path.join(images_dir, 'ai-bot-icon.png')
    if not os.path.exists(bot_path):
        img = Image.new('RGB', (96, 96), color='#1E2022')
        draw = ImageDraw.Draw(img)
        # Cute robot symbol
        draw.rounded_rectangle([24, 28, 72, 68], fill='#72C924', radius=10)
        draw.rectangle([34, 40, 44, 50], fill='#FFFFFF')
        draw.rectangle([52, 40, 62, 50], fill='#FFFFFF')
        draw.rectangle([38, 58, 58, 62], fill='#FFFFFF')
        img.save(bot_path)

    # 5. PWA Icon Assets (Create 192 and 512 png folders)
    for size in [72, 96, 128, 144, 152, 192, 384, 512]:
        pwa_icon_path = os.path.join(icons_dir, f'icon-{size}x{size}.png')
        if not os.path.exists(pwa_icon_path):
            img = Image.new('RGB', (size, size), color='#72C924')
            draw = ImageDraw.Draw(img)
            # Cursive letter O or Orvyn logo background
            draw.ellipse([size*0.1, size*0.1, size*0.9, size*0.9], fill='#FFFFFF')
            draw.text((size*0.35, size*0.25), "O", fill='#F52887', font_size=int(size*0.5))
            img.save(pwa_icon_path)

def seed_database_if_empty(db):
    """Seed base tables on first run to give Orvyn an authentic social feel."""
    if db.users.count_documents({}) > 0:
        return # Seed only if empty

    print("Seeding database with default Orvyn profiles and updates...")
    
    # 1. Create default seed users
    users_data = [
        {
            'name': 'Diya Sharma',
            'username': 'diya.live',
            'email': 'diya@orvyn.local',
            'password_hash': hash_password('password123'),
            'profile_image': '/static/images/default-avatar.png',
            'cover_image': '/static/images/default-cover.png',
            'bio': 'Creative Designer. I build premium web apps, interface mockups and interactive PWAs.',
            'location': 'New Delhi, India',
            'website': 'https://diya.live',
            'interests': ['design', 'creative', 'ai'],
            'followers_count': 1200,
            'following_count': 324,
            'ai_summary': 'Creative UI designer focused on clean web application frontends and interactive PWA solutions.',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(days=90)
        },
        {
            'name': 'Aarav Mehta',
            'username': 'aarav.dev',
            'email': 'aarav@orvyn.local',
            'password_hash': hash_password('password123'),
            'profile_image': '/static/images/default-avatar.png',
            'cover_image': '/static/images/default-cover.png',
            'bio': 'AI Engineer & Full-stack Python Developer. Let\'s build the future of AI Agent systems.',
            'location': 'Bengaluru, India',
            'website': 'https://aarav.dev',
            'interests': ['coding', 'tech', 'ai'],
            'followers_count': 2341,
            'following_count': 512,
            'ai_summary': 'Python developer and AI researcher diving deep into LLM integrations and database architecture.',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(days=120)
        },
        {
            'name': 'Aryan Jha',
            'username': 'aryan.build',
            'email': 'aryan@orvyn.local',
            'password_hash': hash_password('password123'),
            'profile_image': '/static/images/default-avatar.png',
            'cover_image': '/static/images/default-cover.png',
            'bio': 'Developer enthusiast | Testing out the brand new Orvyn Social Media Platform.',
            'location': 'Mumbai, India',
            'website': 'https://github.com/aryan',
            'interests': ['coding', 'tech', 'social'],
            'followers_count': 10,
            'following_count': 2,
            'ai_summary': 'Exploring PWA deployments, MongoDB optimization, and AI tool integrations.',
            'created_at': datetime.datetime.utcnow()
        }
    ]

    inserted_users = {}
    for user_doc in users_data:
        result = db.users.insert_one(user_doc)
        inserted_users[user_doc['username']] = str(result.inserted_id)

    # Create Follow relationships between seeds
    db.follows.insert_many([
        {'follower_id': inserted_users['diya.live'], 'following_id': inserted_users['aarav.dev'], 'created_at': datetime.datetime.utcnow()},
        {'follower_id': inserted_users['aarav.dev'], 'following_id': inserted_users['diya.live'], 'created_at': datetime.datetime.utcnow()},
        {'follower_id': inserted_users['aryan.build'], 'following_id': inserted_users['diya.live'], 'created_at': datetime.datetime.utcnow()},
        {'follower_id': inserted_users['aryan.build'], 'following_id': inserted_users['aarav.dev'], 'created_at': datetime.datetime.utcnow()}
    ])

    # 2. Create Communities
    comms_data = [
        {
            'name': 'Tech Hub',
            'description': 'A hub for software engineers, database admins, and web builders to discuss stack frameworks.',
            'image': '/static/images/default-community.png',
            'creator_id': inserted_users['aarav.dev'],
            'members_count': 3,
            'category': 'tech',
            'rules': '1. Keep discussions technical. 2. Share build in public setups.',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(days=30)
        },
        {
            'name': 'Creators World',
            'description': 'A sanctuary for graphic artists, content strategists, writers and product UI designers.',
            'image': '/static/images/default-community.png',
            'creator_id': inserted_users['diya.live'],
            'members_count': 2,
            'category': 'creative',
            'rules': 'Be kind and respect creative rights.',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(days=25)
        }
    ]

    inserted_comms = {}
    for comm in comms_data:
        result = db.communities.insert_one(comm)
        inserted_comms[comm['name']] = str(result.inserted_id)

    # Insert Community Members
    db.community_members.insert_many([
        {'community_id': inserted_comms['Tech Hub'], 'user_id': inserted_users['aarav.dev'], 'role': 'admin', 'joined_at': datetime.datetime.utcnow()},
        {'community_id': inserted_comms['Tech Hub'], 'user_id': inserted_users['diya.live'], 'role': 'member', 'joined_at': datetime.datetime.utcnow()},
        {'community_id': inserted_comms['Tech Hub'], 'user_id': inserted_users['aryan.build'], 'role': 'member', 'joined_at': datetime.datetime.utcnow()},
        {'community_id': inserted_comms['Creators World'], 'user_id': inserted_users['diya.live'], 'role': 'admin', 'joined_at': datetime.datetime.utcnow()},
        {'community_id': inserted_comms['Creators World'], 'user_id': inserted_users['aryan.build'], 'role': 'member', 'joined_at': datetime.datetime.utcnow()}
    ])

    # 3. Create Posts
    posts_data = [
        {
            'author_id': inserted_users['diya.live'],
            'content': 'Just finished building my new AI-powered habit tracker ✨\nIt\'s simple, clean and actually works!\nWould love your feedback ❤️ #design #ai #webdev',
            'media': [],
            'media_type': 'none',
            'hashtags': ['design', 'ai', 'webdev'],
            'mentions': [],
            'likes_count': 1200,
            'comments_count': 2,
            'shares_count': 89,
            'saves_count': 124,
            'community_id': None,
            'community_name': None,
            'is_repost': False,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        },
        {
            'author_id': inserted_users['aarav.dev'],
            'content': 'Diving deep into MongoDB Atlas indexing. Creating compound text indexes has boosted our semantic discover query speed by over 40%. Stack optimization matters! #coding #tech #mongodb',
            'media': [],
            'media_type': 'none',
            'hashtags': ['coding', 'tech', 'mongodb'],
            'mentions': [],
            'likes_count': 542,
            'comments_count': 1,
            'shares_count': 12,
            'saves_count': 45,
            'community_id': inserted_comms['Tech Hub'],
            'community_name': 'Tech Hub',
            'is_repost': False,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=6)
        }
    ]

    inserted_posts = []
    for post in posts_data:
        result = db.posts.insert_one(post)
        inserted_posts.append(str(result.inserted_id))

    # Insert default comments
    db.comments.insert_many([
        {
            'post_id': inserted_posts[0],
            'author_id': inserted_users['aarav.dev'],
            'content': 'This interface looks absolutely fantastic! The color choices fit perfectly.',
            'likes_count': 5,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        },
        {
            'post_id': inserted_posts[0],
            'author_id': inserted_users['aryan.build'],
            'content': 'Agreed, the animations are super smooth. Eager to check this out.',
            'likes_count': 2,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
        },
        {
            'post_id': inserted_posts[1],
            'author_id': inserted_users['diya.live'],
            'content': 'Nice speed boost! Good database indexing saves a lot of client load time.',
            'likes_count': 1,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=4)
        }
    ])

    # 4. Insert active Stories
    db.stories.insert_many([
        {
            'user_id': inserted_users['aarav.dev'],
            'media': '/static/images/default-cover.png',
            'media_type': 'image',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            'expires_at': datetime.datetime.utcnow() + datetime.timedelta(hours=23)
        },
        {
            'user_id': inserted_users['diya.live'],
            'media': '/static/images/default-cover.png',
            'media_type': 'image',
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=2),
            'expires_at': datetime.datetime.utcnow() + datetime.timedelta(hours=22)
        }
    ])

    # 5. Seed default inbox DMs between diya and aarav
    db.messages.insert_many([
        {
            'sender_id': inserted_users['diya.live'],
            'receiver_id': inserted_users['aarav.dev'],
            'content': 'Hey Aarav! Have you verified the OpenRouter API keys for Orvyn today?',
            'media': None,
            'read': True,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=12)
        },
        {
            'sender_id': inserted_users['aarav.dev'],
            'receiver_id': inserted_users['diya.live'],
            'content': 'Hey Diya, yes, verified. The free models like google/gemma are working perfectly.',
            'media': None,
            'read': True,
            'created_at': datetime.datetime.utcnow() - datetime.timedelta(hours=11)
        }
    ])

    print("Seed complete! Database populated.")

# Instantiated globally for Vercel Serverless/WSGI integration
app = create_app()

if __name__ == '__main__':
    # Runs on default Flask port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
