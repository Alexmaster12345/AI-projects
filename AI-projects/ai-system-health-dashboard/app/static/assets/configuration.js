// Configuration page JavaScript

class ConfigurationManager {
  constructor() {
    this.config = {};
    this.originalConfig = {};
    this.activeTab = 'general';
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadConfig();
    this.setupWebSocket();
  }

  bindEvents() {
    // Tab switching
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('configuration-tab')) {
        this.switchTab(e.target.dataset.tab);
      }
    });

    // Save buttons
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('save-config')) {
        this.saveConfig(e.target.dataset.section);
      }
    });

    // Reset buttons
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('reset-config')) {
        this.resetConfig(e.target.dataset.section);
      }
    });

    // Form inputs
    document.addEventListener('input', (e) => {
      if (e.target.classList.contains('config-input')) {
        this.markConfigChanged(e.target.dataset.section);
      }
    });

    // Test buttons
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('test-connection')) {
        this.testConnection(e.target.dataset.service);
      }
    });
  }

  async loadConfig() {
    try {
      const response = await fetch('/api/config');
      if (response.ok) {
        this.config = await response.json();
        this.originalConfig = JSON.parse(JSON.stringify(this.config)); // Deep copy
        this.renderConfig();
      }
    } catch (error) {
      console.error('Failed to load configuration:', error);
      this.showError('Failed to load configuration');
    }
  }

  renderConfig() {
    this.renderGeneralConfig();
    this.renderMonitoringConfig();
    this.renderProtocolsConfig();
    this.renderStorageConfig();
    this.renderAuthConfig();
  }

  renderGeneralConfig() {
    const container = document.getElementById('general-config');
    if (!container) return;

    container.innerHTML = `
      <div class="config-grid">
        <div class="config-field">
          <label class="config-label">Application Title</label>
          <input type="text" class="config-input" data-section="general" data-key="app.title" 
                 value="${this.config.app?.title || ''}" />
          <div class="config-description">Display title for the application</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Help URL</label>
          <input type="url" class="config-input" data-section="general" data-key="app.help_url" 
                 value="${this.config.app?.help_url || ''}" />
          <div class="config-description">Link to documentation or help page</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Sample Interval (seconds)</label>
          <input type="number" class="config-input" data-section="general" data-key="sampling.sample_interval_seconds" 
                 value="${this.config.sampling?.sample_interval_seconds || 5}" min="1" max="300" />
          <div class="config-description">How often to collect system metrics</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">History Retention (seconds)</label>
          <input type="number" class="config-input" data-section="general" data-key="sampling.history_seconds" 
                 value="${this.config.sampling?.history_seconds || 300}" min="60" max="86400" />
          <div class="config-description">How long to keep metrics data in memory</div>
        </div>
      </div>
    `;
  }

  renderMonitoringConfig() {
    const container = document.getElementById('monitoring-config');
    if (!container) return;

    container.innerHTML = `
      <div class="config-grid">
        <div class="config-field">
          <label class="config-label">Anomaly Window (seconds)</label>
          <input type="number" class="config-input" data-section="monitoring" data-key="anomaly.window_seconds" 
                 value="${this.config.anomaly?.window_seconds || 60}" min="30" max="3600" />
          <div class="config-description">Time window for anomaly detection</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Anomaly Threshold</label>
          <input type="number" class="config-input" data-section="monitoring" data-key="anomaly.z_threshold" 
                 value="${this.config.anomaly?.z_threshold || 2.0}" min="1.0" max="5.0" step="0.1" />
          <div class="config-description">Z-score threshold for anomaly detection</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Protocol Check Interval (seconds)</label>
          <input type="number" class="config-input" data-section="monitoring" data-key="protocols.check_interval_seconds" 
                 value="${this.config.protocols?.check_interval_seconds || 15}" min="5" max="300" />
          <div class="config-description">How often to check protocol connectivity</div>
        </div>
      </div>
    `;
  }

  renderProtocolsConfig() {
    const container = document.getElementById('protocols-config');
    if (!container) return;

    container.innerHTML = `
      <div class="config-grid">
        <div class="config-field">
          <label class="config-label">NTP Server</label>
          <input type="text" class="config-input" data-section="protocols" data-key="ntp.server" 
                 value="${this.config.protocols?.ntp?.server || ''}" />
          <div class="config-description">NTP server for time synchronization</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">NTP Timeout (seconds)</label>
          <input type="number" class="config-input" data-section="protocols" data-key="ntp.timeout_seconds" 
                 value="${this.config.protocols?.ntp?.timeout_seconds || 1.2}" min="0.5" max="10" step="0.1" />
          <div class="config-description">Timeout for NTP queries</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">ICMP Host</label>
          <input type="text" class="config-input" data-section="protocols" data-key="icmp.host" 
                 value="${this.config.protocols?.icmp?.host || ''}" />
          <div class="config-description">Host to ping for connectivity testing</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">SNMP Host</label>
          <input type="text" class="config-input" data-section="protocols" data-key="snmp.host" 
                 value="${this.config.protocols?.snmp?.host || ''}" />
          <div class="config-description">SNMP host for monitoring</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">SNMP Port</label>
          <input type="number" class="config-input" data-section="protocols" data-key="snmp.port" 
                 value="${this.config.protocols?.snmp?.port || 161}" min="1" max="65535" />
          <div class="config-description">SNMP port number</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">NetFlow Port</label>
          <input type="number" class="config-input" data-section="protocols" data-key="netflow.port" 
                 value="${this.config.protocols?.netflow?.port || 2055}" min="1" max="65535" />
          <div class="config-description">NetFlow collector port</div>
        </div>
      </div>
    `;
  }

  renderStorageConfig() {
    const container = document.getElementById('storage-config');
    if (!container) return;

    container.innerHTML = `
      <div class="config-grid">
        <div class="config-field">
          <label class="config-label">Storage Enabled</label>
          <label class="config-checkbox">
            <input type="checkbox" class="config-input" data-section="storage" data-key="enabled" 
                   ${this.config.storage?.enabled ? 'checked' : ''} />
            Enable persistent storage
          </label>
          <div class="config-description">Store metrics data in SQLite database</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">SQLite Retention (seconds)</label>
          <input type="number" class="config-input" data-section="storage" data-key="sqlite_retention_seconds" 
                 value="${this.config.storage?.sqlite_retention_seconds || 86400}" min="3600" max="2592000" />
          <div class="config-description">How long to keep data in SQLite database</div>
        </div>
      </div>
      
      ${this.config.storage?.db_stats ? `
        <div class="config-status success">
          <span class="status-indicator"></span>
          Database connected
        </div>
        <div class="config-preview">
          Database Stats: ${JSON.stringify(this.config.storage.db_stats, null, 2)}
        </div>
      ` : ''}
    `;
  }

  renderAuthConfig() {
    const container = document.getElementById('auth-config');
    if (!container) return;

    container.innerHTML = `
      <div class="config-grid">
        <div class="config-field">
          <label class="config-label">Session Cookie Name</label>
          <input type="text" class="config-input" data-section="auth" data-key="session_cookie_name" 
                 value="${this.config.auth?.session_cookie_name || ''}" readonly />
          <div class="config-description">Name of the session cookie (read-only)</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Session Max Age (seconds)</label>
          <input type="number" class="config-input" data-section="auth" data-key="session_max_age_seconds" 
                 value="${this.config.auth?.session_max_age_seconds || 3600}" min="300" max="86400" />
          <div class="config-description">How long sessions remain valid</div>
        </div>
        
        <div class="config-field">
          <label class="config-label">Remember Me Max Age (seconds)</label>
          <input type="number" class="config-input" data-section="auth" data-key="remember_max_age_seconds" 
                 value="${this.config.auth?.remember_max_age_seconds || 604800}" min="86400" max="2592000" />
          <div class="config-description">How long remember-me cookies last</div>
        </div>
      </div>
    `;
  }

  switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.configuration-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update content
    document.querySelectorAll('.configuration-content').forEach(content => {
      content.classList.toggle('active', content.id === `${tabName}-config`);
    });

    this.activeTab = tabName;
  }

  async saveConfig(section) {
    try {
      const configData = this.collectConfigData(section);
      
      // Note: This would need to be implemented on the backend
      const response = await fetch('/api/admin/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ section, config: configData }),
      });

      if (response.ok) {
        this.showSuccess(`${section} configuration saved successfully`);
        this.originalConfig[section] = JSON.parse(JSON.stringify(configData));
        this.clearChangedState(section);
      } else {
        const error = await response.json();
        this.showError(error.detail || 'Failed to save configuration');
      }
    } catch (error) {
      console.error('Failed to save configuration:', error);
      this.showError('Failed to save configuration');
    }
  }

  collectConfigData(section) {
    const inputs = document.querySelectorAll(`.config-input[data-section="${section}"]`);
    const config = {};

    inputs.forEach(input => {
      const key = input.dataset.key;
      const value = input.type === 'checkbox' ? input.checked : input.value;
      
      // Handle nested keys like "app.title"
      const keys = key.split('.');
      let current = config;
      
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      
      // Convert numeric values
      if (input.type === 'number') {
        current[keys[keys.length - 1]] = parseFloat(value);
      } else {
        current[keys[keys.length - 1]] = value;
      }
    });

    return config;
  }

  resetConfig(section) {
    if (!confirm('Are you sure you want to reset this section to default values?')) return;

    // Reset to original values
    const inputs = document.querySelectorAll(`.config-input[data-section="${section}"]`);
    inputs.forEach(input => {
      const key = input.dataset.key;
      const originalValue = this.getNestedValue(this.originalConfig, key);
      
      if (input.type === 'checkbox') {
        input.checked = originalValue || false;
      } else {
        input.value = originalValue || '';
      }
    });

    this.clearChangedState(section);
    this.showSuccess(`${section} configuration reset to defaults`);
  }

  getNestedValue(obj, key) {
    const keys = key.split('.');
    let current = obj;
    
    for (const k of keys) {
      if (current && typeof current === 'object' && k in current) {
        current = current[k];
      } else {
        return undefined;
      }
    }
    
    return current;
  }

  markConfigChanged(section) {
    const saveBtn = document.querySelector(`.save-config[data-section="${section}"]`);
    if (saveBtn) {
      saveBtn.classList.add('changed');
    }
  }

  clearChangedState(section) {
    const saveBtn = document.querySelector(`.save-config[data-section="${section}"]`);
    if (saveBtn) {
      saveBtn.classList.remove('changed');
    }
  }

  async testConnection(service) {
    const btn = document.querySelector(`.test-connection[data-service="${service}"]`);
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Testing...';
    }

    try {
      const response = await fetch(`/api/admin/test/${service}`);
      if (response.ok) {
        const result = await response.json();
        this.showSuccess(`${service} connection test: ${result.message}`);
      } else {
        const error = await response.json();
        this.showError(`${service} connection test failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Connection test failed:', error);
      this.showError(`${service} connection test failed`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Test Connection';
      }
    }
  }

  showSuccess(message) {
    this.showAlert(message, 'success');
  }

  showError(message) {
    this.showAlert(message, 'error');
  }

  showAlert(message, type) {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.config-alert');
    existingAlerts.forEach(alert => alert.remove());

    // Create new alert
    const alert = document.createElement('div');
    alert.className = `config-alert ${type}`;
    alert.innerHTML = `
      <div class="config-alert-title">${type === 'success' ? 'Success' : 'Error'}</div>
      <div class="config-alert-message">${message}</div>
    `;
    
    // Insert at the top of the container
    const container = document.querySelector('.configuration-container');
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
    const ws = new WebSocket(`ws://${window.location.host}/ws/config`);
    
    ws.onopen = () => {
      console.log('Configuration WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'config_updated') {
        this.loadConfig();
      }
    };
    
    ws.onclose = () => {
      console.log('Configuration WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(() => this.setupWebSocket(), 5000);
    };
    
    ws.onerror = (error) => {
      console.error('Configuration WebSocket error:', error);
    };
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.configurationManager = new ConfigurationManager();
});
