const API_BASE = 'http://127.0.0.1:5000/api';

// Enhanced logging function
function frontendLog(message, type = "INFO", data = null) {
    const timestamp = new Date().toLocaleTimeString();
    const styles = {
        INFO: 'color: blue; font-weight: bold;',
        SUCCESS: 'color: green; font-weight: bold;',
        ERROR: 'color: red; font-weight: bold;',
        WARNING: 'color: orange; font-weight: bold;',
        API: 'color: purple; font-weight: bold;'
    };
    
    console.log(`%c[${timestamp}] [FRONTEND-${type}] ${message}`, styles[type] || 'color: black;');
    if (data) {
        console.log('Data:', data);
    }
}

// Check authentication status when page loads
document.addEventListener('DOMContentLoaded', function() {
    frontendLog('Page loaded, checking authentication status...', 'INFO');
    checkAuthStatus();
});

// Formatting functions
function formatAnswer(text) {
    if (!text) return '<p>No response received.</p>';
    
    console.log('Raw AI response:', text);
    
    // Simple approach: convert markdown to HTML
    let html = text
        // Convert headers
        .replace(/^## (.*$)/gim, '<h3 class="answer-heading">$1</h3>')
        .replace(/^# (.*$)/gim, '<h2 class="answer-main-heading">$1</h2>')
        // Convert bullet points
        .replace(/^- (.*$)/gim, '<li class="answer-list-item">$1</li>')
        // Convert bold text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Convert line breaks to paragraphs
        .split('\n\n')
        .map(paragraph => {
            if (paragraph.trim().startsWith('<h') || paragraph.trim().startsWith('<li')) {
                return paragraph;
            }
            return paragraph ? `<p>${paragraph}</p>` : '';
        })
        .join('');
    
    // Wrap list items in ul
    if (html.includes('<li class="answer-list-item">')) {
        html = html.replace(/(<li class="answer-list-item">.*?<\/li>)+/gs, '<ul class="answer-list">$&</ul>');
    }
    
    return html;
}

function formatInlineMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function increaseCount() {
    const countInput = document.getElementById('emailCount');
    let currentValue = parseInt(countInput.value) || 10;
    if (currentValue < 100) {
        countInput.value = currentValue + 1;
    }
}

function decreaseCount() {
    const countInput = document.getElementById('emailCount');
    let currentValue = parseInt(countInput.value) || 10;
    if (currentValue > 1) {
        countInput.value = currentValue - 1;
    }
}

// Check authentication status when page loads
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
});

// Add enter key support for textarea
document.getElementById('queryInput').addEventListener('keydown', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendQuery();
    }
});

