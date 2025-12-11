// API Base URL
const API_BASE = '';

// State
let currentFilter = 'all';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadStats();
    loadAccounts();
    loadTasks();
    
    // Set up form handlers
    document.getElementById('task-form').addEventListener('submit', handleTaskSubmit);
    document.getElementById('account-form').addEventListener('submit', handleAccountSubmit);
    
    // Set up filter buttons
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active button
            document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Update filter and reload
            currentFilter = e.target.dataset.filter;
            loadTasks(currentFilter === 'all' ? null : currentFilter);
        });
    });
    
    // Auto-refresh every 10 seconds
    setInterval(() => {
        loadStats();
        if (document.getElementById('tasks-tab').classList.contains('active')) {
            loadTasks(currentFilter === 'all' ? null : currentFilter);
        }
    }, 10000);
});

// Tab Management
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            
            // Update buttons
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Update content
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${tabName}-tab`).classList.add('active');
            
            // Load data for tab
            if (tabName === 'accounts') loadAccounts();
            if (tabName === 'tasks') loadTasks(currentFilter === 'all' ? null : currentFilter);
        });
    });
}

// Load Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const data = await response.json();
        
        document.getElementById('total-accounts').textContent = data.total_accounts || 0;
        document.getElementById('active-accounts').textContent = data.active_accounts || 0;
        document.getElementById('completed-tasks').textContent = data.completed_tasks || 0;
        document.getElementById('running-tasks').textContent = data.running_tasks || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Handle Task Submission
async function handleTaskSubmit(e) {
    e.preventDefault();
    
    const taskType = document.getElementById('task-type').value;
    const target = document.getElementById('target').value.trim();
    const maxItems = parseInt(document.getElementById('max-items').value) || 50;
    
    // Validation
    if (!target) {
        showNotification('Please enter a target', 'error');
        return;
    }
    
    if (maxItems < 1 || maxItems > 1000) {
        showNotification('Max items must be between 1 and 1000', 'error');
        return;
    }
    
    // Validate target based on task type
    if (taskType === 'hashtag' && target.startsWith('@')) {
        showNotification('For hashtag scraping, enter hashtag without @ symbol', 'error');
        return;
    }
    
    if ((taskType === 'profile' || taskType === 'posts' || taskType === 'followers' || taskType === 'following') && target.startsWith('#')) {
        showNotification('For profile/posts/followers/following, enter username without # symbol', 'error');
        return;
    }
    
    try {
        showNotification('Creating task...', 'info');
        
        const response = await fetch(`${API_BASE}/api/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                task_type: taskType, 
                target: target,
                max_items: maxItems
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`✅ Task created! Scraping ${maxItems} items from ${target}`, 'success');
            document.getElementById('task-form').reset();
            document.getElementById('max-items').value = 50;
            loadStats();
            
            // Switch to tasks tab after 1 second
            setTimeout(() => {
                document.querySelector('[data-tab="tasks"]').click();
            }, 1000);
        } else {
            showNotification(data.error || 'Failed to create task', 'error');
        }
    } catch (error) {
        showNotification('Error creating task: ' + error.message, 'error');
        console.error('Error creating task:', error);
    }
}

