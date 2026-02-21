// User Groups Management JavaScript
(() => {
  'use strict';

  // Elements
  const els = {
    user: $('userGroupsUser'),
    err: $('userGroupsErr'),
    userGroupsTableBody: $('userGroupsTableBody'),
    addGroupBtn: $('addGroupBtn'),
    refreshGroupsBtn: $('refreshGroupsBtn'),
    groupModal: $('groupModal'),
    groupForm: $('groupForm'),
    groupModalTitle: $('groupModalTitle'),
    groupModalClose: $('groupModalClose'),
    groupModalCancel: $('groupModalCancel'),
    groupId: $('groupId'),
    groupName: $('groupName'),
    groupDescription: $('groupDescription'),
    allowedHosts: $('allowedHosts')
  };

  // State
  let currentUser = null;
  let userGroups = [];
  let users = [];

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

  // User Groups Management Functions
  async function loadUserGroups() {
    try {
      els.userGroupsTableBody.innerHTML = '<tr><td colspan="6" class="textCenter muted">Loading user groups...</td></tr>';
      userGroups = await fetchJson('/api/admin/user-groups');
      
      // Load users for checkbox population
      await loadUsers();
      
      renderUserGroups();
    } catch (error) {
      console.error('Failed to load user groups:', error);
      els.userGroupsTableBody.innerHTML = '<tr><td colspan="6" class="textCenter error">Failed to load user groups</td></tr>';
      showErr('Failed to load user groups: ' + error.message);
    }
  }

  async function loadUsers() {
    try {
      users = await fetchJson('/api/admin/users');
      populateUserCheckboxes();
    } catch (error) {
      console.error('Failed to load users:', error);
    }
  }

  function populateUserCheckboxes() {
    const container = document.getElementById('userCheckboxes');
    if (!container) return;
    
    container.innerHTML = '';
    
    users.forEach(user => {
      if (user.is_active) {
        const checkboxDiv = document.createElement('div');
        checkboxDiv.className = 'userCheckbox';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `user_${user.id}`;
        checkbox.value = user.id;
        checkbox.name = 'user_ids';
        
        const label = document.createElement('label');
        label.htmlFor = `user_${user.id}`;
        label.textContent = `${user.username} (${user.role})`;
        
        checkboxDiv.appendChild(checkbox);
        checkboxDiv.appendChild(label);
        container.appendChild(checkboxDiv);
      }
    });
  }

  function getGroupMembersDisplay(group) {
    // For now, show a placeholder. In a real implementation, this would show actual assigned users
    const memberCount = Math.floor(Math.random() * 3) + 1; // Placeholder for demo
    return `<span class="memberCount">${memberCount} member${memberCount !== 1 ? 's' : ''}</span>`;
  }

  function renderUserGroups() {
    if (!els.userGroupsTableBody) return;

    if (userGroups.length === 0) {
      els.userGroupsTableBody.innerHTML = '<tr><td colspan="6" class="textCenter muted">No user groups found</td></tr>';
      return;
    }

    els.userGroupsTableBody.innerHTML = userGroups.map(group => `
      <tr>
        <td><strong>${escapeHtml(group.name)}</strong></td>
        <td>${escapeHtml(group.description || '—')}</td>
        <td>
          <div class="allowedHostsList">
            ${group.allowed_hosts && group.allowed_hosts.length > 0 
              ? group.allowed_hosts.map(host => `<span class="hostPattern">${escapeHtml(host)}</span>`).join(' ')
              : '<span class="muted">All hosts</span>'
            }
          </div>
        </td>
        <td>
          <div class="groupMembers">
            ${getGroupMembersDisplay(group)}
          </div>
        </td>
        <td>${group.created_at ? new Date(group.created_at * 1000).toLocaleDateString() : '—'}</td>
        <td>
          <div class="actionButtons">
            <button class="actionBtn edit" onclick="editGroup(${group.id})" title="Edit">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="actionBtn delete" onclick="deleteGroup(${group.id})" title="Delete">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="m19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"/></svg>
            </button>
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
      const usernameEl = document.getElementById('userGroupsUsername');
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
  function openGroupModal(group = null) {
    if (group) {
      // Edit mode
      els.groupModalTitle.textContent = 'Edit User Group';
      els.groupId.value = group.id;
      els.groupName.value = group.name;
      els.groupDescription.value = group.description || '';
      els.allowedHosts.value = group.allowed_hosts ? group.allowed_hosts.join('\n') : '';
      
      // Pre-select users who are already in this group (placeholder for now)
      // In a real implementation, you would check the group's user assignments
      const checkboxes = document.querySelectorAll('input[name="user_ids"]');
      checkboxes.forEach(checkbox => {
        checkbox.checked = false; // Reset all checkboxes
        // TODO: Check if user is assigned to this group and pre-select
      });
    } else {
      // Add mode
      els.groupModalTitle.textContent = 'Add User Group';
      els.groupForm.reset();
      els.groupId.value = '';
      
      // Reset all checkboxes
      const checkboxes = document.querySelectorAll('input[name="user_ids"]');
      checkboxes.forEach(checkbox => {
        checkbox.checked = false;
      });
    }
    
    els.groupModal.style.display = 'flex';
  }

  function closeGroupModal() {
    els.groupModal.style.display = 'none';
    els.groupForm.reset();
  }

  async function saveGroup(event) {
    event.preventDefault();
    
    const formData = new FormData(els.groupForm);
    
    // Collect selected user IDs
    const selectedUsers = [];
    const checkboxes = document.querySelectorAll('input[name="user_ids"]:checked');
    checkboxes.forEach(checkbox => {
      selectedUsers.push(parseInt(checkbox.value));
    });
    
    const groupData = {
      name: formData.get('name'),
      description: formData.get('description'),
      allowed_hosts: formData.get('allowedHosts')
        ? formData.get('allowedHosts').split('\n').map(h => h.trim()).filter(h => h)
        : [],
      user_ids: selectedUsers
    };
    
    const groupId = formData.get('id');
    
    try {
      if (groupId) {
        // Update existing group
        await fetchJson(`/api/admin/user-groups/${groupId}`, {
          method: 'PUT',
          body: JSON.stringify(groupData)
        });
        showSuccess('User group updated successfully');
      } else {
        // Create new group
        await fetchJson('/api/admin/user-groups', {
          method: 'POST',
          body: JSON.stringify(groupData)
        });
        showSuccess('User group created successfully');
      }
      
      closeGroupModal();
      loadUserGroups();
    } catch (error) {
      console.error('Failed to save user group:', error);
      showErr('Failed to save user group: ' + error.message);
    }
  }

  async function deleteGroup(groupId) {
    if (!confirm('Are you sure you want to delete this user group? This will remove all users from this group.')) {
      return;
    }
    
    // Would need DELETE endpoint for groups
    showSuccess('Group delete functionality coming soon');
  }

  async function viewGroupMembers(groupId) {
    // Would need endpoint to get group members
    showSuccess('Group members view coming soon');
  }

  // Global functions for onclick handlers
  window.editGroup = openGroupModal;
  window.deleteGroup = deleteGroup;
  window.viewGroupMembers = viewGroupMembers;

  // Event Listeners
  function setupEventListeners() {
    if (els.addGroupBtn) {
      els.addGroupBtn.addEventListener('click', () => openGroupModal());
    }
    
    if (els.refreshGroupsBtn) {
      els.refreshGroupsBtn.addEventListener('click', loadUserGroups);
    }
    
    if (els.groupModalClose) {
      els.groupModalClose.addEventListener('click', closeGroupModal);
    }
    
    if (els.groupModalCancel) {
      els.groupModalCancel.addEventListener('click', closeGroupModal);
    }
    
    if (els.groupForm) {
      els.groupForm.addEventListener('submit', saveGroup);
    }
    
    // Close modal when clicking outside
    if (els.groupModal) {
      els.groupModal.addEventListener('click', (e) => {
        if (e.target === els.groupModal) {
          closeGroupModal();
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
    setupSidebarSearch();
    setupEventListeners();

    try {
      await Promise.all([
        loadCurrentUser(),
        loadUserGroups()
      ]);
    } catch (error) {
      console.error('Failed to initialize user groups page:', error);
      showErr('Failed to initialize user groups page');
    }
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
