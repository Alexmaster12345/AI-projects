// Users page JavaScript

class UsersManager {
  constructor() {
    this.users = [];
    this.currentEditingUser = null;
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadUsers();
    this.setupWebSocket();
  }

  bindEvents() {
    // Add user button
    const addUserBtn = document.getElementById('addUserBtn');
    if (addUserBtn) {
      addUserBtn.addEventListener('click', () => this.showAddUserModal());
    }

    // Modal close buttons
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-close')) {
        this.closeModal();
      }
      if (e.target.classList.contains('modal-overlay')) {
        this.closeModal();
      }
    });

    // Form submissions
    const userForm = document.getElementById('userForm');
    if (userForm) {
      userForm.addEventListener('submit', (e) => this.handleUserSubmit(e));
    }

    // Search functionality
    const searchInput = document.getElementById('userSearch');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterUsers(e.target.value));
    }
  }

  async loadUsers() {
    try {
      const response = await fetch('/api/admin/users');
      if (response.ok) {
        this.users = await response.json();
        this.renderUsers();
      }
    } catch (error) {
      console.error('Failed to load users:', error);
      this.showError('Failed to load users');
    }
  }

  renderUsers() {
    const container = document.getElementById('usersContainer');
    if (!container) return;

    if (this.users.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">👥</div>
          <div class="empty-state-title">No users found</div>
          <div class="empty-state-description">Get started by adding your first user</div>
          <button class="btn primary" onclick="usersManager.showAddUserModal()">Add User</button>
        </div>
      `;
      return;
    }

    container.innerHTML = this.users.map(user => this.createUserCard(user)).join('');
  }

  createUserCard(user) {
    const isActive = user.is_active ? 'active' : 'inactive';
    const roleClass = user.role === 'admin' ? 'admin' : 'viewer';
    
    return `
      <div class="user-card" data-user-id="${user.id}">
        <div class="user-header">
          <div class="user-avatar">${user.username.charAt(0).toUpperCase()}</div>
          <div class="user-info">
            <h3 class="user-name">${user.username}</h3>
            <p class="user-email">${user.email || 'No email'}</p>
          </div>
        </div>
        
        <div class="user-status">
          <span class="status-indicator ${isActive}"></span>
          <span>${isActive ? 'Active' : 'Inactive'}</span>
        </div>
        
        <div class="user-role ${roleClass}">${user.role}</div>
        
        <div class="user-meta">
          <span>ID: ${user.id}</span>
          <span>Created: ${new Date(user.created_at * 1000).toLocaleDateString()}</span>
          ${user.last_login ? `<span>Last login: ${new Date(user.last_login * 1000).toLocaleDateString()}</span>` : ''}
        </div>
        
        <div class="user-actions">
          <button class="btn sm" onclick="usersManager.editUser(${user.id})">Edit</button>
          <button class="btn sm danger" onclick="usersManager.deleteUser(${user.id})">Delete</button>
        </div>
      </div>
    `;
  }

  showAddUserModal() {
    this.currentEditingUser = null;
    const modal = document.getElementById('userModal');
    const form = document.getElementById('userForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Add User';
    if (form) form.reset();
    if (modal) modal.style.display = 'flex';
  }

  editUser(userId) {
    const user = this.users.find(u => u.id === userId);
    if (!user) return;

    this.currentEditingUser = user;
    const modal = document.getElementById('userModal');
    const form = document.getElementById('userForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Edit User';
    if (form) {
      form.username.value = user.username;
      form.email.value = user.email || '';
      form.role.value = user.role;
      form.is_active.checked = user.is_active;
    }
    if (modal) modal.style.display = 'flex';
  }

  async handleUserSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    
    const userData = {
      username: formData.get('username'),
      email: formData.get('email') || null,
      role: formData.get('role'),
      is_active: formData.get('is_active') === 'on'
    };

    // Add password for new users
    if (!this.currentEditingUser) {
      userData.password = formData.get('password');
    }

    try {
      const url = this.currentEditingUser 
        ? `/api/admin/users/${this.currentEditingUser.id}`
        : '/api/admin/users';
      
      const method = this.currentEditingUser ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      if (response.ok) {
        this.showSuccess(this.currentEditingUser ? 'User updated successfully' : 'User created successfully');
        this.closeModal();
        await this.loadUsers();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to save user');
      }
    } catch (error) {
      console.error('Failed to save user:', error);
      this.showError('Failed to save user');
    }
  }

  async deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user?')) return;

    try {
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.showSuccess('User deleted successfully');
        await this.loadUsers();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to delete user');
      }
    } catch (error) {
      console.error('Failed to delete user:', error);
      this.showError('Failed to delete user');
    }
  }

  filterUsers(searchTerm) {
    const filtered = this.users.filter(user => 
      user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (user.email && user.email.toLowerCase().includes(searchTerm.toLowerCase())) ||
      user.role.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const container = document.getElementById('usersContainer');
    if (!container) return;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">No users found</div>
          <div class="empty-state-description">Try adjusting your search terms</div>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(user => this.createUserCard(user)).join('');
  }

  closeModal() {
    const modal = document.getElementById('userModal');
    if (modal) modal.style.display = 'none';
    this.currentEditingUser = null;
  }

  showSuccess(message) {
    this.showAlert(message, 'success');
  }

  showError(message) {
    this.showAlert(message, 'error');
  }

  showAlert(message, type) {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());

    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert ${type}`;
    alert.textContent = message;
    
    // Insert at the top of the container
    const container = document.querySelector('.users-container');
    if (container) {
      container.insertBefore(alert, container.firstChild);
      
      // Auto-remove after 5 seconds
      setTimeout(() => {
        if (alert.parentNode) {
          alert.parentNode.removeChild(alert);
        }
      }, 5000);
    }
  }

  setupWebSocket() {
    // WebSocket for real-time updates
    const ws = new WebSocket(`ws://${window.location.host}/ws/users`);
    
    ws.onopen = () => {
      console.log('Users WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'user_updated') {
        this.loadUsers();
      }
    };
    
    ws.onclose = () => {
      console.log('Users WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(() => this.setupWebSocket(), 5000);
    };
    
    ws.onerror = (error) => {
      console.error('Users WebSocket error:', error);
    };
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.usersManager = new UsersManager();
});
