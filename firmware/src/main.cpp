#include <Arduino.h>
#include <WiFi.h>
#include <ETH.h>
#include <MDNS.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ============ Configuration ============

// Ethernet / PoE Configuration
#define ETH_ADDR        0
#define ETH_POWER_PIN   -1  // Set to -1 if power not controlled
#define ETH_MDC_PIN     23
#define ETH_MDIO_PIN    18
#define ETH_TYPE        ETH_PHY_LAN8720
#define ETH_CLK_MODE    ETH_CLOCK_GPIO0_IN

// MQTT Configuration
#define MQTT_BROKER   "mosquitto"
#define MQTT_PORT     1883
#define MQTT_CLIENT_ID "ir-controller-default"

// Board Configuration (will be overridden on adoption)
String boardID = "ir-controller-default";
String boardName = "Default IR Controller";

// ============ Global Objects ============
EthernetClient ethClient;
PubSubClient mqttClient(ethClient);

// ============ Function Declarations ============
void initEthernet();
void onETHEvent(WiFiEvent_t event);
void setupMDNS();
void setupMQTT();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);

// ============ Setup ============
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n=== VDA IR Control Firmware ===");
  Serial.println("Initializing...");

  // Initialize Ethernet
  initEthernet();

  // Setup MDNS
  setupMDNS();

  // Setup MQTT
  setupMQTT();

  Serial.println("Setup complete!");
}

// ============ Loop ============
void loop() {
  // Maintain MQTT connection
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  delay(10);
}

// ============ Ethernet Initialization ============
void initEthernet() {
  Serial.println("Initializing Ethernet...");

  // Register event handler
  WiFi.onEvent(onETHEvent);

  // Start Ethernet
  ETH.begin(ETH_ADDR, ETH_POWER_PIN, ETH_MDC_PIN, ETH_MDIO_PIN, ETH_TYPE, ETH_CLK_MODE);

  Serial.println("Waiting for Ethernet connection...");
  int timeout = 0;
  while (!ETH.linkUp() && timeout < 100) {
    delay(100);
    timeout++;
  }

  if (ETH.linkUp()) {
    Serial.print("Ethernet connected! IP: ");
    Serial.println(ETH.localIP());
  } else {
    Serial.println("Failed to connect to Ethernet");
  }
}

// ============ Ethernet Event Handler ============
void onETHEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("ETH Started");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("ETH Connected");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.print("ETH Got IP: ");
      Serial.println(ETH.localIP());
      break;
    case ARDUINO_EVENT_ETH_LOST_IP:
      Serial.println("ETH Lost IP");
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      Serial.println("ETH Disconnected");
      break;
    case ARDUINO_EVENT_ETH_STOP:
      Serial.println("ETH Stopped");
      break;
    default:
      break;
  }
}

// ============ mDNS Setup ============
void setupMDNS() {
  Serial.println("Setting up mDNS...");

  if (!MDNS.begin(boardID.c_str())) {
    Serial.println("Failed to setup mDNS!");
  } else {
    MDNS.addService("http", "tcp", 80);
    Serial.print("mDNS hostname: ");
    Serial.println(boardID + ".local");
  }
}

// ============ MQTT Setup ============
void setupMQTT() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

// ============ MQTT Reconnect ============
void reconnectMQTT() {
  if (!ETH.linkUp()) {
    Serial.println("Ethernet not connected, skipping MQTT reconnect");
    delay(5000);
    return;
  }

  static unsigned long lastAttempt = 0;
  unsigned long now = millis();

  if (now - lastAttempt < 5000) {
    return; // Wait 5 seconds between attempts
  }

  lastAttempt = now;

  Serial.print("Attempting MQTT connection to ");
  Serial.println(MQTT_BROKER);

  if (mqttClient.connect(boardID.c_str())) {
    Serial.println("MQTT connected!");

    // Subscribe to control topics
    String topic = "home/ir/" + boardID + "/+/set";
    mqttClient.subscribe(topic.c_str());

    // Publish status
    String statusTopic = "home/ir/" + boardID + "/status";
    mqttClient.publish(statusTopic.c_str(), "online");
  } else {
    Serial.print("MQTT connect failed, rc=");
    Serial.println(mqttClient.state());
  }
}

// ============ MQTT Callback ============
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("MQTT message received: ");
  Serial.println(topic);

  // Parse topic format: home/ir/{boardID}/output_{n}/set
  String topicStr(topic);

  // Extract output number
  int outputStart = topicStr.indexOf("output_");
  if (outputStart != -1) {
    outputStart += 7; // Length of "output_"
    int outputEnd = topicStr.indexOf("/", outputStart);
    String outputStr = topicStr.substring(outputStart, outputEnd);
    int outputNum = outputStr.toInt();

    Serial.print("Sending IR to output: ");
    Serial.println(outputNum);

    // TODO: Implement IR transmission here
  }
}