function openGmailEmail(messageId) {
    if (messageId) {
        const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${messageId}`;
        window.open(gmailUrl, '_blank');
    }
}

async function checkAuthStatus() {
    frontendLog('Checking authentication status...', 'API');
    try {
        const response = await fetch(`${API_BASE}/auth/status`);
        const data = await response.json();
        frontendLog(`Auth status: ${data.authenticated ? 'Authenticated' : 'Not authenticated'}`, 'SUCCESS', data);
        updateAuthUI(data.authenticated, data.email);
    } catch (error) {
        frontendLog('Auth status check failed', 'ERROR', error);
        console.error('Auth status check failed:', error);
        updateAuthUI(false);
    }
}

function updateAuthUI(authenticated, email = '') {
    const authStatus = document.getElementById('authStatus');
    const statusIndicator = document.getElementById('statusIndicator');
    const userEmail = document.getElementById('userEmail');
    const authBtn = document.getElementById('authBtn');
    const authBtnText = document.getElementById('authBtnText');
    
    if (authenticated) {
        statusIndicator.classList.add('authenticated');
        authStatus.textContent = 'Authenticated';
        userEmail.textContent = email || 'Gmail connected';
        authBtnText.textContent = 'Logout';
        authBtn.onclick = logoutGmail; // Change button to logout
        authBtn.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)'; // Red for logout
    } else {
        statusIndicator.classList.remove('authenticated');
        authStatus.textContent = 'Not authenticated';
        userEmail.textContent = '';
        authBtnText.textContent = 'Authenticate';
        authBtn.onclick = authenticateGmail; // Change button to authenticate
        authBtn.style.background = 'linear-gradient(135deg, #3b82f6, #1d4ed8)'; // Blue for login
    }
}

async function authenticateGmail() {
    frontendLog('Starting Gmail authentication...', 'AUTH');
    const authBtn = document.getElementById('authBtn');
    const authBtnText = document.getElementById('authBtnText');
    const authStatus = document.getElementById('authStatus');
    const statusIndicator = document.getElementById('statusIndicator');
    
    // Show loading state
    authBtn.classList.add('loading');
    authBtnText.textContent = 'Authenticating...';
    authStatus.textContent = 'Connecting...';
    
    try {
        const response = await fetch(`${API_BASE}/auth/gmail`);
        const data = await response.json();
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        if (data.status === 'authenticated') {
            frontendLog('Gmail authentication successful', 'SUCCESS', data);
            updateAuthUI(true, data.email);
            showNotification('Successfully authenticated with Gmail!', 'success');
        } else {
            frontendLog('Gmail authentication failed', 'ERROR', data);
            updateAuthUI(false);
            showNotification('Authentication failed. Please try again.', 'error');
        }
    } catch (error) {
        frontendLog('Gmail authentication error', 'ERROR', error);
        console.error('Auth error:', error);
        updateAuthUI(false);
        showNotification('Authentication failed. Make sure server is running.', 'error');
    } finally {
        authBtn.classList.remove('loading');
    }
}

async function logoutGmail() {
    frontendLog('User initiated logout', 'AUTH');
    const authBtn = document.getElementById('authBtn');
    const authBtnText = document.getElementById('authBtnText');
    
    // Show loading state
    authBtn.classList.add('loading');
    authBtnText.textContent = 'Logging out...';
    
    try {
        const response = await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST'
        });
        const data = await response.json();
        
        await new Promise(resolve => setTimeout(resolve, 800));
        
        if (data.status === 'logged_out') {
            updateAuthUI(false);
            showNotification('Successfully logged out. Gmail access revoked.', 'success');
            
            // Clear any displayed results
            document.getElementById('answerContainer').classList.remove('show');
            document.getElementById('sourcesContainer').classList.remove('show');
        } else {
            showNotification('Logout failed. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Logout error:', error);
        showNotification('Logout failed. Please try again.', 'error');
    } finally {
        authBtn.classList.remove('loading');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        animation: slideInRight 0.3s ease;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Add notification animations to CSS
const notificationStyle = document.createElement('style');
notificationStyle.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(notificationStyle);

async function sendQuery() {
    const query = document.getElementById('queryInput').value.trim();
    const emailCount = parseInt(document.getElementById('emailCount').value) || 10;

    frontendLog(`Sending query: "${query}" (analyzing ${emailCount} emails)`, 'API');
    
    const searchBtn = document.getElementById('searchBtn');
    const searchBtnText = document.getElementById('searchBtnText');
    const answerContainer = document.getElementById('answerContainer');
    const sourcesContainer = document.getElementById('sourcesContainer');
    const answer = document.getElementById('answer');
    const sources = document.getElementById('sources');
    
    if (!query) {
        frontendLog('Query rejected - empty input', 'WARNING');
        document.getElementById('queryInput').style.animation = 'shake 0.3s ease-in-out';
        setTimeout(() => {
            document.getElementById('queryInput').style.animation = '';
        }, 300);
        return;
    }

    searchBtn.classList.add('loading');
    searchBtnText.textContent = `Searching ${emailCount} emails...`;
    
    answerContainer.classList.remove('show');
    sourcesContainer.classList.remove('show');

    try {
        frontendLog('Sending request to backend API...', 'API');
        const startTime = Date.now();
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: query,
                max_results: emailCount  // Send the count to backend
            })
        });

        const requestTime = Date.now() - startTime;
        frontendLog(`Backend response received in ${requestTime}ms`, 'API');

        const data = await response.json();
        frontendLog('Backend response data received', 'API', {
            hasAnswer: !!data.answer,
            sourcesCount: data.sources ? data.sources.length : 0,
            error: data.error,
            requiresAuth: data.requires_auth
        });
        
        // Update loading text to show progress
        searchBtnText.textContent = 'Analyzing with AI...';
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Handle authentication errors
        if (data.requires_auth) {
            frontendLog('Authentication required for query', 'WARNING');
            answer.innerHTML = `
                <div class="error-message">
                    <h3>🔐 Authentication Required</h3>
                    <p>${data.error}</p>
                    <button class="auth-prompt-btn" onclick="authenticateGmail()" style="margin-top: 10px;">
                        Click here to authenticate with Gmail
                    </button>
                </div>
            `;
            answerContainer.classList.add('show');
            return;
        }

        if (data.error) {
            frontendLog('Backend returned error', 'ERROR', data.error);
            answer.innerHTML = `<div class="error-message">Error: ${data.error}</div>`;
            answerContainer.classList.add('show');
            return;
        }

        // Display answer with formatted text
        frontendLog('Formatting and displaying AI response', 'INFO');
        
        // ✅ ADD THIS SECTION: Show translated query if available
        let answerHtml = formatAnswer(data.answer);
        if (data.search_metadata && data.search_metadata.gmail_query_used) {
            answerHtml = `<div class="search-note" style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 15px; padding: 8px 12px; background: rgba(148, 163, 184, 0.1); border-radius: 6px; border-left: 3px solid #3b82f6;">
                <strong>Search used:</strong> ${data.search_metadata.gmail_query_used}
            </div>` + answerHtml;
        }

        answer.innerHTML = answerHtml;  // ✅ CHANGE THIS LINE
        answerContainer.classList.add('show');

        // Display sources with dates
        if (data.sources && data.sources.length > 0) {
            frontendLog(`Displaying ${data.sources.length} email sources`, 'SUCCESS');
            sources.innerHTML = `<h3>📧 Related Emails (${data.sources.length} found)</h3>` + 
                data.sources.map((source, index) => {
                    const date = source.date ? formatDate(source.date) : 'Date unknown';
                    const sender = source.sender || 'Unknown Sender';
                    const subject = source.subject || 'No Subject';
                    const body = source.body || source.snippet || 'No content available';
                    
                    return `
                        <div class="source-item" onclick="openGmailEmail('${source.message_id || ''}')" style="animation-delay: ${index * 0.1}s">
                            <div class="source-header">
                                <span class="subject">${subject}</span>
                                <span class="date">${date}</span>
                            </div>
                            <div class="sender">From: ${sender}</div>
                            <div class="body">${body}</div>
                            <div class="click-hint">Click to open in Gmail</div>
                        </div>
                    `;
                }).join('');
            
            setTimeout(() => {
                sourcesContainer.classList.add('show');
            }, 200);
        } else {
            frontendLog('No email sources found', 'INFO');
            sources.innerHTML = '';
        }

        const totalTime = Date.now() - startTime;
        searchBtnText.textContent = `Analysis Complete (${data.sources ? data.sources.length : 0} emails, ${totalTime}ms)`;
        frontendLog(`Query completed in ${totalTime}ms`, 'SUCCESS');

        setTimeout(() => {
            searchBtnText.textContent = 'Search Emails';
        }, 2000);

    } catch (error) {
        frontendLog('Query failed with error', 'ERROR', error);
        console.error('Query error:', error);
        answer.innerHTML = `<div class="error-message">Connection Error: ${error.message}</div>`;
        answerContainer.classList.add('show');
        
        searchBtnText.textContent = 'Error';
        setTimeout(() => {
            searchBtnText.textContent = 'Search Emails';
        }, 1500);
    } finally {
        searchBtn.classList.remove('loading');
    }
}

function setQuery(query, count = null) {
    frontendLog(`Setting query: "${query}"${count ? ` with ${count} emails` : ''}`, 'INFO');
    document.getElementById('queryInput').value = query;
    if (count !== null) {
        document.getElementById('emailCount').value = count;
    }
    document.getElementById('queryInput').focus();
    
    const originalText = document.getElementById('searchBtnText').textContent;
    document.getElementById('searchBtnText').textContent = 'Query set!';
    setTimeout(() => {
        document.getElementById('searchBtnText').textContent = originalText;
    }, 1000);
}

function formatDate(dateString) {
    if (!dateString || dateString === 'Unknown Date') return 'Date unknown';
    
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return dateString;
        }
        
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    } catch (error) {
        return dateString;
    }
}

// Add shake keyframe for empty query feedback
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-4px); }
        75% { transform: translateX(4px); }
    }
`;
document.head.appendChild(style);


