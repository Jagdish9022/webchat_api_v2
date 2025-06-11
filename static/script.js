// Constants
const API_BASE_URL = 'http://localhost:8000/api';
const TOAST_DURATION = 3000;

// JWT helper functions
const JWT = {
    parseJwt(token) {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));

            return JSON.parse(jsonPayload);
        } catch (e) {
            console.error('Error parsing JWT:', e);
            return null;
        }
    }
};

// State management
const state = {
    currentUser: null,
    currentTaskId: null,
    isCompleted: false,
    isProcessing: false,
    collectionName: null
};

// Toast notification system
const Toast = {
    show(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} animate-fade-in`;
        toast.innerHTML = `
            <span class="toast-icon">${type === 'success' ? '✓' : '✕'}</span>
            <span class="toast-message">${message}</span>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, TOAST_DURATION);
    }
};

// UI Components
const UI = {
    showLoading() {
        const spinner = document.createElement('div');
        spinner.className = 'spinner';
        document.body.appendChild(spinner);
    },
    
    hideLoading() {
        const spinner = document.querySelector('.spinner');
        if (spinner) spinner.remove();
    },
    
    updateProgress(status) {
        const steps = {
            'crawling': 1,
            'processing': 2,
            'generating_embeddings': 3,
            'storing': 4,
            'completed': 5
        };

        const messages = {
            'crawling': 'Crawling website...',
            'processing': 'Processing content...',
            'generating_embeddings': 'Generating embeddings...',
            'storing': 'Storing data...',
            'completed': 'Processing completed successfully!'
        };

        // Update steps
        for (let i = 1; i <= 5; i++) {
            const step = document.getElementById(`step${i}`);
            if (i < steps[status]) {
                step.className = 'step step-completed';
            } else if (i === steps[status]) {
                step.className = 'step step-active';
            } else {
                step.className = 'step step-pending';
            }
        }

        // Update message
        const messageEl = document.getElementById('progressMessage');
        messageEl.textContent = messages[status] || '';
        messageEl.className = 'animate-fade-in';
    },
    
    showChatWidgetCode(collectionName) {
        const chatWidgetCode = document.getElementById('chatWidgetCode');
        const iframeCode = document.getElementById('iframeCode');
        
        // Always use user ID as collection name if available
        const finalCollectionName = state.currentUser?.id || collectionName;
        
        if (!finalCollectionName) {
            console.error('No collection name or user ID available');
            Toast.show('Error: Could not generate chat widget code', 'error');
            return;
        }

        // Format the iframe code with syntax highlighting
        const code = `<span class="tag">&lt;iframe</span>
  <span class="attr">src</span>=<span class="string">"http://localhost:8080?collection_name=${finalCollectionName}"</span>
  <span class="attr">width</span>=<span class="string">"500"</span>
  <span class="attr">height</span>=<span class="string">"800"</span>
  <span class="attr">style</span>=<span class="string">"background: transparent; border: none; position: fixed; bottom: 20px; right: 20px; z-index: 9999;"</span>
  <span class="attr">allowtransparency</span>=<span class="string">"true"</span>
  <span class="attr">title</span>=<span class="string">"My Chatbot"</span>&gt;
<span class="tag">&lt;/iframe&gt;</span>`;
        
        iframeCode.innerHTML = code;
        chatWidgetCode.classList.remove('hidden');
        chatWidgetCode.classList.add('animate-fade-in');
        
        // Hide loading spinner after iframe code is shown
        UI.hideLoading();
    }
};

