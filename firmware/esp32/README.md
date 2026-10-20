# Firmware ATMOS — ESP32 / MicroPython

Implementacao independente do backend/frontend. **Estado inicial: simulacao ligada,
envio desligado.** Importar `diagnostics` nao inicia o ciclo. `main.py` na raiz da placa
inicia automaticamente a cada boot; Ctrl+C no console interrompe o programa.

## Pendencias para discutir antes da operacao real

1. **UNIDADES:** `qualidade_ar` sera ADC bruto MQ135 (0–4095), nao ppm nem IQA.
   `luminosidade` sera ADC bruto do divisor LDR (0–4095), nao lux. O dashboard atual
   rotula esses campos como IQA/lux: nao e correto interpretar os dados brutos assim.
   O envio fisico fica bloqueado por `ALLOW_RAW_ADC_UPLOAD = False`. Mudar para True
   aceita somente um ensaio consciente; nao implementa calibracao nem corrige a tela.
   Precisamos decidir depois entre contrato com unidades explicitas e calibracao real.
2. **CHUVA FC37:** apenas deteccao booleana, sem milimetros. A tela atual apresenta mm
   e soma as leituras; essa representacao tambem precisa de revisao futura autorizada.
   FC37 identifica a placa sensora; confirme a placa comparadora, alimentacao e tensao
   da saida DO. `RAIN_ACTIVE_LEVEL = 0` e uma hipotese de bancada, ajustavel apos teste.
3. **HARDWARE:** usuario autorizou ESP32 classico como referencia provisoria. Modelo
   exato, versao MicroPython e breakout BMP280/MQ135 ainda precisam de confirmacao.
   Nao reutilize esta pinagem automaticamente em C3/S3/S2. `HARDWARE_CONFIRMED` deve
   continuar False ate conferir as ligacoes reais.
4. **SIMULACAO:** usa `ATMOS-SIM-01`, separada de `ATMOS-01`. Se a tabela `estacoes`
   tiver chave estrangeira, o identificador simulado precisa existir no banco antes
   do primeiro POST. Nao troque pelo ID real para contornar erro. Nao ha endpoint
   de cadastro de estacao no codigo inspecionado. Nenhuma alteracao de banco foi feita.

## Arquivos e responsabilidades

| Arquivo | Funcao |
| --- | --- |
| `main.py` | Validacao de configuracao, coleta, fila RAM e ciclo de envio |
| `config.py` | Valores publicos, pinagem e travas operacionais |
| `config.example.py` | Exemplo curto; nao e importado pelo programa |
| `secrets.example.py` | Modelo para criar `secrets.py` local, ignorado pelo Git |
| `payload.py` | Montagem e validacao dos sete campos; buffer e backoff |
| `sensors.py` | Simulador e adaptadores para os sensores fisicos |
| `lib/bmp280.py` | Driver I2C local com compensacao pelos coeficientes de fabrica |
| `wifi_manager.py` | Conexao Wi-Fi limitada, reconexao e ajuste de relogio via NTP |
| `api_client.py` | POST HTTP/HTTPS, certificado verificado, timeout e fechamento |
| `diagnostics.py` | Ensaios separados, acionados explicitamente no console |
| `tests/test_firmware.py` | Testes CPython com dados e perifericos simulados |

Nao foi criado `boot.py`: nao ha inicializacao que precise ocorrer antes de `main.py`.

## Compatibilidade com a API atual

`POST /api/dados`, com `Content-Type: application/json`:

```json
{
  "estacao_id": "ATMOS-SIM-01",
  "temperatura": 24.2,
  "umidade": 69.5,
  "pressao": 1010.1,
  "qualidade_ar": 910,
  "luminosidade": 1820,
  "chuva": false
}
```

