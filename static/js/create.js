/* Orvyn JavaScript — AI-Powered Post Creator & Image Captioning Controller */

let attachedFiles = [];

document.addEventListener('DOMContentLoaded', () => {
    const inlineWriteBtn = document.getElementById('ai-write-inline-btn');
    const aiPanel = document.getElementById('ai-composer-panel');
    const closePanelBtn = document.getElementById('ai-panel-close-btn');
    
    // File inputs
    const imgInput = document.getElementById('post-image-file');
    const vidInput = document.getElementById('post-video-file');
    const previewContainer = document.getElementById('media-preview-container');
    
    const publishBtn = document.getElementById('publish-post-btn');
    const contentTextarea = document.getElementById('post-content-input');
    
    // AI Panel elements
    const aiPromptInput = document.getElementById('ai-prompt-input');
    const aiToneSelect = document.getElementById('ai-tone-select');
    const aiStyleSelect = document.getElementById('ai-style-select');
    const aiWriteSubmit = document.getElementById('ai-generate-submit');
    const aiImproveBtn = document.getElementById('ai-improve-draft-btn');
    const aiHashtagsBtn = document.getElementById('ai-hashtags-btn');
    
    const previewBox = document.getElementById('ai-preview-box');
    const previewText = document.getElementById('ai-preview-text');
    const applyDraftBtn = document.getElementById('ai-apply-draft');
    const regenerateBtn = document.getElementById('ai-regenerate');

    // 1. Toggle AI panel visibility
    if (inlineWriteBtn && aiPanel) {
        inlineWriteBtn.addEventListener('click', () => {
            aiPanel.classList.remove('hidden');
            aiPromptInput.focus();
        });
    }
    if (closePanelBtn && aiPanel) {
        closePanelBtn.addEventListener('click', () => {
            aiPanel.classList.add('hidden');
        });
    }

    // 2. Handle File Attachment selections
    if (imgInput && previewContainer) {
        imgInput.addEventListener('change', () => handleAttachments(imgInput.files, 'image'));
    }
    if (vidInput && previewContainer) {
        vidInput.addEventListener('change', () => handleAttachments(vidInput.files, 'video'));
    }
    
    // AI Create trigger
    const aiCreateTrigger = document.getElementById('post-ai-create-btn');
    if (aiCreateTrigger) {
        aiCreateTrigger.addEventListener('click', () => {
            if (aiPanel) aiPanel.classList.remove('hidden');
        });
    }

    function handleAttachments(files, type) {
        previewContainer.classList.remove('hidden');
        
        for (let file of files) {
            attachedFiles.push({ file, type });
            
            const reader = new FileReader();
            const previewItem = document.createElement('div');
            previewItem.className = 'media-preview-item';
            
            reader.onload = (e) => {
                if (type === 'video') {
                    previewItem.innerHTML = `
                        <video src="${e.target.result}"></video>
                        <button class="remove-preview-btn">✕</button>
                    `;
                } else {
                    previewItem.innerHTML = `
                        <img src="${e.target.result}" alt="Preview">
                        <button class="remove-preview-btn">✕</button>
                    `;
                }
                
                // Remove attachment trigger
                previewItem.querySelector('.remove-preview-btn').onclick = () => {
                    attachedFiles = attachedFiles.filter(item => item.file !== file);
                    previewItem.remove();
                    if (attachedFiles.length === 0) previewContainer.classList.add('hidden');
                };
            };
            
            reader.readAsDataURL(file);
            previewContainer.appendChild(previewItem);
            
            // AI Vision Trigger: If user attached a photo, suggest a caption in background!
            if (type === 'image') {
                triggerImageAIAnalysis(file);
            }
        }
    }

    // Background Image Analysis (Describe Image, Caption, Hashtags, Alt Text)
    async function triggerImageAIAnalysis(file) {
        showToast('Orvyn AI analyzing photo...');
        
        const formData = new FormData();
        formData.append('image', file);
        
        try {
            const response = await fetch('/api/ai/caption', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if (response.ok && result.success) {
                const analysis = result.result;
                
                // Display caption suggestion widget
                const captionBox = document.createElement('div');
                captionBox.className = 'ai-image-caption-suggestion';
                captionBox.style.backgroundColor = 'rgba(114, 201, 36, 0.05)';
                captionBox.style.border = '1px dashed var(--parrot-green)';
                captionBox.style.borderRadius = 'var(--border-radius-sm)';
                captionBox.style.padding = '12px';
                captionBox.style.marginTop = '10px';
                captionBox.style.fontSize = '13px';
                
                captionBox.innerHTML = `
                    <div style="font-weight:700; color:var(--parrot-green); display:flex; align-items:center; gap:6px; margin-bottom:6px;">
                        <i data-lucide="sparkles" style="width:14px; height:14px;"></i>
                        <span>AI Suggestion for attached photo:</span>
                    </div>
                    <p style="font-style:italic; margin-bottom:8px;">"${analysis.caption}"</p>
                    <div style="display:flex; gap:8px;">
                        <button type="button" class="btn-use-caption" style="background-color:var(--parrot-green); color:white; font-size:10px; font-weight:700; border-radius:4px; padding:4px 10px;">Use Caption</button>
                        <button type="button" class="btn-dismiss-caption" style="border:1px solid var(--border-color); color:var(--text-secondary); font-size:10px; font-weight:700; border-radius:4px; padding:4px 10px;">Dismiss</button>
                    </div>
                `;
                
                previewContainer.appendChild(captionBox);
                lucide.createIcons();
                
                captionBox.querySelector('.btn-use-caption').onclick = () => {
                    contentTextarea.value = analysis.caption;
                    captionBox.remove();
                };
                captionBox.querySelector('.btn-dismiss-caption').onclick = () => {
                    captionBox.remove();
                };
                
                showToast('AI analysis completed!');
            }
        } catch(e) {
            console.error('Vision analysis pipeline error:', e);
        }
    }

    // 3. AI write submission
    const handleAiWrite = async () => {
        const prompt = aiPromptInput.value.trim();
        if (!prompt) {
            showToast('Enter a short idea prompt first!');
            return;
        }
        
        aiWriteSubmit.disabled = true;
        aiWriteSubmit.textContent = 'Writing...';
        previewBox.classList.add('hidden');
        
        try {
            const response = await fetch('/api/ai/write', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: prompt,
                    tone: aiToneSelect.value,
                    style: aiStyleSelect.value
                })
            });
            
            const result = await response.json();
            if (response.ok && result.success) {
                previewBox.classList.remove('hidden');
                previewText.textContent = result.result;
            } else {
                showToast(result.error);
            }
        } catch(e) {
            showToast('Error connecting to AI writer.');
        } finally {
            aiWriteSubmit.disabled = false;
            aiWriteSubmit.textContent = 'Write';
        }
    };
    
    if (aiWriteSubmit) aiWriteSubmit.addEventListener('click', handleAiWrite);
    
    // Apply draft suggestion
    if (applyDraftBtn) {
        applyDraftBtn.addEventListener('click', () => {
            contentTextarea.value = previewText.textContent;
            previewBox.classList.add('hidden');
            aiPanel.classList.add('hidden');
            showToast('AI Draft applied!');
        });
    }
    
    // Regenerate draft suggestion
    if (regenerateBtn) regenerateBtn.addEventListener('click', handleAiWrite);

    // Improve Draft
    if (aiImproveBtn) {
        aiImproveBtn.addEventListener('click', async () => {
            const currentText = contentTextarea.value.trim();
            if (!currentText) {
                showToast('Write a draft in the post composer box first!');
                return;
            }
            
            aiImproveBtn.disabled = true;
            aiImproveBtn.innerHTML = '<i data-lucide="loader" class="spin"></i> Refining...';
            lucide.createIcons();
            
            try {
                const response = await fetch('/api/ai/improve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        draft: currentText,
                        tone: aiToneSelect.value
                    })
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    contentTextarea.value = result.result;
                    showToast('Draft refined with AI!');
                }
            } catch(e) {
                showToast('Refining failed.');
            } finally {
                aiImproveBtn.disabled = false;
                aiImproveBtn.innerHTML = '<i data-lucide="scissors"></i> <span>Improve Draft</span>';
                lucide.createIcons();
            }
        });
    }

    // AI Hashtags Generator
    if (aiHashtagsBtn) {
        aiHashtagsBtn.addEventListener('click', async () => {
            const currentText = contentTextarea.value.trim();
            if (!currentText) {
                showToast('Write some content first so AI can suggest hashtags.');
                return;
            }
            
            aiHashtagsBtn.disabled = true;
            aiHashtagsBtn.innerHTML = '<i data-lucide="loader" class="spin"></i> Suggesting...';
            lucide.createIcons();
            
            try {
                const response = await fetch('/api/ai/hashtags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: currentText })
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    // Append hashtags
                    contentTextarea.value = `${currentText}\n\n${result.result.join(' ')}`;
                    showToast('Hashtags added!');
                }
            } catch(e) {
                showToast('Hashtag search failed.');
            } finally {
                aiHashtagsBtn.disabled = false;
                aiHashtagsBtn.innerHTML = '<i data-lucide="hash"></i> <span>Add Hashtags</span>';
                lucide.createIcons();
            }
        });
    }

    // 4. Publish Post Submit Form
    if (publishBtn) {
        publishBtn.addEventListener('click', async () => {
            const content = contentTextarea.value.trim();
            if (!content && attachedFiles.length === 0) {
                showToast('Write a post description or upload a file!');
                return;
            }
            
            publishBtn.disabled = true;
            publishBtn.innerHTML = '<span>Publishing...</span> <i data-lucide="loader-2" class="spin"></i>';
            lucide.createIcons();
            
            const formData = new FormData();
            formData.append('content', content);
            
            // Append files
            attachedFiles.forEach(item => {
                formData.append('media', item.file);
            });
            
            try {
                const response = await fetch('/api/posts', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                
                if (response.ok && result.success) {
                    // Reset composer
                    contentTextarea.value = '';
                    attachedFiles = [];
                    previewContainer.innerHTML = '';
                    previewContainer.classList.add('hidden');
                    if (aiPanel) aiPanel.classList.add('hidden');
                    
                    showToast('Post shared to feed successfully!');
                    
                    // Reload home feed if on index page
                    if (typeof loadFeed === 'function') {
                        feedPage = 1;
                        endOfFeed = false;
                        const wrapper = document.getElementById('feed-posts-wrapper');
                        if (wrapper) wrapper.innerHTML = '';
                        loadFeed();
                    }
                } else {
                    showToast(result.error || 'Failed to publish post.');
                }
            } catch(err) {
                showToast('Network error during publishing.');
            } finally {
                publishBtn.disabled = false;
                publishBtn.innerHTML = '<span>Post</span>';
            }
        });
    }
});
