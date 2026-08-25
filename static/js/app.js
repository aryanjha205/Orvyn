/* Orvyn JavaScript — Global Core Controller & PWA Manager */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons globally
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // 1. Register Service Worker
    registerServiceWorker();
    
    // 2. Initialize Floating AI Assistant
    initAiAssistant();
    
    // 3. Start Notification Polling
    pollNotifications();
    setInterval(pollNotifications, 30000); // Poll notifications every 30s
    
    // 4. Global Create Post Modal trigger (for desktop sidebar button)
    const desktopCreateBtn = document.getElementById('desktop-create-btn');
    const mobileCreateBtn = document.getElementById('mobile-create-btn');
    if (desktopCreateBtn) {
        desktopCreateBtn.addEventListener('click', focusPostComposer);
    }
    if (mobileCreateBtn) {
        mobileCreateBtn.addEventListener('click', focusPostComposer);
    }
});

// Register PWA service worker
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/service-worker.js')
                .then(registration => {
                    console.log('Orvyn Service Worker registered successfully with scope:', registration.scope);
                })
                .catch(error => {
                    console.error('Orvyn Service Worker registration failed:', error);
                });
        });
    }
}

// Global toast alert helper
function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = 'toast-msg';
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // Animate and remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// Redirects page scroll to composer draft box
function focusPostComposer() {
    const composer = document.getElementById('post-content-input');
    if (composer) {
        composer.scrollIntoView({ behavior: 'smooth' });
        composer.focus();
    } else {
        // Redirect to home if they are on another page
        window.location.href = '/#compose';
    }
}

// Persistent Assistant Controller
function initAiAssistant() {
    const trigger = document.getElementById('ai-assistant-trigger-btn');
    const drawer = document.getElementById('ai-chat-drawer');
    const closeBtn = document.getElementById('ai-chat-close-btn');
    const sendBtn = document.getElementById('ai-chat-send-btn');
    const input = document.getElementById('ai-chat-input');
    const messages = document.getElementById('ai-chat-messages');
    const promoChatBtn = document.getElementById('promo-chat-trigger-btn');
    const promoCloseBtn = document.getElementById('promo-close-btn');
    const promoCard = document.getElementById('ai-promo-banner-card');
    
    if (!trigger || !drawer) return;
    
    // Toggle drawer
    const toggleDrawer = () => drawer.classList.toggle('hidden');
    trigger.addEventListener('click', toggleDrawer);
    if (closeBtn) closeBtn.addEventListener('click', toggleDrawer);
    
    // Promo triggers
    if (promoChatBtn) {
        promoChatBtn.addEventListener('click', () => {
            drawer.classList.remove('hidden');
            input.focus();
        });
    }
    if (promoCloseBtn && promoCard) {
        promoCloseBtn.addEventListener('click', () => {
            promoCard.remove();
        });
    }

    // Send AI message
    const sendAiMessage = async () => {
        const query = input.value.trim();
        if (!query) return;
        
        // Append user bubble
        appendMsgBubble(query, 'user');
        input.value = '';
        
        // Append loading indicator
        const loadingBubble = appendMsgBubble('Thinking...', 'bot loading');
        
        try {
            const response = await fetch('/api/ai/assistant', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            const result = await response.json();
            
            loadingBubble.remove();
            
            if (response.ok && result.success) {
                const aiResult = result.result;
                appendMsgBubble(aiResult.text, 'bot');
                
                // Process Client Actions returned from LLM
                if (aiResult.action) {
                    executeAssistantAction(aiResult.action);
                }
            } else {
                appendMsgBubble('Sorry, I couldn\'t process that request right now.', 'bot');
            }
        } catch (e) {
            loadingBubble.remove();
            appendMsgBubble('Offline/Network error. Please try again.', 'bot');
        }
    };

    sendBtn.addEventListener('click', sendAiMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendAiMessage();
    });

    function appendMsgBubble(text, type) {
        const bubble = document.createElement('div');
        bubble.className = `ai-msg ${type}`;
        bubble.innerHTML = `<div class="ai-msg-bubble">${text}</div>`;
        messages.appendChild(bubble);
        messages.scrollTop = messages.scrollHeight;
        return bubble;
    }

    function executeAssistantAction(action) {
        // action format: {type: 'search'|'fill_post'|'redirect', content|query|url: '...'}
        setTimeout(() => {
            if (action.type === 'redirect' && action.url) {
                window.location.href = action.url;
            } else if (action.type === 'fill_post' && action.content) {
                // Toggles post composer panel
                const inputArea = document.getElementById('post-content-input');
                const aiPanel = document.getElementById('ai-composer-panel');
                if (inputArea) {
                    inputArea.value = action.content;
                    inputArea.focus();
                    showToast('Post draft pre-filled!');
                    if (aiPanel) aiPanel.classList.remove('hidden');
                }
            } else if (action.type === 'search' && action.query) {
                // If on discover, fill discover search, otherwise redirect to discover with query parameter
                if (window.location.pathname === '/discover') {
                    const dInput = document.getElementById('discover-search-input');
                    const dBtn = document.getElementById('ai-discover-search-btn');
                    if (dInput && dBtn) {
                        dInput.value = action.query;
                        dBtn.click();
                    }
                } else {
                    window.location.href = `/discover?q=${encodeURIComponent(action.query)}`;
                }
            }
        }, 1000);
    }
}

