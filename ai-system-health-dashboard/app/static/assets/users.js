// Users Management JavaScript
(() => {
  'use strict';

  // Elements
  const els = {
    conn: $('usersConn'),
    user: $('usersUser'),
    err: $('usersErr'),
    usersTableBody: $('usersTableBody'),
    addUserBtn: $('addUserBtn'),
    refreshUsersBtn: $('refreshUsersBtn'),
    userModal: $('userModal'),
    userForm: $('userForm'),
    userModalTitle: $('userModalTitle'),
    userModalClose: $('userModalClose'),
    userModalCancel: $('userModalCancel'),
    userId: $('userId'),
    username: $('username'),
    email: $('email'),
    password: $('password'),
    role: $('role'),
    isActive: $('isActive'),
    userGroups: $('userGroups')
  };

  // State
  let currentUser = null;
  let users = [];
  let userGroups = [];

  // Helper functions
  function $(id) {
    return document.getElementById(id);
  }

  function setText(el, text) {
    if (el) el.textContent = text;
  }

  function showErr(message) {
    if (els.err) {
      els.err.textContent = message;
      els.err.style.display = 'block';
      setTimeout(() => {
        els.err.style.display = 'none';
      }, 5000);
    }
  }

  function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success';
    successDiv.textContent = message;
    els.err.parentNode.insertBefore(successDiv, els.err);
    setTimeout(() => {
      successDiv.remove();
    }, 3000);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  // User Management Functions
  async function loadUsers() {
    try {
      els.usersTableBody.innerHTML = '<tr><td colspan="6" class="textCenter muted">Loading users...</td></tr>';
      users = await fetchJson('/api/admin/users');
      renderUsers();
    } catch (error) {
      console.error('Failed to load users:', error);
      els.usersTableBody.innerHTML = '<tr><td colspan="6" class="textCenter error">Failed to load users</td></tr>';
      showErr('Failed to load users: ' + error.message);
    }
  }

  async function loadUserGroups() {
    try {
      userGroups = await fetchJson('/api/admin/user-groups');
      populateUserGroupsSelect();
    } catch (error) {
      console.error('Failed to load user groups:', error);
    }
  }

  function populateUserGroupsSelect() {
    if (!els.userGroups) return;
    
    els.userGroups.innerHTML = '';
    userGroups.forEach(group => {
      const option = document.createElement('option');
      option.value = group.id;
      option.textContent = group.name;
      els.userGroups.appendChild(option);
    });
  }

  function renderUsers() {
    if (!els.usersTableBody) return;

    if (users.length === 0) {
      els.usersTableBody.innerHTML = '<tr><td colspan="6" class="textCenter muted">No users found</td></tr>';
      return;
    }

    els.usersTableBody.innerHTML = users.map(user => `
      <tr>
        <td>${escapeHtml(user.username)}</td>
        <td><span class="roleBadge ${user.role}">${user.role}</span></td>
        <td><span class="statusBadge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>${user.created_at ? new Date(user.created_at * 1000).toLocaleDateString() : '—'}</td>
        <td>${user.last_login ? new Date(user.last_login * 1000).toLocaleString() : 'Never'}</td>
        <td>
          <div class="actionButtons">
            <button class="actionBtn edit" onclick="editUser(${user.id})" title="Edit">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="actionBtn toggle" onclick="toggleUserStatus(${user.id}, ${!user.is_active})" title="${user.is_active ? 'Deactivate' : 'Activate'}">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
            </button>
            ${user.id !== currentUser?.id ? `
              <button class="actionBtn delete" onclick="deleteUser(${user.id})" title="Delete">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="m19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"/></svg>
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  async function loadCurrentUser() {
    try {
      currentUser = await fetchJson('/api/me');
      const usernameEl = document.getElementById('usersUsername');
      if (usernameEl) {
        setText(usernameEl, currentUser && currentUser.username ? currentUser.username : '—');
      } else {
        setText(els.user, currentUser && currentUser.username ? currentUser.username : '—');
      }
    } catch (error) {
      console.error('Failed to load current user:', error);
      currentUser = null;
      setText(els.user, '—');
    }
  }

  // Modal Functions
  function openUserModal(user = null) {
    if (user) {
      // Edit mode
      els.userModalTitle.textContent = 'Edit User';
      els.userId.value = user.id;
      els.username.value = user.username;
      els.email.value = user.email || '';
      els.password.value = '';
      els.password.placeholder = 'Leave blank to keep current password';
      els.role.value = user.role;
      els.isActive.checked = user.is_active;
      
      // Set selected user groups
      Array.from(els.userGroups.options).forEach(option => {
        option.selected = user.user_groups && user.user_groups.includes(parseInt(option.value));
      });
    } else {
      // Add mode
      els.userModalTitle.textContent = 'Add User';
      els.userForm.reset();
      els.userId.value = '';
      els.password.placeholder = '';
    }
    
    els.userModal.style.display = 'flex';
  }

  function closeUserModal() {
    els.userModal.style.display = 'none';
    els.userForm.reset();
  }

  async function saveUser(event) {
    event.preventDefault();
    
    const formData = new FormData(els.userForm);
    const userData = {
      username: formData.get('username'),
      email: formData.get('email'),
      role: formData.get('role'),
      is_active: formData.get('isActive') === 'on',
      user_groups: Array.from(els.userGroups.selectedOptions).map(option => parseInt(option.value))
    };
    
    if (formData.get('password')) {
      userData.password = formData.get('password');
    }
    
    const userId = formData.get('id');
    
    try {
      if (userId) {
        // Update existing user
        await fetchJson(`/api/admin/users/${userId}`, {
          method: 'PUT',
          body: JSON.stringify(userData)
        });
        showSuccess('User updated successfully');
      } else {
        // Create new user
        await fetchJson('/api/admin/users', {
          method: 'POST',
          body: JSON.stringify(userData)
        });
        showSuccess('User created successfully');
      }
      
      closeUserModal();
      loadUsers();
    } catch (error) {
      console.error('Failed to save user:', error);
      showErr('Failed to save user: ' + error.message);
    }
  }

  async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      return;
    }
    
    try {
      await fetchJson(`/api/admin/users/${userId}`, {
        method: 'DELETE'
      });
      showSuccess('User deleted successfully');
      loadUsers();
    } catch (error) {
      console.error('Failed to delete user:', error);
      showErr('Failed to delete user: ' + error.message);
    }
  }

  async function toggleUserStatus(userId, isActive) {
    try {
      await fetchJson(`/api/admin/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: isActive })
      });
      showSuccess(`User ${isActive ? 'activated' : 'deactivated'} successfully`);
      loadUsers();
    } catch (error) {
      console.error('Failed to toggle user status:', error);
      showErr('Failed to update user status: ' + error.message);
    }
  }

  // Global functions for onclick handlers
  window.editUser = openUserModal;
  window.deleteUser = deleteUser;
  window.toggleUserStatus = toggleUserStatus;

  // Event Listeners
  function setupEventListeners() {
    if (els.addUserBtn) {
      els.addUserBtn.addEventListener('click', () => openUserModal());
    }
    
    if (els.refreshUsersBtn) {
      els.refreshUsersBtn.addEventListener('click', loadUsers);
    }
    
    if (els.userModalClose) {
      els.userModalClose.addEventListener('click', closeUserModal);
    }
    
    if (els.userModalCancel) {
      els.userModalCancel.addEventListener('click', closeUserModal);
    }
    
    if (els.userForm) {
      els.userForm.addEventListener('submit', saveUser);
    }
    
    // Close modal when clicking outside
    if (els.userModal) {
      els.userModal.addEventListener('click', (e) => {
        if (e.target === els.userModal) {
          closeUserModal();
        }
      });
    }
  }

  // Setup sidebar search (reuse from other pages)
  function setupSidebarSearch() {
    const searchInput = document.getElementById('sideSearch');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      const items = document.querySelectorAll('.sideItem');
      
      items.forEach(item => {
        const label = item.getAttribute('data-label') || '';
        if (label.toLowerCase().includes(query)) {
          item.style.display = '';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }

  // Initialize
  async function init() {
    els.conn.textContent = 'loading…';
    setupSidebarSearch();
    setupEventListeners();

    try {
      await Promise.all([
        loadCurrentUser(),
        loadUsers(),
        loadUserGroups()
      ]);
      els.conn.textContent = 'ready';
    } catch (error) {
      console.error('Failed to initialize users page:', error);
      els.conn.textContent = 'error';
      showErr('Failed to initialize users page');
    }
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
