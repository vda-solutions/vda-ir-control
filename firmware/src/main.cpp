/*
 * VDA IR Control Firmware
 * For Olimex ESP32-POE-ISO boards
 *
 * Features:
 * - Ethernet with PoE support
 * - HTTP REST API for Home Assistant integration
 * - IR transmission on configurable GPIO pins
 * - IR learning/receiving on input-only GPIO pins
 * - mDNS discovery
 * - Persistent configuration storage
 */

#include <Arduino.h>
#include <ETH.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <IRremoteESP8266.h>
#include <IRsend.h>
#include <IRrecv.h>
#include <IRutils.h>

// ============ ESP32-POE-ISO Ethernet Configuration ============
#define ETH_PHY_TYPE        ETH_PHY_LAN8720
#define ETH_PHY_ADDR        0
#define ETH_PHY_MDC         23
#define ETH_PHY_MDIO        18
#define ETH_PHY_POWER       12
#define ETH_CLK_MODE        ETH_CLOCK_GPIO17_OUT

// ============ Available GPIO Pins for IR ============
// Output-capable pins (directly from Olimex pinout)
const int OUTPUT_CAPABLE_PINS[] = {0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 32, 33};
const int OUTPUT_CAPABLE_COUNT = 12;

// Input-only pins (for IR receiver)
const int INPUT_ONLY_PINS[] = {34, 35, 36, 39};
const int INPUT_ONLY_COUNT = 4;

// ============ Port Configuration ============
struct PortConfig {
  int gpio;
  String mode;  // "ir_output", "ir_input", "disabled"
  String name;
};

#define MAX_PORTS 16
PortConfig ports[MAX_PORTS];
int portCount = 0;

// ============ IR Objects ============
IRsend* irSenders[MAX_PORTS] = {nullptr};
IRrecv* irReceiver = nullptr;
decode_results irResults;
int activeReceiverPort = -1;

// ============ Board Configuration ============
String boardId = "";
String boardName = "VDA IR Controller";
bool adopted = false;

// ============ Global Objects ============
WebServer server(8080);
Preferences preferences;
bool ethConnected = false;

// ============ Function Declarations ============
void initEthernet();
void onEthEvent(WiFiEvent_t event);
void setupWebServer();
void loadConfig();
void saveConfig();
void initPorts();
void initIRSender(int portIndex);
void initIRReceiver(int gpio);

// ============ HTTP Handlers ============
void handleInfo();
void handleStatus();
void handlePorts();
void handleConfigurePort();
void handleAdopt();
void handleSendIR();
void handleTestOutput();
void handleLearningStart();
void handleLearningStop();
void handleLearningStatus();
void handleNotFound();

// ============ Setup ============
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n========================================");
  Serial.println("   VDA IR Control Firmware v1.0.0");
  Serial.println("   For Olimex ESP32-POE-ISO");
  Serial.println("========================================\n");

  // Load saved configuration
  loadConfig();

  // Initialize Ethernet
  initEthernet();

  // Wait for Ethernet connection
  Serial.println("Waiting for Ethernet...");
  int timeout = 0;
  while (!ethConnected && timeout < 100) {
    delay(100);
    timeout++;
  }

  if (ethConnected) {
    // Setup mDNS
    String mdnsName = boardId.length() > 0 ? boardId : "vda-ir-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (MDNS.begin(mdnsName.c_str())) {
      MDNS.addService("http", "tcp", 8080);
      MDNS.addService("vda-ir", "tcp", 8080);
      Serial.printf("mDNS: %s.local\n", mdnsName.c_str());
    }

    // Setup web server
    setupWebServer();

    // Initialize ports
    initPorts();

    Serial.println("\n=== Ready! ===");
    Serial.printf("IP Address: %s\n", ETH.localIP().toString().c_str());
    Serial.printf("Board ID: %s\n", boardId.c_str());
    Serial.printf("HTTP Server: http://%s:8080\n", ETH.localIP().toString().c_str());
  } else {
    Serial.println("ERROR: Ethernet connection failed!");
  }
}

// ============ Loop ============
void loop() {
  server.handleClient();

  // Check for IR signals if receiver is active
  if (irReceiver != nullptr && irReceiver->decode(&irResults)) {
    Serial.println("IR Signal Received!");
    serialPrintUint64(irResults.value, HEX);
    Serial.println();
    irReceiver->resume();
  }

  delay(1);
}

