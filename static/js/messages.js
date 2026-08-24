/* Orvyn JavaScript — Private Messaging & AI Chat Actions Controller */

let activeThreadPartnerId = null;
let messagePollingTimer = null;
let currentMsgAttachmentFile = null;

document.addEventListener('DOMContentLoaded', () => {
    // 1. Load active conversations index
    loadChatThreads();
    
    // Check if URL has active user query parameter
    const params = new URLSearchParams(window.location.search);
    const urlPartnerId = params.get('user');
    if (urlPartnerId) {
        openConversationThread(urlPartnerId);
    }
    
    // 2. Search users to start new chat
    const searchInput = document.getElementById('user-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(searchUsersForChat, 300));
    }
    
    // 3. Send message button click
    const sendBtn = document.getElementById('msg-send-btn');
    const msgInput = document.getElementById('msg-text-input');
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);
    if (msgInput) {
        msgInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }

    // 4. File attachments
    const fileInput = document.getElementById('msg-media-file');
    const attachmentIndicator = document.getElementById('attached-media-indicator');
    const removeAttachmentBtn = document.getElementById('remove-msg-attachment');
    
    if (fileInput && attachmentIndicator) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files[0]) {
                currentMsgAttachmentFile = fileInput.files[0];
                attachmentIndicator.classList.remove('hidden');
            }
        });
    }
    if (removeAttachmentBtn && attachmentIndicator) {
        removeAttachmentBtn.addEventListener('click', () => {
            currentMsgAttachmentFile = null;
            fileInput.value = '';
            attachmentIndicator.classList.add('hidden');
        });
    }
    
    // 5. AI Conversation Actions
    const summarizeBtn = document.getElementById('ai-chat-summarize-btn');
    const tasksBtn = document.getElementById('ai-chat-tasks-btn');
    const drawerClose = document.getElementById('close-chat-ai-drawer');
    const drawerPanel = document.getElementById('chat-ai-insight-panel');
    
    if (summarizeBtn) summarizeBtn.addEventListener('click', () => triggerChatAiAction('summary'));
    if (tasksBtn) tasksBtn.addEventListener('click', () => triggerChatAiAction('tasks'));
    if (drawerClose && drawerPanel) {
        drawerClose.addEventListener('click', () => drawerPanel.classList.add('hidden'));
    }
});

// Load threads lists
async function loadChatThreads() {
    const listContainer = document.getElementById('inbox-threads-list');
    if (!listContainer) return;
    
    try {
        const response = await fetch('/api/messages');
        const result = await response.json();
        
        if (result.success) {
            listContainer.innerHTML = '';
            const threads = result.threads;
            
            if (threads.length === 0) {
                listContainer.innerHTML = '<div class="no-results" style="padding:20px;">No messages inbox. Search users to start a chat!</div>';
                return;
            }
            
            threads.forEach(t => {
                const item = document.createElement('div');
                item.className = `thread-list-item-card ${t.partner.id === activeThreadPartnerId ? 'active' : ''}`;
                item.id = `thread-${t.partner.id}`;
                
                // Unread details
                const unreadLabel = t.unread_count > 0 ? `<span class="u-badge" style="background-color:var(--bright-pink); color:white; font-size:10px; font-weight:700; width:18px; height:18px; border-radius:50%; display:flex; align-items:center; justify-content:center;">${t.unread_count}</span>` : '';
                
                item.innerHTML = `
                    <div style="display:flex; align-items:center; gap:12px; width:100%;">
                        <img src="${t.partner.profile_image}" alt="${t.partner.name}" style="width:40px; height:40px; border-radius:50%; object-fit:cover;">
                        <div class="meta" style="flex:1; min-width:0;">
                            <div class="row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                <span class="name" style="font-weight:700; font-size:14px; color:var(--text-primary);">${t.partner.name}</span>
                                <span class="time" style="font-size:10px; color:var(--text-secondary);">${formatTime(t.last_message.created_at)}</span>
                            </div>
                            <p class="last-msg" style="font-size:12px; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                                ${t.last_message.sender_id === CURRENT_USER.id ? 'You: ' : ''}${t.last_message.content || 'Image attachment'}
                            </p>
                        </div>
                        ${unreadLabel}
                    </div>
                `;
                
                item.addEventListener('click', () => {
                    // Update selection CSS
                    document.querySelectorAll('.thread-list-item-card').forEach(c => c.classList.remove('active'));
                    item.classList.add('active');
                    openConversationThread(t.partner.id);
                });
                
                listContainer.appendChild(item);
            });
        }
    } catch(e) {
        console.error(e);
    }
}