// Authentication handlers
const Auth = {
    async login(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/login/json`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            if (!response.ok) throw new Error('Login failed');

            const data = await response.json();
            localStorage.setItem('token', data.access_token);
            
            // Parse JWT token to get user info
            const tokenData = JWT.parseJwt(data.access_token);
            if (!tokenData || !tokenData.sub) {
                throw new Error('Invalid token data');
            }
            
            state.currentUser = { 
                email,
                id: tokenData.sub // Store user ID from JWT token
            };
            
            return true;
        } catch (error) {
            Toast.show(error.message, 'error');
            return false;
        }
    },

    async signup(email, username, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, username, password })
            });

            if (!response.ok) throw new Error('Signup failed');

            Toast.show('Signup successful! Please login.');
            return true;
        } catch (error) {
            Toast.show(error.message, 'error');
            return false;
        }
    },

    logout() {
        // Clear user data
        localStorage.removeItem('token');
        state.currentUser = null;
        state.currentTaskId = null;
        state.isCompleted = false;
        state.isProcessing = false;
        state.collectionName = null;

        // Show auth container and hide main content
        document.getElementById('authContainer').classList.remove('hidden');
        document.getElementById('mainContent').classList.add('hidden');

        // Reset forms
        document.getElementById('loginForm').reset();
        document.getElementById('signupForm').reset();
        document.getElementById('scrapingForm').reset();

        // Show success message
        Toast.show('Logged out successfully!');
    }
};

// Processing handlers
const Processing = {
    async handleScraping(event) {
        event.preventDefault();
        const url = document.getElementById('url').value;
        const pdfFile = document.getElementById('pdfFile').files[0];
        
        if (state.isProcessing) return;
        state.isProcessing = true;
        
        // Show loading spinner
        UI.showLoading();
        
        // Disable the submit button and show loading state
        const submitButton = event.target.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <div class="inline-block animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
            Processing...
        `;

        // Show progress steps container
        const progressContainer = document.querySelector('.progress-steps').parentElement;
        progressContainer.classList.remove('hidden');
        
        try {
            if (pdfFile) {
                await this.handlePdfUpload(pdfFile);
            } else if (url) {
                await this.handleUrlScraping(url);
            } else {
                throw new Error('Please provide either a URL or upload a PDF file');
            }
        } catch (error) {
            Toast.show(error.message, 'error');
            // Hide progress container on error
            progressContainer.classList.add('hidden');
            // Hide loading spinner on error
            UI.hideLoading();
        } finally {
            state.isProcessing = false;
            // Reset button state
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        }
    },

    async handlePdfUpload(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/upload-and-process`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to process PDF');
        }

        const data = await response.json();
        
        // Always use user ID as collection name
        if (!state.currentUser?.id) {
            throw new Error('User ID not found');
        }
        
        UI.showChatWidgetCode(state.currentUser.id);
        Toast.show('PDF processed successfully!');
    },

    async handleUrlScraping(url) {
        const token = localStorage.getItem('token');
        if (!token) {
            throw new Error('Please login first');
        }

        const response = await fetch(`${API_BASE_URL}/scrape-and-ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ url })
        });

        if (response.status === 401) {
            localStorage.removeItem('token');
            document.getElementById('authContainer').classList.remove('hidden');
            document.getElementById('mainContent').classList.add('hidden');
            throw new Error('Session expired. Please login again.');
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to start scraping');
        }

        const data = await response.json();
        state.currentTaskId = data.task_id;
        
        // Start listening to process status
        this.startProcessStatusCheck();
    },

    async startProcessStatusCheck() {
        if (!state.currentTaskId) return;

        try {
            const eventSource = new EventSource(`${API_BASE_URL}/process-status/${state.currentTaskId}`);
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.error) {
                    eventSource.close();
                    Toast.show(data.error, 'error');
                    UI.hideLoading(); // Hide loading spinner on error
                    return;
                }

                // Update UI with current state
                if (data.states) {
                    const currentState = data.current_state;
                    const stateData = data.states[currentState];
                    
                    // Update progress message
                    const messageEl = document.getElementById('progressMessage');
                    messageEl.textContent = stateData.message;
                    messageEl.className = 'animate-fade-in';

                    // Update steps
                    const steps = {
                        'crawling': 1,
                        'processing': 2,
                        'generating_embeddings': 3,
                        'storing': 4,
                        'completed': 5
                    };

                    for (let i = 1; i <= 5; i++) {
                        const step = document.getElementById(`step${i}`);
                        if (i < steps[currentState]) {
                            step.className = 'step step-completed';
                        } else if (i === steps[currentState]) {
                            step.className = 'step step-active';
                        } else {
                            step.className = 'step step-pending';
                        }
                    }
                }
                
                // If process is complete, close the connection and show iframe
                if (data.is_complete) {
                    eventSource.close();
                    state.isCompleted = true;
                    
                    // Always use user ID as collection name
                    if (!state.currentUser?.id) {
                        Toast.show('Error: User ID not found', 'error');
                        UI.hideLoading(); // Hide loading spinner on error
                        return;
                    }
                    
                    UI.showChatWidgetCode(state.currentUser.id);
                    Toast.show('Processing completed successfully!');
                }
            };

            eventSource.onerror = () => {
                eventSource.close();
                Toast.show('Error checking process status', 'error');
                UI.hideLoading(); // Hide loading spinner on error
            };
        } catch (error) {
            Toast.show(error.message, 'error');
            UI.hideLoading(); // Hide loading spinner on error
        }
    }
};

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Auth form handlers
    document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        if (await Auth.login(email, password)) {
            document.getElementById('authContainer').classList.add('hidden');
            document.getElementById('mainContent').classList.remove('hidden');
        }
    });

    document.getElementById('signupForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('signupEmail').value;
        const username = document.getElementById('signupUsername').value;
        const password = document.getElementById('signupPassword').value;
        
        if (await Auth.signup(email, username, password)) {
            toggleAuthForms();
        }
    });

    // Logout button handler
    document.getElementById('logoutButton')?.addEventListener('click', () => {
        Auth.logout();
    });

    // Scraping form handler
    document.getElementById('scrapingForm')?.addEventListener('submit', (e) => {
        Processing.handleScraping(e);
    });

    // Copy code button handler
    document.getElementById('copyButton')?.addEventListener('click', () => {
        const code = document.getElementById('iframeCode').textContent;
        navigator.clipboard.writeText(code).then(() => {
            Toast.show('Code copied to clipboard!');
        }).catch(() => {
            Toast.show('Failed to copy code', 'error');
        });
    });

    // Check if user is logged in
    const token = localStorage.getItem('token');
    if (token) {
        // Parse JWT token to get user info
        const tokenData = JWT.parseJwt(token);
        if (tokenData && tokenData.sub) {
            state.currentUser = {
                id: tokenData.sub,
                email: tokenData.email || ''
            };
            document.getElementById('authContainer').classList.add('hidden');
            document.getElementById('mainContent').classList.remove('hidden');
        } else {
            // Invalid token, clear it
            localStorage.removeItem('token');
        }
    }
});

// Utility functions
function toggleAuthForms() {
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');
    loginForm.classList.toggle('hidden');
    signupForm.classList.toggle('hidden');
} 