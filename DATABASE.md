# 🌦️ ATMOS — Documentação do Banco de Dados PostgreSQL (Aiven & pgAdmin)

Documentação técnica oficial da modelagem relacional, infraestrutura de hospedagem e dicionário de dados do projeto **ATMOS (Estação Meteorológica & Telemetria)**.

---

## 📌 Visão Geral da Infraestrutura

O banco de dados relacional do **ATMOS** está hospedado como serviço gerenciado em nuvem no **Aiven for PostgreSQL** e administrado localmente através da interface **pgAdmin 4**.

| Parâmetro | Detalhe Técnico |
| :--- | :--- |
| **Provedor Cloud** | [Aiven](https://aiven.io/) (PostgreSQL Managed Service) |
| **Host / Endpoint** | `atmos-jose-c5d6.i.aivencloud.com` |
| **Porta** | `26811` |
| **Database** | `defaultdb` |
| **Usuário Administrativo** | `avnadmin` |
| **Modo de Conexão SSL** | Obrigatório (`sslmode=require`) |
| **Cliente de Gestão Local** | pgAdmin 4 (PostgreSQL Tools) |
| **Driver da Aplicação** | `psycopg` (Python 3.x / FastAPI) |

> [!NOTE] String de Conexão no `.env`
> Para conexão direta do backend FastAPI (`backend/.env`), adote a URI estruturada:
> ```text
> DATABASE_URL=postgresql://avnadmin:[SENHA]@atmos-jose-c5d6.i.aivencloud.com:26811/defaultdb?sslmode=require
> ```

---

## 🗺️ Diagrama Entidade-Relacionamento (DER)

```mermaid
erDiagram
    ESTACOES ||--o{ LEITURAS : "possui (1:N)"
    ESTACOES ||--o{ ALERTAS_CLIMATICOS : "emite (1:N)"
    LEITURAS ||--o| ALERTAS_CLIMATICOS : "origina (1:N)"

    ESTACOES {
        varchar(20) id PK "Identificador único (ex: ATMOS-01)"
        varchar(100) nome "Nome descritivo da estação"
        double_precision latitude "Coordenada de latitude"
        double_precision longitude "Coordenada de longitude"
        timestamptz criado_em "Registro de inclusão no sistema"
    }

    LEITURAS {
        bigserial id_leitura PK "Identificador sequencial da telemetria"
        varchar(20) estacao_id FK "Vínculo com estacoes(id)"
        numeric(4_2) temperatura "Temperatura aferida (°C)"
        numeric(4_2) umidade "Umidade relativa (%)"
        numeric(4_2) pressao "Pressão barométrica (hPa)"
        numeric(4_2) qualidade_ar "Índice de pureza/gases"
        integer luminosidade "Nível de luminosidade (Lux / ADC)"
        integer chuva "Indicador de precipitação (0/1)"
        timestamptz data_hora "Timestamp da leitura com Timezone"
    }

    ALERTAS_CLIMATICOS {
        serial id_alertas PK "Identificador sequencial do alerta"
        varchar(20) estacao_id FK "Vínculo com estacoes(id)"
        bigint leitura_id FK "Vínculo com leituras(id_leitura)"
        varchar(30) tipo_alerta "Categoria do evento (ex: TEMPESTADE, CALOR)"
        text mensagem "Descrição textual da ocorrência"
        timestamptz data_hora "Momento do acionamento do alerta"
    }
```

---

## 🗄️ Dicionário de Dados

### 1. Tabela: `estacoes`
Armazena o cadastro físico e a geolocalização de cada estação meteorológica ou dispositivo IoT integrado.

| Coluna | Tipo de Dado | Nulo | Default | Descrição |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `VARCHAR(20)` | **NÃO** | — | **Chave Primária**. Código identificador único da estação (ex: `ATMOS-01`). |
| `nome` | `VARCHAR(100)` | **NÃO** | — | Nome descritivo amigável da estação (ex: `Estação Central UNIP`). |
| `latitude` | `DOUBLE PRECISION` | **NÃO** | — | Latitude decimal utilizada na plotagem geográfica no Leaflet. |
| `longitude` | `DOUBLE PRECISION` | **NÃO** | — | Longitude decimal utilizada na plotagem geográfica no Leaflet. |
| `criado_em`| `TIMESTAMPTZ` | **NÃO** | `CURRENT_TIMESTAMP` | Data e hora do cadastro com preservação de fuso horário. |

---

### 2. Tabela: `leituras`
Tabela central de telemetria de séries temporais. Registra todas as amostras coletadas pelos sensores conectados ao microcontrolador (ESP32).

| Coluna | Tipo de Dado | Nulo | Default | Descrição |
| :--- | :--- | :---: | :---: | :--- |
| `id_leitura` | `BIGSERIAL` | **NÃO** | Sequência | **Chave Primária**. Identificador único e sequencial da leitura. |
| `estacao_id` | `VARCHAR(20)` | **NÃO** | — | **Chave Estrangeira** referenciando `estacoes(id)`. |
| `temperatura`| `NUMERIC(4,2)`| **NÃO** | — | Temperatura ambiente aferida em graus Celsius (°C). |
| `umidade` | `NUMERIC(4,2)`| **NÃO** | — | Umidade relativa do ar em percentual (0 a 100%). |
| `pressao` | `NUMERIC(4,2)`| **NÃO** | — | Pressão atmosférica medida pelos sensores barométricos. |
| `qualidade_ar`| `NUMERIC(4,2)`| **NÃO** | — | Concentração/qualidade do ar capturada (ex: MQ-135). |
| `luminosidade`| `INTEGER` | **NÃO** | — | Intensidade de luz incidente (LDR ou sensor digital em Lux). |
| `chuva` | `INTEGER` | **NÃO** | — | Status de chuva: binário (0 = ausência, 1 = chuva) ou leitura analógica. |
| `data_hora` | `TIMESTAMPTZ` | **NÃO** | `CURRENT_TIMESTAMP` | Timestamp oficial de recepção da leitura. |

#### Chaves Estrangeiras & Políticas:
* `fk_estacao_leitura`: `FOREIGN KEY (estacao_id) REFERENCES estacoes(id) ON DELETE CASCADE`
  *(Ao remover uma estação, todas as leituras históricas associadas são excluídas em cascata).*

---

### 3. Tabela: `alertas_climaticos`
Registra anomalias, limites operacionais excedidos ou eventos críticos detectados pelas medições.

| Coluna | Tipo de Dado | Nulo | Default | Descrição |
| :--- | :--- | :---: | :---: | :--- |
| `id_alertas` | `SERIAL` | **NÃO** | Sequência | **Chave Primária**. Identificador do alerta. |
| `estacao_id` | `VARCHAR(20)` | **NÃO** | — | **Chave Estrangeira** referenciando `estacoes(id)`. |
| `leitura_id` | `BIGINT` | SIM | `NULL` | **Chave Estrangeira** referenciando a leitura exata que gerou o disparo. |
| `tipo_alerta`| `VARCHAR(30)` | **NÃO** | — | Classificação (`TEMPERATURA_EXTREMA`, `CHUVA_FORTE`, `AR_TÓXICO`, etc.). |
| `mensagem` | `TEXT` | **NÃO** | — | Texto explicativo da ocorrência gerada pelo sistema. |
| `data_hora` | `TIMESTAMPTZ` | **NÃO** | `CURRENT_TIMESTAMP` | Timestamp em que o alerta foi disparado. |

#### Chaves Estrangeiras & Políticas:
* `fk_estacoes_alerta`: `FOREIGN KEY (estacao_id) REFERENCES estacoes(id) ON DELETE CASCADE`
* `fk_leitura_alerta`: `FOREIGN KEY (leitura_id) REFERENCES leituras(id_leitura) ON DELETE SET NULL`
  *(Se a leitura for arquivada ou removida, o histórico de alertas mantém o registro desvinculado).*

---

## 💻 Script DDL de Criação (PostgreSQL Oficial)

Script executado no **pgAdmin 4** com sucesso para criação do schema no Aiven:

```sql
-- 1. Criação da tabela de estações meteorológicas
CREATE TABLE IF NOT EXISTS estacoes (
    id VARCHAR(20) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Criação da tabela de leituras e telemetria
CREATE TABLE IF NOT EXISTS leituras (
    id_leitura BIGSERIAL PRIMARY KEY,
    estacao_id VARCHAR(20) NOT NULL,
    temperatura NUMERIC(4,2) NOT NULL,
    umidade NUMERIC(4,2) NOT NULL,
    pressao NUMERIC(4,2) NOT NULL,
    qualidade_ar NUMERIC(4,2) NOT NULL,
    luminosidade INTEGER NOT NULL,
    chuva INTEGER NOT NULL,
    data_hora TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_estacao_leitura
        FOREIGN KEY (estacao_id)
        REFERENCES estacoes(id)
        ON DELETE CASCADE
);

-- 3. Criação da tabela de alertas de eventos meteorológicos
CREATE TABLE IF NOT EXISTS alertas_climaticos (
    id_alertas SERIAL PRIMARY KEY,
    estacao_id VARCHAR(20) NOT NULL,
    leitura_id BIGINT,
    tipo_alerta VARCHAR(30) NOT NULL,
    mensagem TEXT NOT NULL,
    data_hora TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_estacoes_alerta 
        FOREIGN KEY (estacao_id)
        REFERENCES estacoes(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_leitura_alerta
        FOREIGN KEY (leitura_id)
        REFERENCES leituras(id_leitura)
        ON DELETE SET NULL
);
```

---

## ⚡ Consultas e Índices Recomendados para Otimização

Como a tabela `leituras` cresce como série temporal contínua e as consultas mais comuns no FastAPI filtram por estação e ordenam por data (`ORDER BY data_hora DESC`), os seguintes índices são recomendados no ambiente de produção:

```sql
-- Índice composto para acelerar buscar_ultima e buscar_historico
CREATE INDEX IF NOT EXISTS idx_leituras_estacao_data 
ON leituras (estacao_id, data_hora DESC);

-- Índice para busca rápida de alertas por estação
CREATE INDEX IF NOT EXISTS idx_alertas_estacao_data 
ON alertas_climaticos (estacao_id, data_hora DESC);
```

---

## 🔌 Consumo no Código da Aplicação (FastAPI)

1. **Ingestão (`POST /api/dados`):**
   ```python
   # Executado via app.repositories.leitura_repository.inserir
   INSERT INTO leituras (estacao_id, temperatura, umidade, pressao, qualidade_ar, luminosidade, chuva)
   VALUES (%s, %s, %s, %s, %s, %s, %s);
   ```

2. **Última Leitura (`GET /api/dados?estacao_id=ATMOS-01`):**
   ```python
   # Executado via app.repositories.leitura_repository.buscar_ultima
   SELECT estacao_id, temperatura, umidade, pressao, qualidade_ar, luminosidade, chuva, data_hora
   FROM leituras
   WHERE estacao_id = %s
   ORDER BY data_hora DESC
   LIMIT 1;
   ```

3. **Histórico para Gráficos (`GET /api/historico?estacao_id=ATMOS-01&limite=100`):**
   ```python
   # Executado via app.repositories.leitura_repository.buscar_historico
   SELECT estacao_id, temperatura, umidade, pressao, qualidade_ar, luminosidade, chuva, data_hora
   FROM leituras
   WHERE estacao_id = %s
   ORDER BY data_hora DESC
   LIMIT %s;
   ```
