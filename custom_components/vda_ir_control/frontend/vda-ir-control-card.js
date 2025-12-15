/**
 * VDA IR Control Management Card
 * A custom Lovelace card for managing IR boards, profiles, and devices
 */

class VDAIRControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = {};
    this._activeTab = 'boards';
    this._boards = [];
    this._profiles = [];
    this._devices = [];
    this._selectedBoard = null;
    this._selectedProfile = null;
    this._learningState = null;
    this._ports = [];
    this._gpioPins = [];
    this._portAssignments = {};
    this._learnInputPorts = [];
    this._deviceOutputPorts = [];
    this._builtinProfiles = [];
    this._builtinManufacturers = [];
    this._builtinDeviceTypes = [];
    // Network devices state
    this._networkDevices = [];
    this._selectedNetworkDevice = null;
    this._networkTestResult = null;
    // Serial devices state
    this._serialDevices = [];
    this._selectedSerialDevice = null;
    this._serialTestResult = null;
    this._availableSerialPorts = [];
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._loadData();
    }
  }

  setConfig(config) {
    this._config = config;
  }

  static getConfigElement() {
    return document.createElement('vda-ir-control-card-editor');
  }

  static getStubConfig() {
    return {};
  }

  async _loadData() {
    await Promise.all([
      this._loadBoards(),
      this._loadProfiles(),
      this._loadBuiltinProfiles(),
      this._loadDevices(),
      this._loadGPIOPins(),
      this._loadNetworkDevices(),
      this._loadSerialDevices(),
    ]);
    this._render();
  }

  async _loadGPIOPins() {
    try {
      const resp = await fetch('/api/vda_ir_control/gpio_pins', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._gpioPins = data.pins || [];
        this._reservedPins = data.reserved || [];
      } else {
        this._gpioPins = [];
        this._reservedPins = [];
      }
    } catch (e) {
      console.error('Failed to load GPIO pins:', e);
      this._gpioPins = [];
      this._reservedPins = [];
    }
  }

  async _loadPortAssignments(boardId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/port_assignments/${boardId}`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._portAssignments = data.assignments || {};
      } else {
        this._portAssignments = {};
      }
    } catch (e) {
      console.error('Failed to load port assignments:', e);
      this._portAssignments = {};
    }
  }

  _getGPIOForPort(portNumber) {
    // Map port number to GPIO pin - returns pin info
    // The GPIO mapping will come from the board, but we have defaults
    const pin = this._gpioPins.find(p => p.gpio === portNumber);
    return pin;
  }

  async _loadLearnInputPorts(boardId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/ports/${boardId}`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        // Filter to only IR input ports
        this._learnInputPorts = (data.ports || []).filter(p => p.mode === 'ir_input');
      } else {
        this._learnInputPorts = [];
      }
    } catch (e) {
      console.error('Failed to load input ports:', e);
      this._learnInputPorts = [];
    }
  }

  async _loadDeviceOutputPorts(boardId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/ports/${boardId}`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        // Filter to only IR output ports
        this._deviceOutputPorts = (data.ports || []).filter(p => p.mode === 'ir_output');
      } else {
        this._deviceOutputPorts = [];
      }
    } catch (e) {
      console.error('Failed to load output ports:', e);
      this._deviceOutputPorts = [];
    }
  }

  async _loadBoards() {
    try {
      const resp = await fetch('/api/vda_ir_control/boards', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._boards = data.boards || [];
      } else {
        this._boards = [];
      }
    } catch (e) {
      console.error('Failed to load boards:', e);
      this._boards = [];
    }
  }

  async _loadProfiles() {
    try {
      // Fetch profiles via REST API
      const resp = await fetch('/api/vda_ir_control/profiles', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._profiles = data.profiles || [];
      } else {
        this._profiles = [];
      }
    } catch (e) {
      console.error('Failed to load profiles:', e);
      this._profiles = [];
    }
  }

  async _loadBuiltinProfiles() {
    try {
      const resp = await fetch('/api/vda_ir_control/builtin_profiles', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._builtinProfiles = data.profiles || [];
        this._builtinManufacturers = data.available_manufacturers || [];
        this._builtinDeviceTypes = data.available_device_types || [];
      } else {
        this._builtinProfiles = [];
        this._builtinManufacturers = [];
        this._builtinDeviceTypes = [];
      }
    } catch (e) {
      console.error('Failed to load built-in profiles:', e);
      this._builtinProfiles = [];
      this._builtinManufacturers = [];
      this._builtinDeviceTypes = [];
    }
  }

  async _loadDevices() {
    try {
      // Fetch devices via REST API
      const resp = await fetch('/api/vda_ir_control/devices', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._devices = data.devices || [];
      } else {
        this._devices = [];
      }
    } catch (e) {
      console.error('Failed to load devices:', e);
      this._devices = [];
    }
  }

  async _loadNetworkDevices() {
    try {
      const resp = await fetch('/api/vda_ir_control/network_devices', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._networkDevices = data.devices || [];
      } else {
        this._networkDevices = [];
      }
    } catch (e) {
      console.error('Failed to load network devices:', e);
      this._networkDevices = [];
    }
  }

  async _loadNetworkDevice(deviceId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/network_devices/${deviceId}`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e) {
      console.error('Failed to load network device:', e);
    }
    return null;
  }

  async _loadSerialDevices() {
    try {
      const resp = await fetch('/api/vda_ir_control/serial_devices', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._serialDevices = data.devices || [];
      } else {
        this._serialDevices = [];
      }
    } catch (e) {
      console.error('Failed to load serial devices:', e);
      this._serialDevices = [];
    }
  }

  async _loadSerialDevice(deviceId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e) {
      console.error('Failed to load serial device:', e);
    }
    return null;
  }

  async _loadAvailableSerialPorts() {
    try {
      const resp = await fetch('/api/vda_ir_control/serial_ports', {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._availableSerialPorts = data.ports || [];
      } else {
        this._availableSerialPorts = [];
      }
    } catch (e) {
      console.error('Failed to load serial ports:', e);
      this._availableSerialPorts = [];
    }
  }

  async _loadPorts(boardId) {
    try {
      // Fetch ports via REST API and port assignments in parallel
      const [portsResp] = await Promise.all([
        fetch(`/api/vda_ir_control/ports/${boardId}`, {
          headers: {
            'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          },
        }),
        this._loadPortAssignments(boardId),
      ]);
      if (portsResp.ok) {
        const data = await portsResp.json();
        this._ports = data.ports || [];
      } else {
        // If no ports from board, use GPIO pins as available ports
        this._ports = this._gpioPins
          .filter(p => p.can_output || p.can_input)
          .map(p => ({
            port: p.gpio,
            gpio: p.gpio,
            mode: 'disabled',
            name: '',
          }));
      }
      this._render();
    } catch (e) {
      console.error('Failed to load ports:', e);
      // Fallback to GPIO pins
      this._ports = this._gpioPins
        .filter(p => p.can_output || p.can_input)
        .map(p => ({
          port: p.gpio,
          gpio: p.gpio,
          mode: 'disabled',
          name: '',
        }));
      this._render();
    }
  }

  async _callService(domain, service, data) {
    // Use regular service call (no response needed)
    await this._hass.callService(domain, service, data);
  }

  _getBoards() {
    // Return boards loaded from API
    return this._boards || [];
  }

  _render() {
    const boards = this._getBoards();

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          position: relative;
        }
        .card {
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.1));
          padding: 16px;
        }
        .header {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }
        .header h2 {
          margin: 0;
          flex: 1;
          font-size: 1.4em;
          color: var(--primary-text-color);
        }
        .tabs {
          display: flex;
          border-bottom: 1px solid var(--divider-color);
          margin-bottom: 16px;
        }
        .tab {
          padding: 12px 20px;
          cursor: pointer;
          border: none;
          background: none;
          color: var(--secondary-text-color);
          font-size: 14px;
          font-weight: 500;
          border-bottom: 2px solid transparent;
          transition: all 0.2s;
        }
        .tab:hover {
          color: var(--primary-color);
        }
        .tab.active {
          color: var(--primary-color);
          border-bottom-color: var(--primary-color);
        }
        .content {
          min-height: 300px;
        }
        .list-item {
          display: flex;
          align-items: center;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 8px;
          background: var(--secondary-background-color);
          cursor: pointer;
          transition: background 0.2s;
        }
        .list-item:hover {
          background: var(--primary-color);
          color: white;
        }
        .list-item.selected {
          background: var(--primary-color);
          color: white;
        }
        .list-item-content {
          flex: 1;
        }
        .list-item-title {
          font-weight: 500;
          margin-bottom: 2px;
        }
        .list-item-subtitle {
          font-size: 12px;
          opacity: 0.7;
        }
        .list-item-actions {
          display: flex;
          gap: 8px;
        }
        .btn {
          padding: 8px 16px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
        }
        .btn-primary {
          background: var(--primary-color);
          color: white;
        }
        .btn-primary:hover {
          opacity: 0.9;
        }
        .btn-secondary {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
        }
        .btn-danger {
          background: var(--error-color, #db4437);
          color: white;
        }
        .btn-small {
          padding: 4px 12px;
          font-size: 12px;
        }
        .form-group {
          margin-bottom: 16px;
        }
        .form-group label {
          display: block;
          margin-bottom: 4px;
          font-weight: 500;
          font-size: 14px;
          color: var(--primary-text-color, #212121);
        }
        .form-group input, .form-group select {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 6px;
          font-size: 14px;
          background: var(--input-fill-color, var(--secondary-background-color, #f5f5f5));
          color: var(--primary-text-color, #212121);
          box-sizing: border-box;
        }
        .form-group select option {
          background: var(--card-background-color, white);
          color: var(--primary-text-color, #212121);
        }
        .form-group input:focus, .form-group select:focus {
          outline: none;
          border-color: var(--primary-color);
        }
        .form-row {
          display: flex;
          gap: 16px;
        }
        .form-row .form-group {
          flex: 1;
        }
        .section {
          margin-bottom: 24px;
        }
        .section-title {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 12px;
          color: var(--primary-text-color);
        }
        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--secondary-text-color);
        }
        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 16px;
        }
        .badge {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 500;
          margin-left: 8px;
        }
        .badge-success {
          background: var(--success-color, #4caf50);
          color: white;
        }
        .badge-warning {
          background: var(--warning-color, #ff9800);
          color: white;
        }
        .badge-info {
          background: var(--info-color, #2196f3);
          color: white;
        }
        .port-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          gap: 8px;
        }
        .port-item {
          padding: 12px;
          border-radius: 8px;
          background: var(--secondary-background-color, #f5f5f5);
          color: var(--primary-text-color, #212121);
          text-align: center;
          cursor: pointer;
        }
        .port-item.input {
          border: 2px solid var(--info-color, #2196f3);
        }
        .port-item.output {
          border: 2px solid var(--success-color, #4caf50);
        }
        .port-item.disabled {
          opacity: 0.5;
          border: 2px solid transparent;
        }
        .port-item.assigned {
          box-shadow: 0 0 0 2px var(--warning-color, #ff9800);
        }
        .port-item:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .port-number {
          font-size: 14px;
          font-weight: bold;
          color: var(--primary-text-color, #212121);
        }
        .port-gpio {
          font-size: 12px;
          font-weight: 600;
          color: var(--primary-color);
          margin-top: 2px;
        }
        .port-mode {
          font-size: 10px;
          text-transform: uppercase;
          margin-top: 4px;
          color: var(--secondary-text-color, #666);
        }
        .port-name {
          font-size: 11px;
          margin-top: 4px;
          color: var(--primary-text-color, #212121);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .port-devices {
          font-size: 10px;
          margin-top: 4px;
          padding: 2px 6px;
          background: var(--warning-color, #ff9800);
          color: white;
          border-radius: 10px;
          display: inline-block;
        }
        .learning-status {
          padding: 16px;
          border-radius: 8px;
          background: var(--info-color, #2196f3);
          color: white;
          margin-bottom: 16px;
          text-align: center;
        }
        .learning-status.success {
          background: var(--success-color, #4caf50);
        }
        .command-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
          gap: 8px;
          margin-top: 12px;
        }
        .command-btn {
          padding: 10px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 6px;
          background: var(--secondary-background-color, #f5f5f5);
          color: var(--primary-text-color, #212121);
          cursor: pointer;
          font-size: 12px;
          text-align: center;
          transition: all 0.2s;
        }
        .command-btn:hover {
          border-color: var(--primary-color);
          background: var(--primary-color);
          color: white;
        }
        .command-btn.learned {
          background: var(--success-color, #4caf50);
          color: white;
          border-color: var(--success-color, #4caf50);
        }
        .remote-btn {
          padding: 12px 16px;
          border: none;
          border-radius: 8px;
          background: var(--secondary-background-color, #e0e0e0);
          color: var(--primary-text-color, #212121);
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.15s;
          min-width: 50px;
        }
        .remote-btn:hover {
          background: var(--primary-color);
          color: white;
          transform: scale(1.05);
        }
        .remote-btn:active {
          transform: scale(0.95);
        }
        .remote-btn.power {
          background: var(--error-color, #f44336);
          color: white;
          font-size: 18px;
          padding: 12px 24px;
        }
        .remote-btn.power:hover {
          background: #d32f2f;
        }
        .remote-btn.nav {
          width: 50px;
          height: 50px;
          padding: 0;
          font-size: 18px;
        }
        .remote-btn.nav.ok {
          background: var(--primary-color);
          color: white;
          border-radius: 50%;
        }
        .remote-btn.vol, .remote-btn.chan {
          width: 50px;
          height: 40px;
          font-size: 20px;
          font-weight: bold;
        }
        .remote-btn.vol.mute {
          font-size: 16px;
        }
        .remote-btn.num {
          width: 50px;
          height: 45px;
          font-size: 18px;
          font-weight: 600;
        }
        .remote-btn.input {
          font-size: 11px;
          padding: 8px 12px;
        }
        .remote-btn.play {
          font-size: 16px;
          padding: 10px 14px;
        }
        .remote-btn.play.record {
          color: var(--error-color, #f44336);
        }
        .remote-section {
          padding: 12px;
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 12px;
        }
        .modal {
          position: fixed;
          top: 0;
          left: 0;
          width: 100vw;
          height: 100vh;
          background: rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
        }
        .modal-content {
          background: var(--ha-card-background, var(--card-background-color, white));
          color: var(--primary-text-color, #212121);
          border-radius: 12px;
          padding: 24px;
          max-width: 550px;
          width: 90%;
          max-height: 80vh;
          overflow-y: auto;
          overflow-x: hidden;
        }
        .modal-title {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
          color: var(--primary-text-color, #212121);
        }
        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          margin-top: 24px;
        }
      </style>

      <div class="card">
        <div class="header">
          <h2>VDA IR Control</h2>
        </div>

        <div class="tabs">
          <button class="tab ${this._activeTab === 'boards' ? 'active' : ''}" data-tab="boards">
            Boards
          </button>
          <button class="tab ${this._activeTab === 'profiles' ? 'active' : ''}" data-tab="profiles">
            Profiles
          </button>
          <button class="tab ${this._activeTab === 'devices' ? 'active' : ''}" data-tab="devices">
            Devices
          </button>
          <button class="tab ${this._activeTab === 'network' ? 'active' : ''}" data-tab="network">
            Network
          </button>
          <button class="tab ${this._activeTab === 'serial' ? 'active' : ''}" data-tab="serial">
            Serial
          </button>
        </div>

        <div class="content">
          ${this._renderTabContent(boards)}
        </div>
      </div>

      ${this._renderModal()}
    `;

    this._attachEventListeners();
  }

  _renderTabContent(boards) {
    switch (this._activeTab) {
      case 'boards':
        return this._renderBoardsTab(boards);
      case 'profiles':
        return this._renderProfilesTab();
      case 'devices':
        return this._renderDevicesTab();
      case 'network':
        return this._renderNetworkTab();
      case 'serial':
        return this._renderSerialTab();
      default:
        return '';
    }
  }

  _renderBoardsTab(boards) {
    if (boards.length === 0) {
      return `
        <div class="empty-state">
          <div class="empty-state-icon">📡</div>
          <p>No boards configured</p>
          <p style="font-size: 12px;">Add a board through the integration settings</p>
        </div>
      `;
    }

    return `
      <div class="section">
        <div class="section-title">Connected Boards</div>
        ${boards.map(board => `
          <div class="list-item ${this._selectedBoard === board.board_id ? 'selected' : ''}"
               data-action="select-board" data-board-id="${board.board_id}">
            <div class="list-item-content">
              <div class="list-item-title">
                ${board.board_name}
                <span class="badge badge-success">Online</span>
              </div>
              <div class="list-item-subtitle">
                ${board.board_id} • ${board.ip_address}
              </div>
            </div>
            <div class="list-item-actions">
              <button class="btn btn-secondary btn-small" data-action="configure-ports" data-board-id="${board.board_id}">
                Configure Ports
              </button>
            </div>
          </div>
        `).join('')}
      </div>

      ${this._selectedBoard ? this._renderPortConfig() : ''}
    `;
  }

  _renderPortConfig() {
    if (this._ports.length === 0 && this._gpioPins.length === 0) {
      return `
        <div class="section">
          <div class="section-title">Port Configuration</div>
          <p style="color: var(--primary-text-color);">Loading ports...</p>
        </div>
      `;
    }

    // Use GPIO pins if ports not loaded yet
    const portsToShow = this._ports.length > 0 ? this._ports : this._gpioPins
      .filter(p => p.can_output || p.can_input)
      .map(p => ({ port: p.gpio, gpio: p.gpio, mode: 'disabled', name: '' }));

    return `
      <div class="section">
        <div class="section-title">Port Configuration - ${this._selectedBoard}</div>
        <p style="font-size: 12px; color: var(--secondary-text-color); margin-bottom: 12px;">
          ESP32-POE-ISO GPIO pins available for IR. Click a port to configure.
        </p>
        <div class="port-grid">
          ${portsToShow.map(port => {
            const gpioPin = this._gpioPins.find(p => p.gpio === port.port || p.gpio === port.gpio);
            const assignments = this._portAssignments[port.port] || [];
            const hasAssignments = assignments.length > 0;

            return `
              <div class="port-item ${port.mode === 'ir_input' ? 'input' : port.mode === 'ir_output' ? 'output' : 'disabled'} ${hasAssignments ? 'assigned' : ''}"
                   data-action="edit-port" data-port="${port.port}"
                   title="${gpioPin ? gpioPin.notes : ''}">
                <div class="port-number">Port ${port.port}</div>
                <div class="port-gpio">${gpioPin ? gpioPin.name : `GPIO${port.port}`}</div>
                <div class="port-mode">${port.mode.replace('ir_', '').replace('_', ' ')}</div>
                <div class="port-name">${port.name || '-'}</div>
                ${hasAssignments ? `<div class="port-devices">${assignments.length} device${assignments.length > 1 ? 's' : ''}</div>` : ''}
              </div>
            `;
          }).join('')}
        </div>
        ${this._renderPortLegend()}
      </div>
    `;
  }

  _renderPortLegend() {
    return `
      <div style="margin-top: 16px; padding: 12px; background: var(--secondary-background-color, #f5f5f5); border-radius: 8px;">
        <div style="font-size: 12px; font-weight: 500; margin-bottom: 8px; color: var(--primary-text-color);">Legend</div>
        <div style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 11px; color: var(--primary-text-color);">
          <div style="display: flex; align-items: center; gap: 4px;">
            <span style="width: 12px; height: 12px; border-radius: 3px; border: 2px solid var(--success-color, #4caf50);"></span>
            IR Output
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            <span style="width: 12px; height: 12px; border-radius: 3px; border: 2px solid var(--info-color, #2196f3);"></span>
            IR Input (Receiver)
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            <span style="width: 12px; height: 12px; border-radius: 3px; background: var(--disabled-text-color, #999); opacity: 0.5;"></span>
            Disabled
          </div>
        </div>
        <div style="margin-top: 8px; font-size: 11px; color: var(--secondary-text-color);">
          Input-only GPIOs (34, 35, 36, 39) can only be used as IR receivers.
        </div>
      </div>
    `;
  }

  _renderProfilesTab() {
    return `
      <!-- Built-in Profiles Section -->
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Built-in Profiles</div>
          <span class="badge badge-success">${this._builtinProfiles.length} available</span>
        </div>

        ${this._builtinProfiles.length === 0 ? `
          <p style="color: var(--secondary-text-color); font-size: 13px;">Loading built-in profiles...</p>
        ` : `
          <div style="margin-bottom: 12px;">
            <select id="builtin-filter" data-action="filter-builtin" style="padding: 8px 12px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--input-fill-color, var(--secondary-background-color)); color: var(--primary-text-color);">
              <option value="">All Types</option>
              ${this._builtinDeviceTypes.map(t => `<option value="${t}">${this._formatDeviceType(t)}</option>`).join('')}
            </select>
          </div>
          <div class="builtin-profiles-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px;">
            ${this._builtinProfiles.map(profile => `
              <div class="list-item" style="cursor: default; flex-direction: column; align-items: flex-start; padding: 12px;">
                <div class="list-item-title" style="margin-bottom: 4px;">
                  ${profile.name}
                </div>
                <div class="list-item-subtitle" style="margin-bottom: 8px;">
                  ${profile.manufacturer} • ${this._formatDeviceType(profile.device_type)}
                </div>
                <div style="font-size: 11px; color: var(--secondary-text-color); margin-bottom: 8px;">
                  ${Object.keys(profile.codes || {}).length} commands • ${profile.protocol} protocol
                </div>
                <button class="btn btn-primary btn-small" style="width: 100%;" data-action="use-builtin-profile" data-profile-id="${profile.profile_id}">
                  Use This Profile
                </button>
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <!-- User Profiles Section -->
      <div class="section" style="margin-top: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">My Custom Profiles</div>
          <button class="btn btn-primary btn-small" data-action="create-profile">
            + New Profile
          </button>
        </div>

        ${this._profiles.length === 0 ? `
          <div class="empty-state" style="padding: 20px;">
            <p style="color: var(--secondary-text-color);">No custom profiles yet</p>
            <p style="font-size: 12px; color: var(--secondary-text-color);">Create a profile to learn IR codes from your remotes</p>
          </div>
        ` : this._profiles.map(profile => `
          <div class="list-item ${this._selectedProfile === profile.profile_id ? 'selected' : ''}"
               data-action="select-profile" data-profile-id="${profile.profile_id}">
            <div class="list-item-content">
              <div class="list-item-title">
                ${profile.name}
                <span class="badge badge-info">${profile.device_type}</span>
              </div>
              <div class="list-item-subtitle">
                ${profile.manufacturer || 'Unknown'} ${profile.model || ''} •
                ${profile.learned_commands?.length || 0} commands learned
              </div>
            </div>
            <div class="list-item-actions">
              <button class="btn btn-secondary btn-small" data-action="learn-commands" data-profile-id="${profile.profile_id}">
                Learn
              </button>
              <button class="btn btn-danger btn-small" data-action="delete-profile" data-profile-id="${profile.profile_id}">
                Delete
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  _formatDeviceType(type) {
    const typeMap = {
      'tv': 'TV',
      'cable_box': 'Cable Box',
      'soundbar': 'Soundbar',
      'streaming': 'Streaming Device',
    };
    return typeMap[type] || type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }

  _renderDevicesTab() {
    return `
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Controlled Devices</div>
          <button class="btn btn-primary btn-small" data-action="create-device">
            + New Device
          </button>
        </div>

        ${this._devices.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">📺</div>
            <p>No devices yet</p>
            <p style="font-size: 12px;">Create a device to link a profile to an IR output</p>
          </div>
        ` : this._devices.map(device => `
          <div class="list-item">
            <div class="list-item-content">
              <div class="list-item-title">
                ${device.name}
                ${device.location ? `<span class="badge badge-warning">${device.location}</span>` : ''}
              </div>
              <div class="list-item-subtitle">
                Board: ${device.board_id} • Port: ${device.output_port} • Profile: ${device.device_profile_id}
              </div>
            </div>
            <div class="list-item-actions">
              <button class="btn btn-secondary btn-small" data-action="test-device" data-device-id="${device.device_id}">
                Test
              </button>
              <button class="btn btn-secondary btn-small" data-action="edit-device" data-device-id="${device.device_id}">
                Edit
              </button>
              <button class="btn btn-danger btn-small" data-action="delete-device" data-device-id="${device.device_id}">
                Delete
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  _renderNetworkTab() {
    return `
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Network Devices</div>
          <button class="btn btn-primary btn-small" data-action="create-network-device">
            + Add Network Device
          </button>
        </div>

        ${this._networkDevices.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">🌐</div>
            <p>No network devices</p>
            <p style="font-size: 12px;">Add devices controlled via TCP/UDP (e.g., HDMI matrices)</p>
          </div>
        ` : this._networkDevices.map(device => `
          <div class="list-item ${this._selectedNetworkDevice === device.device_id ? 'selected' : ''}"
               data-action="select-network-device" data-device-id="${device.device_id}">
            <div class="list-item-content">
              <div class="list-item-title">
                ${device.name}
                <span class="badge ${device.connected ? 'badge-success' : 'badge-danger'}">
                  ${device.connected ? 'Online' : 'Offline'}
                </span>
                ${device.device_type === 'hdmi_matrix' ? '<span class="badge badge-info">Matrix</span>' : ''}
                ${device.location ? `<span class="badge badge-warning">${device.location}</span>` : ''}
              </div>
              <div class="list-item-subtitle">
                ${device.host}:${device.port} (${device.protocol.toUpperCase()}) • ${device.command_count} commands
              </div>
            </div>
            <div class="list-item-actions">
              <button class="btn btn-secondary btn-small" data-action="test-network-device" data-device-id="${device.device_id}">
                Test
              </button>
              ${device.device_type === 'hdmi_matrix' ? `
              <button class="btn btn-secondary btn-small" data-action="edit-matrix-io" data-device-id="${device.device_id}" data-device-type="network">
                Edit I/O
              </button>
              ` : ''}
              <button class="btn btn-secondary btn-small" data-action="edit-network-device" data-device-id="${device.device_id}">
                Commands
              </button>
              <button class="btn btn-danger btn-small" data-action="delete-network-device" data-device-id="${device.device_id}">
                Delete
              </button>
            </div>
          </div>
        `).join('')}

        ${this._selectedNetworkDevice ? this._renderNetworkDeviceCommands() : ''}
      </div>

      ${this._renderNetworkTestResult()}
    `;
  }

  _renderNetworkDeviceCommands() {
    const device = this._networkDevices.find(d => d.device_id === this._selectedNetworkDevice);
    if (!device) return '';

    return `
      <div class="section" style="margin-top: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Commands for ${device.name}</div>
          <button class="btn btn-primary btn-small" data-action="add-network-command" data-device-id="${device.device_id}">
            + Add Command
          </button>
        </div>
        <div class="command-list">
          ${!device.commands || Object.keys(device.commands || {}).length === 0 ? `
            <p style="color: var(--secondary-text-color); font-size: 12px;">No commands configured. Add commands to control this device.</p>
          ` : Object.entries(device.commands || {}).map(([id, cmd]) => `
            <div class="command-item" style="display: flex; align-items: center; padding: 8px; background: var(--secondary-background-color); border-radius: 6px; margin-bottom: 4px;">
              <div style="flex: 1;">
                <div style="font-weight: 500;">${cmd.name}</div>
                <div style="font-size: 11px; color: var(--secondary-text-color);">
                  ${cmd.payload} ${cmd.line_ending !== 'none' ? `[${cmd.line_ending.toUpperCase()}]` : ''}
                  ${cmd.is_input_option ? '<span style="color: var(--info-color);">[Input]</span>' : ''}
                  ${cmd.is_query ? '<span style="color: var(--warning-color);">[Query]</span>' : ''}
                </div>
              </div>
              <button class="btn btn-secondary btn-small" data-action="send-network-command"
                      data-device-id="${device.device_id}" data-command-id="${id}">
                Send
              </button>
              <button class="btn btn-danger btn-small" style="margin-left: 4px;" data-action="delete-network-command"
                      data-device-id="${device.device_id}" data-command-id="${id}">
                ×
              </button>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  _renderNetworkTestResult() {
    if (!this._networkTestResult) return '';

    const result = this._networkTestResult;
    return `
      <div class="section" style="margin-top: 16px;">
        <div class="section-title">Test Result</div>
        <div style="padding: 12px; background: var(--secondary-background-color); border-radius: 8px;
                    border-left: 4px solid ${result.success ? 'var(--success-color, #4caf50)' : 'var(--error-color, #f44336)'};">
          <div style="font-weight: 500; margin-bottom: 4px;">${result.success ? 'Success' : 'Failed'}</div>
          <div style="font-size: 12px; color: var(--secondary-text-color);">
            ${result.message || (result.response ? `Response: ${result.response}` : 'No response')}
          </div>
        </div>
      </div>
    `;
  }

  _renderSerialTab() {
    return `
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Serial Devices</div>
          <button class="btn btn-primary btn-small" data-action="create-serial-device">
            + Add Serial Device
          </button>
        </div>

        ${this._serialDevices.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">🔌</div>
            <p>No serial devices</p>
            <p style="font-size: 12px;">Add devices controlled via serial port (direct or via ESP32 bridge)</p>
          </div>
        ` : this._serialDevices.map(device => `
          <div class="list-item ${this._selectedSerialDevice === device.device_id ? 'selected' : ''}"
               data-action="select-serial-device" data-device-id="${device.device_id}">
            <div class="list-item-content">
              <div class="list-item-title">
                ${device.name}
                <span class="badge ${device.connected ? 'badge-success' : 'badge-danger'}">
                  ${device.connected ? 'Online' : 'Offline'}
                </span>
                <span class="badge badge-info">${device.mode === 'direct' ? 'Direct' : 'ESP32 Bridge'}</span>
                ${device.device_type === 'hdmi_matrix' ? '<span class="badge badge-info">Matrix</span>' : ''}
                ${device.location ? `<span class="badge badge-warning">${device.location}</span>` : ''}
              </div>
              <div class="list-item-subtitle">
                ${device.mode === 'direct' ? device.port : `${device.board_id} UART${device.uart_num}`}
                @ ${device.baud_rate} baud • ${device.command_count || 0} commands
              </div>
            </div>
            <div class="list-item-actions">
              <button class="btn btn-secondary btn-small" data-action="test-serial-device" data-device-id="${device.device_id}">
                Test
              </button>
              ${device.device_type === 'hdmi_matrix' ? `
              <button class="btn btn-secondary btn-small" data-action="edit-matrix-io" data-device-id="${device.device_id}" data-device-type="serial">
                Edit I/O
              </button>
              ` : ''}
              <button class="btn btn-secondary btn-small" data-action="edit-serial-device" data-device-id="${device.device_id}">
                Commands
              </button>
              <button class="btn btn-danger btn-small" data-action="delete-serial-device" data-device-id="${device.device_id}">
                Delete
              </button>
            </div>
          </div>
        `).join('')}

        ${this._selectedSerialDevice ? this._renderSerialDeviceCommands() : ''}
      </div>

      ${this._renderSerialTestResult()}
    `;
  }

  _renderSerialDeviceCommands() {
    const device = this._serialDevices.find(d => d.device_id === this._selectedSerialDevice);
    if (!device) return '';

    return `
      <div class="section" style="margin-top: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Commands for ${device.name}</div>
          <button class="btn btn-primary btn-small" data-action="add-serial-command" data-device-id="${device.device_id}">
            + Add Command
          </button>
        </div>
        <div class="command-list">
          ${!device.commands || Object.keys(device.commands || {}).length === 0 ? `
            <p style="color: var(--secondary-text-color); font-size: 12px;">No commands configured. Add commands to control this device.</p>
          ` : Object.entries(device.commands || {}).map(([id, cmd]) => `
            <div class="command-item" style="display: flex; align-items: center; padding: 8px; background: var(--secondary-background-color); border-radius: 6px; margin-bottom: 4px;">
              <div style="flex: 1;">
                <div style="font-weight: 500;">${cmd.name}</div>
                <div style="font-size: 11px; color: var(--secondary-text-color);">
                  ${cmd.payload} ${cmd.line_ending !== 'none' ? `[${cmd.line_ending.toUpperCase()}]` : ''}
                  ${cmd.is_input_option ? '<span style="color: var(--info-color);">[Input]</span>' : ''}
                  ${cmd.is_query ? '<span style="color: var(--warning-color);">[Query]</span>' : ''}
                </div>
              </div>
              <button class="btn btn-secondary btn-small" data-action="send-serial-command"
                      data-device-id="${device.device_id}" data-command-id="${id}">
                Send
              </button>
              <button class="btn btn-danger btn-small" style="margin-left: 4px;" data-action="delete-serial-command"
                      data-device-id="${device.device_id}" data-command-id="${id}">
                ×
              </button>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  _renderSerialTestResult() {
    if (!this._serialTestResult) return '';

    const result = this._serialTestResult;
    return `
      <div class="section" style="margin-top: 16px;">
        <div class="section-title">Test Result</div>
        <div style="padding: 12px; background: var(--secondary-background-color); border-radius: 8px;
                    border-left: 4px solid ${result.success ? 'var(--success-color, #4caf50)' : 'var(--error-color, #f44336)'};">
          <div style="font-weight: 500; margin-bottom: 4px;">${result.success ? 'Success' : 'Failed'}</div>
          <div style="font-size: 12px; color: var(--secondary-text-color);">
            ${result.message || (result.response ? `Response: ${result.response}` : 'No response')}
          </div>
        </div>
      </div>
    `;
  }

  _renderModal() {
    if (!this._modal) return '';

    switch (this._modal.type) {
      case 'create-profile':
        return this._renderCreateProfileModal();
      case 'create-device':
        return this._renderCreateDeviceModal();
      case 'learn-commands':
        return this._renderLearnCommandsModal();
      case 'edit-port':
        return this._renderEditPortModal();
      case 'remote-control':
        return this._renderRemoteControlModal();
      case 'create-network-device':
        return this._renderCreateNetworkDeviceModal();
      case 'add-network-command':
        return this._renderAddNetworkCommandModal();
      case 'create-serial-device':
        return this._renderCreateSerialDeviceModal();
      case 'add-serial-command':
        return this._renderAddSerialCommandModal();
      case 'edit-matrix-io':
        return this._renderEditMatrixIOModal();
      case 'edit-device':
        return this._renderEditDeviceModal();
      default:
        return '';
    }
  }

  _renderCreateProfileModal() {
    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()">
          <div class="modal-title">Create Device Profile</div>

          <div class="form-group">
            <label>Profile ID</label>
            <input type="text" id="profile-id" placeholder="e.g., xfinity_xr15">
          </div>

          <div class="form-group">
            <label>Profile Name</label>
            <input type="text" id="profile-name" placeholder="e.g., Xfinity XR15 Remote">
          </div>

          <div class="form-group">
            <label>Device Type</label>
            <select id="device-type">
              <option value="cable_box">Cable/Satellite Box</option>
              <option value="tv">Television</option>
              <option value="audio_receiver">Audio Receiver/Soundbar</option>
              <option value="streaming_device">Streaming Device</option>
              <option value="dvd_bluray">DVD/Blu-ray Player</option>
              <option value="projector">Projector</option>
              <option value="custom">Custom Device</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Manufacturer</label>
              <input type="text" id="manufacturer" placeholder="e.g., Comcast">
            </div>
            <div class="form-group">
              <label>Model</label>
              <input type="text" id="model" placeholder="e.g., XR15">
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-profile">Create Profile</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderCreateDeviceModal() {
    const boards = this._getBoards();

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()">
          <div class="modal-title">Create Controlled Device</div>

          <div class="form-group">
            <label>Device ID</label>
            <input type="text" id="device-id" placeholder="e.g., bar_tv_1">
          </div>

          <div class="form-group">
            <label>Device Name</label>
            <input type="text" id="device-name" placeholder="e.g., Bar TV 1">
          </div>

          <div class="form-group">
            <label>Location</label>
            <input type="text" id="device-location" placeholder="e.g., Bar Area">
          </div>

          <div class="form-group">
            <label>Profile</label>
            <select id="device-profile">
              ${this._builtinProfiles.length > 0 ? `
                <optgroup label="Built-in Profiles">
                  ${this._builtinProfiles.map(p => `
                    <option value="builtin:${p.profile_id}" ${this._modal?.preselectedProfile === `builtin:${p.profile_id}` ? 'selected' : ''}>${p.name} (${p.manufacturer})</option>
                  `).join('')}
                </optgroup>
              ` : ''}
              ${this._profiles.length > 0 ? `
                <optgroup label="My Custom Profiles">
                  ${this._profiles.map(p => `
                    <option value="${p.profile_id}" ${this._modal?.preselectedProfile === p.profile_id ? 'selected' : ''}>${p.name}</option>
                  `).join('')}
                </optgroup>
              ` : ''}
              ${this._profiles.length === 0 && this._builtinProfiles.length === 0 ? '<option value="">No profiles available</option>' : ''}
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Board</label>
              <select id="device-board" data-action="device-board-changed">
                ${boards.map(b => `
                  <option value="${b.board_id}">${b.board_name}</option>
                `).join('')}
              </select>
            </div>
            <div class="form-group">
              <label>Output Port</label>
              ${this._deviceOutputPorts.length > 0 ? `
                <select id="device-port">
                  ${this._deviceOutputPorts.map(p => `
                    <option value="${p.port}">${p.gpio_name || 'GPIO' + p.gpio} - ${p.name || 'Unnamed'}</option>
                  `).join('')}
                </select>
              ` : `
                <select id="device-port" disabled>
                  <option value="">No IR outputs configured</option>
                </select>
                <div style="font-size: 11px; color: var(--warning-color, #ff9800); margin-top: 4px;">
                  Configure an IR output port on this board first (Boards tab → Configure Ports)
                </div>
              `}
            </div>
          </div>

          ${this._renderMatrixLinkSection()}

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-device">Create Device</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderLearnCommandsModal() {
    const profile = this._profiles.find(p => p.profile_id === this._modal.profileId);
    if (!profile) return '';

    const boards = this._getBoards();
    const learnedCommands = profile.learned_commands || [];

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 700px;">
          <div class="modal-title">Learn IR Commands - ${profile.name}</div>

          ${this._learningState ? `
            <div class="learning-status ${this._learningState.saved ? 'success' : ''}">
              ${this._learningState.saved
                ? `Saved ${this._learningState.command} successfully!`
                : `Waiting for IR signal... Press the button on your remote`}
            </div>
          ` : ''}

          <div class="form-row" style="margin-bottom: 16px;">
            <div class="form-group">
              <label>Board</label>
              <select id="learn-board" data-action="learn-board-changed">
                ${boards.map(b => `
                  <option value="${b.board_id}">${b.board_name}</option>
                `).join('')}
              </select>
            </div>
            <div class="form-group">
              <label>IR Input Port</label>
              ${this._learnInputPorts.length > 0 ? `
                <select id="learn-port">
                  ${this._learnInputPorts.map(p => `
                    <option value="${p.port}">${p.gpio_name || 'GPIO' + p.gpio} - ${p.name || 'Unnamed'}</option>
                  `).join('')}
                </select>
              ` : `
                <select id="learn-port" disabled>
                  <option value="">No IR inputs configured</option>
                </select>
                <div style="font-size: 11px; color: var(--warning-color, #ff9800); margin-top: 4px;">
                  Configure an IR input port on this board first (Boards tab → Configure Ports)
                </div>
              `}
            </div>
          </div>

          <div class="section-title">Commands (click to learn)</div>
          <div class="command-grid">
            ${this._getCommandsForType(profile.device_type).map(cmd => `
              <button class="command-btn ${learnedCommands.includes(cmd) ? 'learned' : ''}"
                      data-action="learn-command" data-command="${cmd}">
                ${this._formatCommand(cmd)}
                ${learnedCommands.includes(cmd) ? ' ✓' : ''}
              </button>
            `).join('')}
          </div>

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Done</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderEditPortModal() {
    const port = this._ports.find(p => p.port === this._modal.port);
    if (!port) return '';

    const gpioPin = this._gpioPins.find(p => p.gpio === port.port || p.gpio === port.gpio);
    const assignments = this._portAssignments[port.port] || [];
    const isInputOnly = gpioPin && !gpioPin.can_output;

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()">
          <div class="modal-title">Configure Port ${port.port}</div>

          ${gpioPin ? `
            <div style="padding: 12px; background: var(--secondary-background-color, #f5f5f5); border-radius: 8px; margin-bottom: 16px;">
              <div style="font-weight: 600; color: var(--primary-text-color);">${gpioPin.name}</div>
              <div style="font-size: 12px; color: var(--secondary-text-color); margin-top: 4px;">${gpioPin.notes}</div>
              ${isInputOnly ? `
                <div style="font-size: 11px; color: var(--warning-color, #ff9800); margin-top: 8px;">
                  ⚠️ This GPIO is input-only and can only be used as an IR receiver.
                </div>
              ` : ''}
            </div>
          ` : ''}

          <div class="form-group">
            <label>Mode</label>
            <select id="port-mode">
              ${!isInputOnly ? `<option value="ir_output" ${port.mode === 'ir_output' ? 'selected' : ''}>IR Output (Transmitter)</option>` : ''}
              <option value="ir_input" ${port.mode === 'ir_input' ? 'selected' : ''}>IR Input (Receiver/Learning)</option>
              <option value="disabled" ${port.mode === 'disabled' ? 'selected' : ''}>Disabled</option>
            </select>
          </div>

          <div class="form-group">
            <label>Name</label>
            <input type="text" id="port-name" value="${port.name || ''}" placeholder="e.g., Bar TV 1">
          </div>

          ${assignments.length > 0 ? `
            <div style="margin-top: 16px;">
              <label style="display: block; margin-bottom: 8px; font-weight: 500; color: var(--primary-text-color);">
                Assigned Devices (${assignments.length})
              </label>
              <div style="background: var(--secondary-background-color, #f5f5f5); border-radius: 8px; padding: 8px;">
                ${assignments.map(a => `
                  <div style="padding: 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--divider-color, #e0e0e0);">
                    <div>
                      <div style="font-weight: 500; color: var(--primary-text-color);">${a.name}</div>
                      <div style="font-size: 11px; color: var(--secondary-text-color);">${a.location || 'No location'}</div>
                    </div>
                  </div>
                `).join('')}
              </div>
              <div style="font-size: 11px; color: var(--secondary-text-color); margin-top: 8px;">
                Multiple devices can share the same IR output port if they're in the same location.
              </div>
            </div>
          ` : ''}

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-port" data-port="${port.port}">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderRemoteControlModal() {
    const device = this._devices.find(d => d.device_id === this._modal.deviceId);
    if (!device) return '';

    // Get commands based on profile type
    const profileId = device.device_profile_id;
    let commands = [];
    let profileName = '';
    let protocol = '';

    if (profileId.startsWith('builtin:')) {
      const builtinId = profileId.substring(8);
      const profile = this._builtinProfiles.find(p => p.profile_id === builtinId);
      if (profile) {
        commands = Object.keys(profile.codes || {});
        profileName = profile.name;
        protocol = profile.protocol;
      }
    } else {
      const profile = this._profiles.find(p => p.profile_id === profileId);
      if (profile) {
        commands = profile.learned_commands || [];
        profileName = profile.name;
      }
    }

    // Group commands by category
    const powerCmds = commands.filter(c => c.includes('power'));
    const volCmds = commands.filter(c => c.includes('volume') || c === 'mute');
    const chanCmds = commands.filter(c => c.includes('channel'));
    const navCmds = commands.filter(c => ['up', 'down', 'left', 'right', 'enter', 'select', 'back', 'exit', 'menu', 'home', 'guide', 'info'].includes(c));
    const numCmds = commands.filter(c => /^[0-9]$/.test(c) || c.includes('digit'));
    const inputCmds = commands.filter(c => c.includes('hdmi') || c.includes('source') || c.includes('input') || c.includes('av') || c.includes('component'));
    const playCmds = commands.filter(c => ['play', 'pause', 'play_pause', 'stop', 'rewind', 'fast_forward', 'record', 'replay', 'skip_prev', 'skip_next'].includes(c));
    const otherCmds = commands.filter(c =>
      !powerCmds.includes(c) && !volCmds.includes(c) && !chanCmds.includes(c) &&
      !navCmds.includes(c) && !numCmds.includes(c) && !inputCmds.includes(c) && !playCmds.includes(c)
    );

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 450px;">
          <div class="modal-title" style="display: flex; justify-content: space-between; align-items: center;">
            <span>Remote: ${device.name}</span>
            <span class="badge badge-info">${profileName}</span>
          </div>

          ${protocol ? `<div style="font-size: 11px; color: var(--secondary-text-color); margin-bottom: 16px;">Protocol: ${protocol}</div>` : ''}

          ${this._modal.lastSent ? `
            <div style="padding: 8px 12px; background: var(--success-color, #4caf50); color: white; border-radius: 6px; margin-bottom: 16px; text-align: center; font-size: 13px;">
              Sent: ${this._formatCommand(this._modal.lastSent)}
            </div>
          ` : ''}

          <div class="remote-layout" style="display: flex; flex-direction: column; gap: 16px;">

            <!-- Power -->
            ${powerCmds.length > 0 ? `
              <div class="remote-section">
                <div style="display: flex; justify-content: center; gap: 8px; flex-wrap: wrap;">
                  ${powerCmds.map(cmd => `
                    <button class="remote-btn power" data-action="send-remote-cmd" data-command="${cmd}">
                      ${cmd === 'power' ? '⏻' : cmd === 'power_on' ? '⏻ On' : cmd === 'power_off' ? '⏻ Off' : this._formatCommand(cmd)}
                    </button>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Navigation D-pad -->
            ${navCmds.length > 0 ? `
              <div class="remote-section">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; max-width: 180px; margin: 0 auto;">
                  <div></div>
                  ${navCmds.includes('up') ? `<button class="remote-btn nav" data-action="send-remote-cmd" data-command="up">▲</button>` : '<div></div>'}
                  <div></div>
                  ${navCmds.includes('left') ? `<button class="remote-btn nav" data-action="send-remote-cmd" data-command="left">◀</button>` : '<div></div>'}
                  ${navCmds.includes('select') || navCmds.includes('enter') ? `<button class="remote-btn nav ok" data-action="send-remote-cmd" data-command="${navCmds.includes('select') ? 'select' : 'enter'}">OK</button>` : '<div></div>'}
                  ${navCmds.includes('right') ? `<button class="remote-btn nav" data-action="send-remote-cmd" data-command="right">▶</button>` : '<div></div>'}
                  <div></div>
                  ${navCmds.includes('down') ? `<button class="remote-btn nav" data-action="send-remote-cmd" data-command="down">▼</button>` : '<div></div>'}
                  <div></div>
                </div>
                <div style="display: flex; justify-content: center; gap: 8px; margin-top: 8px; flex-wrap: wrap;">
                  ${navCmds.filter(c => !['up','down','left','right','select','enter'].includes(c)).map(cmd => `
                    <button class="remote-btn" data-action="send-remote-cmd" data-command="${cmd}">${this._formatCommand(cmd)}</button>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Volume & Channel -->
            ${volCmds.length > 0 || chanCmds.length > 0 ? `
              <div class="remote-section" style="display: flex; justify-content: space-around;">
                ${volCmds.length > 0 ? `
                  <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                    <span style="font-size: 11px; color: var(--secondary-text-color);">Volume</span>
                    ${volCmds.includes('volume_up') ? `<button class="remote-btn vol" data-action="send-remote-cmd" data-command="volume_up">+</button>` : ''}
                    ${volCmds.includes('mute') ? `<button class="remote-btn vol mute" data-action="send-remote-cmd" data-command="mute">🔇</button>` : ''}
                    ${volCmds.includes('volume_down') ? `<button class="remote-btn vol" data-action="send-remote-cmd" data-command="volume_down">−</button>` : ''}
                  </div>
                ` : ''}
                ${chanCmds.length > 0 ? `
                  <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                    <span style="font-size: 11px; color: var(--secondary-text-color);">Channel</span>
                    ${chanCmds.includes('channel_up') ? `<button class="remote-btn chan" data-action="send-remote-cmd" data-command="channel_up">▲</button>` : ''}
                    ${chanCmds.includes('channel_down') ? `<button class="remote-btn chan" data-action="send-remote-cmd" data-command="channel_down">▼</button>` : ''}
                  </div>
                ` : ''}
              </div>
            ` : ''}

            <!-- Number Pad -->
            ${numCmds.length > 0 ? `
              <div class="remote-section">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; max-width: 180px; margin: 0 auto;">
                  ${['1','2','3','4','5','6','7','8','9','','0',''].map(n => {
                    if (n === '') return '<div></div>';
                    const cmd = numCmds.find(c => c === n || c === `digit_${n}` || c.endsWith(n));
                    return cmd ? `<button class="remote-btn num" data-action="send-remote-cmd" data-command="${cmd}">${n}</button>` : '<div></div>';
                  }).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Input Selection -->
            ${inputCmds.length > 0 ? `
              <div class="remote-section">
                <div style="font-size: 11px; color: var(--secondary-text-color); margin-bottom: 8px; text-align: center;">Inputs</div>
                <div style="display: flex; justify-content: center; gap: 6px; flex-wrap: wrap;">
                  ${inputCmds.map(cmd => `
                    <button class="remote-btn input" data-action="send-remote-cmd" data-command="${cmd}">${this._formatCommand(cmd)}</button>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Playback Controls -->
            ${playCmds.length > 0 ? `
              <div class="remote-section">
                <div style="display: flex; justify-content: center; gap: 6px; flex-wrap: wrap;">
                  ${playCmds.includes('rewind') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="rewind">⏪</button>` : ''}
                  ${playCmds.includes('play') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="play">▶</button>` : ''}
                  ${playCmds.includes('play_pause') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="play_pause">⏯</button>` : ''}
                  ${playCmds.includes('pause') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="pause">⏸</button>` : ''}
                  ${playCmds.includes('stop') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="stop">⏹</button>` : ''}
                  ${playCmds.includes('fast_forward') ? `<button class="remote-btn play" data-action="send-remote-cmd" data-command="fast_forward">⏩</button>` : ''}
                  ${playCmds.includes('record') ? `<button class="remote-btn play record" data-action="send-remote-cmd" data-command="record">⏺</button>` : ''}
                </div>
              </div>
            ` : ''}

            <!-- Other Commands -->
            ${otherCmds.length > 0 ? `
              <div class="remote-section">
                <div style="font-size: 11px; color: var(--secondary-text-color); margin-bottom: 8px; text-align: center;">Other</div>
                <div style="display: flex; justify-content: center; gap: 6px; flex-wrap: wrap;">
                  ${otherCmds.map(cmd => `
                    <button class="remote-btn" data-action="send-remote-cmd" data-command="${cmd}">${this._formatCommand(cmd)}</button>
                  `).join('')}
                </div>
              </div>
            ` : ''}

          </div>

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Close</button>
          </div>
        </div>
      </div>
    `;
  }

  _getCommandsForType(deviceType) {
    const commands = {
      cable_box: [
        'power_on', 'power_off', 'power_toggle',
        'digit_0', 'digit_1', 'digit_2', 'digit_3', 'digit_4',
        'digit_5', 'digit_6', 'digit_7', 'digit_8', 'digit_9',
        'channel_up', 'channel_down', 'channel_enter', 'channel_prev',
        'volume_up', 'volume_down', 'mute',
        'guide', 'menu', 'info', 'exit', 'back',
        'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right', 'select',
        'play', 'pause', 'stop', 'rewind', 'fast_forward', 'record',
      ],
      tv: [
        'power_on', 'power_off', 'power_toggle',
        'volume_up', 'volume_down', 'mute',
        'input_hdmi1', 'input_hdmi2', 'input_hdmi3', 'input_hdmi4',
        'input_component', 'input_composite', 'input_antenna', 'input_cycle',
        'menu', 'exit', 'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right', 'select',
      ],
      audio_receiver: [
        'power_on', 'power_off', 'power_toggle',
        'volume_up', 'volume_down', 'mute',
        'input_hdmi1', 'input_hdmi2', 'input_optical', 'input_bluetooth', 'input_cycle',
      ],
      streaming_device: [
        'power_on', 'power_off', 'power_toggle',
        'home', 'menu', 'back',
        'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right', 'select',
        'play', 'pause', 'play_pause', 'rewind', 'fast_forward',
      ],
      dvd_bluray: [
        'power_on', 'power_off', 'power_toggle', 'eject',
        'play', 'pause', 'stop', 'rewind', 'fast_forward', 'skip_prev', 'skip_next',
        'menu', 'title_menu', 'popup_menu',
        'arrow_up', 'arrow_down', 'arrow_left', 'arrow_right', 'select',
      ],
      projector: [
        'power_on', 'power_off', 'power_toggle',
        'input_hdmi1', 'input_hdmi2', 'input_vga', 'input_cycle',
        'menu', 'exit', 'freeze', 'blank',
      ],
      custom: ['power_toggle'],
    };
    return commands[deviceType] || commands.custom;
  }

  _formatCommand(cmd) {
    return cmd.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }

  _renderMatrixLinkSection() {
    // Combine network and serial devices that could be matrices
    const matrixDevices = [
      ...this._networkDevices.map(d => ({ ...d, type: 'network' })),
      ...this._serialDevices.map(d => ({ ...d, type: 'serial' })),
    ];

    if (matrixDevices.length === 0) {
      return `
        <div style="margin-top: 16px; padding: 12px; background: var(--secondary-background-color, #f5f5f5); border-radius: 8px;">
          <div style="font-weight: 500; color: var(--secondary-text-color);">Link to HDMI Matrix (Optional)</div>
          <div style="font-size: 12px; color: var(--secondary-text-color); margin-top: 4px;">
            No network or serial devices configured. Add a matrix device in the Network or Serial tab first.
          </div>
        </div>
      `;
    }

    return `
      <div style="margin-top: 16px; padding: 12px; background: var(--secondary-background-color, #f5f5f5); border-radius: 8px;">
        <div class="form-group" style="margin-bottom: 8px;">
          <label><input type="checkbox" id="device-link-matrix" data-action="toggle-matrix-link" style="margin-right: 8px; vertical-align: middle;" />Link to HDMI Matrix</label>
          <small>Link this device to an HDMI matrix output for input selection</small>
        </div>
        <div id="matrix-link-options" style="display: none;">
          <div class="form-group">
            <label>Matrix Device</label>
            <select id="device-matrix-id" data-action="matrix-device-changed">
              <option value="">Select a matrix...</option>
              ${matrixDevices.map(d => `
                <option value="${d.device_id}" data-type="${d.type}">${d.name} (${d.type === 'network' ? 'Network' : 'Serial'})</option>
              `).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Matrix Output</label>
            <select id="device-matrix-output">
              <option value="">Select matrix first...</option>
            </select>
            <small>Which matrix output is this device connected to?</small>
          </div>
        </div>
      </div>
    `;
  }

  _getMatrixOutputOptions(matrixDevice) {
    // Get input commands (is_input_option=true) from the matrix device
    // These represent available inputs that can be routed to outputs
    const commands = matrixDevice.commands || {};
    const inputCommands = Object.values(commands).filter(cmd => cmd.is_input_option);

    // For now, provide generic output options 1-8
    // In a real implementation, this could be based on the device type
    const outputs = [];
    for (let i = 1; i <= 8; i++) {
      outputs.push({ value: String(i), label: `Output ${i}` });
    }
    return outputs;
  }

  async _updateMatrixOutputOptions(matrixDeviceId) {
    const outputSelect = this.shadowRoot.getElementById('device-matrix-output');
    if (!outputSelect) return;

    if (!matrixDeviceId) {
      outputSelect.innerHTML = '<option value="">Select matrix first...</option>';
      return;
    }

    // Find the matrix device to get its type
    const matrixIdSelect = this.shadowRoot.getElementById('device-matrix-id');
    const selectedOption = matrixIdSelect?.options[matrixIdSelect.selectedIndex];
    const matrixType = selectedOption?.dataset.type;

    // Fetch matrix device to get actual output names
    try {
      const endpoint = matrixType === 'network'
        ? `/api/vda_ir_control/network_devices/${matrixDeviceId}`
        : `/api/vda_ir_control/serial_devices/${matrixDeviceId}`;

      const resp = await fetch(endpoint, {
        headers: { 'Authorization': `Bearer ${this._hass.auth.data.access_token}` },
      });

      if (resp.ok) {
        const device = await resp.json();
        const outputs = device.matrix_outputs || [];

        if (outputs.length > 0) {
          let html = '<option value="">Select output...</option>';
          outputs.forEach(o => {
            html += `<option value="${o.index}">${o.name || 'Output ' + o.index}</option>`;
          });
          outputSelect.innerHTML = html;
          return;
        }
      }
    } catch (e) {
      console.error('Failed to fetch matrix outputs:', e);
    }

    // Fallback to generic options 1-8
    let html = '<option value="">Select output...</option>';
    for (let i = 1; i <= 8; i++) {
      html += `<option value="${i}">Output ${i}</option>`;
    }
    outputSelect.innerHTML = html;
  }

  _renderCreateNetworkDeviceModal() {
    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 550px;">
          <div class="modal-header">
            <h3>Add Network Device</h3>
            <button class="modal-close" data-action="close-modal">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Device ID</label>
              <input type="text" id="network-device-id" placeholder="hdmi_matrix_1" />
              <small>Unique identifier (lowercase, underscores ok)</small>
            </div>
            <div class="form-group">
              <label>Name</label>
              <input type="text" id="network-device-name" placeholder="HDMI Matrix" />
            </div>
            <div class="form-group">
              <label>Host/IP Address</label>
              <input type="text" id="network-device-host" placeholder="192.168.1.100" />
            </div>
            <div class="form-group">
              <label>Port</label>
              <input type="number" id="network-device-port" value="8000" min="1" max="65535" />
            </div>
            <div class="form-group">
              <label>Protocol</label>
              <select id="network-device-protocol">
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
              </select>
            </div>
            <div class="form-group">
              <label>Device Type</label>
              <select id="network-device-type" data-action="network-device-type-changed">
                <option value="hdmi_matrix">HDMI Matrix</option>
                <option value="hdmi_switch">HDMI Switch</option>
                <option value="av_processor">AV Processor</option>
                <option value="custom">Custom</option>
              </select>
            </div>

            <!-- Matrix Configuration (shown when device type is hdmi_matrix) -->
            <div id="matrix-config-section" style="margin-top: 16px; padding: 12px; background: var(--secondary-background-color); border-radius: 8px;">
              <div style="font-weight: 500; margin-bottom: 12px;">Matrix Configuration</div>
              <div style="display: flex; gap: 16px;">
                <div class="form-group" style="flex: 1;">
                  <label>Number of Inputs</label>
                  <select id="matrix-input-count" data-action="matrix-config-changed">
                    ${[2,4,6,8,10,12,16].map(n => `<option value="${n}" ${n === 4 ? 'selected' : ''}>${n}</option>`).join('')}
                  </select>
                </div>
                <div class="form-group" style="flex: 1;">
                  <label>Number of Outputs</label>
                  <select id="matrix-output-count" data-action="matrix-config-changed">
                    ${[2,4,6,8,10,12,16].map(n => `<option value="${n}" ${n === 4 ? 'selected' : ''}>${n}</option>`).join('')}
                  </select>
                </div>
              </div>

              <div class="form-group" style="margin-top: 12px;">
                <label>Routing Command Template</label>
                <input type="text" id="matrix-command-template" placeholder="s in {input} av out {output}!"
                       style="font-family: monospace;" />
                <small style="display: block; margin-top: 4px; color: var(--secondary-text-color);">
                  Use <code>{input}</code> and <code>{output}</code> as placeholders. Example: <code>s in {input} av out {output}!</code> becomes <code>s in 1 av out 3!</code>
                </small>
              </div>

              <div class="form-group" style="margin-top: 8px;">
                <label>Line Ending</label>
                <select id="matrix-command-line-ending">
                  <option value="none">None</option>
                  <option value="cr">CR (\\r)</option>
                  <option value="lf">LF (\\n)</option>
                  <option value="crlf" selected>CRLF (\\r\\n)</option>
                </select>
              </div>

              <div class="form-group" style="margin-top: 12px;">
                <label>Status Query Template (optional)</label>
                <input type="text" id="matrix-status-command" placeholder="r status! or r out {output} status!"
                       style="font-family: monospace;" />
                <small style="display: block; margin-top: 4px; color: var(--secondary-text-color);">
                  Use <code>{output}</code> for per-output queries (creates one command per output), or no placeholder for a single global status command.
                </small>
              </div>

              <div id="matrix-io-names" style="margin-top: 12px;">
                ${this._renderMatrixIONames(4, 4)}
              </div>
            </div>

            <div class="form-group" style="margin-top: 16px;">
              <label>Location (optional)</label>
              <input type="text" id="network-device-location" placeholder="Living Room" />
            </div>
            <div style="margin-top: 16px;">
              <button class="btn btn-secondary" data-action="test-connection">Test Connection</button>
              <span id="test-connection-result" style="margin-left: 8px; font-size: 12px;"></span>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-network-device">Create Device</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderMatrixIONames(inputCount, outputCount) {
    return `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div>
          <div style="font-size: 12px; font-weight: 500; margin-bottom: 8px; color: var(--secondary-text-color);">Input Names</div>
          ${Array.from({length: inputCount}, (_, i) => `
            <div style="margin-bottom: 4px;">
              <input type="text" class="matrix-input-name" data-index="${i+1}"
                     placeholder="Input ${i+1}" value="HDMI ${i+1}"
                     style="width: 100%; padding: 6px 8px; font-size: 12px;" />
            </div>
          `).join('')}
        </div>
        <div>
          <div style="font-size: 12px; font-weight: 500; margin-bottom: 8px; color: var(--secondary-text-color);">Output Names</div>
          ${Array.from({length: outputCount}, (_, i) => `
            <div style="margin-bottom: 4px;">
              <input type="text" class="matrix-output-name" data-index="${i+1}"
                     placeholder="Output ${i+1}" value="Output ${i+1}"
                     style="width: 100%; padding: 6px 8px; font-size: 12px;" />
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  _toggleMatrixConfigSection(deviceType) {
    const section = this.shadowRoot.getElementById('matrix-config-section');
    if (section) {
      section.style.display = (deviceType === 'hdmi_matrix') ? 'block' : 'none';
    }
  }

  _updateMatrixIONames() {
    const inputCount = parseInt(this.shadowRoot.getElementById('matrix-input-count')?.value || 4);
    const outputCount = parseInt(this.shadowRoot.getElementById('matrix-output-count')?.value || 4);
    const container = this.shadowRoot.getElementById('matrix-io-names');
    if (container) {
      container.innerHTML = this._renderMatrixIONames(inputCount, outputCount);
    }
  }

  _getMatrixConfig() {
    const deviceType = this.shadowRoot.getElementById('network-device-type')?.value;
    if (deviceType !== 'hdmi_matrix') return null;

    const inputNames = [];
    const outputNames = [];

    this.shadowRoot.querySelectorAll('.matrix-input-name').forEach(input => {
      inputNames.push({
        index: parseInt(input.dataset.index),
        name: input.value || `HDMI ${input.dataset.index}`
      });
    });

    this.shadowRoot.querySelectorAll('.matrix-output-name').forEach(input => {
      outputNames.push({
        index: parseInt(input.dataset.index),
        name: input.value || `Output ${input.dataset.index}`
      });
    });

    const commandTemplate = this.shadowRoot.getElementById('matrix-command-template')?.value || '';
    const lineEnding = this.shadowRoot.getElementById('matrix-command-line-ending')?.value || 'crlf';
    const statusCommand = this.shadowRoot.getElementById('matrix-status-command')?.value || '';

    return {
      inputs: inputNames,
      outputs: outputNames,
      command_template: commandTemplate,
      line_ending: lineEnding,
      status_command: statusCommand
    };
  }

  _renderAddNetworkCommandModal() {
    const deviceId = this._modal?.deviceId;
    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 550px;">
          <div class="modal-header">
            <h3>Add Command</h3>
            <button class="modal-close" data-action="close-modal">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Command ID</label>
              <input type="text" id="command-id" placeholder="power_on" />
              <small>Unique identifier (lowercase, underscores ok)</small>
            </div>
            <div class="form-group">
              <label>Name</label>
              <input type="text" id="command-name" placeholder="Power On" />
            </div>
            <div class="form-group">
              <label>Payload</label>
              <input type="text" id="command-payload" placeholder="s power 1" />
              <small>The command to send (text or hex)</small>
            </div>
            <div style="display: flex; gap: 16px;">
              <div class="form-group" style="flex: 1;">
                <label>Format</label>
                <select id="command-format">
                  <option value="text">Text</option>
                  <option value="hex">Hex</option>
                </select>
              </div>
              <div class="form-group" style="flex: 1;">
                <label>Line Ending</label>
                <select id="command-line-ending">
                  <option value="none">None</option>
                  <option value="!">! (Exclamation)</option>
                  <option value="cr">CR</option>
                  <option value="lf">LF</option>
                  <option value="crlf">CRLF</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label><input type="checkbox" id="command-is-input" style="margin-right: 8px; vertical-align: middle;" />Input selection</label>
              <small>Check if this selects an input (HDMI 1, HDMI 2, etc.)</small>
            </div>
            <div class="form-group" id="input-value-group" style="display: none;">
              <label>Input Value</label>
              <input type="text" id="command-input-value" placeholder="1" />
              <small>The value this input represents (e.g., "1" for HDMI 1)</small>
            </div>
            <div class="form-group">
              <label><input type="checkbox" id="command-is-query" style="margin-right: 8px; vertical-align: middle;" />Query command</label>
              <small>Check if this queries device state</small>
            </div>
            <div class="form-group" id="response-pattern-group" style="display: none;">
              <label>Response Pattern (regex)</label>
              <input type="text" id="command-response-pattern" placeholder="input (\\d+)" />
              <small>Regex to extract state from response</small>
            </div>
            <div class="form-group" id="state-key-group" style="display: none;">
              <label>State Key</label>
              <input type="text" id="command-state-key" placeholder="current_input" />
              <small>Which state this updates (current_input, power, etc.)</small>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-network-command" data-device-id="${deviceId}">Add Command</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderCreateSerialDeviceModal() {
    const boards = this._getBoards();
    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 550px;">
          <div class="modal-header">
            <h3>Add Serial Device</h3>
            <button class="modal-close" data-action="close-modal">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Device ID</label>
              <input type="text" id="serial-device-id" placeholder="hdmi_matrix_1" />
              <small>Unique identifier (lowercase, underscores ok)</small>
            </div>
            <div class="form-group">
              <label>Name</label>
              <input type="text" id="serial-device-name" placeholder="HDMI Matrix" />
            </div>
            <div class="form-group">
              <label>Connection Mode</label>
              <select id="serial-device-mode" data-action="serial-mode-changed">
                <option value="direct">Direct (USB/Serial on Home Assistant)</option>
                <option value="bridge">ESP32 Bridge (via IR Board)</option>
              </select>
            </div>

            <!-- Direct mode fields -->
            <div id="serial-direct-fields">
              <div class="form-group">
                <label>Serial Port</label>
                <select id="serial-device-port">
                  ${this._availableSerialPorts.length === 0 ? `
                    <option value="">No ports found - enter manually</option>
                  ` : this._availableSerialPorts.map(p => `
                    <option value="${p.device}">${p.device} ${p.description ? `(${p.description})` : ''}</option>
                  `).join('')}
                </select>
                <input type="text" id="serial-device-port-manual" placeholder="/dev/ttyUSB0" style="margin-top: 4px;" />
                <small>Select from list or enter path manually</small>
              </div>
            </div>

            <!-- Bridge mode fields -->
            <div id="serial-bridge-fields" style="display: none;">
              <div class="form-group">
                <label>ESP32 Board</label>
                <select id="serial-device-board">
                  ${boards.map(b => `
                    <option value="${b.board_id}">${b.board_name} (${b.ip_address})</option>
                  `).join('')}
                  ${boards.length === 0 ? '<option value="">No boards available</option>' : ''}
                </select>
              </div>
              <div style="display: flex; gap: 16px;">
                <div class="form-group" style="flex: 1;">
                  <label>UART Number</label>
                  <select id="serial-device-uart">
                    <option value="1">UART 1</option>
                    <option value="2">UART 2</option>
                  </select>
                </div>
                <div class="form-group" style="flex: 1;">
                  <label>RX Pin (GPIO)</label>
                  <input type="number" id="serial-device-rx-pin" value="9" min="0" max="39" />
                </div>
                <div class="form-group" style="flex: 1;">
                  <label>TX Pin (GPIO)</label>
                  <input type="number" id="serial-device-tx-pin" value="10" min="0" max="39" />
                </div>
              </div>
              <small style="color: var(--secondary-text-color);">
                Olimex POE-ISO: UART1 RX=9, TX=10 | DevKit: UART1 RX=16, TX=17 or UART2 RX=25, TX=26
              </small>
            </div>

            <!-- Common fields -->
            <div style="display: flex; gap: 16px; margin-top: 16px;">
              <div class="form-group" style="flex: 1;">
                <label>Baud Rate</label>
                <select id="serial-device-baud">
                  <option value="9600">9600</option>
                  <option value="19200">19200</option>
                  <option value="38400">38400</option>
                  <option value="57600">57600</option>
                  <option value="115200" selected>115200</option>
                  <option value="230400">230400</option>
                </select>
              </div>
              <div class="form-group" style="flex: 1;">
                <label>Data Bits</label>
                <select id="serial-device-data-bits">
                  <option value="7">7</option>
                  <option value="8" selected>8</option>
                </select>
              </div>
            </div>
            <div style="display: flex; gap: 16px;">
              <div class="form-group" style="flex: 1;">
                <label>Parity</label>
                <select id="serial-device-parity">
                  <option value="N" selected>None</option>
                  <option value="E">Even</option>
                  <option value="O">Odd</option>
                </select>
              </div>
              <div class="form-group" style="flex: 1;">
                <label>Stop Bits</label>
                <select id="serial-device-stop-bits">
                  <option value="1" selected>1</option>
                  <option value="2">2</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label>Device Type</label>
              <select id="serial-device-type">
                <option value="hdmi_matrix">HDMI Matrix</option>
                <option value="hdmi_switch">HDMI Switch</option>
                <option value="av_processor">AV Processor</option>
                <option value="projector">Projector</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div class="form-group">
              <label>Location (optional)</label>
              <input type="text" id="serial-device-location" placeholder="Living Room" />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-serial-device">Create Device</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderAddSerialCommandModal() {
    const deviceId = this._modal?.deviceId;
    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 550px;">
          <div class="modal-header">
            <h3>Add Serial Command</h3>
            <button class="modal-close" data-action="close-modal">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Command ID</label>
              <input type="text" id="serial-command-id" placeholder="power_on" />
              <small>Unique identifier (lowercase, underscores ok)</small>
            </div>
            <div class="form-group">
              <label>Name</label>
              <input type="text" id="serial-command-name" placeholder="Power On" />
            </div>
            <div class="form-group">
              <label>Payload</label>
              <input type="text" id="serial-command-payload" placeholder="PWR ON" />
              <small>The command to send (text or hex)</small>
            </div>
            <div style="display: flex; gap: 16px;">
              <div class="form-group" style="flex: 1;">
                <label>Format</label>
                <select id="serial-command-format">
                  <option value="text">Text</option>
                  <option value="hex">Hex</option>
                </select>
              </div>
              <div class="form-group" style="flex: 1;">
                <label>Line Ending</label>
                <select id="serial-command-line-ending">
                  <option value="none">None</option>
                  <option value="!">! (Exclamation)</option>
                  <option value="cr">CR</option>
                  <option value="lf">LF</option>
                  <option value="crlf" selected>CRLF</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label><input type="checkbox" id="serial-command-is-input" style="margin-right: 8px; vertical-align: middle;" />Input selection</label>
              <small>Check if this selects an input (HDMI 1, HDMI 2, etc.)</small>
            </div>
            <div class="form-group" id="serial-input-value-group" style="display: none;">
              <label>Input Value</label>
              <input type="text" id="serial-command-input-value" placeholder="1" />
              <small>The value this input represents (e.g., "1" for HDMI 1)</small>
            </div>
            <div class="form-group">
              <label><input type="checkbox" id="serial-command-is-query" style="margin-right: 8px; vertical-align: middle;" />Query command</label>
              <small>Check if this queries device state</small>
            </div>
            <div class="form-group" id="serial-response-pattern-group" style="display: none;">
              <label>Response Pattern (regex)</label>
              <input type="text" id="serial-command-response-pattern" placeholder="INPUT:(\\d+)" />
              <small>Regex to extract state from response</small>
            </div>
            <div class="form-group" id="serial-state-key-group" style="display: none;">
              <label>State Key</label>
              <input type="text" id="serial-command-state-key" placeholder="current_input" />
              <small>Which state this updates (current_input, power, etc.)</small>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-serial-command" data-device-id="${deviceId}">Add Command</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderEditMatrixIOModal() {
    const matrixDevice = this._modal?.matrixDevice;
    if (!matrixDevice) return '';

    const matrixInputs = matrixDevice.matrix_inputs || [];
    const matrixOutputs = matrixDevice.matrix_outputs || [];

    // Get all controlled devices for the dropdowns
    const availableDevices = this._devices || [];

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()" style="max-width: 600px;">
          <div class="modal-header">
            <h3>Edit Matrix I/O: ${matrixDevice.name}</h3>
            <button class="modal-close" data-action="close-modal">&times;</button>
          </div>
          <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
            <p style="color: var(--secondary-text-color); font-size: 12px; margin-bottom: 16px;">
              Assign source devices to inputs and display devices to outputs. This helps organize your matrix routing.
            </p>

            <div style="margin-bottom: 24px;">
              <h4 style="margin: 0 0 12px 0; font-size: 14px; color: var(--primary-text-color);">Inputs (Sources)</h4>
              <div style="background: var(--secondary-background-color); padding: 12px; border-radius: 8px;">
                ${matrixInputs.length === 0 ? `
                  <p style="color: var(--secondary-text-color); font-size: 12px;">No inputs configured for this matrix.</p>
                ` : matrixInputs.map((input, idx) => `
                  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <span style="min-width: 80px; font-size: 13px;">Input ${input.index}:</span>
                    <input type="text" class="matrix-input-name-edit" data-index="${input.index}"
                           value="${input.name || ''}" placeholder="Input ${input.index} name"
                           style="flex: 1; padding: 6px 10px; border: 1px solid var(--divider-color); border-radius: 4px;" />
                    <select class="matrix-input-device" data-index="${input.index}"
                            style="flex: 1; padding: 6px 10px; border: 1px solid var(--divider-color); border-radius: 4px;">
                      <option value="">-- Unassigned --</option>
                      ${availableDevices.map(d => `
                        <option value="${d.device_id}" ${input.device_id === d.device_id ? 'selected' : ''}>${d.name}</option>
                      `).join('')}
                    </select>
                  </div>
                `).join('')}
              </div>
            </div>

            <div>
              <h4 style="margin: 0 0 12px 0; font-size: 14px; color: var(--primary-text-color);">Outputs (Displays)</h4>
              <div style="background: var(--secondary-background-color); padding: 12px; border-radius: 8px;">
                ${matrixOutputs.length === 0 ? `
                  <p style="color: var(--secondary-text-color); font-size: 12px;">No outputs configured for this matrix.</p>
                ` : matrixOutputs.map((output, idx) => `
                  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <span style="min-width: 80px; font-size: 13px;">Output ${output.index}:</span>
                    <input type="text" class="matrix-output-name-edit" data-index="${output.index}"
                           value="${output.name || ''}" placeholder="Output ${output.index} name"
                           style="flex: 1; padding: 6px 10px; border: 1px solid var(--divider-color); border-radius: 4px;" />
                    <select class="matrix-output-device" data-index="${output.index}"
                            style="flex: 1; padding: 6px 10px; border: 1px solid var(--divider-color); border-radius: 4px;">
                      <option value="">-- Unassigned --</option>
                      ${availableDevices.map(d => `
                        <option value="${d.device_id}" ${output.device_id === d.device_id ? 'selected' : ''}>${d.name}</option>
                      `).join('')}
                    </select>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="save-matrix-io">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  async _openEditMatrixModal(deviceId, deviceType) {
    // Load full device details with matrix_inputs and matrix_outputs
    try {
      const endpoint = deviceType === 'network'
        ? `/api/vda_ir_control/network_devices/${deviceId}`
        : `/api/vda_ir_control/serial_devices/${deviceId}`;

      // Load matrix device and controlled devices in parallel
      const [matrixResp, devicesResp] = await Promise.all([
        fetch(endpoint, {
          headers: { 'Authorization': `Bearer ${this._hass.auth.data.access_token}` }
        }),
        fetch('/api/vda_ir_control/devices', {
          headers: { 'Authorization': `Bearer ${this._hass.auth.data.access_token}` }
        })
      ]);

      if (matrixResp.ok) {
        const matrixDevice = await matrixResp.json();

        // Get controlled devices that are linked to this matrix
        let linkedDevices = [];
        if (devicesResp.ok) {
          const devicesData = await devicesResp.json();
          linkedDevices = (devicesData.devices || []).filter(d =>
            d.matrix_device_id === deviceId
          );
        }

        // Merge linked devices into matrix outputs
        // If a controlled device is linked to an output, set that output's device_id
        if (matrixDevice.matrix_outputs) {
          matrixDevice.matrix_outputs = matrixDevice.matrix_outputs.map(output => {
            // Check if any controlled device is linked to this output
            const linkedDevice = linkedDevices.find(d =>
              String(d.matrix_output) === String(output.index)
            );
            if (linkedDevice && !output.device_id) {
              // Use the linked device's ID for this output
              return { ...output, device_id: linkedDevice.device_id };
            }
            return output;
          });
        }

        this._modal = {
          type: 'edit-matrix-io',
          matrixDevice: matrixDevice,
          deviceType: deviceType,
          linkedDevices: linkedDevices  // Store for reference
        };
        this._render();
      } else {
        console.error('Failed to load matrix device');
      }
    } catch (e) {
      console.error('Failed to load matrix device:', e);
    }
  }

  async _saveMatrixIO() {
    const matrixDevice = this._modal?.matrixDevice;
    const deviceType = this._modal?.deviceType;
    if (!matrixDevice) return;

    // Gather updated inputs
    const matrixInputs = [];
    this.shadowRoot.querySelectorAll('.matrix-input-device').forEach(select => {
      const index = parseInt(select.dataset.index);
      const nameInput = this.shadowRoot.querySelector(`.matrix-input-name-edit[data-index="${index}"]`);
      matrixInputs.push({
        index: index,
        name: nameInput?.value || '',
        device_id: select.value || null
      });
    });

    // Gather updated outputs
    const matrixOutputs = [];
    this.shadowRoot.querySelectorAll('.matrix-output-device').forEach(select => {
      const index = parseInt(select.dataset.index);
      const nameInput = this.shadowRoot.querySelector(`.matrix-output-name-edit[data-index="${index}"]`);
      matrixOutputs.push({
        index: index,
        name: nameInput?.value || '',
        device_id: select.value || null
      });
    });

    try {
      const endpoint = deviceType === 'network'
        ? `/api/vda_ir_control/network_devices/${matrixDevice.device_id}`
        : `/api/vda_ir_control/serial_devices/${matrixDevice.device_id}`;

      const resp = await fetch(endpoint, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          matrix_inputs: matrixInputs,
          matrix_outputs: matrixOutputs
        })
      });

      if (resp.ok) {
        this._modal = null;
        // Reload devices to reflect changes
        if (deviceType === 'network') {
          await this._loadNetworkDevices();
        } else {
          await this._loadSerialDevices();
        }
        this._render();
      } else {
        const err = await resp.json();
        alert('Failed to save: ' + (err.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to save matrix I/O:', e);
      alert('Failed to save matrix I/O configuration');
    }
  }

  _renderEditDeviceModal() {
    const device = this._modal?.editDevice;
    if (!device) return '';

    const boards = this._getBoards();
    const matrixDevices = [
      ...this._networkDevices.map(d => ({ ...d, type: 'network' })),
      ...this._serialDevices.map(d => ({ ...d, type: 'serial' })),
    ];

    const hasMatrixLink = device.matrix_device_id ? true : false;

    return `
      <div class="modal" data-action="close-modal">
        <div class="modal-content" onclick="event.stopPropagation()">
          <div class="modal-title">Edit Device: ${device.name}</div>

          <div class="form-group">
            <label>Device ID</label>
            <input type="text" id="edit-device-id" value="${device.device_id}" disabled style="background: var(--secondary-background-color);">
            <small>Device ID cannot be changed</small>
          </div>

          <div class="form-group">
            <label>Device Name</label>
            <input type="text" id="edit-device-name" value="${device.name}" placeholder="e.g., Bar TV 1">
          </div>

          <div class="form-group">
            <label>Location</label>
            <input type="text" id="edit-device-location" value="${device.location || ''}" placeholder="e.g., Bar Area">
          </div>

          <div class="form-group">
            <label>Profile</label>
            <select id="edit-device-profile">
              ${this._builtinProfiles.length > 0 ? `
                <optgroup label="Built-in Profiles">
                  ${this._builtinProfiles.map(p => `
                    <option value="builtin:${p.profile_id}" ${device.device_profile_id === `builtin:${p.profile_id}` ? 'selected' : ''}>${p.name} (${p.manufacturer})</option>
                  `).join('')}
                </optgroup>
              ` : ''}
              ${this._profiles.length > 0 ? `
                <optgroup label="My Custom Profiles">
                  ${this._profiles.map(p => `
                    <option value="${p.profile_id}" ${device.device_profile_id === p.profile_id ? 'selected' : ''}>${p.name}</option>
                  `).join('')}
                </optgroup>
              ` : ''}
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Board</label>
              <select id="edit-device-board" data-action="edit-device-board-changed">
                ${boards.map(b => `
                  <option value="${b.board_id}" ${device.board_id === b.board_id ? 'selected' : ''}>${b.board_name}</option>
                `).join('')}
              </select>
            </div>
            <div class="form-group">
              <label>Output Port</label>
              ${this._deviceOutputPorts.length > 0 ? `
                <select id="edit-device-port">
                  ${this._deviceOutputPorts.map(p => `
                    <option value="${p.port}" ${device.output_port === p.port ? 'selected' : ''}>${p.gpio_name || 'GPIO' + p.gpio} - ${p.name || 'Unnamed'}</option>
                  `).join('')}
                </select>
              ` : `
                <select id="edit-device-port" disabled>
                  <option value="${device.output_port}">Port ${device.output_port}</option>
                </select>
              `}
            </div>
          </div>

          <!-- Matrix Link Section -->
          <div style="margin-top: 16px; padding: 12px; background: var(--secondary-background-color, #f5f5f5); border-radius: 8px;">
            <div class="form-group" style="margin-bottom: 8px;">
              <label><input type="checkbox" id="edit-device-link-matrix" ${hasMatrixLink ? 'checked' : ''} style="margin-right: 8px; vertical-align: middle;" />Link to HDMI Matrix</label>
              <small>Link this device to an HDMI matrix output for input selection</small>
            </div>
            <div id="edit-matrix-link-options" style="display: ${hasMatrixLink ? 'block' : 'none'};">
              <div class="form-group">
                <label>Matrix Device</label>
                <select id="edit-device-matrix-id">
                  <option value="">Select a matrix...</option>
                  ${matrixDevices.map(d => `
                    <option value="${d.device_id}" data-type="${d.type}" ${device.matrix_device_id === d.device_id ? 'selected' : ''}>${d.name} (${d.type === 'network' ? 'Network' : 'Serial'})</option>
                  `).join('')}
                </select>
              </div>
              <div class="form-group">
                <label>Matrix Output</label>
                <select id="edit-device-matrix-output">
                  ${this._modal?.matrixOutputOptions ? this._modal.matrixOutputOptions.map(o => `
                    <option value="${o.value}" ${device.matrix_output === o.value ? 'selected' : ''}>${o.label}</option>
                  `).join('') : `<option value="${device.matrix_output || ''}">Output ${device.matrix_output || '?'}</option>`}
                </select>
                <small>Which matrix output is this device connected to?</small>
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn btn-secondary" data-action="close-modal">Cancel</button>
            <button class="btn btn-primary" data-action="update-device">Save Changes</button>
          </div>
        </div>
      </div>
    `;
  }

  async _openEditDeviceModal(deviceId) {
    const device = this._devices.find(d => d.device_id === deviceId);
    if (!device) {
      console.error('Device not found:', deviceId);
      return;
    }

    // Load output ports for the device's board
    this._deviceOutputPorts = [];
    if (device.board_id) {
      await this._loadDeviceOutputPorts(device.board_id);
    }

    // Load matrix output options if linked to a matrix
    let matrixOutputOptions = null;
    if (device.matrix_device_id) {
      try {
        const endpoint = device.matrix_device_type === 'network'
          ? `/api/vda_ir_control/network_devices/${device.matrix_device_id}`
          : `/api/vda_ir_control/serial_devices/${device.matrix_device_id}`;

        const resp = await fetch(endpoint, {
          headers: { 'Authorization': `Bearer ${this._hass.auth.data.access_token}` }
        });

        if (resp.ok) {
          const matrixDevice = await resp.json();
          const outputs = matrixDevice.matrix_outputs || [];
          matrixOutputOptions = outputs.map(o => ({
            value: String(o.index),
            label: o.name || `Output ${o.index}`
          }));
        }
      } catch (e) {
        console.error('Failed to load matrix outputs:', e);
      }
    }

    this._modal = {
      type: 'edit-device',
      editDevice: device,
      matrixOutputOptions: matrixOutputOptions
    };
    this._render();

    // Add event listener for matrix link checkbox after render
    setTimeout(() => {
      const checkbox = this.shadowRoot.getElementById('edit-device-link-matrix');
      const optionsDiv = this.shadowRoot.getElementById('edit-matrix-link-options');
      if (checkbox && optionsDiv) {
        checkbox.addEventListener('change', (e) => {
          optionsDiv.style.display = e.target.checked ? 'block' : 'none';
        });
      }

      // Add listener for matrix device change to update outputs
      const matrixSelect = this.shadowRoot.getElementById('edit-device-matrix-id');
      if (matrixSelect) {
        matrixSelect.addEventListener('change', async (e) => {
          await this._updateEditMatrixOutputOptions(e.target.value, e.target.options[e.target.selectedIndex]?.dataset.type);
        });
      }
    }, 0);
  }

  async _updateEditMatrixOutputOptions(matrixDeviceId, matrixType) {
    const outputSelect = this.shadowRoot.getElementById('edit-device-matrix-output');
    if (!outputSelect) return;

    if (!matrixDeviceId) {
      outputSelect.innerHTML = '<option value="">Select matrix first...</option>';
      return;
    }

    try {
      const endpoint = matrixType === 'network'
        ? `/api/vda_ir_control/network_devices/${matrixDeviceId}`
        : `/api/vda_ir_control/serial_devices/${matrixDeviceId}`;

      const resp = await fetch(endpoint, {
        headers: { 'Authorization': `Bearer ${this._hass.auth.data.access_token}` }
      });

      if (resp.ok) {
        const device = await resp.json();
        const outputs = device.matrix_outputs || [];
        if (outputs.length > 0) {
          outputSelect.innerHTML = outputs.map(o => `
            <option value="${o.index}">${o.name || 'Output ' + o.index}</option>
          `).join('');
        } else {
          // Default to 8 outputs
          outputSelect.innerHTML = Array.from({length: 8}, (_, i) => `
            <option value="${i+1}">Output ${i+1}</option>
          `).join('');
        }
      }
    } catch (e) {
      console.error('Failed to fetch matrix outputs:', e);
    }
  }

  async _updateDevice() {
    const device = this._modal?.editDevice;
    if (!device) return;

    const name = this.shadowRoot.getElementById('edit-device-name')?.value?.trim();
    const location = this.shadowRoot.getElementById('edit-device-location')?.value?.trim();
    const profileId = this.shadowRoot.getElementById('edit-device-profile')?.value;
    const boardId = this.shadowRoot.getElementById('edit-device-board')?.value;
    const port = parseInt(this.shadowRoot.getElementById('edit-device-port')?.value) || 0;

    // Matrix link fields
    const linkMatrix = this.shadowRoot.getElementById('edit-device-link-matrix')?.checked;
    const matrixIdSelect = this.shadowRoot.getElementById('edit-device-matrix-id');
    const matrixOutputSelect = this.shadowRoot.getElementById('edit-device-matrix-output');

    if (!name) {
      alert('Device name is required');
      return;
    }

    const serviceData = {
      device_id: device.device_id,
      name: name,
      location: location || '',
      device_profile_id: profileId,
      board_id: boardId,
      output_port: port,
    };

    // Add matrix link data if enabled
    if (linkMatrix && matrixIdSelect && matrixIdSelect.value) {
      const selectedOption = matrixIdSelect.options[matrixIdSelect.selectedIndex];
      serviceData.matrix_device_id = matrixIdSelect.value;
      serviceData.matrix_device_type = selectedOption.dataset.type;
      serviceData.matrix_output = matrixOutputSelect ? matrixOutputSelect.value : null;
    } else {
      // Clear matrix link
      serviceData.matrix_device_id = null;
      serviceData.matrix_device_type = null;
      serviceData.matrix_output = null;
    }

    try {
      await this._hass.callService('vda_ir_control', 'update_device', serviceData);
      this._modal = null;
      await this._loadDevices();
      this._render();
    } catch (e) {
      console.error('Failed to update device:', e);
      alert('Failed to update device: ' + e.message);
    }
  }

  _attachEventListeners() {
    // Tab clicks
    this.shadowRoot.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        this._activeTab = e.target.dataset.tab;
        this._selectedBoard = null;
        this._selectedProfile = null;
        this._render();
      });
    });

    // All other actions (click)
    this.shadowRoot.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', (e) => this._handleAction(e));
    });

    // Select change events
    this.shadowRoot.querySelectorAll('select[data-action]').forEach(el => {
      el.addEventListener('change', (e) => this._handleAction(e));
    });
  }

  async _handleAction(e) {
    const action = e.target.closest('[data-action]')?.dataset.action;
    if (!action) return;

    switch (action) {
      case 'select-board':
        this._selectedBoard = e.target.closest('[data-board-id]').dataset.boardId;
        await this._loadPorts(this._selectedBoard);
        break;

      case 'configure-ports':
        this._selectedBoard = e.target.dataset.boardId;
        await this._loadPorts(this._selectedBoard);
        break;

      case 'edit-port':
        this._modal = { type: 'edit-port', port: parseInt(e.target.closest('[data-port]').dataset.port) };
        this._render();
        break;

      case 'save-port':
        await this._savePort(parseInt(e.target.dataset.port));
        break;

      case 'create-profile':
        this._modal = { type: 'create-profile' };
        this._render();
        break;

      case 'save-profile':
        await this._saveProfile();
        break;

      case 'delete-profile':
        await this._deleteProfile(e.target.dataset.profileId);
        break;

      case 'learn-commands':
        this._modal = { type: 'learn-commands', profileId: e.target.dataset.profileId };
        this._learningState = null;
        this._learnInputPorts = [];
        // Load input ports for the first board
        if (this._boards.length > 0) {
          await this._loadLearnInputPorts(this._boards[0].board_id);
        }
        this._render();
        break;

      case 'learn-command':
        await this._startLearning(e.target.dataset.command);
        break;

      case 'learn-board-changed':
        const selectedBoardId = e.target.value;
        await this._loadLearnInputPorts(selectedBoardId);
        this._render();
        break;

      case 'create-device':
        this._modal = { type: 'create-device' };
        this._deviceOutputPorts = [];
        // Load output ports for the first board
        if (this._boards.length > 0) {
          await this._loadDeviceOutputPorts(this._boards[0].board_id);
        }
        this._render();
        break;

      case 'device-board-changed':
        const deviceBoardId = e.target.value;
        await this._loadDeviceOutputPorts(deviceBoardId);
        this._render();
        break;

      case 'toggle-matrix-link':
        const matrixOptions = this.shadowRoot.getElementById('matrix-link-options');
        if (matrixOptions) {
          matrixOptions.style.display = e.target.checked ? 'block' : 'none';
        }
        break;

      case 'matrix-device-changed':
        await this._updateMatrixOutputOptions(e.target.value);
        break;

      case 'save-device':
        await this._saveDevice();
        break;

      case 'delete-device':
        await this._deleteDevice(e.target.dataset.deviceId);
        break;

      case 'edit-device':
        await this._openEditDeviceModal(e.target.dataset.deviceId);
        break;

      case 'update-device':
        await this._updateDevice();
        break;

      case 'test-device':
        // Open remote control modal instead of just testing power
        this._modal = { type: 'remote-control', deviceId: e.target.dataset.deviceId };
        this._render();
        break;

      case 'send-remote-cmd':
        await this._sendRemoteCommand(e.target.dataset.command);
        break;

      case 'close-modal':
        this._modal = null;
        this._learningState = null;
        this._render();
        break;

      case 'use-builtin-profile':
        // Open device creation modal with this profile pre-selected
        this._modal = { type: 'create-device', preselectedProfile: `builtin:${e.target.dataset.profileId}` };
        this._deviceOutputPorts = [];
        if (this._boards.length > 0) {
          await this._loadDeviceOutputPorts(this._boards[0].board_id);
        }
        this._render();
        break;

      case 'filter-builtin':
        await this._filterBuiltinProfiles(e.target.value);
        break;

      // Network device actions
      case 'create-network-device':
        this._modal = { type: 'create-network-device' };
        this._render();
        break;

      case 'select-network-device':
        this._selectedNetworkDevice = e.target.closest('[data-device-id]').dataset.deviceId;
        // Load full device details including commands
        const deviceDetails = await this._loadNetworkDevice(this._selectedNetworkDevice);
        if (deviceDetails) {
          // Update the device in our list with full commands
          const idx = this._networkDevices.findIndex(d => d.device_id === this._selectedNetworkDevice);
          if (idx >= 0) {
            this._networkDevices[idx] = { ...this._networkDevices[idx], commands: deviceDetails.commands };
          }
        }
        this._render();
        break;

      case 'edit-network-device':
        e.stopPropagation();
        this._selectedNetworkDevice = e.target.closest('[data-device-id]').dataset.deviceId;
        const details = await this._loadNetworkDevice(this._selectedNetworkDevice);
        if (details) {
          const index = this._networkDevices.findIndex(d => d.device_id === this._selectedNetworkDevice);
          if (index >= 0) {
            this._networkDevices[index] = { ...this._networkDevices[index], commands: details.commands };
          }
        }
        this._render();
        break;

      case 'delete-network-device':
        e.stopPropagation();
        if (confirm('Are you sure you want to delete this network device?')) {
          await this._deleteNetworkDevice(e.target.closest('[data-device-id]').dataset.deviceId);
        }
        break;

      case 'test-connection':
        await this._testNetworkConnection();
        break;

      case 'network-device-type-changed':
        this._toggleMatrixConfigSection(e.target.value);
        break;

      case 'matrix-config-changed':
        this._updateMatrixIONames();
        break;

      case 'save-network-device':
        await this._saveNetworkDevice();
        break;

      case 'add-network-command':
        this._modal = { type: 'add-network-command', deviceId: e.target.dataset.deviceId };
        this._render();
        // Add event listeners for checkbox toggles after render
        setTimeout(() => {
          const isInputCheckbox = this.shadowRoot.getElementById('command-is-input');
          const isQueryCheckbox = this.shadowRoot.getElementById('command-is-query');
          if (isInputCheckbox) {
            isInputCheckbox.addEventListener('change', (evt) => {
              this.shadowRoot.getElementById('input-value-group').style.display = evt.target.checked ? 'block' : 'none';
            });
          }
          if (isQueryCheckbox) {
            isQueryCheckbox.addEventListener('change', (evt) => {
              this.shadowRoot.getElementById('response-pattern-group').style.display = evt.target.checked ? 'block' : 'none';
              this.shadowRoot.getElementById('state-key-group').style.display = evt.target.checked ? 'block' : 'none';
            });
          }
        }, 0);
        break;

      case 'save-network-command':
        await this._saveNetworkCommand(e.target.dataset.deviceId);
        break;

      case 'send-network-command':
        await this._sendNetworkCommand(e.target.dataset.deviceId, e.target.dataset.commandId);
        break;

      case 'delete-network-command':
        if (confirm('Delete this command?')) {
          await this._deleteNetworkCommand(e.target.dataset.deviceId, e.target.dataset.commandId);
        }
        break;

      case 'test-network-device':
        e.stopPropagation();
        await this._testNetworkDevice(e.target.closest('[data-device-id]').dataset.deviceId);
        break;

      case 'edit-matrix-io':
        e.stopPropagation();
        const matrixDeviceId = e.target.closest('[data-device-id]').dataset.deviceId;
        const matrixDeviceType = e.target.dataset.deviceType; // 'network' or 'serial'
        await this._openEditMatrixModal(matrixDeviceId, matrixDeviceType);
        break;

      case 'save-matrix-io':
        await this._saveMatrixIO();
        break;

      // Serial device actions
      case 'create-serial-device':
        this._modal = { type: 'create-serial-device' };
        await this._loadAvailableSerialPorts();
        this._render();
        // Add mode change listener after render
        setTimeout(() => {
          const modeSelect = this.shadowRoot.getElementById('serial-device-mode');
          if (modeSelect) {
            modeSelect.addEventListener('change', (evt) => {
              const directFields = this.shadowRoot.getElementById('serial-direct-fields');
              const bridgeFields = this.shadowRoot.getElementById('serial-bridge-fields');
              if (evt.target.value === 'direct') {
                directFields.style.display = 'block';
                bridgeFields.style.display = 'none';
              } else {
                directFields.style.display = 'none';
                bridgeFields.style.display = 'block';
              }
            });
          }
        }, 0);
        break;

      case 'select-serial-device':
        this._selectedSerialDevice = e.target.closest('[data-device-id]').dataset.deviceId;
        const serialDetails = await this._loadSerialDevice(this._selectedSerialDevice);
        if (serialDetails) {
          const idx = this._serialDevices.findIndex(d => d.device_id === this._selectedSerialDevice);
          if (idx >= 0) {
            this._serialDevices[idx] = { ...this._serialDevices[idx], commands: serialDetails.commands };
          }
        }
        this._render();
        break;

      case 'edit-serial-device':
        e.stopPropagation();
        this._selectedSerialDevice = e.target.closest('[data-device-id]').dataset.deviceId;
        const serialDet = await this._loadSerialDevice(this._selectedSerialDevice);
        if (serialDet) {
          const index = this._serialDevices.findIndex(d => d.device_id === this._selectedSerialDevice);
          if (index >= 0) {
            this._serialDevices[index] = { ...this._serialDevices[index], commands: serialDet.commands };
          }
        }
        this._render();
        break;

      case 'delete-serial-device':
        e.stopPropagation();
        if (confirm('Are you sure you want to delete this serial device?')) {
          await this._deleteSerialDevice(e.target.closest('[data-device-id]').dataset.deviceId);
        }
        break;

      case 'save-serial-device':
        await this._saveSerialDevice();
        break;

      case 'add-serial-command':
        this._modal = { type: 'add-serial-command', deviceId: e.target.dataset.deviceId };
        this._render();
        // Add checkbox listeners after render
        setTimeout(() => {
          const isInputCheckbox = this.shadowRoot.getElementById('serial-command-is-input');
          const isQueryCheckbox = this.shadowRoot.getElementById('serial-command-is-query');
          if (isInputCheckbox) {
            isInputCheckbox.addEventListener('change', (evt) => {
              this.shadowRoot.getElementById('serial-input-value-group').style.display = evt.target.checked ? 'block' : 'none';
            });
          }
          if (isQueryCheckbox) {
            isQueryCheckbox.addEventListener('change', (evt) => {
              this.shadowRoot.getElementById('serial-response-pattern-group').style.display = evt.target.checked ? 'block' : 'none';
              this.shadowRoot.getElementById('serial-state-key-group').style.display = evt.target.checked ? 'block' : 'none';
            });
          }
        }, 0);
        break;

      case 'save-serial-command':
        await this._saveSerialCommand(e.target.dataset.deviceId);
        break;

      case 'send-serial-command':
        await this._sendSerialCommand(e.target.dataset.deviceId, e.target.dataset.commandId);
        break;

      case 'delete-serial-command':
        if (confirm('Delete this command?')) {
          await this._deleteSerialCommand(e.target.dataset.deviceId, e.target.dataset.commandId);
        }
        break;

      case 'test-serial-device':
        e.stopPropagation();
        await this._testSerialDevice(e.target.closest('[data-device-id]').dataset.deviceId);
        break;
    }
  }

  async _filterBuiltinProfiles(deviceType) {
    try {
      const url = deviceType
        ? `/api/vda_ir_control/builtin_profiles?device_type=${deviceType}`
        : '/api/vda_ir_control/builtin_profiles';
      const resp = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        this._builtinProfiles = data.profiles || [];
      }
      this._render();
    } catch (e) {
      console.error('Failed to filter profiles:', e);
    }
  }

  async _savePort(portNum) {
    const mode = this.shadowRoot.getElementById('port-mode').value;
    const name = this.shadowRoot.getElementById('port-name').value;

    try {
      await this._hass.callService('vda_ir_control', 'configure_port', {
        board_id: this._selectedBoard,
        port: portNum,
        mode: mode,
        name: name,
      });
      this._modal = null;
      await this._loadPorts(this._selectedBoard);
    } catch (e) {
      console.error('Failed to save port:', e);
      alert('Failed to save port configuration');
    }
  }

  async _saveProfile() {
    const profileId = this.shadowRoot.getElementById('profile-id').value;
    const name = this.shadowRoot.getElementById('profile-name').value;
    const deviceType = this.shadowRoot.getElementById('device-type').value;
    const manufacturer = this.shadowRoot.getElementById('manufacturer').value;
    const model = this.shadowRoot.getElementById('model').value;

    if (!profileId || !name) {
      alert('Please fill in Profile ID and Name');
      return;
    }

    try {
      await this._hass.callService('vda_ir_control', 'create_profile', {
        profile_id: profileId,
        name: name,
        device_type: deviceType,
        manufacturer: manufacturer,
        model: model,
      });
      this._modal = null;
      await this._loadProfiles();
      this._render();
    } catch (e) {
      console.error('Failed to create profile:', e);
      alert('Failed to create profile');
    }
  }

  async _deleteProfile(profileId) {
    if (!confirm(`Delete profile "${profileId}"?`)) return;

    try {
      await this._hass.callService('vda_ir_control', 'delete_profile', {
        profile_id: profileId,
      });
      await this._loadProfiles();
      this._render();
    } catch (e) {
      console.error('Failed to delete profile:', e);
      alert('Failed to delete profile');
    }
  }

  async _startLearning(command) {
    const boardId = this.shadowRoot.getElementById('learn-board').value;
    const portSelect = this.shadowRoot.getElementById('learn-port');
    const port = parseInt(portSelect.value);

    if (!port || isNaN(port)) {
      alert('Please configure an IR input port on this board first.\n\nGo to Boards tab → Configure Ports → Set a GPIO as "IR Input"');
      return;
    }

    try {
      await this._hass.callService('vda_ir_control', 'start_learning', {
        board_id: boardId,
        profile_id: this._modal.profileId,
        command: command,
        port: port,
        timeout: 15,
      });

      this._learningState = { command: command, active: true };
      this._render();

      // Poll for result
      this._pollLearningStatus(boardId);
    } catch (e) {
      console.error('Failed to start learning:', e);
      alert('Failed to start learning mode');
    }
  }

  async _pollLearningStatus(boardId) {
    const maxAttempts = 30;
    let attempts = 0;

    const poll = async () => {
      if (!this._learningState?.active || !this._modal) return;

      try {
        const resp = await fetch(`/api/vda_ir_control/learning/${boardId}`, {
          headers: {
            'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          },
        });

        if (!resp.ok) {
          throw new Error('Failed to get status');
        }

        const status = await resp.json();

        if (status?.saved) {
          this._learningState = { ...this._learningState, saved: true, active: false };
          await this._loadProfiles();
          this._render();
          return;
        }

        if (status?.received_code) {
          this._learningState = { ...this._learningState, saved: true, active: false };
          await this._loadProfiles();
          this._render();
          return;
        }

        attempts++;
        if (attempts < maxAttempts && this._learningState?.active) {
          setTimeout(poll, 500);
        } else {
          this._learningState = null;
          this._render();
        }
      } catch (e) {
        console.error('Failed to get learning status:', e);
      }
    };

    poll();
  }

  async _saveDevice() {
    const deviceId = this.shadowRoot.getElementById('device-id').value;
    const name = this.shadowRoot.getElementById('device-name').value;
    const location = this.shadowRoot.getElementById('device-location').value;
    const profileId = this.shadowRoot.getElementById('device-profile').value;
    const boardId = this.shadowRoot.getElementById('device-board').value;
    const portSelect = this.shadowRoot.getElementById('device-port');
    const port = parseInt(portSelect.value);

    // Matrix link fields
    const linkMatrixCheckbox = this.shadowRoot.getElementById('device-link-matrix');
    const linkMatrix = linkMatrixCheckbox ? linkMatrixCheckbox.checked : false;
    const matrixIdSelect = this.shadowRoot.getElementById('device-matrix-id');
    const matrixOutputSelect = this.shadowRoot.getElementById('device-matrix-output');

    if (!deviceId || !name || !profileId || !boardId) {
      alert('Please fill in all required fields');
      return;
    }

    if (!port || isNaN(port)) {
      alert('Please configure an IR output port on this board first.\n\nGo to Boards tab → Configure Ports → Set a GPIO as "IR Output"');
      return;
    }

    // Build service data
    const serviceData = {
      device_id: deviceId,
      name: name,
      location: location,
      profile_id: profileId,
      board_id: boardId,
      output_port: port,
    };

    // Add matrix link data if enabled
    if (linkMatrix && matrixIdSelect && matrixIdSelect.value) {
      const selectedOption = matrixIdSelect.options[matrixIdSelect.selectedIndex];
      serviceData.matrix_device_id = matrixIdSelect.value;
      serviceData.matrix_device_type = selectedOption.dataset.type;
      serviceData.matrix_output = matrixOutputSelect ? matrixOutputSelect.value : null;
    }

    try {
      await this._hass.callService('vda_ir_control', 'create_device', serviceData);
      this._modal = null;
      await this._loadDevices();
      this._render();
    } catch (e) {
      console.error('Failed to create device:', e);
      alert('Failed to create device');
    }
  }

  async _deleteDevice(deviceId) {
    if (!confirm(`Delete device "${deviceId}"?`)) return;

    try {
      await this._hass.callService('vda_ir_control', 'delete_device', {
        device_id: deviceId,
      });
      await this._loadDevices();
      this._render();
    } catch (e) {
      console.error('Failed to delete device:', e);
      alert('Failed to delete device');
    }
  }

  async _sendRemoteCommand(command) {
    if (!this._modal || !this._modal.deviceId) return;

    try {
      await this._hass.callService('vda_ir_control', 'send_command', {
        device_id: this._modal.deviceId,
        command: command,
      });
      // Update modal to show last sent command
      this._modal.lastSent = command;
      this._render();

      // Clear the "sent" indicator after 1.5 seconds
      setTimeout(() => {
        if (this._modal && this._modal.lastSent === command) {
          this._modal.lastSent = null;
          this._render();
        }
      }, 1500);
    } catch (e) {
      console.error('Failed to send command:', e);
      alert(`Failed to send ${command}`);
    }
  }

  // ========== Network Device Methods ==========

  async _testNetworkConnection() {
    const host = this.shadowRoot.getElementById('network-device-host').value;
    const port = parseInt(this.shadowRoot.getElementById('network-device-port').value);
    const protocol = this.shadowRoot.getElementById('network-device-protocol').value;
    const resultSpan = this.shadowRoot.getElementById('test-connection-result');

    if (!host || !port) {
      resultSpan.textContent = 'Enter host and port first';
      resultSpan.style.color = 'var(--error-color, #f44336)';
      return;
    }

    resultSpan.textContent = 'Testing...';
    resultSpan.style.color = 'var(--secondary-text-color)';

    try {
      const resp = await fetch('/api/vda_ir_control/test_connection', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ host, port, protocol }),
      });
      const result = await resp.json();
      resultSpan.textContent = result.success ? 'Connected!' : result.message;
      resultSpan.style.color = result.success ? 'var(--success-color, #4caf50)' : 'var(--error-color, #f44336)';
    } catch (e) {
      resultSpan.textContent = 'Test failed: ' + e.message;
      resultSpan.style.color = 'var(--error-color, #f44336)';
    }
  }

  async _saveNetworkDevice() {
    const deviceId = this.shadowRoot.getElementById('network-device-id').value.trim();
    const name = this.shadowRoot.getElementById('network-device-name').value.trim();
    const host = this.shadowRoot.getElementById('network-device-host').value.trim();
    const port = parseInt(this.shadowRoot.getElementById('network-device-port').value);
    const protocol = this.shadowRoot.getElementById('network-device-protocol').value;
    const deviceType = this.shadowRoot.getElementById('network-device-type').value;
    const location = this.shadowRoot.getElementById('network-device-location').value.trim();

    if (!deviceId || !name || !host || !port) {
      alert('Please fill in all required fields');
      return;
    }

    // Get matrix configuration if applicable
    const matrixConfig = this._getMatrixConfig();

    try {
      const resp = await fetch('/api/vda_ir_control/network_devices', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          name,
          host,
          port,
          protocol,
          device_type: deviceType,
          location,
          matrix_config: matrixConfig,
        }),
      });

      if (resp.ok) {
        this._modal = null;
        await this._loadNetworkDevices();
        this._render();
      } else {
        const error = await resp.json();
        alert('Failed to create device: ' + (error.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to create network device:', e);
      alert('Failed to create device');
    }
  }

  async _deleteNetworkDevice(deviceId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/network_devices/${deviceId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      if (resp.ok) {
        if (this._selectedNetworkDevice === deviceId) {
          this._selectedNetworkDevice = null;
        }
        await this._loadNetworkDevices();
        this._render();
      } else {
        alert('Failed to delete device');
      }
    } catch (e) {
      console.error('Failed to delete network device:', e);
      alert('Failed to delete device');
    }
  }

  async _saveNetworkCommand(deviceId) {
    const commandId = this.shadowRoot.getElementById('command-id').value.trim();
    const name = this.shadowRoot.getElementById('command-name').value.trim();
    const payload = this.shadowRoot.getElementById('command-payload').value;
    const format = this.shadowRoot.getElementById('command-format').value;
    const lineEnding = this.shadowRoot.getElementById('command-line-ending').value;
    const isInput = this.shadowRoot.getElementById('command-is-input').checked;
    const inputValue = this.shadowRoot.getElementById('command-input-value')?.value || '';
    const isQuery = this.shadowRoot.getElementById('command-is-query').checked;
    const responsePattern = this.shadowRoot.getElementById('command-response-pattern')?.value || '';
    const stateKey = this.shadowRoot.getElementById('command-state-key')?.value || '';

    if (!commandId || !name || !payload) {
      alert('Please fill in command ID, name, and payload');
      return;
    }

    try {
      const resp = await fetch(`/api/vda_ir_control/network_devices/${deviceId}/commands`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command_id: commandId,
          name,
          payload,
          format,
          line_ending: lineEnding,
          is_input_option: isInput,
          input_value: inputValue,
          is_query: isQuery,
          response_pattern: responsePattern,
          response_state_key: stateKey,
        }),
      });

      if (resp.ok) {
        this._modal = null;
        // Reload device details
        const details = await this._loadNetworkDevice(deviceId);
        if (details) {
          const index = this._networkDevices.findIndex(d => d.device_id === deviceId);
          if (index >= 0) {
            this._networkDevices[index] = { ...this._networkDevices[index], commands: details.commands };
          }
        }
        this._render();
      } else {
        const error = await resp.json();
        alert('Failed to add command: ' + (error.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to add command:', e);
      alert('Failed to add command');
    }
  }

  async _deleteNetworkCommand(deviceId, commandId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/network_devices/${deviceId}/commands/${commandId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      if (resp.ok) {
        // Reload device details
        const details = await this._loadNetworkDevice(deviceId);
        if (details) {
          const index = this._networkDevices.findIndex(d => d.device_id === deviceId);
          if (index >= 0) {
            this._networkDevices[index] = { ...this._networkDevices[index], commands: details.commands };
          }
        }
        this._render();
      } else {
        alert('Failed to delete command');
      }
    } catch (e) {
      console.error('Failed to delete command:', e);
      alert('Failed to delete command');
    }
  }

  async _sendNetworkCommand(deviceId, commandId) {
    this._networkTestResult = null;
    this._render();

    try {
      const resp = await fetch(`/api/vda_ir_control/network_devices/${deviceId}/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command_id: commandId,
          wait_for_response: true,
          timeout: 2.0,
        }),
      });

      const result = await resp.json();
      this._networkTestResult = {
        success: result.success,
        response: result.response,
        message: result.error || null,
      };
      this._render();

      // Clear result after 5 seconds
      setTimeout(() => {
        this._networkTestResult = null;
        this._render();
      }, 5000);
    } catch (e) {
      console.error('Failed to send command:', e);
      this._networkTestResult = {
        success: false,
        message: 'Failed to send command: ' + e.message,
      };
      this._render();
    }
  }

  async _testNetworkDevice(deviceId) {
    this._networkTestResult = { success: true, message: 'Checking connection...' };
    this._render();

    try {
      const device = this._networkDevices.find(d => d.device_id === deviceId);
      if (!device) return;

      const resp = await fetch('/api/vda_ir_control/test_connection', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          host: device.host,
          port: device.port,
          protocol: device.protocol,
        }),
      });

      const result = await resp.json();
      this._networkTestResult = result;
      this._render();

      // Clear result after 5 seconds
      setTimeout(() => {
        this._networkTestResult = null;
        this._render();
      }, 5000);
    } catch (e) {
      console.error('Failed to test device:', e);
      this._networkTestResult = {
        success: false,
        message: 'Test failed: ' + e.message,
      };
      this._render();
    }
  }

  // ========== Serial Device Methods ==========

  async _saveSerialDevice() {
    const deviceId = this.shadowRoot.getElementById('serial-device-id').value.trim();
    const name = this.shadowRoot.getElementById('serial-device-name').value.trim();
    const mode = this.shadowRoot.getElementById('serial-device-mode').value;
    const deviceType = this.shadowRoot.getElementById('serial-device-type').value;
    const location = this.shadowRoot.getElementById('serial-device-location').value.trim();
    const baudRate = parseInt(this.shadowRoot.getElementById('serial-device-baud').value);
    const dataBits = parseInt(this.shadowRoot.getElementById('serial-device-data-bits').value);
    const parity = this.shadowRoot.getElementById('serial-device-parity').value;
    const stopBits = parseInt(this.shadowRoot.getElementById('serial-device-stop-bits').value);

    if (!deviceId || !name) {
      alert('Please fill in Device ID and Name');
      return;
    }

    const deviceData = {
      device_id: deviceId,
      name,
      mode,
      device_type: deviceType,
      location,
      baud_rate: baudRate,
      data_bits: dataBits,
      parity,
      stop_bits: stopBits,
    };

    if (mode === 'direct') {
      const portSelect = this.shadowRoot.getElementById('serial-device-port').value;
      const portManual = this.shadowRoot.getElementById('serial-device-port-manual').value.trim();
      deviceData.port = portManual || portSelect;
      if (!deviceData.port) {
        alert('Please enter or select a serial port');
        return;
      }
    } else {
      deviceData.board_id = this.shadowRoot.getElementById('serial-device-board').value;
      deviceData.uart_num = parseInt(this.shadowRoot.getElementById('serial-device-uart').value);
      deviceData.rx_pin = parseInt(this.shadowRoot.getElementById('serial-device-rx-pin').value);
      deviceData.tx_pin = parseInt(this.shadowRoot.getElementById('serial-device-tx-pin').value);
      if (!deviceData.board_id) {
        alert('Please select an ESP32 board');
        return;
      }
    }

    try {
      const resp = await fetch('/api/vda_ir_control/serial_devices', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(deviceData),
      });

      if (resp.ok) {
        this._modal = null;
        await this._loadSerialDevices();
        this._render();
      } else {
        const error = await resp.json();
        alert('Failed to create device: ' + (error.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to create serial device:', e);
      alert('Failed to create device');
    }
  }

  async _deleteSerialDevice(deviceId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      if (resp.ok) {
        if (this._selectedSerialDevice === deviceId) {
          this._selectedSerialDevice = null;
        }
        await this._loadSerialDevices();
        this._render();
      } else {
        alert('Failed to delete device');
      }
    } catch (e) {
      console.error('Failed to delete serial device:', e);
      alert('Failed to delete device');
    }
  }

  async _saveSerialCommand(deviceId) {
    const commandId = this.shadowRoot.getElementById('serial-command-id').value.trim();
    const name = this.shadowRoot.getElementById('serial-command-name').value.trim();
    const payload = this.shadowRoot.getElementById('serial-command-payload').value;
    const format = this.shadowRoot.getElementById('serial-command-format').value;
    const lineEnding = this.shadowRoot.getElementById('serial-command-line-ending').value;
    const isInput = this.shadowRoot.getElementById('serial-command-is-input').checked;
    const inputValue = this.shadowRoot.getElementById('serial-command-input-value')?.value || '';
    const isQuery = this.shadowRoot.getElementById('serial-command-is-query').checked;
    const responsePattern = this.shadowRoot.getElementById('serial-command-response-pattern')?.value || '';
    const stateKey = this.shadowRoot.getElementById('serial-command-state-key')?.value || '';

    if (!commandId || !name || !payload) {
      alert('Please fill in command ID, name, and payload');
      return;
    }

    try {
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}/commands`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command_id: commandId,
          name,
          payload,
          format,
          line_ending: lineEnding,
          is_input_option: isInput,
          input_value: inputValue,
          is_query: isQuery,
          response_pattern: responsePattern,
          response_state_key: stateKey,
        }),
      });

      if (resp.ok) {
        this._modal = null;
        // Reload device details
        const details = await this._loadSerialDevice(deviceId);
        if (details) {
          const index = this._serialDevices.findIndex(d => d.device_id === deviceId);
          if (index >= 0) {
            this._serialDevices[index] = { ...this._serialDevices[index], commands: details.commands };
          }
        }
        this._render();
      } else {
        const error = await resp.json();
        alert('Failed to add command: ' + (error.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Failed to add command:', e);
      alert('Failed to add command');
    }
  }

  async _deleteSerialCommand(deviceId, commandId) {
    try {
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}/commands/${commandId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      if (resp.ok) {
        // Reload device details
        const details = await this._loadSerialDevice(deviceId);
        if (details) {
          const index = this._serialDevices.findIndex(d => d.device_id === deviceId);
          if (index >= 0) {
            this._serialDevices[index] = { ...this._serialDevices[index], commands: details.commands };
          }
        }
        this._render();
      } else {
        alert('Failed to delete command');
      }
    } catch (e) {
      console.error('Failed to delete serial command:', e);
      alert('Failed to delete command');
    }
  }

  async _sendSerialCommand(deviceId, commandId) {
    this._serialTestResult = null;
    this._render();

    try {
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command_id: commandId,
          wait_for_response: true,
          timeout: 2.0,
        }),
      });

      const result = await resp.json();
      this._serialTestResult = {
        success: result.success,
        response: result.response,
        message: result.error || null,
      };
      this._render();

      // Clear result after 5 seconds
      setTimeout(() => {
        this._serialTestResult = null;
        this._render();
      }, 5000);
    } catch (e) {
      console.error('Failed to send command:', e);
      this._serialTestResult = {
        success: false,
        message: 'Failed to send command: ' + e.message,
      };
      this._render();
    }
  }

  async _testSerialDevice(deviceId) {
    this._serialTestResult = { success: true, message: 'Testing connection...' };
    this._render();

    try {
      const device = this._serialDevices.find(d => d.device_id === deviceId);
      if (!device) return;

      // For serial devices, we check the state endpoint
      const resp = await fetch(`/api/vda_ir_control/serial_devices/${deviceId}/state`, {
        headers: {
          'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
        },
      });

      const result = await resp.json();
      this._serialTestResult = {
        success: result.connected,
        message: result.connected ? 'Device is connected' : 'Device is not connected',
      };
      this._render();

      // Clear result after 5 seconds
      setTimeout(() => {
        this._serialTestResult = null;
        this._render();
      }, 5000);
    } catch (e) {
      console.error('Failed to test device:', e);
      this._serialTestResult = {
        success: false,
        message: 'Test failed: ' + e.message,
      };
      this._render();
    }
  }

  getCardSize() {
    return 6;
  }
}

customElements.define('vda-ir-control-card', VDAIRControlCard);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'vda-ir-control-card',
  name: 'VDA IR Control',
  description: 'Management card for VDA IR Control system',
});
