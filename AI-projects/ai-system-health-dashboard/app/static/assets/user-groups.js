// User Groups page JavaScript

class UserGroupsManager {
  constructor() {
    this.groups = [];
    this.users = [];
    this.currentEditingGroup = null;
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadData();
    this.setupWebSocket();
  }

  bindEvents() {
    // Add group button
    const addGroupBtn = document.getElementById('addGroupBtn');
    if (addGroupBtn) {
      addGroupBtn.addEventListener('click', () => this.showAddGroupModal());
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
    const groupForm = document.getElementById('groupForm');
    if (groupForm) {
      groupForm.addEventListener('submit', (e) => this.handleGroupSubmit(e));
    }

    // Search functionality
    const searchInput = document.getElementById('groupSearch');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterGroups(e.target.value));
    }
  }

  async loadData() {
    try {
      const [groupsResponse, usersResponse] = await Promise.all([
        fetch('/api/admin/user-groups'),
        fetch('/api/admin/users')
      ]);

      if (groupsResponse.ok) {
        this.groups = await groupsResponse.json();
      }

      if (usersResponse.ok) {
        this.users = await usersResponse.json();
      }

      this.renderGroups();
    } catch (error) {
      console.error('Failed to load data:', error);
      this.showError('Failed to load data');
    }
  }

  renderGroups() {
    const container = document.getElementById('groupsContainer');
    if (!container) return;

    if (this.groups.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">👥</div>
          <div class="empty-state-title">No groups found</div>
          <div class="empty-state-description">Create your first user group to organize permissions</div>
          <button class="btn primary" onclick="userGroupsManager.showAddGroupModal()">Add Group</button>
        </div>
      `;
      return;
    }

    container.innerHTML = this.groups.map(group => this.createGroupCard(group)).join('');
  }

  createGroupCard(group) {
    const members = this.getGroupMembers(group.id);
    const memberCount = members.length;
    
    return `
      <div class="group-card" data-group-id="${group.id}">
        <div class="group-header">
          <div class="group-info">
            <h3 class="group-name">${group.name}</h3>
            <p class="group-description">${group.description || 'No description'}</p>
          </div>
        </div>
        
        <div class="group-stats">
          <div class="group-stat">
            <span class="group-stat-value">${memberCount}</span>
            <span class="group-stat-label">Members</span>
          </div>
          <div class="group-stat">
            <span class="group-stat-value">${group.allowed_hosts ? JSON.parse(group.allowed_hosts || '[]').length : 0}</span>
            <span class="group-stat-label">Allowed Hosts</span>
          </div>
        </div>
        
        <div class="group-meta">
          <span>Created: ${new Date(group.created_at * 1000).toLocaleDateString()}</span>
        </div>
        
        <div class="group-actions">
          <button class="btn sm" onclick="userGroupsManager.editGroup(${group.id})">Edit</button>
          <button class="btn sm danger" onclick="userGroupsManager.deleteGroup(${group.id})">Delete</button>
        </div>
      </div>
    `;
  }

  getGroupMembers(groupId) {
    // This would need to be implemented based on your API structure
    return this.users.filter(user => {
      // Placeholder logic - you'd need to implement actual membership checking
      return user.groups && user.groups.includes(groupId);
    });
  }

  showAddGroupModal() {
    this.currentEditingGroup = null;
    const modal = document.getElementById('groupModal');
    const form = document.getElementById('groupForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Add User Group';
    if (form) form.reset();
    if (modal) modal.style.display = 'flex';
  }

  editGroup(groupId) {
    const group = this.groups.find(g => g.id === groupId);
    if (!group) return;

    this.currentEditingGroup = group;
    const modal = document.getElementById('groupModal');
    const form = document.getElementById('groupForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Edit User Group';
    if (form) {
      form.name.value = group.name;
      form.description.value = group.description || '';
      form.allowed_hosts.value = group.allowed_hosts ? JSON.parse(group.allowed_hosts).join(', ') : '';
    }
    if (modal) modal.style.display = 'flex';
  }

  async handleGroupSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    
    const groupData = {
      name: formData.get('name'),
      description: formData.get('description') || null,
      allowed_hosts: formData.get('allowed_hosts') 
        ? JSON.stringify(formData.get('allowed_hosts').split(',').map(h => h.trim()).filter(h => h))
        : JSON.stringify([])
    };

    try {
      const url = this.currentEditingGroup 
        ? `/api/admin/user-groups/${this.currentEditingGroup.id}`
        : '/api/admin/user-groups';
      
      const method = this.currentEditingGroup ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(groupData),
      });

      if (response.ok) {
        this.showSuccess(this.currentEditingGroup ? 'Group updated successfully' : 'Group created successfully');
        this.closeModal();
        await this.loadData();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to save group');
      }
    } catch (error) {
      console.error('Failed to save group:', error);
      this.showError('Failed to save group');
    }
  }

  async deleteGroup(groupId) {
    if (!confirm('Are you sure you want to delete this user group?')) return;

    try {
      const response = await fetch(`/api/admin/user-groups/${groupId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.showSuccess('Group deleted successfully');
        await this.loadData();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to delete group');
      }
    } catch (error) {
      console.error('Failed to delete group:', error);
      this.showError('Failed to delete group');
    }
  }

  filterGroups(searchTerm) {
    const filtered = this.groups.filter(group => 
      group.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (group.description && group.description.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const container = document.getElementById('groupsContainer');
    if (!container) return;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">No groups found</div>
          <div class="empty-state-description">Try adjusting your search terms</div>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(group => this.createGroupCard(group)).join('');
  }

  closeModal() {
    const modal = document.getElementById('groupModal');
    if (modal) modal.style.display = 'none';
    this.currentEditingGroup = null;
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
    const container = document.querySelector('.user-groups-container');
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
    const ws = new WebSocket(`ws://${window.location.host}/ws/user-groups`);
    
    ws.onopen = () => {
      console.log('User Groups WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'group_updated') {
        this.loadData();
      }
    };
    
    ws.onclose = () => {
      console.log('User Groups WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(() => this.setupWebSocket(), 5000);
    };
    
    ws.onerror = (error) => {
      console.error('User Groups WebSocket error:', error);
    };
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.userGroupsManager = new UserGroupsManager();
});
