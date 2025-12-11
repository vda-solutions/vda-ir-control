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
      this._loadDevices(),
      this._loadGPIOPins(),
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
        .modal {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .modal-content {
          background: var(--ha-card-background, var(--card-background-color, white));
          color: var(--primary-text-color, #212121);
          border-radius: 12px;
          padding: 24px;
          max-width: 500px;
          width: 90%;
          max-height: 80vh;
          overflow-y: auto;
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
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="section-title" style="margin-bottom: 0;">Device Profiles</div>
          <button class="btn btn-primary btn-small" data-action="create-profile">
            + New Profile
          </button>
        </div>

        ${this._profiles.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <p>No profiles yet</p>
            <p style="font-size: 12px;">Create a profile to start learning IR codes</p>
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
              <button class="btn btn-danger btn-small" data-action="delete-device" data-device-id="${device.device_id}">
                Delete
              </button>
            </div>
          </div>
        `).join('')}
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
              ${this._profiles.length > 0 ? this._profiles.map(p => `
                <option value="${p.profile_id}">${p.name}</option>
              `).join('') : '<option value="">No profiles - create one first</option>'}
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

      case 'save-device':
        await this._saveDevice();
        break;

      case 'delete-device':
        await this._deleteDevice(e.target.dataset.deviceId);
        break;

      case 'test-device':
        await this._testDevice(e.target.dataset.deviceId);
        break;

      case 'close-modal':
        this._modal = null;
        this._learningState = null;
        this._render();
        break;
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

    if (!deviceId || !name || !profileId || !boardId) {
      alert('Please fill in all required fields');
      return;
    }

    if (!port || isNaN(port)) {
      alert('Please configure an IR output port on this board first.\n\nGo to Boards tab → Configure Ports → Set a GPIO as "IR Output"');
      return;
    }

    try {
      await this._hass.callService('vda_ir_control', 'create_device', {
        device_id: deviceId,
        name: name,
        location: location,
        profile_id: profileId,
        board_id: boardId,
        output_port: port,
      });
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

  async _testDevice(deviceId) {
    const device = this._devices.find(d => d.device_id === deviceId);
    if (!device) return;

    try {
      await this._hass.callService('vda_ir_control', 'send_command', {
        device_id: deviceId,
        command: 'power_toggle',
      });
      alert('Sent power_toggle command');
    } catch (e) {
      console.error('Failed to test device:', e);
      alert('Failed to send command (maybe power_toggle not learned yet)');
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
