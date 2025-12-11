"""Constants for VDA IR Control integration."""

DOMAIN = "vda_ir_control"
PLATFORM_SWITCH = "switch"
PLATFORM_BUTTON = "button"

# Configuration keys
CONF_MQTT_BROKER = "mqtt_broker"
CONF_MQTT_PORT = "mqtt_port"
CONF_DISCOVERY_SUBNET = "discovery_subnet"

# Default values
DEFAULT_MQTT_PORT = 1883
DEFAULT_DISCOVERY_SUBNET = "192.168.1"

# MQTT Topic patterns
MQTT_BASE = "home/ir"
MQTT_DISCOVERY = f"{MQTT_BASE}/+/discover"
MQTT_STATUS = f"{MQTT_BASE}/{{board_id}}/status"
MQTT_CONTROL = f"{MQTT_BASE}/{{board_id}}/output_{{output}}/set"

# Attributes
ATTR_BOARD_ID = "board_id"
ATTR_BOARD_NAME = "board_name"
ATTR_MAC_ADDRESS = "mac_address"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_OUTPUT_COUNT = "output_count"
ATTR_IP_ADDRESS = "ip_address"