// Handle Account Submission
async function handleAccountSubmit(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        showNotification('Please enter username and password', 'error');
        return;
    }
    
    const cleanUsername = username.replace('@', '');
    
    try {
        showNotification('Adding account...', 'info');
        
        const response = await fetch(`${API_BASE}/api/accounts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                username: cleanUsername, 
                password: password 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('✅ Account added successfully!', 'success');
            document.getElementById('account-form').reset();
            loadAccounts();
            loadStats();
        } else {
            showNotification(data.error || 'Failed to add account', 'error');
        }
    } catch (error) {
        showNotification('Error adding account: ' + error.message, 'error');
        console.error('Error adding account:', error);
    }
}

// Load Accounts
async function loadAccounts() {
    const accountsList = document.getElementById('accounts-list');
    accountsList.innerHTML = '<div class="loading">Loading accounts...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/api/accounts`);
        const accounts = await response.json();
        
        if (accounts.length === 0) {
            accountsList.innerHTML = '<div class="empty-state">📭 No accounts added yet.<br>Add your first Instagram account above to start scraping!</div>';
            return;
        }
        
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Status</th>
                        <th>Tasks Completed</th>
                        <th>Last Used</th>
                        <th>Active</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        accounts.forEach(acc => {
            const lastUsed = acc.last_used 
                ? new Date(acc.last_used).toLocaleString() 
                : 'Never';
            
            html += `
                <tr>
                    <td>#${acc.id}</td>
                    <td><strong>@${acc.username}</strong></td>
                    <td><span class="badge badge-${acc.status}">${acc.status}</span></td>
                    <td>${acc.tasks_completed}</td>
                    <td>${lastUsed}</td>
                    <td>${acc.is_active ? '✅' : '❌'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        accountsList.innerHTML = html;
    } catch (error) {
        accountsList.innerHTML = '<div class="empty-state" style="color: var(--danger-color);">❌ Error loading accounts</div>';
        console.error('Error loading accounts:', error);
    }
}

// Load Tasks
async function loadTasks(status = null) {
    const tasksList = document.getElementById('tasks-list');
    tasksList.innerHTML = '<div class="loading">Loading tasks...</div>';
    
    try {
        const url = status ? `${API_BASE}/api/tasks?status=${status}` : `${API_BASE}/api/tasks`;
        const response = await fetch(url);
        const tasks = await response.json();
        
        if (tasks.length === 0) {
            const filterMsg = status ? ` with status "${status}"` : '';
            tasksList.innerHTML = `<div class="empty-state">📋 No tasks found${filterMsg}.<br>Create your first scraping task to get started!</div>`;
            return;
        }
        
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Target</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        tasks.forEach(task => {
            const createdDate = new Date(task.created_at).toLocaleString();
            const taskTypeIcon = {
                'profile': '👤',
                'posts': '📸',
                'hashtag': '#️⃣',
                'followers': '👥',
                'following': '👤'
            }[task.task_type] || '📊';
            
            html += `
                <tr>
                    <td><strong>#${task.id}</strong></td>
                    <td><span class="badge badge-info">${taskTypeIcon} ${task.task_type}</span></td>
                    <td><strong>${task.target}</strong></td>
                    <td><span class="badge badge-${task.status}">${task.status}</span></td>
                    <td>${createdDate}</td>
                    <td>
                        ${task.status === 'completed' 
                            ? `
                                <button class="action-btn" onclick="viewTaskData(${task.id})" style="background: #667eea;">📊 View</button>
                                <button class="action-btn" onclick="exportCSV(${task.id})" style="background: #48bb78;">📥 CSV</button>
                                <button class="action-btn" onclick="exportJSON(${task.id})" style="background: #764ba2;">💾 JSON</button>
                              ` 
                            : task.status === 'running'
                            ? '<span style="color: var(--info-color)">⏳ Running...</span>'
                            : task.status === 'failed'
                            ? '<span style="color: var(--danger-color)">❌ Failed</span>'
                            : '<span style="color: var(--warning-color)">⏸️ Pending</span>'
                        }
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        tasksList.innerHTML = html;
    } catch (error) {
        tasksList.innerHTML = '<div class="empty-state" style="color: var(--danger-color);">❌ Error loading tasks</div>';
        console.error('Error loading tasks:', error);
    }
}

// Export CSV
function exportCSV(taskId) {
    showNotification('Downloading CSV...', 'info');
    window.location.href = `${API_BASE}/api/tasks/${taskId}/export/csv`;
    setTimeout(() => {
        showNotification('✅ CSV download started', 'success');
    }, 500);
}

// Export JSON
function exportJSON(taskId) {
    showNotification('Downloading JSON...', 'info');
    window.location.href = `${API_BASE}/api/tasks/${taskId}/export/json`;
    setTimeout(() => {
        showNotification('✅ JSON download started', 'success');
    }, 500);
}

// View Task Data
async function viewTaskData(taskId) {
    try {
        showNotification('Loading task data...', 'info');
        
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}/data`);
        const data = await response.json();
        
        if (!data || (Array.isArray(data) && data.length === 0)) {
            showNotification('No data found for this task', 'warning');
            return;
        }
        
        // Create a new window to display data
        const dataWindow = window.open('', '_blank', 'width=1000,height=700');
        
        if (!dataWindow) {
            showNotification('Please allow popups to view task data', 'warning');
            return;
        }
        
        dataWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Task #${taskId} - Scraped Data</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 20px;
                        color: #333;
                    }
                    .container {
                        max-width: 1100px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 15px;
                        padding: 30px;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
                    }
                    h1 {
                        color: #667eea;
                        margin-bottom: 10px;
                    }
                    .info {
                        background: #f0f4ff;
                        padding: 15px;
                        border-radius: 8px;
                        margin-bottom: 20px;
                        border-left: 4px solid #667eea;
                    }
                    pre {
                        background: #1a202c;
                        color: #48bb78;
                        padding: 20px;
                        border-radius: 8px;
                        overflow: auto;
                        max-height: 450px;
                        font-size: 13px;
                        line-height: 1.5;
                    }
                    .btn {
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                        margin-right: 10px;
                        margin-bottom: 10px;
                    }
                    .btn-primary { background: #667eea; }
                    .btn-primary:hover { background: #5568d3; }
                    .btn-success { background: #48bb78; }
                    .btn-success:hover { background: #38a169; }
                    .btn-secondary { background: #764ba2; }
                    .btn-secondary:hover { background: #653d8c; }
                    .actions {
                        margin-bottom: 20px;
                        display: flex;
                        flex-wrap: wrap;
                        gap: 10px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎯 Task #${taskId} - Scraped Data</h1>
                    <div class="info">
                        <strong>Items Count:</strong> ${Array.isArray(data) ? data.length : 1}<br>
                        <strong>Retrieved:</strong> ${new Date().toLocaleString()}
                    </div>
                    <div class="actions">
                        <button class="btn btn-success" onclick="downloadCSV()">📊 Download CSV</button>
                        <button class="btn btn-secondary" onclick="downloadJSON()">💾 Download JSON</button>
                        <button class="btn btn-primary" onclick="copyToClipboard()">📋 Copy to Clipboard</button>
                    </div>
                    <pre id="json-data">${JSON.stringify(data, null, 2)}</pre>
                </div>
                <script>
                    const jsonData = ${JSON.stringify(data)};
                    const taskId = ${taskId};
                    
                    function downloadCSV() {
                        window.location.href = '/api/tasks/' + taskId + '/export/csv';
                    }
                    
                    function downloadJSON() {
                        window.location.href = '/api/tasks/' + taskId + '/export/json';
                    }
                    
                    function copyToClipboard() {
                        const text = document.getElementById('json-data').textContent;
                        navigator.clipboard.writeText(text).then(() => {
                            alert('✅ Copied to clipboard!');
                        }).catch(err => {
                            alert('❌ Failed to copy: ' + err);
                        });
                    }
                </script>
            </body>
            </html>
        `);
        
        dataWindow.document.close();
        showNotification('✅ Task data opened in new window', 'success');
        
    } catch (error) {
        showNotification('Error loading task data: ' + error.message, 'error');
        console.error('Error viewing task data:', error);
    }
}

// Show Notification
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, type === 'info' ? 2000 : 4000);
}

// Utility: Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Utility: Validate Instagram username
function isValidUsername(username) {
    const regex = /^[a-zA-Z0-9._]{1,30}$/;
    return regex.test(username);
}

// Export for debugging
window.debugAPI = {
    loadStats,
    loadAccounts,
    loadTasks,
    exportCSV,
    exportJSON,
    currentFilter: () => currentFilter
};

console.log('🚀 Instagram Scraper Pro initialized');
console.log('💡 Type window.debugAPI in console for debug functions');
