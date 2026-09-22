/*
  ESP32 four-way traffic signal controller.

  Serial protocol (115200 baud):
    RX: PHASE,<phase>,<duration_seconds>,<request_id>
    TX: ACK,<phase>,<duration_seconds>,<request_id>

  Allowed phases: NS_GREEN, NS_YELLOW, EW_GREEN, EW_YELLOW, ALL_RED.
  A hardware watchdog forces ALL_RED if backend commands stop for 10 seconds.
*/

struct Lamps { uint8_t red; uint8_t yellow; uint8_t green; };

const Lamps NORTH = {13, 14, 16};
const Lamps SOUTH = {17, 18, 19};
const Lamps EAST  = {21, 22, 23};
const Lamps WEST  = {25, 26, 27};

unsigned long lastValidCommand = 0;
unsigned long commandDeadline = 0;
String currentPhase = "ALL_RED";

void writeLamps(const Lamps &lamps, bool red, bool yellow, bool green) {
  digitalWrite(lamps.red, red ? HIGH : LOW);
  digitalWrite(lamps.yellow, yellow ? HIGH : LOW);
  digitalWrite(lamps.green, green ? HIGH : LOW);
}

void allRed() {
  writeLamps(NORTH, true, false, false);
  writeLamps(SOUTH, true, false, false);
  writeLamps(EAST,  true, false, false);
  writeLamps(WEST,  true, false, false);
  currentPhase = "ALL_RED";
}

bool applyPhase(const String &phase) {
  // Brief all-red write makes each phase update fail-safe and effectively atomic.
  allRed();

  if (phase == "ALL_RED") return true;
  if (phase == "NS_GREEN") {
    writeLamps(NORTH, false, false, true);
    writeLamps(SOUTH, false, false, true);
  } else if (phase == "NS_YELLOW") {
    writeLamps(NORTH, false, true, false);
    writeLamps(SOUTH, false, true, false);
  } else if (phase == "EW_GREEN") {
    writeLamps(EAST, false, false, true);
    writeLamps(WEST, false, false, true);
  } else if (phase == "EW_YELLOW") {
    writeLamps(EAST, false, true, false);
    writeLamps(WEST, false, true, false);
  } else {
    allRed();
    return false;
  }
  currentPhase = phase;
  return true;
}

void handleCommand(String line) {
  line.trim();
  int p1 = line.indexOf(',');
  int p2 = line.indexOf(',', p1 + 1);
  int p3 = line.indexOf(',', p2 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0 || line.substring(0, p1) != "PHASE") {
    Serial.println("ERR,BAD_FORMAT");
    return;
  }

  String phase = line.substring(p1 + 1, p2);
  String duration = line.substring(p2 + 1, p3);
  String requestId = line.substring(p3 + 1);
  int seconds = duration.toInt();
  if (seconds < 0 || seconds > 60 || !applyPhase(phase)) {
    Serial.println("ERR,INVALID_PHASE_OR_DURATION," + requestId);
    return;
  }

  lastValidCommand = millis();
  // Permit the entire commanded phase plus 5 s for transport/scheduler jitter.
  commandDeadline = lastValidCommand + ((unsigned long)seconds + 5UL) * 1000UL;
  Serial.println("ACK," + phase + "," + String(seconds) + "," + requestId);
}

void setup() {
  Serial.begin(115200);
  const Lamps all[] = {NORTH, SOUTH, EAST, WEST};
  for (const Lamps &lamps : all) {
    pinMode(lamps.red, OUTPUT);
    pinMode(lamps.yellow, OUTPUT);
    pinMode(lamps.green, OUTPUT);
  }
  allRed();
  lastValidCommand = millis();
  commandDeadline = lastValidCommand + 5000UL;
  Serial.println("READY,ALL_RED");
}

void loop() {
  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\n'));
  }
  if ((long)(millis() - commandDeadline) > 0 && currentPhase != "ALL_RED") {
    allRed();
    Serial.println("FAILSAFE,ALL_RED");
  }
}
