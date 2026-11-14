#include <Arduino.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>
#include <WiFi.h>
#include "secrets.h"
#include <time.h>
#include <LittleFS.h>

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

const time_t MIN_VALID_TIME = 1700000000;

bool timeIsValid() {
    return time(nullptr) >= MIN_VALID_TIME;
}

struct Record {
    uint32_t epoch;
    uint16_t co2;
    int16_t temp100;
    uint16_t hum100;
    uint8_t spare[6];
};

struct Header {
    uint32_t readIdx;
    uint32_t writeIdx;
    uint32_t count;
};

#ifndef __INTELLISENSE__
static_assert(sizeof(Record) == 16, "Record must be 16 bytes");
#endif
const uint32_t CAPACITY = 20160;
Header hdr;

const uint32_t CHUNK_SIZE = 500;
Record chunk[CHUNK_SIZE];

void saveHeader() {
    File f = LittleFS.open("/hdr.bin", "w");
    if (!f) {return;}
    f.write((const uint8_t*)&hdr, sizeof(hdr));
    f.close();
}

void loadHeader() {
    if (!LittleFS.exists("/hdr.bin")) {
        saveHeader();
        return;
    }
    File f = LittleFS.open("/hdr.bin", "r");
    if (!f) {return;}
    f.read((uint8_t*)&hdr, sizeof(hdr));
    f.close();
}

void appendRecord(const Record& r) {
    File f;
    if (!LittleFS.exists("/buf.bin")) {
        f = LittleFS.open("/buf.bin", "w");
    } else {
        f = LittleFS.open("/buf.bin", "r+");
    }
    if (!f) {return;}

    f.seek(hdr.writeIdx * sizeof(r));
    f.write((const uint8_t*)&r, sizeof(r));
    f.close();

    hdr.writeIdx = (hdr.writeIdx + 1) % CAPACITY;

    if (hdr.count < CAPACITY) {
        hdr.count += 1;
    } else {
        hdr.readIdx = (hdr.readIdx + 1) % CAPACITY;
    }

    saveHeader();
}

void readChunk(uint32_t& n) {
    if (n == 0) {return;}

    File f;
    if (LittleFS.exists("/buf.bin")) {
        f = LittleFS.open("/buf.bin", "r");
    } else { n = 0; return; }

    if (!f) {n = 0; return;}

    for (uint32_t i = 0; i < n; i += 1) {

        f.seek((hdr.readIdx + i) % CAPACITY * sizeof(chunk[i]));
        f.read((uint8_t*) &chunk[i], sizeof(chunk[i]));
    }

    f.close();
}

bool sendChunk(uint32_t& n) {

    if (n==0) {return false;}

    return true;
}

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

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t WifiStart = millis();
    while (WiFi.status() != WL_CONNECTED and millis() - WifiStart < 15000) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("RSSI: %d\n", WiFi.RSSI());
    } else {
        Serial.printf("Wi-Fi failed, status %d\n", WiFi.status());
    }

    configTime(0, 0, "pool.ntp.org");

    uint32_t ntpStart = millis();
    while (!timeIsValid() and millis() - ntpStart < 10000) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();
    Serial.printf("now: %lld\n", (long long)time(nullptr));

    bool fsMounted = LittleFS.begin(true);
    Serial.printf("LittleFS: %s\n", fsMounted ? "mounted" : "FAILED");

    if (fsMounted) {
        loadHeader();
        Serial.printf("hdr: read %lu, write %lu, count %lu\n", hdr.readIdx, hdr.writeIdx, hdr.count);
    }
}

void loop() {
    uint32_t now = millis();

    if (!warmedUp && now >= WARMUP_MS) {
        warmedUp = true;
        lastWindowMs = now;
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
        
        if (sampleCount > 0 && timeIsValid()) {
            const uint16_t co2Avg = co2Sum / sampleCount;
            const float tempAvg = tempSum / sampleCount;
            const float humAvg  = humSum / sampleCount;

            struct tm t;
            char createdAt[25];
            const time_t nowUtc = time(nullptr);

            gmtime_r(&nowUtc, &t);
            strftime(createdAt, sizeof(createdAt), "%Y-%m-%dT%H:%M:%SZ", &t);

            Serial.printf("avg (%u): CO2 %u ppm, T %.1f C, RH %.1f %%, created at: %s\n", sampleCount, co2Avg, tempAvg, humAvg, createdAt);

            Record r = {};
            r.co2 = co2Avg;
            r.temp100 = lroundf(tempAvg * 100);
            r.hum100 = lroundf(humAvg * 100);
            r.epoch = nowUtc;

            appendRecord(r);
            Serial.printf("stored: write %lu, count %lu\n", hdr.writeIdx, hdr.count);
        }
        co2Sum = 0;
        tempSum = 0.0;
        humSum = 0.0;
        sampleCount = 0;

    }

    if (hdr.count > 0) {
        uint32_t n = min(hdr.count, CHUNK_SIZE);
        readChunk(n);
        if (sendChunk(n)) {
            hdr.count -= n;
            hdr.readIdx = (hdr.readIdx + n) % CAPACITY;
            saveHeader();
            Serial.printf("synced %lu, read %lu, count %lu\n", n, hdr.readIdx, hdr.count);
        }

    }

}