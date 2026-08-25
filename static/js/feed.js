/* Orvyn JavaScript — Home Feed, Stories & Comment Modal Controller */

let currentFeedTab = 'for_you';
let feedPage = 1;
let loadingFeed = false;
let endOfFeed = false;

// Comments variables
let activeCommentPostId = null;

// Stories state variables
let storyThreads = [];
let activeThreadIndex = 0;
let activeStoryIndex = 0;
let storyTimer = null;
let storyStartTime = 0;
let storyDuration = 6000;
let storyTimeRemaining = 6000;
let isStoryPaused = false;

function getViewedStories() {
    try {
        const data = localStorage.getItem('orvyn_viewed_stories');
        return data ? JSON.parse(data) : [];
    } catch (e) {
        return [];
    }
}

function markStoryAsViewed(storyId) {
    try {
        let viewed = getViewedStories();
        if (!viewed.includes(storyId)) {
            viewed.push(storyId);
            localStorage.setItem('orvyn_viewed_stories', JSON.stringify(viewed));
        }
    } catch (e) {
        console.error(e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initial Feeds Load
    loadFeed();
    loadStories();
    
    // 2. Tab Navigation clicks
    const tabs = document.querySelectorAll('.feed-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            currentFeedTab = tab.getAttribute('data-feed');
            feedPage = 1;
            endOfFeed = false;
            
            const feedPosts = document.getElementById('feed-posts-wrapper');
            if (feedPosts) feedPosts.innerHTML = '';
            
            loadFeed();
        });
    });
    
    // 3. Infinite scroll scroll listener
    window.addEventListener('scroll', () => {
        const trigger = document.getElementById('infinite-scroll-trigger');
        if (!trigger) return;
        
        const rect = trigger.getBoundingClientRect();
        if (rect.top <= window.innerHeight + 150 && !loadingFeed && !endOfFeed) {
            feedPage += 1;
            loadFeed();
        }
    });

    // 4. Story upload hooks
    const addStoryBtn = document.getElementById('add-story-btn');
    const storyInput = document.getElementById('story-file-input');
    if (addStoryBtn && storyInput) {
        addStoryBtn.addEventListener('click', () => storyInput.click());
        storyInput.addEventListener('change', uploadStoryFile);
    }
    
    // 5. Comments modal hooks
    const commentClose = document.getElementById('comment-modal-close');
    const commentSubmit = document.getElementById('comment-submit-btn');
    const commentInput = document.getElementById('comment-text-input');
    const aiRepliesBtn = document.getElementById('get-ai-replies-btn');
    
    if (commentClose) commentClose.addEventListener('click', closeCommentModal);
    if (commentSubmit) commentSubmit.addEventListener('click', submitComment);
    if (commentInput) {
        commentInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitComment();
        });
    }
    if (aiRepliesBtn) aiRepliesBtn.addEventListener('click', fetchAiReplySuggestions);
});

