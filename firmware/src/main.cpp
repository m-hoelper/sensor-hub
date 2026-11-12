#include <Arduino.h>
const uint32_t PRINT_INTERVAL_MS = 1000;
uint32_t lastTimeMs = 0;
bool ledOn = false;

void setup() {

    Serial.begin(115200);
    while (!Serial && millis() < 3000) {}
    
    rgbLedWrite(RGB_BUILTIN, 0, 0, 0);
    sleep(2);
    Serial.printf("flash: %lu bytes\n", ESP.getFlashChipSize());
    Serial.printf("psram: %lu bytes\n", ESP.getPsramSize());
    
}

void loop() {
    uint32_t now = millis();

    if (now - lastTimeMs >= PRINT_INTERVAL_MS) {
        lastTimeMs = now;
        Serial.printf("uptime %lu s\n", now / 1000);

        if (!ledOn) {rgbLedWrite(RGB_BUILTIN, 10, 30, 80);
        } else {rgbLedWrite(RGB_BUILTIN, 0, 0, 0);}
        
        ledOn = !ledOn;
    }

}