Temperatura em Celsius, umidade em %, pressao absoluta em hPa. Nao e pressao corrigida
ao nivel do mar. Numeros MQ135/LDR acima sao apenas simulados na escala ADC bruta.
`chuva` vai como booleano JSON, nao como string. O modelo Pydantic exige esses sete
campos; repository converte bool em inteiro ao inserir e service devolve chuva como
float nas consultas. Isso foi confirmado no codigo; o esquema PostgreSQL real nao
foi consultado. Sensores incompletos impedem o envio da amostra inteira, pois a API
nao aceita campos faltantes/nulos. Nao se inventam zeros nem se reutiliza leitura velha.

O firmware aplica faixas locais (DHT22 -40–80 C e 0–100%, BMP280 300–1100 hPa,
ADC 0–4095). A API atual tem apenas tipos, sem essas validacoes de faixa.

## Pinagem provisoria e ligacoes

Use numeros GPIO, nao a posicao fisica dos pinos no conector.

| Componente | Sinal | GPIO provisorio | Observacao |
| --- | --- | --- | --- |
| AM2302 / DHT22 | DATA | 4 | Pull-up tipico 4,7–10 kOhm para 3,3 V se nao houver no modulo |
| BMP280 | SDA | 21 | I2C 100 kHz, pull-ups para 3,3 V |
| BMP280 | SCL | 22 | Endereco 0x76 ou 0x77 |
| MQ135 | AO adaptado | 34 | ADC1; entrada apenas |
| LDR + resistor | Meio do divisor | 35 | ADC1; entrada apenas |
| FC37 + comparador | DO adaptado | 27 | Entrada digital; nao ligar AO neste pino para este firmware |

Todos os circuitos devem compartilhar GND. Alimente DHT22 e breakout BMP280 compativeis
com 3,3 V; confirme o esquema do breakout. O chip BMP280 nao aceita 5 V diretamente.
Modulos MQ135 frequentemente usam 5 V no aquecedor: confira consumo e fonte adequada;
nao alimente o aquecedor por GPIO. AO pode ultrapassar a tensao permitida pelo ADC:
meça/adapte com divisor/buffer apropriado ANTES de conectar. Atenuacao ADC nao protege
contra sobretensao. O mesmo cuidado vale para DO do comparador FC37: confirme se ha
pull-up a 5 V e adapte o nivel ou use alimentacao compativel segundo o modulo real.

LDR: uma montagem inicial e `3V3 → LDR → GPIO35 → resistor → GND` (resistor de 10 kOhm
e apenas ponto de partida). Nessa montagem o ADC tende a subir com mais luz; inverter
as posicoes inverte a escala. Nenhuma conversao para lux foi implementada.

MQ135: a espera de 180 s do codigo e so uma trava operacional configuravel. Nao prova
estabilizacao e nao substitui o condicionamento inicial recomendado pelo fabricante,
calibracao, circuito conhecido nem compensacao ambiental. A escala nao permite
afirmar concentracao de gases ou qualidade ambiental validada.

## Instalar MicroPython e transferir

1. Identifique a placa e use o firmware MicroPython correspondente. No Thonny,
   abra a selecao de interpretador, escolha MicroPython (ESP32), porta USB correta
   e a opcao de instalar/atualizar firmware. A gravacao pode apagar os arquivos da
   placa; salve o que precisar antes. Nao grave uma imagem de ESP32 classico em C3/S3.
2. Use uma versao estavel com `network`, `machine`, `dht`, `ssl.SSLContext`,
   `ssl.PROTOCOL_TLS_CLIENT`, `ssl.CERT_REQUIRED`, `socket`, `json`, `struct` e
   `ntptime`. A versao exata disponivel na placa ainda nao foi validada. No REPL,
   `import sys; print(sys.implementation)` ajuda a identifica-la.
3. No painel de arquivos do Thonny, transfira os `.py` de `firmware/esp32/` para
   a raiz do dispositivo, preservando a pasta `lib/`. Nao transfira `tests/`, README
   ou arquivos `.example.py`. Transfira `main.py` por ultimo para facilitar o preparo.
