# Orvyn — AI-Powered Social Media PWA

Orvyn is a mobile-first Progressive Web App (PWA) that combines modern social media interaction patterns with a native AI layer. Built using Flask, Vanilla JS, CSS3, and MongoDB Atlas, Orvyn integrates OpenRouter to power social composition, image captioning, translation, direct message reply assistance, and a floating chatbot helper.

## Features

1. **Authentication**: Secure registration, login/logout, and session configuration.
2. **Social Feed**: Infinite scrolling feed with `For You`, `Following`, `Trending`, and tag categories.
3. **AI Post Composer**: Inline writing tools supporting professional/funny/inspirational tones and automatic hashtags extraction.
4. **AI Vision Captioner**: Automatically scans uploaded images in the background to suggest accessibility alt text, descriptions, and catchy caption scripts.
5. **Private DMs**: Near real-time polling chat threads, image uploads in chat, and AI suggestion chips based on received messages.
6. **Group Communities**: Create, join, and participate in topic-based groups, supported by the **AI Community Moderator** to summarize discussions and identify unanswered questions.
7. **PWA Integration**: Caching of stylesheets and static files using a service worker for offline accessibility and fast repeat visits.
8. **Creator Analytics**: Dynamic analytics parsing real engagement counts (likes, comments, shares, views) and delivering actual creator suggestions.

---

## Technical Stack

* **Frontend**: HTML5, CSS3 (Vanilla design system + responsive rules), Vanilla JavaScript (Lucide icons).
* **Backend**: Python + Flask.
* **Database**: MongoDB Atlas.
* **AI Provider**: OpenRouter API (utilizing free model `google/gemma-2-9b-it:free` and `google/gemini-flash-1.5:free` for vision-based image analyses).
* **Storage**: Local uploads directory (`static/uploads/`) with image validation and compression using `Pillow`.

---

## Installation & Local Setup

### 1. Clone & Prep Workspace
Ensure you have Python 3.10+ installed. Navigate to the root directory and install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (based on `.env.example`):

```env
# Flask Settings
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Database Settings
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/orvyn_db?retryWrites=true&w=majority

# AI Service Settings
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
AI_MODEL=google/gemma-2-9b-it:free

# Local uploads
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=16777216
```

### 3. Run the Application
Start the Flask development server:

```bash
python app.py
```

The application will run on `http://127.0.0.1:5000/`.
On startup, Orvyn automatically checks the database. If it is empty, it populates it with realistic demo users (like `@diya.live` and `@aarav.dev`), trending communities, mock posts, chat logs, and active stories so the platform is pre-populated out-of-the-box!

---

## PWA Capabilities
* **Installation**: Open Orvyn in Chrome, Safari, or Edge and click the install prompt in the address bar to add Orvyn to your desktop/mobile home screen.
* **Offline Caching**: Stylesheets, scripts, fonts, and avatar placeholders are cached offline. If network connection is lost, users can still view pages and browse previously cached posts.

---

## Verification & Testing
To run a test verification of routes and database connectivity:

```bash
python -m unittest tests/test_endpoints.py
```
*(Tests cover user registration, login redirects, post insertions, and OpenRouter AI connections).*