// Open active thread chat workspace
async function openConversationThread(partner_id) {
    activeThreadPartnerId = partner_id;
    
    // DOM switches
    document.getElementById('no-chat-open-placeholder').classList.add('hidden');
    document.getElementById('active-chat-container').classList.remove('hidden');
    document.getElementById('chat-workspace-panel').classList.add('active'); // mobile view trigger
    document.getElementById('chat-ai-insight-panel').classList.add('hidden'); // Close AI drawer
    
    const messagesArea = document.getElementById('chat-messages-scroll-area');
    messagesArea.innerHTML = '<div class="loading-state"><p>Opening conversation...</p></div>';
    
    try {
        const response = await fetch(`/api/messages/${partner_id}`);
        const result = await response.json();
        
        if (result.success) {
            // Set header partner name and details
            document.getElementById('chat-partner-name').textContent = result.partner.name;
            document.getElementById('chat-partner-avatar').src = result.partner.profile_image;
            document.getElementById('chat-header-profile-link').onclick = () => {
                window.location.href = `/profile/${result.partner.username}`;
            };
            
            renderMessageStream(result.messages);
            
            // AI suggested replies module: trigger suggestions from last message
            if (result.messages.length > 0) {
                const lastMsg = result.messages[result.messages.length - 1];
                if (lastMsg.sender_id !== CURRENT_USER.id) {
                    suggestChatReplies(lastMsg.content);
                } else {
                    document.getElementById('chat-ai-replies-wrapper').classList.add('hidden');
                }
            } else {
                document.getElementById('chat-ai-replies-wrapper').classList.add('hidden');
            }
            
            // Launch live poller interval
            launchMessagePoller();
        }
    } catch(e) {
        messagesArea.innerHTML = '<p class="error-msg">Failed opening messages thread.</p>';
    }
}

function renderMessageStream(list) {
    const area = document.getElementById('chat-messages-scroll-area');
    area.innerHTML = '';
    
    if (list.length === 0) {
        area.innerHTML = '<div class="no-posts" style="padding:40px; text-align:center;">Say Hello! Start the conversation. 👋</div>';
        return;
    }
    
    list.forEach(m => {
        const bubble = document.createElement('div');
        const isSelf = m.sender_id === CURRENT_USER.id;
        bubble.className = `chat-bubble-row ${isSelf ? 'self' : 'partner'}`;
        
        // Attachment HTML
        let mediaHtml = '';
        if (m.media) {
            mediaHtml = `<div class="msg-media-box" style="border-radius:10px; overflow:hidden; max-width:200px; margin-bottom:6px;"><img src="${m.media}" alt="Attached media" style="width:100%; display:block;"></div>`;
        }
        
        // Double click bubble to translate
        bubble.innerHTML = `
            <div class="msg-bubble-card" style="max-width:70%; padding:10px 14px; border-radius:18px; font-size:13px; margin-bottom:4px; cursor:pointer;" title="Double click to translate text" ondblclick="translateMessageBubble(this)">
                ${mediaHtml}
                <p class="msg-text">${m.content}</p>
                <span class="msg-time" style="font-size:9px; opacity:0.6; display:block; text-align:right; margin-top:4px;">${formatTime(m.created_at)}</span>
            </div>
        `;
        
        // Alignment
        bubble.style.display = 'flex';
        bubble.style.justifyContent = isSelf ? 'flex-end' : 'flex-start';
        bubble.style.marginBottom = '12px';
        
        const card = bubble.querySelector('.msg-bubble-card');
        if (isSelf) {
            card.style.background = 'var(--gradient-primary)';
            card.style.color = 'white';
            card.style.borderTopRightRadius = '4px';
        } else {
            card.style.backgroundColor = 'var(--bg-secondary)';
            card.style.color = 'var(--text-primary)';
            card.style.borderTopLeftRadius = '4px';
        }
        
        area.appendChild(bubble);
    });
    
    // Auto Scroll to bottom
    area.scrollTop = area.scrollHeight;
}