// Load Post Feeds from database
async function loadFeed() {
    if (loadingFeed) return;
    loadingFeed = true;
    
    const wrapper = document.getElementById('feed-posts-wrapper');
    const spinner = document.getElementById('scroll-spinner');
    const skeleton = document.getElementById('feed-skeleton');
    
    if (spinner) spinner.classList.remove('hidden');
    
    try {
        const response = await fetch(`/api/feed?type=${currentFeedTab}&page=${feedPage}&limit=6`);
        if (!response.ok) {
            throw new Error(`Feed request failed with HTTP ${response.status}`);
        }
        const result = await response.json();
        
        if (skeleton) skeleton.classList.add('hidden');
        if (spinner) spinner.classList.add('hidden');
        
        if (result.success) {
            const posts = result.posts;
            
            if (posts.length === 0) {
                endOfFeed = true;
                if (feedPage === 1 && wrapper) {
                    wrapper.innerHTML = '<div class="no-posts">No posts found in this feed. Start following users or post a new update!</div>';
                } else if (wrapper) {
                    const finishedLabel = document.createElement('div');
                    finishedLabel.className = 'end-of-feed-tag';
                    finishedLabel.style.textAlign = 'center';
                    finishedLabel.style.padding = '20px';
                    finishedLabel.style.color = 'var(--text-secondary)';
                    finishedLabel.style.fontSize = '12px';
                    finishedLabel.textContent = 'You have caught up with all updates! 🎉';
                    wrapper.appendChild(finishedLabel);
                }
                loadingFeed = false;
                return;
            }
            
            posts.forEach(post => {
                // Ensure duplicate checks
                if (!document.getElementById(`post-${post.id}`)) {
                    const card = createPostCardElement(post);
                    wrapper.appendChild(card);
                }
            });
            
            lucide.createIcons();
        }
    } catch(err) {
        console.error(err);
        if (skeleton) skeleton.classList.add('hidden');
        if (spinner) spinner.classList.add('hidden');
        if (feedPage === 1 && wrapper && wrapper.children.length <= 1) {
            wrapper.innerHTML = '<div class="no-posts">Unable to load the feed right now. Please refresh and try again.</div>';
        }
        showToast('Error connecting to feed network.');
    } finally {
        if (spinner) spinner.classList.add('hidden');
        loadingFeed = false;
    }
}

// Stories Tray Loader
async function loadStories() {
    try {
        const response = await fetch('/api/stories');
        const result = await response.json();
        if (result.success) {
            storyThreads = result.threads;
            renderStoriesTray(storyThreads);
        }
    } catch(e) {
        console.error(e);
    }
}

function renderStoriesTray(threads) {
    const tray = document.getElementById('stories-tray');
    if (!tray) return;
    
    // Clear everything except first Add story card
    const addCard = tray.firstElementChild;
    tray.innerHTML = '';
    tray.appendChild(addCard);
    
    threads.forEach((t, tIndex) => {
        const viewedList = getViewedStories();
        // Check if all stories in the thread are viewed
        const isAllViewed = t.stories.every(story => viewedList.includes(story.id));
        const statusClass = isAllViewed ? 'read' : 'unread';

        const card = document.createElement('div');
        card.className = 'story-card';
        card.innerHTML = `
            <div class="story-avatar-container ${statusClass}">
                <img src="${t.user.profile_image}" alt="${t.user.name}">
            </div>
            <span class="story-user-name">${t.user.name.split(' ')[0]}</span>
        `;
        
        card.addEventListener('click', () => {
            openStoryViewer(tIndex, 0);
        });
        
        tray.appendChild(card);
    });
}

// Upload Story Media
async function uploadStoryFile() {
    const fileInput = document.getElementById('story-file-input');
    const file = fileInput.files[0];
    if (!file) return;
    
    showToast('Uploading story...');
    
    const formData = new FormData();
    formData.append('media', file);
    
    try {
        const response = await fetch('/api/stories', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            showToast('Story shared successfully! Expiring in 24 hours.');
            loadStories();
        } else {
            showToast(result.error);
        }
    } catch(e) {
        showToast('Error uploading story.');
    } finally {
        fileInput.value = '';
    }
}

// Full screen Story player modal
function openStoryViewer(threadIdx, storyIdx) {
    activeThreadIndex = threadIdx;
    activeStoryIndex = storyIdx;
    
    const modal = document.getElementById('story-viewer');
    if (!modal) return;
    
    modal.classList.remove('hidden');
    playActiveStory();
    
    // Bind navigation buttons once
    document.getElementById('story-viewer-close').onclick = closeStoryViewer;
    document.getElementById('story-prev-btn').onclick = navigateStoryPrev;
    document.getElementById('story-next-btn').onclick = navigateStoryNext;

    // Press and hold pause/resume hooks
    const viewerCard = document.querySelector('.story-viewer-card');
    if (viewerCard) {
        viewerCard.onmousedown = (e) => {
            if (e.target.closest('#story-viewer-delete-btn') || e.target.closest('#story-viewer-close') || e.target.closest('.story-nav')) return;
            pauseStory();
        };
        viewerCard.onmouseup = resumeStory;
        viewerCard.onmouseleave = resumeStory;
        
        viewerCard.ontouchstart = (e) => {
            if (e.target.closest('#story-viewer-delete-btn') || e.target.closest('#story-viewer-close') || e.target.closest('.story-nav')) return;
            pauseStory();
        };
        viewerCard.ontouchend = resumeStory;
        viewerCard.ontouchcancel = resumeStory;
    }
}

