import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'orvyn_default_secret_key_1827')
    
    # MongoDB Atlas settings
    MONGO_URI = os.environ.get('MONGO_URI')
    
    # AI settings
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'mock').lower()
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
    AI_MODEL = os.environ.get('AI_MODEL', 'google/gemma-2-9b-it:free')
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)) # 16 MB max
    
    # Session configurations
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
