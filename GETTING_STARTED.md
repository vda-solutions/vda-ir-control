# Getting Started with VDA IR Control

## Test Environment Setup

### Home Assistant & MQTT (Docker)

This project includes Docker Compose setup for Home Assistant and Mosquitto MQTT broker.

#### Prerequisites
- Docker & Docker Compose installed
- On macOS: Colima (lightweight Docker) or Docker Desktop
- Internet connection for initial setup

#### Starting the Services

1. **Start Colima** (macOS only):
   ```bash
   colima start
   ```

2. **Start Home Assistant and MQTT**:
   ```bash
   cd /Users/vinny/vda-ir-control
   docker compose up -d
   ```

3. **Wait for startup** (5-10 minutes on first run):
   ```bash
   docker compose logs homeassistant
   ```

4. **Access Home Assistant**:
   - URL: `http://localhost:8123`
   - Complete onboarding wizard
   - Create admin user

#### Stopping Services
```bash
docker compose down
```

#### Viewing Logs
```bash
# All services
docker compose logs -f

# Just Home Assistant
docker compose logs -f homeassistant

# Just MQTT
docker compose logs -f mosquitto
```

### Directory Structure

```
config/                    # Home Assistant configuration
├── configuration.yaml     # Main HA config
├── automations.yaml
├── scripts.yaml
├── scenes.yaml
└── groups.yaml

mosquitto/                 # MQTT Broker config
├── config/
│   └── mosquitto.conf
├── data/                  # Persistent data
└── log/                   # Logs

firmware/                  # ESP firmware (to be created)
homeassistant/             # Custom HA integration (to be created)
database/                  # IR code database (to be created)
```

### Firmware Development

See `CLAUDE.md` for firmware setup with PlatformIO, Ethernet, and MQTT configuration.

### Useful Commands

**Check if Docker is running:**
```bash
docker ps
```

**Manual MQTT publish (for testing):**
```bash
docker compose exec mosquitto mosquitto_pub -t home/ir/test -m "test message"
```

**Connect to Home Assistant container shell:**
```bash
docker compose exec homeassistant bash
```

**View HA file structure:**
```bash
docker compose exec homeassistant ls -la /config
```

### Troubleshooting

**"Failed to connect to Docker daemon"**
- On macOS: Run `colima start` first
- On Linux: Ensure Docker daemon is running (`sudo systemctl start docker`)

**Home Assistant stuck on "Starting"**
- Wait longer (can take 5-10 minutes)
- Check logs: `docker compose logs homeassistant`
- Ensure sufficient disk space

**MQTT not connecting**
- Verify mosquitto is running: `docker compose ps`
- Check configuration in `config/configuration.yaml`

**Port already in use**
- Edit `docker-compose.yml` to use different ports (e.g., 8124 instead of 8123)
