#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>

/*
 ==============================================================================
  ATMOS — Estação Meteorológica & Telemetria IoT
  Firmware Oficial ESP32
  Integração direta com API FastAPI (Render / Local) e PostgreSQL no Aiven.
 ==============================================================================
*/

// ==========================================
// 1. CONFIGURAÇÕES DE REDE & API
// ==========================================
const char* WIFI_SSID     = "Sweet Child O' Modem";
const char* WIFI_PASSWORD = "P@ty4104";

// Identificador desta estação física (cadastrada na tabela 'estacoes')
const char* ESTACAO_ID    = "ATMOS-01";

// URL do Backend:
// Para teste local na mesma rede: "http://SEU_IP_LOCAL:8000/api/dados"
// Para ambiente de produção no Render: "https://atmos-jio7.onrender.com/api/dados"
const char* API_URL       = "https://atmos-jio7.onrender.com/api/dados";

// Intervalo entre leituras e envios (em milissegundos) — Ex: 30 segundos
const unsigned long INTERVALO_LEITURA = 30000;
unsigned long ultimaLeitura = 0;

// ==========================================
// 2. DEFINIÇÃO DE PINAGEM (RESTRITA AO ADC1)
// ==========================================
// IMPORTANTE: O ESP32 desativa o ADC2 quando o Wi-Fi está ligado.
// Todos os pinos analógicos aqui utilizam obrigatoriamente o ADC1 (GPIOs 32 a 39).

#define DHTPIN        4       // Pino digital do sensor DHT (GPIO 4)
#define DHTTYPE       DHT11   // Altere para DHT22 se estiver usando o modelo branco AM2302

#define PIN_CHUVA_DO  16      // Entrada digital do módulo de chuva (D0 - 0 = chuva detectada, 1 = seco)
#define PIN_CHUVA_AO  34      // Entrada analógica do módulo de chuva (ADC1_CH6 - GPIO 34)

#define PIN_GAS_MQ    35      // Entrada analógica do sensor de gás MQ-135 (ADC1_CH7 - GPIO 35)
#define PIN_LDR       32      // Entrada analógica do sensor de luminosidade LDR (ADC1_CH4 - GPIO 32)

// Barramento I2C para BMP280 / BME280:
// SDA padrão = GPIO 21
// SCL padrão = GPIO 22

// ==========================================
// 3. OBJETOS DOS SENSORES
// ==========================================
DHT dht(DHTPIN, DHTTYPE);
Adafruit_BMP280 bmp; // Barômetro I2C (endereços típicos: 0x76 ou 0x77)
bool bmpDisponivel = false;

// ==========================================
// 4. FUNÇÕES DE CONECTIVIDADE
// ==========================================
void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("[Wi-Fi] Conectando a ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[Wi-Fi] Conectado com sucesso!");
    Serial.print("[Wi-Fi] IP obtido: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[Wi-Fi] Falha ao conectar. Tentando novamente no próximo ciclo.");
  }
}

// ==========================================
// 5. INICIALIZAÇÃO DO SISTEMA (SETUP)
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- [ATMOS] Inicializando Estação Meteorológica ---");

  // Configuração dos pinos digitais
  pinMode(PIN_CHUVA_DO, INPUT);

  // Inicialização do barramento I2C
  Wire.begin(21, 22);

  // Inicializa o DHT
  dht.begin();
  Serial.println("[Sensoriamento] DHT inicializado.");

  // Inicializa o Barômetro BMP280 (tenta endereço 0x76 e depois 0x77)
  if (bmp.begin(0x76) || bmp.begin(0x77)) {
    Serial.println("[Sensoriamento] Barômetro BMP280 detectado no barramento I2C.");
    bmpDisponivel = true;
  } else {
    Serial.println("[Sensoriamento] AVISO: BMP280 não detectado (verifique endereço 0x76/0x77 e conexões SDA/SCL).");
  }

  // Conecta ao Wi-Fi
  conectarWiFi();
}

