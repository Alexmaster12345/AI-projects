// Inventory page JavaScript

class InventoryManager {
  constructor() {
    this.items = [];
    this.categories = [];
    this.locations = [];
    this.currentEditingItem = null;
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadData();
    this.setupWebSocket();
  }

  bindEvents() {
    // Add item button
    const addItemBtn = document.getElementById('addItemBtn');
    if (addItemBtn) {
      addItemBtn.addEventListener('click', () => this.showAddItemModal());
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
    const itemForm = document.getElementById('itemForm');
    if (itemForm) {
      itemForm.addEventListener('submit', (e) => this.handleItemSubmit(e));
    }

    // Search and filters
    const searchInput = document.getElementById('inventorySearch');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterItems());
    }

    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
      categoryFilter.addEventListener('change', () => this.filterItems());
    }

    const locationFilter = document.getElementById('locationFilter');
    if (locationFilter) {
      locationFilter.addEventListener('change', () => this.filterItems());
    }
  }

  async loadData() {
    try {
      const response = await fetch('/api/inventory');
      if (response.ok) {
        this.items = await response.json();
        this.extractCategoriesAndLocations();
        this.renderItems();
        this.populateFilters();
      }
    } catch (error) {
      console.error('Failed to load inventory:', error);
      this.showError('Failed to load inventory');
    }
  }

  extractCategoriesAndLocations() {
    this.categories = [...new Set(this.items.map(item => item.category).filter(Boolean))];
    this.locations = [...new Set(this.items.map(item => item.location).filter(Boolean))];
  }

  populateFilters() {
    const categoryFilter = document.getElementById('categoryFilter');
    const locationFilter = document.getElementById('locationFilter');

    if (categoryFilter) {
      categoryFilter.innerHTML = '<option value="">All Categories</option>' +
        this.categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');
    }

    if (locationFilter) {
      locationFilter.innerHTML = '<option value="">All Locations</option>' +
        this.locations.map(loc => `<option value="${loc}">${loc}</option>`).join('');
    }
  }

  renderItems() {
    const container = document.getElementById('inventoryContainer');
    if (!container) return;

    if (this.items.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📦</div>
          <div class="empty-state-title">No items found</div>
          <div class="empty-state-description">Add your first inventory item to get started</div>
          <button class="btn primary" onclick="inventoryManager.showAddItemModal()">Add Item</button>
        </div>
      `;
      return;
    }

    container.innerHTML = this.items.map(item => this.createItemCard(item)).join('');
    this.updateStats();
  }

  createItemCard(item) {
    return `
      <div class="inventory-item" data-item-id="${item.id}">
        <div class="inventory-item-header">
          <div class="inventory-item-info">
            <h3 class="inventory-item-name">${item.name}</h3>
            ${item.category ? `<span class="inventory-item-category">${item.category}</span>` : ''}
            ${item.location ? `<p class="inventory-item-location">📍 ${item.location}</p>` : ''}
          </div>
          <div class="inventory-item-actions">
            <button class="btn icon sm" onclick="inventoryManager.editItem(${item.id})" title="Edit">✏️</button>
            <button class="btn icon sm danger" onclick="inventoryManager.deleteItem(${item.id})" title="Delete">🗑️</button>
          </div>
        </div>
        
        <div class="inventory-item-quantity">
          <span class="inventory-item-quantity-value">${item.quantity}</span>
          <span>units</span>
        </div>
        
        ${item.notes ? `<div class="inventory-item-description">${item.notes}</div>` : ''}
        
        <div class="inventory-item-meta">
          <span>ID: ${item.id}</span>
          <span>Added: ${new Date(item.created_ts * 1000).toLocaleDateString()}</span>
        </div>
      </div>
    `;
  }

  showAddItemModal() {
    this.currentEditingItem = null;
    const modal = document.getElementById('itemModal');
    const form = document.getElementById('itemForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Add Inventory Item';
    if (form) form.reset();
    if (modal) modal.style.display = 'flex';
  }

  editItem(itemId) {
    const item = this.items.find(i => i.id === itemId);
    if (!item) return;

    this.currentEditingItem = item;
    const modal = document.getElementById('itemModal');
    const form = document.getElementById('itemForm');
    const title = document.getElementById('modalTitle');
    
    if (title) title.textContent = 'Edit Inventory Item';
    if (form) {
      form.name.value = item.name;
      form.category.value = item.category || '';
      form.location.value = item.location || '';
      form.quantity.value = item.quantity;
      form.notes.value = item.notes || '';
    }
    if (modal) modal.style.display = 'flex';
  }

  async handleItemSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    
    const itemData = {
      name: formData.get('name'),
      category: formData.get('category') || null,
      location: formData.get('location') || null,
      quantity: parseInt(formData.get('quantity')) || 1,
      notes: formData.get('notes') || null
    };

    try {
      const url = this.currentEditingItem 
        ? `/api/admin/inventory/${this.currentEditingItem.id}`
        : '/api/admin/inventory';
      
      const method = this.currentEditingItem ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(itemData),
      });

      if (response.ok) {
        this.showSuccess(this.currentEditingItem ? 'Item updated successfully' : 'Item added successfully');
        this.closeModal();
        await this.loadData();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to save item');
      }
    } catch (error) {
      console.error('Failed to save item:', error);
      this.showError('Failed to save item');
    }
  }

  async deleteItem(itemId) {
    if (!confirm('Are you sure you want to delete this item?')) return;

    try {
      const response = await fetch(`/api/admin/inventory/${itemId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.showSuccess('Item deleted successfully');
        await this.loadData();
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to delete item');
      }
    } catch (error) {
      console.error('Failed to delete item:', error);
      this.showError('Failed to delete item');
    }
  }

  filterItems() {
    const searchTerm = document.getElementById('inventorySearch')?.value.toLowerCase() || '';
    const categoryFilter = document.getElementById('categoryFilter')?.value || '';
    const locationFilter = document.getElementById('locationFilter')?.value || '';

    const filtered = this.items.filter(item => {
      const matchesSearch = !searchTerm || 
        item.name.toLowerCase().includes(searchTerm) ||
        (item.category && item.category.toLowerCase().includes(searchTerm)) ||
        (item.location && item.location.toLowerCase().includes(searchTerm)) ||
        (item.notes && item.notes.toLowerCase().includes(searchTerm));

      const matchesCategory = !categoryFilter || item.category === categoryFilter;
      const matchesLocation = !locationFilter || item.location === locationFilter;

      return matchesSearch && matchesCategory && matchesLocation;
    });

    const container = document.getElementById('inventoryContainer');
    if (!container) return;

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">No items found</div>
          <div class="empty-state-description">Try adjusting your search or filters</div>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(item => this.createItemCard(item)).join('');
  }

  updateStats() {
    const totalItems = this.items.reduce((sum, item) => sum + item.quantity, 0);
    const totalCategories = this.categories.length;
    const totalLocations = this.locations.length;

    this.updateStat('total-items', totalItems);
    this.updateStat('total-categories', totalCategories);
    this.updateStat('total-locations', totalLocations);
  }

  updateStat(id, value) {
    const element = document.getElementById(`${id}-value`);
    if (element) {
      element.textContent = value;
    }
  }

  closeModal() {
    const modal = document.getElementById('itemModal');
    if (modal) modal.style.display = 'none';
    this.currentEditingItem = null;
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
    const container = document.querySelector('.inventory-container');
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
    const ws = new WebSocket(`ws://${window.location.host}/ws/inventory`);
    
    ws.onopen = () => {
      console.log('Inventory WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'inventory_updated') {
        this.loadData();
      }
    };
    
    ws.onclose = () => {
      console.log('Inventory WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(() => this.setupWebSocket(), 5000);
    };
    
    ws.onerror = (error) => {
      console.error('Inventory WebSocket error:', error);
    };
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.inventoryManager = new InventoryManager();
});
