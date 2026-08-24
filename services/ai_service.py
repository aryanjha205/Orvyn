import os
import base64
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

class AIService:
    @staticmethod
    def _call_openrouter(messages, model=None, response_format=None):
        """Helper to send requests to OpenRouter."""
        api_key = Config.OPENROUTER_API_KEY
        provider = Config.AI_PROVIDER
        
        if provider == 'mock' or not api_key:
            return None
            
        selected_model = model or Config.AI_MODEL
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://orvyn-app.local",
            "X-Title": "Orvyn PWA"
        }
        
        data = {
            "model": selected_model,
            "messages": messages
        }
        
        if response_format:
            data["response_format"] = response_format
            
        try:
            # Set a timeout of 10 seconds to ensure the page doesn't hang indefinitely
            response = requests.post(url, headers=headers, json=data, timeout=12)
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                logger.warning(f"OpenRouter API returned error code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to communicate with OpenRouter API: {e}")
            return None

    @classmethod
    def generate_post(cls, prompt: str, tone: str = "friendly", style: str = "engaging") -> str:
        """Generate a social media post from a short prompt idea."""
        system_instruction = (
            f"You are an expert social media copywriter for Orvyn. "
            f"Generate a post based on the user's idea. "
            f"Tone: {tone}. Style: {style}. "
            f"Write ONLY the post content. Keep it within 280 characters. "
            f"Include appropriate emojis and spacing. Do not include quotes."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Idea: {prompt}"}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            return ai_response
            
        # Fallback Mock Generation
        mock_posts = {
            "professional": f"Excited to share that we are diving deep into the next phase of our development! 🚀 {prompt}. Let's push the boundaries of what's possible with modern architecture. #BuildInPublic #TechInnovation",
            "casual": f"So... {prompt.lower()} and honestly, it's pretty awesome. Still a lot of code to write but we're getting there! What are you working on today? 👇",
            "funny": f"My coffee is 90% logic, 10% anxiety, and 100% focused on this: {prompt}. Yes, I know math is hard. But code is harder! ☕️💻 #DeveloperLife",
            "inspirational": f"Every big project starts with a small step. ✨ {prompt}. Keep coding, keep building, and never let temporary setbacks stop your creative momentum. 🌟 #Motivation",
            "educational": f"Quick tip: When working on this - '{prompt}' - always remember to double-check database indexes. It saves querying time later! 💡 #CodingTips #WebDev",
            "friendly": f"Hey friends! Just wanted to share: {prompt}. Hope everyone is having a productive week! Let me know your thoughts on this! 😊👋"
        }
        return mock_posts.get(tone.lower(), f"Just sharing a quick update: {prompt} ✨ #Orvyn #AI")

    @classmethod
    def improve_post(cls, draft: str, tone: str = "friendly") -> str:
        """Improve an existing draft post."""
        system_instruction = (
            f"You are an AI writing assistant. Improve the following social media draft. "
            f"Make it more compelling, grammatically perfect, and format it nicely. "
            f"Keep the original meaning but style it to be {tone}. "
            f"Output ONLY the improved text, no intro, no outro, no markdown wrappers."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Draft: {draft}"}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            return ai_response
            
        # Fallback Mock
        return f"{draft} ✨ (Refined with {tone.capitalize()} style! Ready to share with your audience) 🚀"

    @classmethod
    def generate_hashtags(cls, text: str) -> list:
        """Generate relevant hashtags for the given post text."""
        system_instruction = (
            "You are a social media hashtag generator. Analyze the text and return 4 to 6 relevant hashtags. "
            "Separate them with spaces. Return ONLY the hashtags, e.g. '#python #coding #ai'. No other text."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Post content: {text}"}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            tags = [tag.strip() for tag in ai_response.split() if tag.startswith('#')]
            if tags:
                return tags
                
        # Fallback Mock Hashtag Extractor
        words = text.lower().replace('#', '').split()
        keywords = ['coding', 'tech', 'ai', 'developer', 'startup', 'webdev', 'python', 'design', 'social']
        found = [f"#{kw}" for kw in keywords if kw in words]
        if len(found) < 3:
            found.extend(['#Orvyn', '#SocialMedia', '#AICommunity'])
        return list(set(found))[:5]

    @classmethod
    def translate_text(cls, text: str, target_lang: str) -> str:
        """Translate a post into another language."""
        system_instruction = (
            f"You are a precise translator. Translate the text into {target_lang}. "
            f"Maintain the formatting, emojis, and hashtags. "
            f"Output ONLY the translated text, no explanation."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": text}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            return ai_response
            
        # Fallback Mock
        translations = {
            "spanish": f"[Translated to Spanish]: {text} (Traducción simulada)",
            "french": f"[Translated to French]: {text} (Traduction simulée)",
            "german": f"[Translated to German]: {text} (Simulierte Übersetzung)",
            "japanese": f"[Translated to Japanese]: {text} (模擬翻訳)"
        }
        return translations.get(target_lang.lower(), f"[Translated to {target_lang}]: {text}")

    @classmethod
    def suggest_comment_reply(cls, comment_text: str) -> str:
        """Suggest a short reply to a post comment."""
        system_instruction = (
            "Suggest a short, friendly, and context-appropriate response to this comment on a social post. "
            "Keep it under 100 characters. Output ONLY the response, no quotes."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Comment: {comment_text}"}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            return ai_response
            
        # Fallback Mock
        if 'great' in comment_text.lower() or 'awesome' in comment_text.lower() or 'love' in comment_text.lower():
            return "Thank you so much! I really appreciate the feedback. 🙏✨"
        if 'question' in comment_text.lower() or 'how' in comment_text.lower():
            return "Great question! I'll follow up in direct messages to explain. 📩"
        return "Thanks for stopping by and leaving a comment! 😊"

    @classmethod
    def describe_image(cls, image_path: str) -> dict:
        """Describe image, suggest accessibility alt text, suggest hashtags and captions."""
        # Convert local image to base64
        base64_image = ""
        try:
            if os.path.exists(image_path):
                with open(image_path, "rb") as image_file:
                    base64_image = base64_encode = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading image for AI description: {e}")
            
        # Try vision models on OpenRouter (e.g. google/gemini-flash-1.5:free)
        if base64_image and Config.OPENROUTER_API_KEY and Config.AI_PROVIDER != 'mock':
            ext = image_path.rsplit('.', 1)[1].lower() if '.' in image_path else 'jpeg'
            mime_type = f"image/{ext}" if ext in ['png', 'gif', 'webp'] else "image/jpeg"
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image and return a JSON object with keys: 'description' (general detail), 'caption' (catchy social media caption), 'alt_text' (short accessibility description), and 'tags' (array of 4 tags). Keep your output strict JSON format only."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Using Gemini Flash Free for vision tasks
            ai_response = cls._call_openrouter(messages, model="google/gemini-flash-1.5:free", response_format={"type": "json_object"})
            if ai_response:
                try:
                    import json
                    parsed = json.loads(ai_response)
                    return parsed
                except Exception:
                    # Try manual string parsing if json parsing failed
                    pass
                    
        # Fallback Mock description
        return {
            "description": "A workspace showing a developer's setup with a code editor on screen, coffee, and ambient warm lighting.",
            "caption": "Late night coding sessions fueled by caffeine and pure excitement! 💻✨ #BuildInPublic #DevLife",
            "alt_text": "Close-up of a laptop displaying lines of code alongside a warm cup of coffee on a desk.",
            "tags": ["coding", "programming", "workspace", "tech"]
        }

    @classmethod
    def get_assistant_response(cls, query: str, context: dict = None) -> dict:
        """
        Conversational assistant logic. 
        Returns dict with:
          - text: Response message
          - action: Optional client action to execute (e.g. {"type": "search", "query": "..."})
        """
        context_str = str(context or {})
        system_instruction = (
            "You are Orvyn, the friendly and futuristic AI assistant of the Orvyn Social PWA. "
            "You help users draft posts, find developers, check notifications, and search the platform. "
            "Based on the user query and session context, respond in strict JSON format. "
            "JSON structure:\n"
            "{\n"
            "  \"text\": \"Your response message to show in the chat. Use friendly emojis.\",\n"
            "  \"action\": null or {\"type\": \"search\"|\"fill_post\"|\"redirect\", \"query\"|\"content\"|\"url\": \"...\"}\n"
            "}\n"
            "Supported actions:\n"
            "- search: type='search', query='search text'\n"
            "- fill_post: type='fill_post', content='post contents'\n"
            "- redirect: type='redirect', url='/profile' or '/messages' or '/communities'\n"
            "Be conversational and brief."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Context: {context_str}\nQuery: {query}"}
        ]
        
        # Request in JSON format
        ai_response = cls._call_openrouter(messages, response_format={"type": "json_object"})
        if ai_response:
            try:
                import json
                parsed = json.loads(ai_response)
                # Ensure structure
                if "text" in parsed:
                    return parsed
            except Exception as e:
                logger.error(f"Error parsing assistant JSON: {e}")
                
        # Mock responses based on keyword queries
        q = query.lower()
        response = {"text": "I can help you build your social circle! Ask me to 'find AI developers', 'help write a post', or 'go to my profile'.", "action": None}
        
        if "help me write" in q or "write a post" in q or "create a post" in q:
            idea = query.replace("help me write a post about", "").replace("write a post about", "").strip()
            if not idea or idea == q:
                idea = "building my new social media PWA called Orvyn"
            post_content = f"Building the future of social media with Orvyn! 🚀 Check out my progress on this new AI-powered PWA. #BuildInPublic #Orvyn"
            response = {
                "text": "Sure, I've crafted a post for you! I've loaded it directly into your post creator so you can edit it. 📝",
                "action": {"type": "fill_post", "content": post_content}
            }
        elif "find" in q or "search" in q:
            search_query = query.replace("find", "").replace("search for", "").replace("show me", "").strip()
            response = {
                "text": f"Scanning the Orvyn network... 🔍 Let's search for '{search_query}'!",
                "action": {"type": "search", "query": search_query}
            }
        elif "profile" in q:
            response = {
                "text": "Taking you straight to your profile! 👤 You can view your posts and regenerate your AI summary there.",
                "action": {"type": "redirect", "url": "/profile"}
            }
        elif "message" in q or "chat" in q:
            response = {
                "text": "Opening your messages inbox! ✉️ Stay connected with your friends.",
                "action": {"type": "redirect", "url": "/messages"}
            }
        elif "community" in q or "communities" in q:
            response = {
                "text": "Opening the Communities portal! 🌐 Find your hub of creators, developers, or designers.",
                "action": {"type": "redirect", "url": "/communities"}
            }
        elif "notification" in q:
            response = {
                "text": "Here's a quick notification summary: You have 3 new notifications (likes on your latest code screenshot, and a follow request). 🔔",
                "action": None
            }
        elif "best" in q or "analytics" in q or "perform" in q:
            response = {
                "text": "📊 Insight: Your posts with images are getting 40% more saves and likes! Keep posting visual updates. #CreatorInsights",
                "action": None
            }
            
        return response

    @classmethod
    def generate_profile_summary(cls, user_data: dict, posts_data: list) -> str:
        """Generate a 1-sentence summary of the user profile based on interests and posts."""
        interests = ", ".join(user_data.get('interests', []))
        recent_posts = " | ".join([p.get('content', '') for p in posts_data[:3]])
        
        system_instruction = (
            "You are an AI profiling bot. Write a concise, professional, yet engaging 1-sentence bio summary "
            "for this user's profile based on their interests and recent activity. "
            "Keep it under 120 characters. Example: 'Software architect passionate about cloud tech and UI design.' "
            "Return ONLY the summary. No intro, no quotes."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"User: {user_data.get('name')}. Interests: {interests}. Recent Posts: {recent_posts}"}
        ]
        
        ai_response = cls._call_openrouter(messages)
        if ai_response:
            return ai_response
            
        # Fallback Mock Bio
        interest_words = user_data.get('interests', [])
        primary_interest = interest_words[0].capitalize() if interest_words else "Technology"
        secondary_interest = f" & {interest_words[1]}" if len(interest_words) > 1 else ""
        return f"{primary_interest}{secondary_interest} builder sharing updates and exploring the future of social networks. 🚀"