4. Para ensaios com rede, copie `secrets.example.py` como `secrets.py` localmente,
   preencha Wi-Fi e envie esse arquivo para a raiz da placa. A rede deve ser compativel
   com o ESP32 classico (2,4 GHz). Nao coloque credenciais em `config.py`.
5. Para HTTPS, obtenha a CA raiz publica confiavel da cadeia do dominio da API,
   por fonte oficial da autoridade certificadora, e transfira como `ca.der` (DER)
   ou ajuste `TLS_CA_FILE` para um arquivo PEM compativel. Nao use chave privada,
   nao aceite certificado capturado de uma conexao nao confiavel e nao desabilite
   verificacao para contornar erros. Renovacoes/mudancas de cadeia podem exigir
   atualizar a CA. Nenhuma CA foi embutida ou baixada automaticamente.
6. Ajuste o RTC por USB ou permita NTP. TLS exige hora correta. O codigo tenta NTP
   quando o relogio ainda esta anterior a 2025; nao e sincronizacao continua.

Nao ha dependencias `pip` para instalar na placa nem driver externo para baixar:
o BMP280 local utiliza os coeficientes de calibracao de fabrica. Dependencias do
backend nao devem ser copiadas para o ESP32. `dht.DHT22` atende AM2302 compativel.
Se `ssl.SSLContext` nao existir, escolha firmware compativel; nao ha fallback inseguro.

## Ensaios separados no REPL

Interrompa `main.py` com Ctrl+C antes dos ensaios. Depois de alterar configuracao,
reinicie o interpretador para recarregar os modulos.

**1. Gerar leitura e JSON, sem rede ou sensores:**

```python
import diagnostics
amostra = diagnostics.sample()
```

**2. Testar somente Wi-Fi** (com `secrets.py` configurado, envio pode seguir desligado):

```python
diagnostics.connect_wifi()
```

**3. Um POST simulado:** confirme o cadastro de `ATMOS-SIM-01` no banco, configure CA
e URL, mantenha `SIMULATION = True` e habilite `SEND_ENABLED = True`. Reinicie, interrompa
o ciclo e execute `diagnostics.send_once()`. Cada chamada faz no maximo um POST.
Para evitar que `main.py` inicie envios ao reiniciar durante este preparo, transfira-o
somente depois dos ensaios ou salve temporariamente na placa com outro nome.

**4. Sensor individual:** apos confirmar ligacoes e marcar `HARDWARE_CONFIRMED = True`,
use `diagnostics.read_sensor("dht")`, `"bmp"`, `"mq"`, `"ldr"` ou `"rain"`.
Esses comandos nao enviam dados, mesmo com `SIMULATION = True`. Respeite 2 segundos
entre chamadas DHT22. Inicialize uma vez `read_sensor("mq")` e aguarde o aquecimento
antes de repetir. Molhe/seque a superficie do FC37 com cuidado, mantendo a eletronica
seca, e confirme se o resultado booleano e correto; ajuste `RAIN_ACTIVE_LEVEL` se preciso.
O BMP280 e inicializado somente ao pedir pressao; sua ausencia nao impede ensaiar DHT/LDR.

**5. Operacao periodica:** inicialmente deixe `SEND_ENABLED = False`; rode `main.py`
e confira logs. Padrao: amostra a cada 60 s, explicitamente marcada como simulada.
Para dados reais use `SIMULATION = False`, hardware confirmado e mantenha envio
desligado ate resolver as unidades. Todos os campos precisam de leitura valida.

**6. Conferir no backend:** em `/docs`, use `GET /api/dados` e `GET /api/historico`
com `estacao_id=ATMOS-SIM-01`. No Postman, use os mesmos parametros. O dashboard atual
consulta a estacao padrao, sem seletor: nao mostrara automaticamente a estacao simulada.
Nao foi alterado para contornar essa separacao.

## Falhas, repeticao e limites