// Polling live messages
function launchMessagePoller() {
    clearTimeout(messagePollingTimer);
    messagePollingTimer = setTimeout(async function poll() {
        if (activeThreadPartnerId) {
            try {
                const response = await fetch(`/api/messages/${activeThreadPartnerId}`);
                const result = await response.json();
                if (result.success) {
                    // Update counts check
                    const messagesArea = document.getElementById('chat-messages-scroll-area');
                    const existingCount = messagesArea.querySelectorAll('.chat-bubble-row').length;
                    
                    if (result.messages.length !== existingCount) {
                        renderMessageStream(result.messages);
                        
                        // Suggest replies if partner sent new message
                        const lastMsg = result.messages[result.messages.length - 1];
                        if (lastMsg && lastMsg.sender_id !== CURRENT_USER.id) {
                            suggestChatReplies(lastMsg.content);
                        }
                    }
                }
            } catch(e) {}
            messagePollingTimer = setTimeout(poll, 5000); // Poll every 5s
        }
    }, 5000);
}

// Send Message
async function sendChatMessage() {
    const textInput = document.getElementById('msg-text-input');
    const translateDropdown = document.getElementById('msg-translate-language');
    const sendBtn = document.getElementById('msg-send-btn');
    
    let text = textInput.value.trim();
    if (!text && !currentMsgAttachmentFile) return;
    
    sendBtn.disabled = true;
    
    // Check outgoing translation
    const targetLang = translateDropdown.value;
    if (targetLang && text) {
        showToast('Translating outgoing message...');
        try {
            const transResponse = await fetch('/api/ai/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, target_lang: targetLang })
            });
            const transResult = await transResponse.json();
            if (transResponse.ok && transResult.success) {
                text = transResult.result;
            }
        } catch(e) {
            console.error('Translation pipeline error:', e);
        }
    }
    
    const formData = new FormData();
    formData.append('receiver_id', activeThreadPartnerId);
    formData.append('content', text);
    if (currentMsgAttachmentFile) {
        formData.append('media', currentMsgAttachmentFile);
    }
    
    try {
        const response = await fetch('/api/messages', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            textInput.value = '';
            currentMsgAttachmentFile = null;
            document.getElementById('attached-media-indicator').classList.add('hidden');
            document.getElementById('msg-media-file').value = '';
            
            // Reload stream
            openConversationThread(activeThreadPartnerId);
            loadChatThreads(); // Refresh thread list on left
        } else {
            showToast(result.error);
        }
    } catch(e) {
        showToast('Error sending message.');
    } finally {
        sendBtn.disabled = false;
    }
}

// Inline reply suggestions
async function suggestChatReplies(commentText) {
    const wrapper = document.getElementById('chat-ai-replies-wrapper');
    const container = document.getElementById('chat-ai-reply-chips-container');
    if (!wrapper || !container) return;
    
    try {
        const response = await fetch('/api/ai/reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment: commentText })
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            wrapper.classList.remove('hidden');
            container.innerHTML = '';
            
            const replies = [result.result, "Sounds good!", "Let's do it! 🚀"];
            replies.forEach(reply => {
                const chip = document.createElement('div');
                chip.className = 'ai-reply-chip';
                chip.style.backgroundColor = 'rgba(245, 40, 135, 0.08)';
                chip.style.border = '1px solid rgba(245, 40, 135, 0.2)';
                chip.style.color = 'var(--bright-pink)';
                chip.style.padding = '6px 12px';
                chip.style.borderRadius = '20px';
                chip.style.fontSize = '11px';
                chip.style.fontWeight = '700';
                chip.style.cursor = 'pointer';
                chip.style.whiteSpace = 'nowrap';
                chip.textContent = reply;
                
                chip.addEventListener('click', () => {
                    document.getElementById('msg-text-input').value = reply;
                    document.getElementById('msg-text-input').focus();
                });
                
                container.appendChild(chip);
            });
        }
    } catch(e) {}
}

