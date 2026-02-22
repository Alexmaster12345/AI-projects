// Users Management JavaScript
(() => {
  'use strict';

  // Helper functions
  function $(id) {
    return document.getElementById(id);
  }

  // Elements
  const els = {
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
    isActive: $('isActive')
  };

  // State
  let currentUser = null;
  let users = [];

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
      console.log('Loading users from API...');
      els.usersTableBody.innerHTML = '<tr><td colspan="7" class="textCenter muted">Loading users...</td></tr>';
      users = await fetchJson('/api/admin/users');
      console.log('Users loaded:', users);
      renderUsers();
    } catch (error) {
      console.error('Failed to load users:', error);
      els.usersTableBody.innerHTML = '<tr><td colspan="10" class="textCenter error">Failed to load users</td></tr>';
      showErr('Failed to load users: ' + error.message);
    }
  }

  function renderUsers() {
    if (!els.usersTableBody) return;

    if (users.length === 0) {
      els.usersTableBody.innerHTML = '<tr><td colspan="10" class="textCenter muted">No users found</td></tr>';
      return;
    }

    els.usersTableBody.innerHTML = users.map(user => `
      <tr>
        <td><strong>${escapeHtml(user.username)}</strong></td>
        <td>${escapeHtml(user.email || '—')}</td>
        <td><span class="roleBadge ${user.role}">${escapeHtml(user.role)}</span></td>
        <td><span class="statusBadge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>${user.created_at ? new Date(user.created_at * 1000).toLocaleDateString() : '—'}</td>
        <td>${user.last_login ? new Date(user.last_login * 1000).toLocaleString() : 'Never'}</td>
        <td style="text-align:center;">
          <button class="actionBtn edit" onclick="editUser(${user.id})" title="Edit">✏️ Edit</button>
        </td>
        <td style="text-align:center;">
          <button class="actionBtn edit" onclick="openResetPasswordModal(${user.id})" title="Reset Password" style="background:rgba(255,152,0,0.15);border-color:rgba(255,152,0,0.4);color:#ffb74d;">🔑 Reset</button>
        </td>
        <td style="text-align:center;">
          <button class="actionBtn delete" onclick="deleteUser(${user.id})" title="Delete">🗑️ Delete</button>
        </td>
        <td style="text-align:center;">
          <button class="actionBtn ${user.is_active ? 'delete' : 'edit'}" onclick="toggleUserStatus(${user.id})" title="${user.is_active ? 'Deactivate' : 'Activate'}">
            ${user.is_active ? 'Deactivate' : 'Activate'}
          </button>
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
      console.log('Loading current user from API...');
      currentUser = await fetchJson('/api/me');
      console.log('Current user loaded:', currentUser);
      const usernameEl = document.getElementById('usersUsername');
      if (usernameEl) {
        setText(usernameEl, currentUser && currentUser.username ? currentUser.username : '—');
      }
    } catch (error) {
      console.error('Failed to load current user:', error);
      const usernameEl = document.getElementById('usersUsername');
      if (usernameEl) {
        setText(usernameEl, '—');
      }
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
      els.role.value = user.role;
      els.isActive.checked = user.is_active;
    } else {
      // Add mode
      els.userModalTitle.textContent = 'Add User';
      els.userForm.reset();
      els.userId.value = '';
      els.isActive.checked = true;
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
      password: formData.get('password'),
      role: formData.get('role'),
      is_active: formData.get('isActive') === 'on'
    };
    
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

  async function toggleUserStatus(userId) {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    
    const newStatus = !user.is_active;
    const action = newStatus ? 'activate' : 'deactivate';
    
    if (!confirm(`Are you sure you want to ${action} this user?`)) {
      return;
    }
    
    try {
      await fetchJson(`/api/admin/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: newStatus })
      });
      showSuccess(`User ${action}d successfully`);
      loadUsers();
    } catch (error) {
      console.error('Failed to toggle user status:', error);
      showErr('Failed to toggle user status: ' + error.message);
    }
  }

  // Reset Password Modal
  function openResetPasswordModal(userId) {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    document.getElementById('resetUserId').value = userId;
    document.getElementById('resetUsername').textContent = user.username;
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';
    document.getElementById('resetErr').style.display = 'none';
    document.getElementById('resetPasswordModal').style.display = 'flex';
  }

  function closeResetPasswordModal() {
    document.getElementById('resetPasswordModal').style.display = 'none';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';
  }

  async function doResetPassword() {
    const userId = document.getElementById('resetUserId').value;
    const newPwd = document.getElementById('newPassword').value.trim();
    const confirmPwd = document.getElementById('confirmPassword').value.trim();
    const errEl = document.getElementById('resetErr');

    errEl.style.display = 'none';
    if (!newPwd) { errEl.textContent = 'Password cannot be empty.'; errEl.style.display = ''; return; }
    if (newPwd !== confirmPwd) { errEl.textContent = 'Passwords do not match.'; errEl.style.display = ''; return; }
    if (newPwd.length < 4) { errEl.textContent = 'Password must be at least 4 characters.'; errEl.style.display = ''; return; }

    try {
      await fetchJson(`/api/admin/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ password: newPwd })
      });
      closeResetPasswordModal();
      showSuccess('Password reset successfully');
    } catch (e) {
      errEl.textContent = 'Failed to reset password: ' + (e.message || e);
      errEl.style.display = '';
    }
  }

  // Global functions for onclick handlers
  window.editUser = (userId) => {
    const user = users.find(u => u.id === userId);
    if (user) openUserModal(user);
  };
  window.openResetPasswordModal = openResetPasswordModal;
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

    const resetClose = document.getElementById('resetModalClose');
    const resetCancel = document.getElementById('resetModalCancel');
    const resetSave = document.getElementById('resetModalSave');
    if (resetClose) resetClose.addEventListener('click', closeResetPasswordModal);
    if (resetCancel) resetCancel.addEventListener('click', closeResetPasswordModal);
    if (resetSave) resetSave.addEventListener('click', doResetPassword);
    const resetModal = document.getElementById('resetPasswordModal');
    if (resetModal) resetModal.addEventListener('click', (e) => { if (e.target === resetModal) closeResetPasswordModal(); });
    
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
    console.log('Users page initializing...');
    setupSidebarSearch();
    setupEventListeners();

    try {
      console.log('Loading current user and users...');
      await Promise.all([
        loadCurrentUser(),
        loadUsers()
      ]);
      console.log('Users page loaded successfully');
    } catch (error) {
      console.error('Failed to initialize users page:', error);
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
