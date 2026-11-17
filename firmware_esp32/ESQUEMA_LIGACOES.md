# ⚡ ATMOS — Guia de Ligação Elétrica & Pinagem do ESP32

Documentação de engenharia para montagem segura da bancada de sensores do **ATMOS** na protoboard com **ESP32 NodeMCU** e fonte ajustável **MB102**.

---

## ⚠️ Regras Fundamentais de Segurança Elétrica

> [!CAUTION] Tensão Lógica Máxima do ESP32: 3.3V
> - Os pinos GPIO e canais ADC do ESP32 operam exclusivamente com **3.3V**. Aplicar 5V diretamente em qualquer pino do ESP32 causará **queima irreversível do SoC**.
> - **GND Comum Obrigatório:** O pino `GND` da fonte MB102 **DEVE** estar conectado fisicamente ao pino `GND` do ESP32 para nivelar o potencial de referência de todos os sinais.

> [!IMPORTANT] Restrição Crítica: Conflito de Wi-Fi e ADC2
> - O ESP32 compartilha o controlador **ADC2** com o rádio Wi-Fi. Quando o Wi-Fi está em operação, **qualquer leitura analógica nos pinos do ADC2 falhará ou retornará ruído**.
> - Portanto, todas as leituras analógicas devem utilizar exclusivamente pinos do **ADC1** (GPIOs **32, 33, 34, 35, 36/VP, 39/VN**).

---

## 🔌 Distribuição de Alimentação (Fonte MB102)

Configure os jumpers da fonte **MB102**:
- **Barramento A (Superior da Protoboard):** Jumper em **5V** (alimentação do filamento do sensor MQ-135/MQ-2).
- **Barramento B (Inferior da Protoboard):** Jumper em **3.3V** (alimentação dos módulos DHT, BMP280, sensor de chuva e LDR).

---

## 📋 Tabela Mestra de Pinagem (ESP32)

| Componente | Pino do Sensor | Pino ESP32 | Barramento de Alimentação | Notas de Engenharia |
| :--- | :--- | :--- | :--- | :--- |
| **GND Geral** | GND (todos) | **GND** | Linha Azul (-) | Todos os terras interligados |
| **DHT11 / DHT22** | VCC | — | **3.3V** (Linha Vermelha) | Alimentar em 3.3V |
| | DATA | **GPIO 4** | — | Resistor de 4.7kΩ/10kΩ pull-up para 3.3V (se não for módulo com placa) |
| | GND | **GND** | Linha Azul (-) | Terra comum |
| **Barômetro BMP280**| VCC | — | **3.3V** (Linha Vermelha) | Nativamente 3.3V |
| | GND | **GND** | Linha Azul (-) | Terra comum |
| | SDA | **GPIO 21** | — | Linha de Dados I2C |
| | SCL | **GPIO 22** | — | Linha de Clock I2C |
| **Sensor de Chuva** | VCC | — | **3.3V** (Linha Vermelha) | Alimentar em 3.3V para o sinal D0 sair em 3.3V |
| | GND | **GND** | Linha Azul (-) | Terra comum |
| | D0 (Digital) | **GPIO 16** | — | LOW = Molhado / HIGH = Seco |
| | A0 (Analógico) | **GPIO 34** (ADC1) | — | Opcional: leitura contínua de umidade na placa |
| **Sensor de Gás (MQ)**| VCC | — | **5V** (Barramento MB102) | Exige 5V no aquecedor interno |
| | GND | **GND** | Linha Azul (-) | Terra comum |
| | A0 (Analógico) | **GPIO 35** (ADC1) | — | Atenção com divisor de tensão (1kΩ / 2kΩ) se passar de 3.3V |
| **LDR (Luz)** | VCC | — | **3.3V** (Linha Vermelha) | Divisor resistivo com resistor de 10kΩ |
| | Sinal | **GPIO 32** (ADC1) | — | Leitura de luminosidade (0 a 4095) |

---

## 📦 Bibliotecas Necessárias no Arduino IDE

1. **`DHT sensor library`** (por Adafruit) + **`Adafruit Unified Sensor`**
2. **`Adafruit BMP280 Library`**
3. **`ArduinoJson`** (por Benoit Blanchon — Versão 6.x ou 7.x)
