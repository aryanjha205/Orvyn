/* Orvyn JavaScript — User Profile tabs & AI Bio Summary Regenerator Controller */

let activeProfileTab = 'posts';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initial Feed Load for profile
    loadProfileFeed();

    // 2. Tab Navigation
    const tabs = document.querySelectorAll('.profile-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            activeProfileTab = tab.getAttribute('data-tab');
            loadProfileFeed();
        });
    });

    // 3. Follow / Unfollow toggler
    const followBtn = document.getElementById('profile-follow-btn');
    if (followBtn) {
        followBtn.addEventListener('click', toggleProfileFollow);
    }
    
    // 4. Edit Profile Avatar & Cover triggers
    const avatarTrigger = document.getElementById('edit-avatar-trigger');
    const avatarInput = document.getElementById('avatar-file-input');
    const coverTrigger = document.getElementById('edit-cover-trigger');
    const coverInput = document.getElementById('cover-file-input');
    
    if (avatarTrigger && avatarInput) {
        avatarTrigger.addEventListener('click', () => avatarInput.click());
        avatarInput.addEventListener('change', () => uploadProfileMedia(avatarInput.files[0], 'avatar'));
    }
    if (coverTrigger && coverInput) {
        coverTrigger.addEventListener('click', () => coverInput.click());
        coverInput.addEventListener('change', () => uploadProfileMedia(coverInput.files[0], 'cover'));
    }

    // 5. AI Profile Summary Bio Regenerator
    const regenerateSummaryBtn = document.getElementById('regenerate-summary-btn');
    if (regenerateSummaryBtn) {
        regenerateSummaryBtn.addEventListener('click', regenerateAiSummary);
    }
    
    // Share Profile button
    const shareProfileBtn = document.getElementById('share-profile-btn');
    if (shareProfileBtn) {
        shareProfileBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(window.location.href);
            showToast('Profile link copied to clipboard! 📋');
        });
    }
});

// Load Profile Posts matching Tab
async function loadProfileFeed() {
    const container = document.getElementById('profile-feed-container');
    const skeleton = document.getElementById('profile-skeleton');
    
    if (!container) return;
    container.innerHTML = '';
    if (skeleton) container.appendChild(skeleton);
    
    try {
        const response = await fetch(`/api/users/${TARGET_USER_USERNAME}`);
        const result = await response.json();
        
        if (skeleton) skeleton.remove();
        
        if (result.success) {
            let posts = result.posts;
            
            if (activeProfileTab === 'media') {
                // Filter posts that have media attachments
                posts = posts.filter(p => p.media && p.media.length > 0);
            } else if (activeProfileTab === 'saved') {
                posts = result.saved_posts || [];
            } else if (activeProfileTab === 'communities') {
                // Fetch communities for this profile
                loadProfileCommunities(container);
                return;
            }
            
            if (posts.length === 0) {
                container.innerHTML = '<div class="no-posts">No posts found in this section.</div>';
                return;
            }
            
            posts.forEach(post => {
                const card = createPostCardElement(post);
                container.appendChild(card);
            });
            
            lucide.createIcons();
        }
    } catch(err) {
        console.error(err);
        container.innerHTML = '<p class="error-msg">Error querying user profile.</p>';
    }
}

// Fetch joined groups for profile tab
async function loadProfileCommunities(container) {
    container.innerHTML = '<div class="loading-state"><p>Loading communities...</p></div>';
    try {
        const response = await fetch('/api/communities');
        const result = await response.json();
        if (result.success) {
            container.innerHTML = '';
            
            // Filter user's joined communities
            const userComms = result.communities.filter(c => c.is_member);
            if (userComms.length === 0) {
                container.innerHTML = '<div class="no-posts">Not a member of any communities yet. Go to Communities or Discover to join!</div>';
                return;
            }
            
            const grid = document.createElement('div');
            grid.className = 'profile-communities-grid';
            grid.style.display = 'grid';
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(200px, 1fr))';
            grid.style.gap = '16px';
            
            userComms.forEach(c => {
                grid.innerHTML += `
                    <div class="community-explore-card" onclick="window.location.href='/communities'" style="border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding:16px; background-color:white; cursor:pointer;">
                        <img src="${c.image}" alt="${c.name}" style="width:50px; height:50px; border-radius:10px; object-fit:cover; margin-bottom:10px;">
                        <h4>${c.name}</h4>
                        <span style="font-size:12px; color:var(--text-secondary);">${c.members_count} Members</span>
                    </div>
                `;
            });
            container.appendChild(grid);
        }
    } catch(e) {
        container.innerHTML = '<p class="error-msg">Error loading communities list.</p>';
    }
}

// Follow/Unfollow profile trigger
async function toggleProfileFollow() {
    const btn = document.getElementById('profile-follow-btn');
    const targetUserId = btn.getAttribute('data-id');
    const isFollowing = btn.classList.contains('following');
    
    btn.disabled = true;
    const url = `/api/users/${targetUserId}/follow`;
    
    try {
        const response = await fetch(url, {
            method: isFollowing ? 'DELETE' : 'POST'
        });
        const result = await response.json();
        
        if (response.ok && result.success) {
            const countLabel = document.getElementById('followers-count');
            if (countLabel) {
                countLabel.textContent = parseInt(countLabel.textContent) + (isFollowing ? -1 : 1);
            }
            
            if (isFollowing) {
                btn.textContent = 'Follow';
                btn.classList.remove('following');
                showToast('Unfollowed user.');
            } else {
                btn.textContent = 'Following';
                btn.classList.add('following');
                showToast('Following user!');
            }
        }
    } catch(e) {
        showToast('Connection error updating follow network.');
    } finally {
        btn.disabled = false;
    }
}

// Upload Cover or Avatar
async function uploadProfileMedia(file, type) {
    if (!file) return;
    showToast(`Uploading profile ${type}...`);
    const formData = new FormData();
    formData.append(type === 'avatar' ? 'profile_image' : 'cover_image', file);
    try {
        const response = await fetch('/api/auth/profile', { method: 'POST', body: formData });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Unable to update your profile image.');
        }

        if (type === 'avatar') {
            document.querySelectorAll('.profile-main-avatar, .header-user-avatar').forEach(image => {
                image.src = result.user.profile_image;
            });
        } else {
            const cover = document.querySelector('.cover-image-container');
            cover.style.backgroundImage = `url('${result.user.cover_image}')`;
            cover.setAttribute('data-cover', result.user.cover_image);
        }
        showToast(`Profile ${type} updated!`);
    } catch (error) {
        console.error(error);
        showToast(error.message || `Could not update profile ${type}.`);
    }
}

// Regenerate AI Summary Bio
async function regenerateAiSummary() {
    const btn = document.getElementById('regenerate-summary-btn');
    const textLabel = document.getElementById('ai-summary-text');
    const icon = document.getElementById('reg-summary-icon');
    
    btn.disabled = true;
    icon.classList.add('spin');
    textLabel.textContent = 'Orvyn AI analyzing your feed activity and interests...';
    
    try {
        const response = await fetch('/api/ai/profile-summary', { method: 'POST' });
        const result = await response.json();
        
        if (response.ok && result.success) {
            textLabel.textContent = result.summary;
            showToast('AI Profile Summary updated!');
        } else {
            showToast(result.error);
        }
    } catch(e) {
        showToast('Error regeneratig summary.');
    } finally {
        btn.disabled = false;
        icon.classList.remove('spin');
    }
}