// ============ Ethernet ============
void initEthernet() {
  WiFi.onEvent(onEthEvent);
  ETH.begin(ETH_PHY_ADDR, ETH_PHY_POWER, ETH_PHY_MDC, ETH_PHY_MDIO, ETH_PHY_TYPE, ETH_CLK_MODE);
}

void onEthEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("ETH: Started");
      ETH.setHostname(boardId.length() > 0 ? boardId.c_str() : "vda-ir-controller");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("ETH: Connected");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.printf("ETH: Got IP - %s\n", ETH.localIP().toString().c_str());
      Serial.printf("ETH: MAC - %s\n", ETH.macAddress().c_str());
      ethConnected = true;
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      Serial.println("ETH: Disconnected");
      ethConnected = false;
      break;
    case ARDUINO_EVENT_ETH_STOP:
      Serial.println("ETH: Stopped");
      ethConnected = false;
      break;
    default:
      break;
  }
}

// ============ Configuration ============
void loadConfig() {
  preferences.begin("vda-ir", true);

  boardId = preferences.getString("boardId", "");
  boardName = preferences.getString("boardName", "VDA IR Controller");
  adopted = preferences.getBool("adopted", false);
  portCount = preferences.getInt("portCount", 0);

  // Generate default board ID if not set
  if (boardId.length() == 0) {
    boardId = "vda-ir-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  }

  // Load port configurations
  for (int i = 0; i < portCount && i < MAX_PORTS; i++) {
    String key = "port" + String(i);
    ports[i].gpio = preferences.getInt((key + "_gpio").c_str(), 0);
    ports[i].mode = preferences.getString((key + "_mode").c_str(), "disabled");
    ports[i].name = preferences.getString((key + "_name").c_str(), "");
  }

  // If no ports configured, set up defaults
  if (portCount == 0) {
    // Add all available GPIO pins as disabled by default
    for (int i = 0; i < OUTPUT_CAPABLE_COUNT && portCount < MAX_PORTS; i++) {
      ports[portCount].gpio = OUTPUT_CAPABLE_PINS[i];
      ports[portCount].mode = "disabled";
      ports[portCount].name = "";
      portCount++;
    }
    for (int i = 0; i < INPUT_ONLY_COUNT && portCount < MAX_PORTS; i++) {
      ports[portCount].gpio = INPUT_ONLY_PINS[i];
      ports[portCount].mode = "disabled";
      ports[portCount].name = "";
      portCount++;
    }
  }

  preferences.end();

  Serial.printf("Loaded config: boardId=%s, ports=%d\n", boardId.c_str(), portCount);
}

void saveConfig() {
  preferences.begin("vda-ir", false);

  preferences.putString("boardId", boardId);
  preferences.putString("boardName", boardName);
  preferences.putBool("adopted", adopted);
  preferences.putInt("portCount", portCount);

  for (int i = 0; i < portCount; i++) {
    String key = "port" + String(i);
    preferences.putInt((key + "_gpio").c_str(), ports[i].gpio);
    preferences.putString((key + "_mode").c_str(), ports[i].mode);
    preferences.putString((key + "_name").c_str(), ports[i].name);
  }

  preferences.end();
  Serial.println("Configuration saved");
}

// ============ Port Initialization ============
void initPorts() {
  for (int i = 0; i < portCount; i++) {
    if (ports[i].mode == "ir_output") {
      initIRSender(i);
    } else if (ports[i].mode == "ir_input") {
      initIRReceiver(ports[i].gpio);
    }
  }
}

void initIRSender(int portIndex) {
  if (irSenders[portIndex] != nullptr) {
    delete irSenders[portIndex];
  }
  irSenders[portIndex] = new IRsend(ports[portIndex].gpio);
  irSenders[portIndex]->begin();
  Serial.printf("IR Sender initialized on GPIO%d\n", ports[portIndex].gpio);
}

void initIRReceiver(int gpio) {
  if (irReceiver != nullptr) {
    delete irReceiver;
  }
  irReceiver = new IRrecv(gpio);
  irReceiver->enableIRIn();
  activeReceiverPort = gpio;
  Serial.printf("IR Receiver initialized on GPIO%d\n", gpio);
}

// ============ Web Server Setup ============
void setupWebServer() {
  server.on("/info", HTTP_GET, handleInfo);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/ports", HTTP_GET, handlePorts);
  server.on("/ports/configure", HTTP_POST, handleConfigurePort);
  server.on("/adopt", HTTP_POST, handleAdopt);
  server.on("/send_ir", HTTP_POST, handleSendIR);
  server.on("/test_output", HTTP_POST, handleTestOutput);
  server.on("/learning/start", HTTP_POST, handleLearningStart);
  server.on("/learning/stop", HTTP_POST, handleLearningStop);
  server.on("/learning/status", HTTP_GET, handleLearningStatus);
  server.onNotFound(handleNotFound);

  server.enableCORS(true);
  server.begin();
  Serial.println("HTTP server started on port 8080");
}

// ============ HTTP Handlers ============
void handleInfo() {
  JsonDocument doc;

  doc["board_id"] = boardId;
  doc["board_name"] = boardName;
  doc["mac_address"] = ETH.macAddress();
  doc["ip_address"] = ETH.localIP().toString();
  doc["firmware_version"] = "1.0.0";
  doc["adopted"] = adopted;
  doc["total_ports"] = portCount;

  int outputCount = 0, inputCount = 0;
  for (int i = 0; i < portCount; i++) {
    if (ports[i].mode == "ir_output") outputCount++;
    if (ports[i].mode == "ir_input") inputCount++;
  }
  doc["output_count"] = outputCount;
  doc["input_count"] = inputCount;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleStatus() {
  JsonDocument doc;

  doc["board_id"] = boardId;
  doc["online"] = true;
  doc["uptime_seconds"] = millis() / 1000;
  doc["free_heap"] = ESP.getFreeHeap();
  doc["eth_connected"] = ethConnected;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handlePorts() {
  JsonDocument doc;

  doc["total_ports"] = portCount;
  JsonArray portsArray = doc["ports"].to<JsonArray>();

  for (int i = 0; i < portCount; i++) {
    JsonObject port = portsArray.add<JsonObject>();
    port["port"] = ports[i].gpio;
    port["gpio"] = ports[i].gpio;
    port["mode"] = ports[i].mode;
    port["name"] = ports[i].name;
    port["gpio_name"] = "GPIO" + String(ports[i].gpio);

    // Check if input-only
    bool isInputOnly = false;
    for (int j = 0; j < INPUT_ONLY_COUNT; j++) {
      if (INPUT_ONLY_PINS[j] == ports[i].gpio) {
        isInputOnly = true;
        break;
      }
    }
    port["can_input"] = true;
    port["can_output"] = !isInputOnly;
  }

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleConfigurePort() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, server.arg("plain"));

  if (error) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  int gpio = doc["port"] | -1;
  String mode = doc["mode"] | "";
  String name = doc["name"] | "";

  // Find port by GPIO
  int portIndex = -1;
  for (int i = 0; i < portCount; i++) {
    if (ports[i].gpio == gpio) {
      portIndex = i;
      break;
    }
  }

  if (portIndex == -1) {
    server.send(400, "application/json", "{\"error\":\"Invalid GPIO\"}");
    return;
  }

  // Check if trying to set output on input-only pin
  if (mode == "ir_output") {
    for (int i = 0; i < INPUT_ONLY_COUNT; i++) {
      if (INPUT_ONLY_PINS[i] == gpio) {
        server.send(400, "application/json", "{\"error\":\"GPIO is input-only\"}");
        return;
      }
    }
  }

  // Update port config
  ports[portIndex].mode = mode;
  ports[portIndex].name = name;

  // Reinitialize port
  if (mode == "ir_output") {
    initIRSender(portIndex);
  } else if (mode == "ir_input") {
    initIRReceiver(gpio);
  }

  // Save config
  saveConfig();

  JsonDocument response;
  response["success"] = true;
  response["port"] = gpio;
  response["mode"] = mode;
  response["name"] = name;

  String responseStr;
  serializeJson(response, responseStr);
  server.send(200, "application/json", responseStr);
}

void handleAdopt() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  JsonDocument doc;
  deserializeJson(doc, server.arg("plain"));

  String newBoardId = doc["board_id"] | "";
  String newBoardName = doc["board_name"] | "";

  if (newBoardId.length() == 0) {
    server.send(400, "application/json", "{\"error\":\"board_id required\"}");
    return;
  }

  boardId = newBoardId;
  boardName = newBoardName.length() > 0 ? newBoardName : boardId;
  adopted = true;

  saveConfig();

  // Update mDNS
  MDNS.end();
  MDNS.begin(boardId.c_str());
  MDNS.addService("http", "tcp", 8080);

  JsonDocument response;
  response["success"] = true;
  response["board_id"] = boardId;

  String responseStr;
  serializeJson(response, responseStr);
  server.send(200, "application/json", responseStr);

  Serial.printf("Board adopted as: %s (%s)\n", boardId.c_str(), boardName.c_str());
}

void handleSendIR() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  JsonDocument doc;
  deserializeJson(doc, server.arg("plain"));

  int output = doc["output"] | -1;
  String code = doc["code"] | "";
  String protocol = doc["protocol"] | "nec";

  // Find port index
  int portIndex = -1;
  for (int i = 0; i < portCount; i++) {
    if (ports[i].gpio == output && ports[i].mode == "ir_output") {
      portIndex = i;
      break;
    }
  }

  if (portIndex == -1 || irSenders[portIndex] == nullptr) {
    server.send(400, "application/json", "{\"error\":\"Invalid output or not configured\"}");
    return;
  }

  // Parse and send IR code
  uint64_t codeValue = strtoull(code.c_str(), nullptr, 16);

  if (protocol == "nec") {
    irSenders[portIndex]->sendNEC(codeValue);
  } else if (protocol == "sony") {
    irSenders[portIndex]->sendSony(codeValue);
  } else if (protocol == "rc5") {
    irSenders[portIndex]->sendRC5(codeValue);
  } else if (protocol == "rc6") {
    irSenders[portIndex]->sendRC6(codeValue);
  } else {
    // Send as raw NEC by default
    irSenders[portIndex]->sendNEC(codeValue);
  }

  Serial.printf("Sent IR code 0x%llX via GPIO%d\n", codeValue, output);

  server.send(200, "application/json", "{\"success\":true}");
}