// Double click bubble to translate
window.translateMessageBubble = async (bubble) => {
    const textLabel = bubble.querySelector('.msg-text');
    const originalText = textLabel.textContent;
    
    showToast('Translating message...');
    
    try {
        const response = await fetch('/api/ai/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: originalText, target_lang: 'english' })
        });
        const result = await response.json();
        if (response.ok && result.success) {
            textLabel.innerHTML = `${result.result} <br><span style="font-size:9px; opacity:0.7; font-weight:700;">(Translated to English)</span>`;
        }
    } catch(e) {
        showToast('Translation error.');
    }
};

// AI Insights: Chat Summary and Tasks Extraction
async function triggerChatAiAction(type) {
    const drawer = document.getElementById('chat-ai-insight-panel');
    const drawerTitle = document.getElementById('chat-ai-drawer-title');
    const drawerContent = document.getElementById('chat-ai-drawer-content');
    
    drawer.classList.remove('hidden');
    drawerTitle.textContent = type === 'summary' ? 'Conversation Summary' : 'Action Items Extracted';
    drawerContent.innerHTML = '<p class="loading"><i data-lucide="loader" class="spin"></i> Querying AI agent insights...</p>';
    lucide.createIcons();
    
    // Compile last 10 messages for context
    const bubbleTexts = Array.from(document.querySelectorAll('.chat-bubble-row .msg-text')).map(el => el.textContent);
    const conversationContext = bubbleTexts.slice(-10).join(' | ');
    
    const query = type === 'summary' 
        ? `Provide a neat 2-sentence summary of this conversation history: ${conversationContext}`
        : `Analyze this chat log and extract commitments, action items, or checklists. Format as standard checklist rows: [ ] task. Log: ${conversationContext}`;
        
    try {
        const response = await fetch('/api/ai/assistant', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const result = await response.json();
        if (response.ok && result.success) {
            let resText = result.result.text;
            
            // Format task lists if checklist
            if (type === 'tasks') {
                resText = resText.replace(/\[\s*\]/g, '<input type="checkbox">')
                                 .replace(/- \[ \]/g, '<p><input type="checkbox">')
                                 .replace(/\[x\]/g, '<input type="checkbox" checked>');
            }
            
            drawerContent.innerHTML = `<div style="font-size:13px; line-height:1.6;">${resText}</div>`;
        } else {
            drawerContent.textContent = result.error || 'Failed generating insights.';
        }
    } catch(e) {
        drawerContent.textContent = 'Connection timeout.';
    }
}

// User Search inside inbox
async function searchUsersForChat() {
    const query = document.getElementById('user-search-input').value.trim();
    const box = document.getElementById('new-chat-search-results');
    
    if (!query) {
        box.classList.add('hidden');
        return;
    }
    
    try {
        const response = await fetch(`/api/users/search?q=${encodeURIComponent(query)}&limit=12`);
        const result = await response.json();
        
        if (result.success) {
            box.classList.remove('hidden');
            box.innerHTML = '';
            const list = result.users || [];
            
            if (list.length === 0) {
                box.innerHTML = '<div style="padding:10px; font-size:12px; color:var(--text-secondary);">No profiles found.</div>';
                return;
            }
            
            list.forEach(u => {
                const row = document.createElement('div');
                row.className = 'search-user-result-row';
                row.style.display = 'flex';
                row.style.alignItems = 'center';
                row.style.gap = '10px';
                row.style.padding = '8px 12px';
                row.style.cursor = 'pointer';
                row.style.borderBottom = '1px solid var(--border-color)';
                
                row.innerHTML = `
                    <img src="${u.profile_image}" style="width:30px; height:30px; border-radius:50%; object-fit:cover;">
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-size:12px; font-weight:700;">${u.name}</span>
                        <span style="font-size:10px; color:var(--text-secondary);">@${u.username}</span>
                    </div>
                `;
                
                row.addEventListener('click', () => {
                    box.classList.add('hidden');
                    document.getElementById('user-search-input').value = '';
                    openConversationThread(u.id);
                });
                
                box.appendChild(row);
            });
        }
    } catch(e) {}
}

// Helpers
function debounce(func, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => func.apply(this, args), delay);
    };
}

function formatTime(isoString) {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch(e) {
        return '';
    }
}