- Wi-Fi: ate 3 tentativas de 10 s, com pequenas esperas entre elas. Esgotadas as
  tentativas, espera progressiva de 60, 120, 240 e no maximo 300 s entre ciclos falhos.
  Reinicia a espera em 60 s apos sucesso. A coleta tambem desacelera nessas falhas.
- HTTP: timeout de socket de 20 s, incluindo operacoes TLS conforme o port. DNS
  (`getaddrinfo`) pode ultrapassar esse tempo; nao ha promessa de deadline global.
  O ciclo inclui leitura/rede mais a espera: nao e amostragem de precisao a cada 60 s.
- TLS: verificacao obrigatoria da cadeia CA e hostname; falta de suporte/certificado
  nao muda automaticamente para HTTP. `ALLOW_LOCAL_HTTP` e opcao explicita para
  bancada, usando IP da maquina na LAN, nunca 127.0.0.1. Use `/api/dados` completo.
- HTTP/JSON: aceita o contrato atual (200 com objeto JSON contendo `dados`).
  422 significa revisar payload; 503, revisar banco/servico; 429, reduzir frequencia;
  3xx, conferir URL final. Corpo de erro nao vai ao console. Respostas maiores que
  4096 bytes, cabecalhos grandes, resposta sem Content-Length ou chunked sao recusados.
  HTTP/1.0 + Connection: close e usado para favorecer respostas com Content-Length.
- Duplicacao: API nao oferece idempotencia. Cada leitura e retirada da fila ANTES do
  POST e nunca repetida, inclusive em timeout, resposta perdida, erro HTTP ou JSON.
  Isso prioriza evitar duplicatas e pode perder leituras. Backoff vale para proximas
  leituras, nao retransmissao da mesma. Nenhuma garantia de entrega exatamente uma vez.
- Buffer RAM: no maximo 3 leituras ainda nao tentadas; descarta as mais antigas e
  expira apos 180 s. Envia no maximo uma por ciclo para evitar rajadas. Reiniciar perde
  a fila. Nao ha gravacao repetida em flash. A API registra horario de recebimento,
  nao coleta: leituras atrasadas terao horario deslocado em ate o limite do buffer.
- Sensores: falhas descartam a amostra inteira e tentam novamente no ciclo seguinte.
  Na inicializacao fisica as configuracoes sao tentadas novamente; falhas de leitura
  BMP280 tambem recriam o driver na proxima tentativa. Nenhum reset automatico da placa.
- Logs: nao imprimem senha, SSID, corpo de erro ou detalhes de excecao de rede.
  Verifique identificacao e escala dos dados antes de habilitar operacao continua.

## Testes no computador

Na raiz do repositorio, com Python e Pydantic ja disponiveis:

```powershell
python -B -m unittest discover -s firmware/esp32/tests -v
```

Testes usam simulacao/fakes e leem apenas o modelo Pydantic do backend. Nao importam
`app.config`, nao abrem `.env`, nao conectam ao banco nem enviam dados para Render.
Cobrem contrato, valores invalidos, BMP280 com vetor de referencia, parser HTTP,
timeout/fechamento, backoff, fila e nao repeticao depois de POST incerto.
Nao substituem validacao em MicroPython real: RAM/TLS, USB, Wi-Fi e sensores fisicos
ainda precisam ser testados na placa. Nenhum teste fisico foi realizado aqui.

## Referencias tecnicas

- [MicroPython: ESP32 e ADC](https://docs.micropython.org/en/latest/esp32/quickref.html)
- [MicroPython: instalacao ESP32](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html)
- [MicroPython: SSL/TLS e verificacao](https://docs.micropython.org/en/latest/library/ssl.html)
- [Bosch: datasheet BMP280](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp280-ds001.pdf)

As paginas `latest` podem descrever recursos de desenvolvimento: confira a pagina
da versao instalada antes de montar/operar. Este firmware ainda nao foi homologado
para uma versao especifica de MicroPython ou modelo de breakout.
