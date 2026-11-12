#include <Arduino.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>

const uint8_t SDA_PIN = 8;
const uint8_t SCL_PIN = 9;

const uint32_t PRINT_INTERVAL_MS = 10000;
uint32_t lastTimeMs = 0;

bool ledOn = false;

SensirionI2cScd4x sensor;
const u32_t MEASURE_INTERVAL_MS = 1000;
uint32_t lastMeasureMs = 0;

uint32_t co2Sum = 0;
float tempSum = 0.0;
float humSum = 0.0;
uint8_t sampleCount = 0;

const uint32_t WINDOW_MS = 30000;
uint32_t lastWindowMs = 0;

const u32_t WARMUP_MS = 240000;
bool warmedUp = false;

uint16_t co2 = 0;
float temp = 0.0;
float humidity = 0.0;

void setup() {

    Serial.begin(115200);
    while (!Serial && millis() < 3000) {}
    delay(2000);
    
    rgbLedWrite(RGB_BUILTIN, 0, 0, 0);

    Serial.printf("flash: %lu bytes\n", ESP.getFlashChipSize());
    Serial.printf("psram: %lu bytes\n", ESP.getPsramSize());

    Wire.begin(SDA_PIN, SCL_PIN);

    for (uint8_t i = 1; i < 127; i++) {
        Wire.beginTransmission(i);
        u_int8_t result = Wire.endTransmission();
        if (result == 0) {
            Serial.printf("adresse: %d\n", i);
        }

    }

    sensor.begin(Wire, SCD40_I2C_ADDR_62);
    sensor.wakeUp();
    sensor.stopPeriodicMeasurement();
    sensor.reinit();

    int16_t err = sensor.startPeriodicMeasurement();
    if (err != 0) {
    Serial.printf("start failed: %d\n", err);
    }
    
}

void loop() {
    uint32_t now = millis();

    if (!warmedUp && now >= WARMUP_MS) {
        warmedUp = true;
        lastWindowMs = now;
        lastMeasureMs = now;
    }

    if (now - lastTimeMs >= PRINT_INTERVAL_MS) {
        lastTimeMs = now;
        Serial.printf("uptime %lu s\n", now / 1000);

        if (!ledOn) {rgbLedWrite(RGB_BUILTIN, 10, 30, 80);
        } else {rgbLedWrite(RGB_BUILTIN, 0, 0, 0);}
        
        ledOn = !ledOn;
    }

    if (now - lastMeasureMs >= MEASURE_INTERVAL_MS && warmedUp){
        lastMeasureMs = now;

        bool ready = false;
        sensor.getDataReadyStatus(ready);

        if (ready) {
            int16_t err = sensor.readMeasurement(co2, temp, humidity);
            if (err != 0) {Serial.printf("read failed: %d\n", err);
            } else {
                sampleCount += 1;

                co2Sum += co2;
                tempSum += temp;
                humSum += humidity;

                Serial.printf("Co2: %d ppm\ntemp: %.1f\nhumidity: %.1f\n", co2, temp, humidity);            
            }
        }
        
    }

    if (now - lastWindowMs >= WINDOW_MS && warmedUp){
        lastWindowMs = now;
        
        if (sampleCount > 0) {
            uint16_t co2Avg = co2Sum / sampleCount;
            float tempAvg = tempSum / sampleCount;
            float humAvg  = humSum / sampleCount;

            Serial.printf("avg (%u): CO2 %u ppm, T %.1f C, RH %.1f %%\n", sampleCount, co2Avg, tempAvg, humAvg);
        }
        co2Sum = 0;
        tempSum = 0.0;
        humSum = 0.0;
        sampleCount = 0;

    }

}