function playActiveStory() {
    const thread = storyThreads[activeThreadIndex];
    if (!thread) {
        closeStoryViewer();
        return;
    }
    
    const story = thread.stories[activeStoryIndex];
    if (!story) {
        // Move to next thread
        if (activeThreadIndex + 1 < storyThreads.length) {
            openStoryViewer(activeThreadIndex + 1, 0);
        } else {
            closeStoryViewer();
        }
        return;
    }
    
    // Mark as viewed
    markStoryAsViewed(story.id);
    
    // Set user headers
    document.getElementById('story-viewer-name').textContent = thread.user.name;
    document.getElementById('story-viewer-avatar').src = thread.user.profile_image;
    
    // Show/hide Delete button
    const deleteBtn = document.getElementById('story-viewer-delete-btn');
    if (deleteBtn) {
        if (thread.user.id === CURRENT_USER.id) {
            deleteBtn.classList.remove('hidden');
            
            // Delete story click action
            deleteBtn.onclick = async (e) => {
                e.stopPropagation();
                pauseStory();
                if (confirm('Delete this story status permanently?')) {
                    try {
                        const response = await fetch(`/api/stories/${story.id}`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        
                        if (response.ok && result.success) {
                            showToast('Story deleted successfully!');
                            closeStoryViewer();
                            await loadStories();
                        } else {
                            showToast(result.error || 'Failed to delete story.');
                            resumeStory();
                        }
                    } catch(err) {
                        showToast('Connection error during deletion.');
                        resumeStory();
                    }
                } else {
                    resumeStory();
                }
            };
        } else {
            deleteBtn.classList.add('hidden');
        }
    }
    
    // Determine duration
    storyDuration = story.media_type === 'video' ? 10000 : 6000;
    storyTimeRemaining = storyDuration;
    storyStartTime = Date.now();
    isStoryPaused = false;
    
    // Render progress indicators
    renderStoryProgressIndicators();
    
    // Render content
    const mediaBox = document.getElementById('story-viewer-media-box');
    mediaBox.innerHTML = '';
    
    if (story.media_type === 'video') {
        const vid = document.createElement('video');
        vid.src = story.media;
        vid.autoplay = true;
        vid.playsInline = true;
        mediaBox.appendChild(vid);
        
        vid.onloadedmetadata = () => {
            storyDuration = Math.min(vid.duration * 1000, 15000) || 10000;
            storyTimeRemaining = storyDuration;
            storyStartTime = Date.now();
            renderStoryProgressIndicators();
            
            clearTimeout(storyTimer);
            storyTimer = setTimeout(navigateStoryNext, storyTimeRemaining);
        };
        
        vid.onended = navigateStoryNext;
        
        clearTimeout(storyTimer);
        storyTimer = setTimeout(navigateStoryNext, storyTimeRemaining);
    } else {
        const img = document.createElement('img');
        img.src = story.media;
        mediaBox.appendChild(img);
        
        clearTimeout(storyTimer);
        storyTimer = setTimeout(navigateStoryNext, storyTimeRemaining);
    }
    
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function renderStoryProgressIndicators() {
    const thread = storyThreads[activeThreadIndex];
    if (!thread) return;
    
    const progressRow = document.getElementById('story-progress-row');
    progressRow.innerHTML = '';
    
    thread.stories.forEach((_, sIdx) => {
        const segment = document.createElement('div');
        segment.className = 'story-progress-segment';
        const fill = document.createElement('div');
        fill.className = 'story-progress-fill';
        
        if (sIdx < activeStoryIndex) {
            fill.style.width = '100%';
            fill.style.transition = 'none';
        } else if (sIdx === activeStoryIndex) {
            fill.style.width = '0%';
            fill.style.transition = 'none';
            setTimeout(() => {
                if (!isStoryPaused) {
                    fill.style.transition = `width ${storyTimeRemaining}ms linear`;
                    fill.style.width = '100%';
                }
            }, 50);
        } else {
            fill.style.width = '0%';
            fill.style.transition = 'none';
        }
        
        segment.appendChild(fill);
        progressRow.appendChild(segment);
    });
}

function pauseStory() {
    if (isStoryPaused) return;
    isStoryPaused = true;
    
    const elapsed = Date.now() - storyStartTime;
    storyTimeRemaining = Math.max(0, storyTimeRemaining - elapsed);
    clearTimeout(storyTimer);
    
    const mediaBox = document.getElementById('story-viewer-media-box');
    const video = mediaBox.querySelector('video');
    if (video) video.pause();
    
    const activeFill = document.querySelector('.story-progress-segment:nth-child(' + (activeStoryIndex + 1) + ') .story-progress-fill');
    if (activeFill) {
        const currentWidth = activeFill.getBoundingClientRect().width;
        const parentWidth = activeFill.parentElement.getBoundingClientRect().width;
        activeFill.style.width = (currentWidth / parentWidth * 100) + '%';
        activeFill.style.transition = 'none';
    }
}

function resumeStory() {
    if (!isStoryPaused) return;
    isStoryPaused = false;
    storyStartTime = Date.now();
    
    const mediaBox = document.getElementById('story-viewer-media-box');
    const video = mediaBox.querySelector('video');
    if (video) video.play();
    
    const activeFill = document.querySelector('.story-progress-segment:nth-child(' + (activeStoryIndex + 1) + ') .story-progress-fill');
    if (activeFill) {
        activeFill.style.transition = `width ${storyTimeRemaining}ms linear`;
        activeFill.offsetHeight; // Force reflow
        activeFill.style.width = '100%';
    }
    
    clearTimeout(storyTimer);
    storyTimer = setTimeout(navigateStoryNext, storyTimeRemaining);
}

function navigateStoryNext() {
    clearTimeout(storyTimer);
    const thread = storyThreads[activeThreadIndex];
    if (activeStoryIndex + 1 < thread.stories.length) {
        openStoryViewer(activeThreadIndex, activeStoryIndex + 1);
    } else {
        if (activeThreadIndex + 1 < storyThreads.length) {
            openStoryViewer(activeThreadIndex + 1, 0);
        } else {
            closeStoryViewer();
        }
    }
}

function navigateStoryPrev() {
    clearTimeout(storyTimer);
    if (activeStoryIndex > 0) {
        openStoryViewer(activeThreadIndex, activeStoryIndex - 1);
    } else {
        if (activeThreadIndex > 0) {
            const prevThread = storyThreads[activeThreadIndex - 1];
            openStoryViewer(activeThreadIndex - 1, prevThread.stories.length - 1);
        } else {
            openStoryViewer(activeThreadIndex, 0);
        }
    }
}

function closeStoryViewer() {
    clearTimeout(storyTimer);
    const modal = document.getElementById('story-viewer');
    if (modal) modal.classList.add('hidden');
    // Re-render tray to show updated read/unread status borders instantly
    renderStoriesTray(storyThreads);
}

// Comments Box Drawer Actions
async function openCommentModal(post_id) {
    activeCommentPostId = post_id;
    
    const modal = document.getElementById('comment-modal');
    const container = document.getElementById('comments-list-container');
    const postSnippet = document.getElementById('comment-modal-post-snippet');
    const aiRepliesRow = document.getElementById('ai-replies-row');
    
    if (!modal) return;
    
    modal.classList.remove('hidden');
    aiRepliesRow.classList.add('hidden');
    container.innerHTML = '<div class="loading-state"><p>Loading comments...</p></div>';
    
    // Snippet from feed
    const parentPost = document.getElementById(`post-${post_id}`);
    if (parentPost && postSnippet) {
        postSnippet.innerHTML = parentPost.querySelector('.post-content-body').innerHTML;
    }
    
    try {
        const response = await fetch(`/api/posts/${post_id}`);
        const result = await response.json();
        
        if (result.success) {
            container.innerHTML = '';
            const comments = result.comments;
            
            if (comments.length === 0) {
                container.innerHTML = '<div class="no-results">No comments yet. Write one below!</div>';
                return;
            }
            
            comments.forEach(c => {
                container.appendChild(createCommentElement(c));
            });
        }
    } catch(e) {
        container.innerHTML = '<p class="error-msg">Error querying comments.</p>';
    }
}

function createCommentElement(comment) {
    const el = document.createElement('div');
    el.className = 'comment-item-card';
    el.innerHTML = `
        <div class="c-header">
            <img src="${comment.author.profile_image}" alt="${comment.author.name}">
            <div class="c-meta">
                <span class="c-name">${comment.author.name}</span>
                <span class="c-handle">@${comment.author.username}</span>
            </div>
        </div>
        <p class="c-body">${comment.content}</p>
    `;
    return el;
}

async function submitComment() {
    const input = document.getElementById('comment-text-input');
    const text = input.value.trim();
    if (!text || !activeCommentPostId) return;
    
    const submitBtn = document.getElementById('comment-submit-btn');
    submitBtn.disabled = true;
    
    try {
        const response = await fetch(`/api/posts/${activeCommentPostId}/comment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text })
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            input.value = '';
            
            // Reload comments list
            openCommentModal(activeCommentPostId);
            
            // Use the server's authoritative count rather than incrementing a
            // potentially stale value rendered earlier.
            const countBtn = document.querySelector(`#post-${activeCommentPostId} .action-btn-item:nth-child(2) .count`);
            if (countBtn) {
                countBtn.textContent = result.comments_count;
            }
        }
    } catch(e) {
        showToast('Error sharing comment.');
    } finally {
        submitBtn.disabled = false;
    }
}

function closeCommentModal() {
    const modal = document.getElementById('comment-modal');
    if (modal) modal.classList.add('hidden');
    activeCommentPostId = null;
}

// AI Replies module
async function fetchAiReplySuggestions() {
    const container = document.getElementById('ai-reply-chips');
    const row = document.getElementById('ai-replies-row');
    const btn = document.getElementById('get-ai-replies-btn');
    
    // Get last comment text in list
    const lastCommentBody = document.querySelector('#comments-list-container .comment-item-card:last-child .c-body');
    if (!lastCommentBody) {
        showToast('You need at least one comment to suggest replies!');
        return;
    }
    
    const commentText = lastCommentBody.textContent;
    btn.disabled = true;
    btn.textContent = 'Analyzing comment...';
    
    try {
        const response = await fetch('/api/ai/reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment: commentText })
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            row.classList.remove('hidden');
            container.innerHTML = '';
            
            const replies = Array.isArray(result.result) ? result.result : [result.result];
            
            replies.forEach(reply => {
                const chip = document.createElement('div');
                chip.className = 'ai-reply-chip';
                chip.style.backgroundColor = 'rgba(114, 201, 36, 0.08)';
                chip.style.border = '1px solid rgba(114, 201, 36, 0.2)';
                chip.style.color = 'var(--parrot-green)';
                chip.style.padding = '6px 12px';
                chip.style.borderRadius = '20px';
                chip.style.fontSize = '11px';
                chip.style.fontWeight = '700';
                chip.style.cursor = 'pointer';
                chip.style.whiteSpace = 'nowrap';
                chip.textContent = reply;
                
                chip.addEventListener('click', () => {
                    document.getElementById('comment-text-input').value = reply;
                    document.getElementById('comment-text-input').focus();
                });
                
                container.appendChild(chip);
            });
        } else {
            showToast(result.error);
        }
    } catch(e) {
        showToast('Connection error getting suggestions.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="sparkles"></i> <span>Get AI Reply Suggestions</span>';
        lucide.createIcons();
    }
}
