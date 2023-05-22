#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "env.h"
#include <OneWire.h>
#include <DallasTemperature.h>

const char* post_endpoint = API_URL_POST;
const char* get_endpoint = API_URL_GET;

#define ONE_WIRE_BUS 4
OneWire one_wire(ONE_WIRE_BUS);
DallasTemperature temp_sensors(&one_wire);	

const int fan_pin = 22;
const int light_pin = 23;
const int pir_pin = 15;
int pir_state;

float random_float(float min, float max)
{
    float scale = rand() / (float) RAND_MAX; /* [0, 1.0] */
    return min + scale * (max - min);       /* [min, max] */
}

void setup() {
  temp_sensors.begin();
  Serial.begin(9600);
  pinMode(fan_pin, OUTPUT);
  pinMode(light_pin, OUTPUT);
  pinMode(pir_pin, INPUT);
  pinMode(ONE_WIRE_BUS, INPUT);

  WiFi.begin(WIFI_USER, WIFI_PASS);
  Serial.println("Connecting");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nThe Bluetooth Device is Ready to Pair");
  Serial.print("Connected @");
  Serial.print(WiFi.localIP());
}


void loop() {
  // Read temperature// Send the command to get temperatures
  temp_sensors.requestTemperatures(); 

  // Print the temperature in Celsius
  Serial.print("Temperature: ");
  float temperature = temp_sensors.getTempCByIndex(0);
  Serial.print(temperature);
  Serial.print((char)176); // Shows degrees character
  Serial.print("C  |  "); 
  pir_state = digitalRead(pir_pin);
  Serial.print("\n");
  Serial.print("");
  Serial.print(pir_state);
  Serial.println("");
  
  // POST Request
  if (WiFi.status() == WL_CONNECTED) {   
    HTTPClient http;
    String http_response;

    // POST request
    http.begin(post_endpoint);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<1024> post_doc; // Empty JSONDocument
    String http_request_data; // Emtpy string to be used to store HTTP request data string
    
    post_doc["temperature"] = temperature;
    post_doc["presence"] = !pir_state;
    serializeJson(post_doc, http_request_data);

    int post_response_code = http.POST(http_request_data);

    if (post_response_code > 0) {
        Serial.print("Response:");
        Serial.print(post_response_code);
    } else {
        Serial.print("Error: ");
        Serial.println(post_response_code);
    }
      
    http.end();
      
   // GET request
    http.begin(get_endpoint);
    int http_response_code = http.GET();

    if (http_response_code > 0) {
        Serial.print("Response:");
        Serial.print(http_response_code);
        http_response = http.getString();
        Serial.println(http_response);
    } else {
        Serial.print("Error: ");
        Serial.println(http_response_code);
    }
      
    http.end();

    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, http_response);

    if (error) { 
        Serial.print("deserializeJson() failed:");
        Serial.println(error.c_str());
        return;
    }
      
    bool light_state = doc["light"];
    bool fan_state = doc["fan"];
  
    Serial.println("Light:");
    Serial.println(light_state);
    Serial.println("Fan:");
    Serial.println(fan_state);

    digitalWrite(fan_pin, fan_state);
    digitalWrite(light_pin, light_state);
      
    Serial.println("Light and Fan Switched Successfully");
      
    delay(1000);   
  } else {
    Serial.println("Not Connected");
  }
  
}
