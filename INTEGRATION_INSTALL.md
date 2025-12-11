# Installing VDA IR Control Integration in Test HA

## Quick Setup

### 1. Copy Integration to Home Assistant
```bash
# Create custom_components directory in HA config
docker-compose exec homeassistant mkdir -p /config/custom_components

# Copy the integration
docker-compose exec homeassistant cp -r /config/homeassistant/vda_ir_control /config/custom_components/
```

### 2. Restart Home Assistant
```bash
docker-compose restart homeassistant

# Or via HA UI: Settings → System → System Options → Restart Home Assistant
```

### 3. Add Integration in Home Assistant UI
1. Go to `http://localhost:8123`
2. Click Settings → Devices & Services
3. Click "Create Integration"
4. Search for "VDA IR Control"
5. Click on it
6. Follow the setup wizard

### 4. Test with Service Calls
Once integration is installed, you can test services in Developer Tools:

```yaml
# Test service: discover boards
service: vda_ir_control.discover_boards
data:
  subnet: "192.168.1"
```

## Local Development Setup

### Option A: Copy to HA Container (Recommended for Testing)
```bash
# From repo root
docker-compose exec homeassistant bash

# Inside container:
cp -r /config/homeassistant/vda_ir_control /config/custom_components/
exit

# Restart HA
docker-compose restart homeassistant
```

### Option B: Direct File Mapping (For Active Development)
Edit `docker-compose.yml`:
```yaml
homeassistant:
  volumes:
    - ./config:/config
    - ./homeassistant/vda_ir_control:/config/custom_components/vda_ir_control
```

Then restart containers:
```bash
docker-compose down
docker-compose up -d
```

## File Structure for Custom Component

Home Assistant expects custom components at:
```
~/.homeassistant/
└── custom_components/
    └── vda_ir_control/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── services.py
        ├── switch.py
        ├── strings.json
        ├── manifest.json
        ├── py.typed
        └── strings/
            └── en.json (optional, for translations)
```

## Checking Installation

### View HA Logs
```bash
docker-compose logs -f homeassistant | grep vda_ir_control
```

### Check if Integration Loaded
1. Go to Settings → Devices & Services
2. Look for "VDA IR Control" in the integrations list
3. If present, it loaded successfully

### Check Configuration Entries
```bash
docker-compose exec homeassistant cat /config/.storage/core.config_entries
```

Look for entries with `domain: vda_ir_control`

## Troubleshooting

### Integration Not Appearing in Setup
1. **Check manifest.json syntax**
   ```bash
   docker-compose exec homeassistant python3 -m json.tool /config/custom_components/vda_ir_control/manifest.json
   ```

2. **Check HA logs for import errors**
   ```bash
   docker-compose logs homeassistant | grep -i "vda_ir_control"
   ```

3. **Restart HA**
   ```bash
   docker-compose restart homeassistant
   ```

### Config Flow Errors
1. Verify all imports in `config_flow.py` are correct
2. Check `const.py` has all required constants
3. Look for Python syntax errors:
   ```bash
   docker-compose exec homeassistant python3 -m py_compile /config/custom_components/vda_ir_control/*.py
   ```

### Services Not Registering
1. Check `services.py` for syntax errors
2. Verify `async_setup_services()` is called in `__init__.py`
3. Check HA logs for registration errors

## Testing Without Physical Boards

### Mock Board HTTP Server
Create a simple mock server for testing:

```python
# Create a file: test_mock_board.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MockBoardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/info':
            response = {
                "board_id": "ir-test-board",
                "board_name": "Test Board",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "ip_address": "127.0.0.1",
                "firmware_version": "1.0.0",
                "output_count": 5
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/adopt':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8080), MockBoardHandler)
    print("Mock board running on http://127.0.0.1:8080")
    server.serve_forever()
```

Run it:
```bash
python3 test_mock_board.py
```

Then discover/adopt at `127.0.0.1:8080`

## Development Workflow

1. **Make changes** to integration files
2. **Reload custom components** (if using direct file mapping):
   - Settings → Developer Tools → YAML → Custom Components Reload
   - Or: `docker-compose restart homeassistant`
3. **Test** via UI or Developer Tools
4. **Check logs** for errors:
   ```bash
   docker-compose logs homeassistant
   ```

## Next Steps

1. Test integration loads in HA
2. Create test fixtures for config flow testing
3. Implement board discovery (mDNS or subnet scanning)
4. Test service handlers
5. Create admin dashboard Lovelace cards