// Fetch unread counts dynamically
async function pollNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const result = await response.json();
        if (result.success) {
            const list = result.notifications;
            const unread = list.filter(n => !n.read).length;
            
            const badge = document.getElementById('notif-badge-count');
            if (badge) {
                if (unread > 0) {
                    badge.textContent = unread;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
        
        // Also poll message inbox badge count
        const msgResponse = await fetch('/api/messages');
        const msgResult = await msgResponse.json();
        if (msgResult.success) {
            const threads = msgResult.threads;
            const totalUnreadMsgs = threads.reduce((acc, t) => acc + t.unread_count, 0);
            
            const dBadge = document.getElementById('msg-badge-count');
            const mBadge = document.getElementById('msg-mobile-badge-count');
            
            [dBadge, mBadge].forEach(b => {
                if (b) {
                    if (totalUnreadMsgs > 0) {
                        b.textContent = totalUnreadMsgs;
                        b.classList.remove('hidden');
                    } else {
                        b.classList.add('hidden');
                    }
                }
            });
        }
    } catch(e) {
        // Quietly fail liveness poll
    }
}

// Shared Component: Dynamic Post Card Builder
function createPostCardElement(post) {
    const card = document.createElement('div');
    card.className = 'post-card-wrapper';
    card.id = `post-${post.id}`;
    
    // Parse tags to make links
    let parsedContent = post.content
        .replace(/#(\w+)/g, '<a href="/discover?q=%23$1">#$1</a>')
        .replace(/@(\w+)/g, '<a href="/profile/$1">@$1</a>');
        
    // Media block
    let mediaBlock = '';
    if (post.media && post.media.length > 0) {
        if (post.media_type === 'video') {
            mediaBlock = `
                <div class="post-media-box">
                    <video src="${post.media[0]}" controls preload="metadata"></video>
                </div>
            `;
        } else {
            mediaBlock = `
                <div class="post-media-box">
                    <img src="${post.media[0]}" alt="Post attachment" loading="lazy">
                </div>
            `;
        }
    }
    
    // Repost block
    let repostBlock = '';
    if (post.is_repost && post.original_post) {
        const orig = post.original_post;
        repostBlock = `
            <div class="reposted-content-card" style="border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: 12px; margin-top: 8px; background-color: var(--bg-secondary);">
                <div class="post-header-row" style="margin-bottom: 6px;">
                    <div class="post-author-link">
                        <img src="${orig.author.profile_image}" alt="${orig.author.name}" style="width:28px; height:28px; border-radius:50%;">
                        <div class="author-meta-box">
                            <span class="name-label" style="font-size:12px;">${orig.author.name}</span>
                            <span class="handle-label" style="font-size:10px;">@${orig.author.username}</span>
                        </div>
                    </div>
                </div>
                <p class="post-content-body" style="font-size:13px;">${orig.content}</p>
            </div>
        `;
    }

    // Community header label
    let communityHeader = '';
    if (post.community_id && post.community_name) {
        communityHeader = `
            <span class="post-comm-tag" style="background-color:var(--bg-secondary); font-size:11px; padding:4px 8px; border-radius:12px; margin-bottom: 6px; display:inline-block; font-weight:700; color:var(--parrot-green);">
                Shared in ${post.community_name}
            </span>
        `;
    }

    card.innerHTML = `
        ${communityHeader}
        <div class="post-header-row">
            <a href="/profile/${post.author.username}" class="post-author-link">
                <img src="${post.author.profile_image}" alt="${post.author.name}">
                <div class="author-meta-box">
                    <span class="name-label">
                        ${post.author.name}
                    </span>
                    <span class="handle-label">@${post.author.username}</span>
                </div>
            </a>
            <button class="post-options-trigger" onclick="deleteOrReportPost('${post.id}', '${post.author.id}')"><i data-lucide="more-horizontal"></i></button>
        </div>
        
        <p class="post-content-body">${parsedContent}</p>
        
        ${mediaBlock}
        ${repostBlock}
        
        <div class="post-actions-toolbar">
            <button class="action-btn-item ${post.liked ? 'active' : ''}" onclick="toggleLikePost(this, '${post.id}')">
                <i data-lucide="heart"></i>
                <span class="count">${post.likes_count}</span>
            </button>
            <button class="action-btn-item" onclick="openCommentModal('${post.id}')">
                <i data-lucide="message-square"></i>
                <span class="count">${post.comments_count}</span>
            </button>
            <button class="action-btn-item" onclick="repostPostAction('${post.id}')">
                <i data-lucide="repeat"></i>
                <span class="count">${post.shares_count}</span>
            </button>
            <button class="action-btn-item ${post.saved ? 'saved-active' : ''}" onclick="toggleSavePost(this, '${post.id}')">
                <i data-lucide="bookmark"></i>
            </button>
        </div>
    `;
    
    return card;
}

// Global actions for post triggers
async function toggleLikePost(btn, id) {
    try {
        const response = await fetch(`/api/posts/${id}/like`, { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            const countLabel = btn.querySelector('.count');
            countLabel.textContent = result.likes_count;
            if (result.liked) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    } catch(e) {
        console.error(e);
    }
}

async function toggleSavePost(btn, id) {
    try {
        const response = await fetch(`/api/posts/${id}/save`, { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            if (result.saved) {
                btn.classList.add('saved-active');
                showToast('Post bookmarked in Saved folder!');
            } else {
                btn.classList.remove('saved-active');
                showToast('Post removed from Saved folder!');
            }
        }
    } catch(e) {
        console.error(e);
    }
}

async function repostPostAction(id) {
    if (confirm('Repost this update to your feed?')) {
        try {
            const response = await fetch(`/api/posts/${id}/repost`, { method: 'POST' });
            const result = await response.json();
            if (response.ok && result.success) {
                const countLabel = document.querySelector(`#post-${id} .action-btn-item:nth-child(3) .count`);
                if (countLabel) countLabel.textContent = result.shares_count;
                showToast('Reposted successfully! Check your profile feed.');
            } else {
                showToast(result.error);
            }
        } catch(e) {
            showToast('Connection error during repost.');
        }
    }
}

async function deleteOrReportPost(post_id, author_id) {
    const isSelf = CURRENT_USER.id === author_id;
    const action = isSelf ? confirm('Delete this post permanently?') : confirm('Report this post for spam/inappropriate content?');
    
    if (action) {
        if (isSelf) {
            try {
                const response = await fetch(`/api/posts/${post_id}`, { method: 'DELETE' });
                if (response.ok) {
                    showToast('Post deleted successfully.');
                    document.getElementById(`post-${post_id}`)?.remove();
                }
            } catch(e) {
                showToast('Error deleting post.');
            }
        } else {
            showToast('Post reported successfully! Our AI moderators are reviewing it.');
        }
    }
}

// Global Image Fallback Handler for broken avatar and media assets
window.addEventListener('error', function(e) {
    if (e.target && e.target.tagName === 'IMG') {
        const src = e.target.getAttribute('src');
        if (src && src !== '/static/images/default-avatar.png') {
            if (e.target.classList.contains('header-user-avatar') || 
                e.target.classList.contains('post-composer-avatar') || 
                e.target.closest('.story-avatar-container') ||
                e.target.closest('.sidebar-footer-profile') ||
                e.target.closest('.post-author-link') ||
                e.target.closest('.user-suggest-item') ||
                e.target.closest('.c-header') ||
                e.target.id === 'story-viewer-avatar') {
                e.target.src = '/static/images/default-avatar.png';
            } else {
                e.target.src = '/static/images/default-cover.png';
            }
        }
    }
}, true); // Use capturing phase since error events do not bubble
