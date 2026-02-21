// Overview page JavaScript

class OverviewManager {
  constructor() {
    this.metrics = {};
    this.alerts = [];
    this.charts = {};
    this.init();
  }

  async init() {
    this.bindEvents();
    await this.loadData();
    this.setupWebSocket();
    this.startAutoRefresh();
  }

  bindEvents() {
    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadData());
    }

    // Time range selector
    const timeRange = document.getElementById('timeRange');
    if (timeRange) {
      timeRange.addEventListener('change', (e) => {
        this.updateTimeRange(e.target.value);
      });
    }
  }

  async loadData() {
    try {
      const [metricsResponse, alertsResponse] = await Promise.all([
        fetch('/api/metrics/latest'),
        fetch('/api/insights')
      ]);

      if (metricsResponse.ok) {
        this.metrics = await metricsResponse.json();
        this.renderMetrics();
      }

      if (alertsResponse.ok) {
        const insights = await alertsResponse.json();
        this.alerts = insights.anomalies || [];
        this.renderAlerts();
      }

      this.renderCharts();
    } catch (error) {
      console.error('Failed to load overview data:', error);
      this.showError('Failed to load data');
    }
  }

  renderMetrics() {
    this.renderMetricCard('cpu', this.metrics.cpu_percent, '%');
    this.renderMetricCard('memory', this.metrics.mem_percent, '%');
    this.renderMetricCard('disk', this.getDiskUsage(), '%');
    this.renderMetricCard('uptime', this.formatUptime(this.metrics.uptime_seconds), '');
    this.renderMetricCard('load', this.metrics.load1, '');
    this.renderMetricCard('processes', this.metrics.top_processes?.length || 0, '');
  }

  renderMetricCard(id, value, unit) {
    const valueElement = document.getElementById(`${id}-value`);
    const changeElement = document.getElementById(`${id}-change`);
    
    if (valueElement) {
      valueElement.textContent = value + unit;
    }

    if (changeElement) {
      // Simulate change calculation (in real app, this would compare with previous value)
      const change = Math.random() * 10 - 5; // Random change between -5 and 5
      changeElement.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`;
      changeElement.className = `overview-metric-change ${change >= 0 ? 'positive' : 'negative'}`;
    }
  }

  renderAlerts() {
    const container = document.getElementById('alerts-container');
    if (!container) return;

    if (this.alerts.length === 0) {
      container.innerHTML = `
        <div class="overview-alert info">
          <div class="overview-alert-icon"></div>
          <div class="overview-alert-content">
            <div class="overview-alert-title">System Operating Normally</div>
            <div class="overview-alert-description">No active alerts detected</div>
          </div>
        </div>
      `;
      return;
    }

    container.innerHTML = this.alerts.map(alert => this.createAlertHTML(alert)).join('');
  }

  createAlertHTML(alert) {
    const severityClass = alert.severity === 'crit' ? 'critical' : alert.severity;
    return `
      <div class="overview-alert ${severityClass}">
        <div class="overview-alert-icon"></div>
        <div class="overview-alert-content">
          <div class="overview-alert-title">${alert.metric.toUpperCase()} Alert</div>
          <div class="overview-alert-description">${alert.message}</div>
          <div class="overview-alert-time">${new Date().toLocaleTimeString()}</div>
        </div>
      </div>
    `;
  }

  renderCharts() {
    this.renderCPUChart();
    this.renderMemoryChart();
    this.renderNetworkChart();
  }

  renderCPUChart() {
    const container = document.getElementById('cpu-chart-content');
    if (!container) return;

    // Simple chart implementation (in real app, use a charting library)
    const cpuUsage = this.metrics.cpu_percent || 0;
    const color = cpuUsage > 80 ? '#dc2626' : cpuUsage > 60 ? '#d97706' : '#16a34a';
    
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem;">
        <div style="font-size: 3rem; font-weight: bold; color: ${color};">
          ${cpuUsage.toFixed(1)}%
        </div>
        <div style="color: var(--text-muted); margin-top: 0.5rem;">CPU Usage</div>
        <div style="width: 100%; height: 8px; background: var(--border); border-radius: 4px; margin-top: 1rem;">
          <div style="width: ${cpuUsage}%; height: 100%; background: ${color}; border-radius: 4px;"></div>
        </div>
      </div>
    `;
  }

  renderMemoryChart() {
    const container = document.getElementById('memory-chart-content');
    if (!container) return;

    const memUsage = this.metrics.mem_percent || 0;
    const color = memUsage > 85 ? '#dc2626' : memUsage > 70 ? '#d97706' : '#16a34a';
    
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem;">
        <div style="font-size: 3rem; font-weight: bold; color: ${color};">
          ${memUsage.toFixed(1)}%
        </div>
        <div style="color: var(--text-muted); margin-top: 0.5rem;">Memory Usage</div>
        <div style="width: 100%; height: 8px; background: var(--border); border-radius: 4px; margin-top: 1rem;">
          <div style="width: ${memUsage}%; height: 100%; background: ${color}; border-radius: 4px;"></div>
        </div>
      </div>
    `;
  }

  renderNetworkChart() {
    const container = document.getElementById('network-chart-content');
    if (!container) return;

    const netIO = this.metrics.net;
    if (!netIO) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 2rem;">No network data available</div>';
      return;
    }

    const sentMB = (netIO.bytes_sent / 1024 / 1024).toFixed(1);
    const recvMB = (netIO.bytes_recv / 1024 / 1024).toFixed(1);
    
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem;">
        <div style="display: flex; justify-content: space-around; margin-bottom: 1rem;">
          <div>
            <div style="font-size: 1.5rem; font-weight: bold; color: var(--primary);">
              ${sentMB} MB
            </div>
            <div style="color: var(--text-muted); font-size: 0.875rem;">Sent</div>
          </div>
          <div>
            <div style="font-size: 1.5rem; font-weight: bold; color: var(--success);">
              ${recvMB} MB
            </div>
            <div style="color: var(--text-muted); font-size: 0.875rem;">Received</div>
          </div>
        </div>
        <div style="color: var(--text-muted); font-size: 0.875rem;">Network I/O</div>
      </div>
    `;
  }

  getDiskUsage() {
    if (!this.metrics.disk || this.metrics.disk.length === 0) return 0;
    return this.metrics.disk[0].percent || 0;
  }

  formatUptime(seconds) {
    if (!seconds) return '0d 0h';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
      return `${days}d ${hours}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  }

  updateTimeRange(range) {
    // Update charts based on selected time range
    console.log('Time range changed to:', range);
    this.loadData();
  }

  startAutoRefresh() {
    // Refresh data every 30 seconds
    setInterval(() => {
      this.loadData();
    }, 30000);
  }

  setupWebSocket() {
    // WebSocket for real-time updates
    const ws = new WebSocket(`ws://${window.location.host}/ws/metrics`);
    
    ws.onopen = () => {
      console.log('Overview WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'metrics_update') {
        this.metrics = data.metrics;
        this.renderMetrics();
      }
    };
    
    ws.onclose = () => {
      console.log('Overview WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(() => this.setupWebSocket(), 5000);
    };
    
    ws.onerror = (error) => {
      console.error('Overview WebSocket error:', error);
    };
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
    const container = document.querySelector('.overview-container');
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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.overviewManager = new OverviewManager();
});