void handleTestOutput() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  JsonDocument doc;
  deserializeJson(doc, server.arg("plain"));

  int output = doc["output"] | -1;
  int duration = doc["duration_ms"] | 500;

  // Find port
  int portIndex = -1;
  for (int i = 0; i < portCount; i++) {
    if (ports[i].gpio == output) {
      portIndex = i;
      break;
    }
  }

  if (portIndex == -1) {
    server.send(400, "application/json", "{\"error\":\"Invalid output\"}");
    return;
  }

  // Send test pattern (simple carrier burst)
  pinMode(output, OUTPUT);
  for (int i = 0; i < duration; i++) {
    digitalWrite(output, HIGH);
    delayMicroseconds(13);
    digitalWrite(output, LOW);
    delayMicroseconds(13);
  }

  Serial.printf("Test signal sent on GPIO%d for %dms\n", output, duration);

  server.send(200, "application/json", "{\"success\":true}");
}

void handleLearningStart() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"No body\"}");
    return;
  }

  JsonDocument doc;
  deserializeJson(doc, server.arg("plain"));

  int port = doc["port"] | 34;  // Default to GPIO34

  // Initialize receiver on specified port
  initIRReceiver(port);

  JsonDocument response;
  response["success"] = true;
  response["port"] = port;

  String responseStr;
  serializeJson(response, responseStr);
  server.send(200, "application/json", responseStr);

  Serial.printf("Learning mode started on GPIO%d\n", port);
}

void handleLearningStop() {
  if (irReceiver != nullptr) {
    irReceiver->disableIRIn();
  }
  activeReceiverPort = -1;

  server.send(200, "application/json", "{\"success\":true}");
  Serial.println("Learning mode stopped");
}

void handleLearningStatus() {
  JsonDocument doc;

  doc["active"] = (activeReceiverPort >= 0);
  doc["port"] = activeReceiverPort;

  // Check if we received a code
  if (irReceiver != nullptr && irReceiver->decode(&irResults)) {
    JsonObject receivedCode = doc["received_code"].to<JsonObject>();
    receivedCode["protocol"] = typeToString(irResults.decode_type);
    receivedCode["code"] = "0x" + uint64ToString(irResults.value, HEX);
    receivedCode["bits"] = irResults.bits;

    irReceiver->resume();
  }

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"Not found\"}");
}
