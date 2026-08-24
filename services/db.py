import os
import logging
from pymongo import MongoClient, TEXT
from config import Config

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MongoClient
mongo_client = None
db = None

def init_db(app=None):
    global mongo_client, db
    
    mongo_uri = Config.MONGO_URI
    if not mongo_uri:
        logger.error("MONGO_URI not configured in environment variables.")
        raise ValueError("MONGO_URI configuration is missing.")
        
    try:
        # Create client
        mongo_client = MongoClient(mongo_uri)
        # Verify connection
        mongo_client.admin.command('ping')
        logger.info("Successfully connected to MongoDB Atlas!")
        
        # Get database name from URI or use default 'orvyn_db'
        # Parse DB name from mongodb+srv://.../dbname?options
        db_name = 'orvyn_db'
        path_part = mongo_uri.split('/')[-1] if '/' in mongo_uri else ''
        if path_part:
            db_name = path_part.split('?')[0] if '?' in path_part else path_part
            if not db_name:
                db_name = 'orvyn_db'
                
        db = mongo_client[db_name]
        logger.info(f"Using database: {db_name}")
        
        # Create Indexes
        create_indexes()
        
        return db
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        # Return fallback local database or raise error
        raise e

def create_indexes():
    global db
    if db is None:
        logger.error("Database connection not initialized.")
        return
        
    try:
        # 1. users
        db.users.create_index("username", unique=True)
        db.users.create_index("email", unique=True)
        db.users.create_index("created_at")
        
        # 2. posts
        db.posts.create_index("author_id")
        db.posts.create_index("created_at")
        # Text index for search (content + hashtags)
        db.posts.create_index([("content", TEXT), ("hashtags", TEXT)], name="post_search_idx")
        
        # 3. follows
        db.follows.create_index([("follower_id", 1), ("following_id", 1)], unique=True)
        db.follows.create_index("following_id")
        
        # 4. likes
        db.likes.create_index([("user_id", 1), ("post_id", 1)], unique=True)
        db.likes.create_index("post_id")
        
        # 5. saves
        db.saves.create_index([("user_id", 1), ("post_id", 1)], unique=True)
        
        # 6. communities
        db.communities.create_index("name", unique=True)
        db.communities.create_index("category")
        db.communities.create_index([("name", TEXT), ("description", TEXT)], name="community_search_idx")
        
        # 7. community_members
        db.community_members.create_index([("community_id", 1), ("user_id", 1)], unique=True)
        
        # 8. messages
        db.messages.create_index("sender_id")
        db.messages.create_index("receiver_id")
        db.messages.create_index([("sender_id", 1), ("receiver_id", 1), ("created_at", 1)])
        
        # 9. notifications
        db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        
        # 10. stories
        db.stories.create_index("user_id")
        db.stories.create_index("expires_at")
        
        logger.info("Database indexes verified/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")

def get_db():
    global db
    if db is None:
        init_db()
    return db
