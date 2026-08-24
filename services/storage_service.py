import os
import time
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from config import Config

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm'}

def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Verify file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, user_id: str, file_type: str = 'image') -> str:
    """
    Saves an uploaded file locally and returns its relative static URL.
    - file: Flask FileStorage object from request.files
    - user_id: ID of the user uploading the file
    - file_type: 'image' or 'video'
    """
    if not file or file.filename == '':
        return None

    # Check directories - route to writeable /tmp on Vercel serverless environments
    is_vercel = os.environ.get('VERCEL') == '1'
    upload_dir = '/tmp' if is_vercel else Config.UPLOAD_FOLDER
    
    if not os.path.exists(upload_dir):
        try:
            os.makedirs(upload_dir, exist_ok=True)
        except Exception:
            upload_dir = '/tmp'
            os.makedirs(upload_dir, exist_ok=True)

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    # Validate extension
    if file_type == 'image':
        if not allowed_file(filename, ALLOWED_IMAGE_EXTENSIONS):
            raise ValueError(f"Invalid image format. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    elif file_type == 'video':
        if not allowed_file(filename, ALLOWED_VIDEO_EXTENSIONS):
            raise ValueError(f"Invalid video format. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}")
    else:
        if not (allowed_file(filename, ALLOWED_IMAGE_EXTENSIONS) or allowed_file(filename, ALLOWED_VIDEO_EXTENSIONS)):
            raise ValueError("Unsupported file format.")

    # Generate unique, collision-proof name
    unique_id = uuid.uuid4().hex[:10]
    new_filename = f"{user_id}_{int(time.time())}_{unique_id}.{ext}"
    file_path = os.path.join(upload_dir, new_filename)

    # Save file
    file.save(file_path)

    # If it's an image, verify it with Pillow and optionally resize/compress
    if file_type == 'image' or (file_type == 'auto' and ext in ALLOWED_IMAGE_EXTENSIONS):
        try:
            with Image.open(file_path) as img:
                img.verify() # Verify it is a valid image
            
            # Re-open to compress/optimize if it's large (e.g. > 1.5MB)
            file_size = os.path.getsize(file_path)
            if file_size > 1.5 * 1024 * 1024:
                with Image.open(file_path) as img:
                    # Convert RGBA to RGB for jpeg save if necessary
                    if img.mode in ('RGBA', 'LA') and ext in ('jpg', 'jpeg'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3])
                        img = background
                    # Resize if extremely large
                    max_size = 1920
                    if img.size[0] > max_size or img.size[1] > max_size:
                        img.thumbnail((max_size, max_size))
                    # Save with optimization
                    img.save(file_path, quality=85, optimize=True)
        except Exception as e:
            # Delete invalid file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise ValueError("Uploaded file is a corrupted or invalid image.")

    # Return the relative URL to access the file in browser
    return f"/static/uploads/{new_filename}"