// ==========================================
// 6. LOOP PRINCIPAL
// ==========================================
void loop() {
  conectarWiFi();

  if (millis() - ultimaLeitura >= INTERVALO_LEITURA) {
    ultimaLeitura = millis();

    // 1. Leitura do DHT (Temperatura e Umidade)
    float tempDHT = dht.readTemperature();
    float umidDHT = dht.readHumidity();

    // Validação de integridade do DHT
    if (isnan(tempDHT) || isnan(umidDHT)) {
      Serial.println("[Sensoriamento] Erro ao ler dados do DHT!");
      tempDHT = 0.0;
      umidDHT = 0.0;
    }

    // 2. Leitura do Barômetro BMP280 (Pressão atmosférica em hPa)
    float pressao = 1013.25; // valor default se sensor ausente
    if (bmpDisponivel) {
      pressao = bmp.readPressure() / 100.0F; // Converte Pa para hPa
      if (tempDHT == 0.0) {
        tempDHT = bmp.readTemperature(); // Fallback se DHT falhar
      }
    }

    // 3. Leitura do Sensor de Gás / Qualidade do Ar (MQ-135)
    // Leitura ADC de 12 bits (0 a 4095). Escala linear para índice de telemetria
    int rawGas = analogRead(PIN_GAS_MQ);
    float qualidadeAr = (float)rawGas;

    // 4. Leitura do Sensor de Luminosidade (LDR)
    int luminosidade = analogRead(PIN_LDR);

    // 5. Leitura do Sensor de Chuva
    // Módulo digital LM393: LOW quando detecta líquido nas trilhas, HIGH quando seco
    int leituraChuvaDigital = digitalRead(PIN_CHUVA_DO);
    bool estaChovendo = (leituraChuvaDigital == LOW);

    // Exibição serial de depuração
    Serial.println("\n--- [ATMOS] Leituras dos Sensores ---");
    Serial.printf("Temperatura:  %.2f °C\n", tempDHT);
    Serial.printf("Umidade:      %.2f %%\n", umidDHT);
    Serial.printf("Pressão:      %.2f hPa\n", pressao);
    Serial.printf("Qualidade Ar: %.2f (ADC: %d)\n", qualidadeAr, rawGas);
    Serial.printf("Luminosidade: %d\n", luminosidade);
    Serial.printf("Chuva:        %s\n", estaChovendo ? "SIM" : "NÃO");

    // Envio HTTP POST se o Wi-Fi estiver conectado
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(API_URL);
      http.addHeader("Content-Type", "application/json");

      // Monta o payload estruturado (schema DadosSensores do FastAPI)
      StaticJsonDocument<256> doc;
      doc["estacao_id"]   = ESTACAO_ID;
      doc["temperatura"]  = serialized(String(tempDHT, 2));
      doc["umidade"]      = serialized(String(umidDHT, 2));
      doc["pressao"]      = serialized(String(pressao, 2));
      doc["qualidade_ar"] = serialized(String(qualidadeAr, 2));
      doc["luminosidade"] = luminosidade;
      doc["chuva"]        = estaChovendo;

      String payloadJson;
      serializeJson(doc, payloadJson);

      Serial.print("[HTTP] Enviando POST para: ");
      Serial.println(API_URL);
      Serial.print("[HTTP] Payload: ");
      Serial.println(payloadJson);

      int httpResponseCode = http.POST(payloadJson);

      if (httpResponseCode > 0) {
        String resposta = http.getString();
        Serial.printf("[HTTP] Sucesso! Código de resposta: %d\n", httpResponseCode);
        Serial.println("[HTTP] Resposta da API: " + resposta);
      } else {
        Serial.printf("[HTTP] Erro no envio POST. Código: %d (%s)\n", httpResponseCode, http.errorToString(httpResponseCode).c_str());
      }

      http.end();
    } else {
      Serial.println("[HTTP] Wi-Fi desconectado. Envio ignorado.");
    }
  }
}
