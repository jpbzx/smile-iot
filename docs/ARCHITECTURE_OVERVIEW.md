# 🏗️ SMILE-IoT Architecture Overview

## Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura em Camadas](#arquitetura-em-camadas)
3. [Componentes Principais](#componentes-principais)
4. [Fluxos de Dados](#fluxos-de-dados)
5. [Integração de Componentes](#integração-de-componentes)
6. [Tecnologias Stack](#tecnologias-stack)
7. [Segurança e Configuração](#segurança-e-configuração)
8. [Estado Atual e Roadmap](#estado-atual-e-roadmap)

---

## Visão Geral

**SMILE-IoT** é um sistema IoT de monitorização **não-invasiva** de consumo energético em instalações AC domésticas e comerciais. Funciona recolhendo leituras de sensores em tempo real, processando-as em edge (ESP32), transmitindo para backend via MQTT, e apresentando dados através de um dashboard interativo com capacidades de controlo e análise.

```
Objetivo Primário: Medir consumo energético AC sem interrupção de circuito
Precisão: ±3% em corrente, atualização: 5 segundos
Segurança: Controlo de overcurrent com relay automático
Alcance: Instalações residenciais e comerciais até 30A
```

---

## Arquitetura em Camadas

### Diagrama de Arquitetura em 4 Camadas

```mermaid
graph TD
    subgraph USER["👥 UTILIZADOR FINAL"]
        U["Browser/Mobile"]
    end
    
    subgraph PRESENTATION["🎨 CAMADA APRESENTAÇÃO"]
        P1["Streamlit Dashboard"]
        P2["Login & RBAC"]
        P3["Gráficos Tempo Real"]
        P4["Controlo Relay"]
    end
    
    subgraph APPLICATION["🔄 CAMADA APLICAÇÃO"]
        A1["MQTT Subscriber"]
        A2["Parser CSV"]
        A3["Enriquecimento Dados"]
    end
    
    subgraph DATABASE["💾 CAMADA DADOS"]
        D1["PostgreSQL<br/>Utilizadores"]
        D2["InfluxDB<br/>Série Temporal"]
    end
    
    subgraph IOT["🔌 CAMADA IOT"]
        I1["Sensor SCT-013"]
        I2["Op-Amp & ADC"]
        I3["Firmware ESP32<br/>C++ Arduino"]
        I4["WiFi & MQTT"]
    end
    
    U -->|HTTP| P1
    P1 --> P2 & P3 & P4
    
    I1 -->|Sinal Analógico| I2
    I2 -->|Sinal Digital| I3
    I3 -->|Payload| I4
    
    I4 -->|MQTT Publish| A1
    P4 -->|MQTT Command| I4
    
    A1 -->|Dados Brutos| A2
    A2 -->|Valores Extraídos| A3
    
    A3 -->|Write| D1
    A3 -->|Write Metrics| D2
    
    P2 -.->|Query/Auth| D1
    P3 -.->|Query Metrics| D2
```

---

## Componentes Principais

### 1️⃣ Hardware (Percepção)

#### Sensor: SCT-013-030
- **Tipo**: Transformador de corrente AC (pinça magnética)
- **Range**: 0-30A AC, saída 0-1V
- **Precisão**: ±3%
- **Delay**: ~0.5s
- **Aplicação**: Mede corrente sem quebra de circuito (non-invasive)

**Diagrama do Sensor:**
```mermaid
graph LR
    A["⚡ Condutor AC<br/>Load Circuit"] -->|Campo Magnético| B["🧲 Núcleo Magnético<br/>SCT-013"]
    B -->|Indução Mútua| C["📊 Saída 0-1V<br/>Secundário"]
    C -->|Sinal Fraco| D["🔊 Op-Amp<br/>Amplificador<br/>Ganho 30x"]
    D -->|0-3.3V| E["🎚️ ADC 12-bit<br/>ESP32<br/>0-4095"]
```

#### Condicionamento de Sinal
- **Op-Amp**: Amplifica saída 0-1V para 0-3.3V (range do ADC do ESP32)
- **Fator de escala**: ~30x
- **Resultado**: ADC lê valores 0-4095 correspondentes a 0-30A

#### Microcontrolador: ESP32 DevKit V1
- **Processador**: Dual-core Xtensa 32-bit @ 240MHz
- **RAM**: 520KB SRAM
- **Storage**: 4MB Flash
- **WiFi**: 802.11 b/g/n (nativo)
- **ADC**: 12-bit, até 18 canais, ~10 kHz sampling
- **GPIO**: Controla relay de corte (GPIO 25)

---

### 2️⃣ Firmware (Edge Processing)

**Localização**: `firmware/src/main.cpp`

#### Fluxo de Execução Principal

```mermaid
flowchart TD
    A["🔌 Startup<br/>Inicialização"] --> B["📡 WiFi Connect"]
    B --> C["🔌 MQTT Connect<br/>broker.emqx.io:1883"]
    C --> D["📌 Subscribe<br/>smile-iot/command"]
    
    D --> E["🔄 MAIN LOOP"]
    
    E --> F["📖 ADC Read<br/>GPIO 34<br/>~10kHz sampling"]
    F --> G["⚙️ Cálculo RMS<br/>100 amostras<br/>40ms - Rápido"]
    G --> H["⚙️ Cálculo RMS<br/>2500 amostras<br/>1s - Preciso"]
    
    H --> I{"5 segundos<br/>passaram?"}
    I -->|NÃO| J["⏳ Delay 10ms"]
    I -->|SIM| K["📤 MQTT Publish<br/>CSV Format"]
    
    K --> L{"Corrente<br/>I > 15A?"}
    L -->|NÃO| J
    L -->|SIM| M["🚨 Relay OFF<br/>GPIO 25 = LOW<br/>Segurança"]
    
    M --> J
    J --> E
```

#### Cálculo RMS Dual

O firmware implementa **dois tipos de RMS**:

| Tipo | Amostras | Período | Latência | Uso |
|------|----------|---------|----------|-----|
| **Rápido** | 100 | 40ms | Imediato | Detecção de overcurrent (segurança) |
| **Preciso** | 2500 | 1s | 1s | Qualidade telemetria (relatórios) |

**Fórmula RMS:**
```
I_rms = √(Σ(i_n)²) / N
```

Onde:
- `i_n` = amostra de corrente (ADC 0-4095 mapeada para 0-30A)
- `N` = número de amostras

#### Payload MQTT

**Tema**: `smile-iot/power`

**Formato**: CSV compacto (4 valores)
```csv
5.23,5.18,1,5.20
│    │    │  │
│    │    │  └─ RMS Preciso (2500 amostras)
│    │    └────── Relay Status (1=ON, 0=OFF)
│    └───────────── RMS Rápido (100 amostras)
└────────────────── Peak Instantâneo
```

**Tamanho**: ~30 bytes (vs ~200 bytes em JSON) = **85% redução**

---

### 3️⃣ Backend (Orquestração de Dados)

**Localização**: `software/`

#### Componentes

```mermaid
graph TB
    subgraph BACKEND["🐍 PYTHON BACKEND"]
        B["MQTT Subscriber<br/>paho-mqtt"]
        P["Parser CSV<br/>Extract Values"]
        E["Enricher<br/>Add power_W"]
    end
    
    subgraph PG["🗄️ POSTGRESQL 15"]
        U["Users Table<br/>username, email"]
        C["Credentials<br/>bcrypt hash"]
        R["RBAC Roles<br/>user/admin"]
    end
    
    subgraph IDB["⏱️ INFLUXDB 2.7"]
        M["Measurement<br/>energy_reading"]
        RT["Retenção<br/>90 dias"]
    end
    
    subgraph UI["🎨 STREAMLIT UI"]
        L["Login Panel"]
        D["Dashboard<br/>Gráficos & KPIs"]
        A["Admin Panel"]
    end
    
    B -->|Parse CSV| P
    P -->|Enrich| E
    E -->|Auth Validate| U
    E -->|Write Point| M
    M --> RT
    
    UI -->|Query| U
    UI -->|Query| M
    D -->|MQTT Cmd| B
```

#### MQTT Client (`utils/mqtt_client.py`)

```python
# Configuração
client = mqtt.Client(client_id="smile-dashboard")
client.connect(broker="broker.emqx.io", port=1883, keepalive=60)
client.subscribe("smile-iot/power")

# Callback ao receber mensagem
def on_message(client, userdata, msg):
    # Parse CSV
    rms_fast, rms_precise, relay_status, rms_1s = parse_csv(msg.payload)
    
    # Enriquecimento
    power_W = 230V * rms_precise
    
    # Escrever para InfluxDB
    write_to_influx(current_A=rms_precise, power_W=power_W, timestamp=now)
```

#### PostgreSQL Manager (`db/postgres_manager.py`)

**Schema Principal**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,      -- bcrypt hash
    role VARCHAR(20) DEFAULT 'user',          -- 'user' or 'admin'
    failed_attempts INT DEFAULT 0,
    locked_until TIMESTAMP,                   -- Lockout após 5 tentativas
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE password_resets (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Fluxo de Autenticação**:
```mermaid
flowchart TD
    A["🔑 Login Form"] --> B["Utilizador Input<br/>username + password"]
    B --> C["Query PostgreSQL"]
    C --> D{"User<br/>Exists?"}
    
    D -->|NÃO| E["❌ Error:<br/>Invalid Credentials"]
    
    D -->|SIM| F["bcrypt.checkpw<br/>Verify Password"]
    F --> G{"Password<br/>Correto?"}
    
    G -->|NÃO| H["📈 Incrementa<br/>failed_attempts"]
    H --> I{"Tentativas<br/>> 5?"}
    I -->|NÃO| E
    I -->|SIM| J["🔒 Lockout<br/>15 minutos"]
    J --> K["❌ Too Many Attempts"]
    
    G -->|SIM| L["✅ Autenticação OK"]
    L --> M["📋 Session State<br/>user_id, role"]
    M --> N["🎨 Redirect<br/>Dashboard"]
```

#### InfluxDB Manager (`db/influx_manager.py`)

**Bucket**: `energy_data`  
**Organização**: `smile_org`  
**Retenção**: 90 dias

**Schema (Measurement)**:
```
Measurement: energy_reading
├─ Tags (indexed):
│  ├─ device_id: "esp32-001"
│  └─ sensor_type: "SCT-013-030"
├─ Fields (values):
│  ├─ current_A: 5.23 (float)
│  ├─ power_W: 1202.9 (float)
│  ├─ relay_status: 1 (int, 0=OFF 1=ON)
│  └─ rms_fast: 5.18 (float)
└─ Timestamp: 2026-05-22T14:30:45Z
```

**Exemplo de escrita**:
```python
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

client = InfluxDBClient(url="http://localhost:8086", token="token", org="smile_org")
write_api = client.write_api(write_options=SYNCHRONOUS)

point = Point("energy_reading") \
    .tag("device_id", "esp32-001") \
    .field("current_A", 5.23) \
    .field("power_W", 1202.9) \
    .field("relay_status", 1) \
    .time(datetime.utcnow(), WritePrecision.NS)

write_api.write(bucket="energy_data", record=point)
```

---

### 4️⃣ Dashboard (Streamlit)

**Localização**: `software/app.py` + `software/views/`

#### Estrutura de Páginas

```mermaid
graph TD
    A["🎨 Streamlit App<br/>app.py"] -->|Check| B{"Autenticado?"}
    
    B -->|NÃO| C["🔑 LOGIN PAGE<br/>views/login.py"]
    C -->|Submit| D["🗄️ PostgreSQL<br/>Verify Credentials"]
    D -->|OK| A
    
    B -->|SIM<br/>role=user| E["📊 DASHBOARD<br/>views/dashboard.py"]
    B -->|SIM<br/>role=admin| F["⚙️ ADMIN PANEL<br/>views/admin_panel.py"]
    
    E --> E1["📈 Série Temporal<br/>Gráfico Altair"]
    E --> E2["💡 KPIs em Tempo Real<br/>Métrica Cards"]
    E --> E3["🔌 Controlo Relay<br/>ON/OFF Button"]
    
    F --> F1["👤 Gestão Utilizadores<br/>CRUD"]
    F --> F2["📋 Logs & Audit<br/>Activity"]
    
    A -->|Sempre| G["👤 PROFILE<br/>views/profile.py"]
```

#### Dashboard Principal

**Componentes principais**:

1. **Série Temporal (Gráfico)**
   - Query InfluxDB: últimas 24h
   - Biblioteca: Altair (vega-lite)
   - Atualização: a cada 5s (st.rerun)
   - Métrica: Corrente (A) ou Potência (W)

```python
# Query InfluxDB para últimas 24h
query = 'from(bucket: "energy_data") \
         |> range(start: -24h) \
         |> filter(fn: (r) => r._measurement == "energy_reading") \
         |> filter(fn: (r) => r._field == "current_A")'

# DataFrame + Gráfico Altair
df = client.query_api().query_data_frame(query)
chart = alt.Chart(df).mark_line().encode(x='_time', y='_value')
st.altair_chart(chart, use_container_width=True)
```

2. **KPIs em Tempo Real**
   - Corrente Atual (A)
   - Potência Atual (W)
   - Energia Acumulada (kWh)
   - Status Relay (ON/OFF)

```python
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Corrente", f"{current_A:.2f} A", delta="↑ 0.5A")
with col2:
    st.metric("Potência", f"{power_W:.0f} W", delta="↑ 100W")
```

3. **Controlo de Relay**
   - Botão ON/OFF
   - MQTT Publish: `smile-iot/command` com payload `1` ou `0`
   - Feedback em tempo real

```python
if st.button("Desligar Relay", key="relay_off"):
    mqtt_client.publish("smile-iot/command", payload="0")
    st.success("Relay desligado!")
```

---

## Fluxos de Dados

### 1. Fluxo de Leitura (Telemetria)

```mermaid
graph LR
    A["⚡ Corrente AC<br/>Load Circuit"] -->|0-30A| B["🧲 Sensor<br/>SCT-013-030"]
    B -->|0-1V| C["🔊 Op-Amp<br/>Gain 30x"]
    C -->|0-3.3V| D["🎚️ ADC<br/>ESP32<br/>10kHz"]
    D -->|RMS Calc<br/>100 & 2500| E["⚙️ Firmware<br/>Calculate RMS"]
    E -->|CSV<br/>5.23,5.18,1,5.20| F["📤 MQTT Publish<br/>broker.emqx.io"]
    F -->|Topic:<br/>smile-iot/power| G["📥 Python<br/>Subscriber"]
    G -->|Parse| H["📊 Parser<br/>Extract Values"]
    H -->|Enrich<br/>Power = 230V×I| I["🧮 Enricher<br/>Add Metadata"]
    I -->|Write Point| J["💾 InfluxDB<br/>energy_reading"]
    J -->|Query 24h| K["🎨 Streamlit<br/>Dashboard"]
    K -->|HTTP| L["👥 Browser<br/>End-User"]
```

**Latência Total**: ~2-3 segundos (ADC 40ms + MQTT 500ms + Backend 500ms + Query 300ms + Render 300ms)

---

### 2. Fluxo de Controlo (Comando Bidirecional)

```mermaid
graph LR
    A["🎨 Streamlit<br/>Dashboard"] -->|Click| B["Utilizador<br/>ON/OFF Button"]
    B -->|Payload 1/0| C["📡 MQTT Publish<br/>smile-iot/command"]
    C -->|Subscribe| D["☁️ MQTT Broker<br/>broker.emqx.io"]
    D -->|Callback| E["🔌 ESP32<br/>Firmware"]
    E -->|GPIO 25| F["🎚️ digitalWrite<br/>HIGH / LOW"]
    F -->|Controla| G["🔌 Relay<br/>AC Contactor"]
    G -->|Muda Estado| H["⚡ Load<br/>ON/OFF"]
    H -->|Status Update| I["📤 MQTT Publish<br/>smile-iot/power"]
    I -->|Feedback| J["📥 Python<br/>Backend"]
    J -->|Write| K["💾 InfluxDB<br/>relay_status"]
    K -->|st.rerun| L["🎨 Dashboard<br/>Refresh"]
```

**Latência Total**: ~1-2 segundos (UI click 100ms + MQTT 500ms + Relay 100ms + MQTT feedback 500ms + Dashboard refresh 300ms)

---

### 3. Fluxo de Autenticação

```mermaid
graph TD
    A["🔑 Login Form<br/>views/login.py"]
    B["Utilizador input:<br/>username + password"]
    C["📤 POST /login<br/>Streamlit form"]
    D["🗄️ PostgreSQL Query<br/>SELECT * FROM users"]
    E{"User<br/>Exists?"}
    F["🔐 bcrypt.checkpw<br/>verify password"]
    G{"Password<br/>Correct?"}
    H["📈 Incrementa failed_attempts"]
    I{"Tentativas<br/>>= 5?"}
    J["🔒 Lockout<br/>locked_until = NOW() + 15min"]
    K["❌ Error: Too many attempts"]
    L["❌ Error: Invalid password"]
    M["✅ Match!"]
    N["📋 st.session_state<br/>user_id, username, role"]
    O["📊 Redirect Dashboard"]
    
    A --> B
    B --> C
    C --> D
    D --> E
    E -->|Não| L
    E -->|Sim| F
    F --> G
    G -->|Não| H
    H --> I
    I -->|Sim| J
    I -->|Não| L
    J --> K
    G -->|Sim| M
    M --> N
    N --> O
```

---

## Integração de Componentes

### Diagrama de Dependências

```mermaid
graph TB
    FW["🔌 FIRMWARE<br/>main.cpp"]
    LIB1["📚 EmonLib<br/>RMS"]
    LIB2["📚 PubSubClient<br/>MQTT"]
    
    FW -->|usa| LIB1
    FW -->|usa| LIB2
    FW -->|publica| MQTT["☁️ MQTT BROKER<br/>broker.emqx.io"]
    
    MQTT -->|subscribe| MQTT_CLI["📡 mqtt_client.py"]
    
    MQTT_CLI -->|parse| PARSER["📊 Parser<br/>CSV → Dict"]
    PARSER -->|enrich| ENRICHER["🧮 Enricher<br/>Add power_W"]
    
    ENRICHER -->|escreve| IDB["⏱️ InfluxDB<br/>Timeseries"]
    ENRICHER -->|valida| PG["🗄️ PostgreSQL<br/>Users DB"]
    
    PG_MGR["📄 postgres_manager.py"]
    IDB_MGR["📄 influx_manager.py"]
    
    PG_MGR -->|queries| PG
    IDB_MGR -->|queries| IDB
    
    DASHBOARD["🎨 STREAMLIT APP<br/>app.py"]
    
    DASHBOARD -->|imports| MQTT_CLI
    DASHBOARD -->|imports| PG_MGR
    DASHBOARD -->|imports| IDB_MGR
    
    LOGIN["🔑 views/login.py"]
    DASH_VIEW["📊 views/dashboard.py"]
    ADMIN["⚙️ views/admin_panel.py"]
    
    DASHBOARD -->|routes| LOGIN
    DASHBOARD -->|routes| DASH_VIEW
    DASHBOARD -->|routes| ADMIN
    
    LOGIN -->|auth| PG_MGR
    DASH_VIEW -->|query| IDB_MGR
    DASH_VIEW -->|publish| MQTT
    ADMIN -->|manage| PG_MGR
```

### Matriz de Dependências

| Componente | Depende De | Fornece | Interface |
|-----------|-----------|---------|-----------|
| **Firmware** | EmonLib, PubSubClient, WiFi | MQTT Messages (CSV) | Tema: `smile-iot/power` |
| **MQTT Client** | paho-mqtt, PostgreSQL | Dados Enriquecidos | InfluxDB Write API |
| **PostgreSQL Mgr** | psycopg2, bcrypt | Validação Utilizadores | SELECT, INSERT, UPDATE |
| **InfluxDB Mgr** | influxdb-client | Query Série Temporal | InfluxDB Query API |
| **Streamlit App** | Todos os anteriores | UI Interativa | HTTP (Browser) |

---

## Tecnologias Stack

### Frontend
- **Streamlit**: Framework Python para UI web
- **Altair**: Visualização de dados (Vega-Lite)
- **Python**: Linguagem principal backend

### Backend
- **Python 3.8+**
- **paho-mqtt**: Cliente MQTT
- **pandas**: Data manipulation
- **python-dotenv**: Gestão de variáveis de ambiente

### Bases de Dados
- **PostgreSQL 15**: Utilizadores, RBAC, credenciais
- **InfluxDB 2.7**: Série temporal (energy readings)

### Orquestração
- **Docker Compose**: Containerização de serviços
- **Docker**: Isolamento de ambiente

### Segurança
- **bcrypt**: Hash de passwords
- **SMTPLIB**: Email para password reset

### Hardware
- **ESP32 DevKit V1**: Microcontrolador
- **C++ (Arduino)**: Firmware
- **PlatformIO**: Build system para firmware
- **EmonLib**: Cálculo RMS

### Comunicação
- **MQTT**: Protocol de publish-subscribe
- **broker.emqx.io**: Public MQTT broker (free tier)
- **WiFi 802.11**: Conectividade ESP32

---

## Segurança e Configuração

### Variáveis de Ambiente (`.env`)

```bash
# PostgreSQL Configuração
DB_HOST=localhost
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=your_secure_password
DB_NAME=smile_iot_users

# InfluxDB Configuração
INFLUX_URL=http://localhost:8086
INFLUX_ORG=smile_org
INFLUX_BUCKET=energy_data
INFLUX_ADMIN_TOKEN=your_influx_token

# MQTT Configuração
MQTT_BROKER=broker.emqx.io
MQTT_PORT=1883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password

# Email (Password Reset)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Segurança
MAX_FAILED_ATTEMPTS=5
LOCKOUT_MINUTES=15
SESSION_TIMEOUT_MIN=30
PASSWORD_RESET_EXPIRES_MIN=60

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### Segurança: Boas Práticas Implementadas

✅ **Implementado:**
- Passwords com bcrypt (hash seguro)
- Lockout após 5 tentativas falhadas
- Session management via Streamlit
- PostgreSQL com queries parametrizadas (SQL injection prevention)
- RBAC (role-based access control) user/admin

⚠️ **Em Progresso:**
- Variáveis de ambiente em `.env` (não commitado)
- MQTT sem TLS (recomendação: usar porta 8883 com TLS)

🔴 **TODO:**
- Autenticação 2FA
- HTTPS para Streamlit
- Refresh tokens
- Audit logging completo
- Encriptação de dados sensíveis em repouso

---

## Estado Atual e Roadmap

### ✅ Funcionalidades Implementadas (v0.2-beta)

| Feature | Status | Detalhe |
|---------|--------|---------|
| **Leitura RMS** | ✅ Completo | Dual mode (rápido 40ms + preciso 1s) |
| **MQTT Publish** | ✅ Completo | CSV compacto, 5s update interval |
| **PostgreSQL** | ✅ Completo | Users, RBAC, password reset |
| **InfluxDB** | ✅ Completo | 90 dias retenção, query API |
| **Dashboard** | ✅ Completo | Gráficos, KPIs, controlo relay |
| **Autenticação** | ✅ Completo | bcrypt, lockout, password reset |
| **RBAC** | ✅ Completo | user vs admin roles |
| **Controlo Relay** | ✅ Completo | ON/OFF via MQTT bidirecional |
| **Overcurrent Safety** | ✅ Completo | Relay OFF automático se I > 15A |
| **Docker** | ✅ Completo | Compose para PostgreSQL + InfluxDB |
| **Bootstrap** | ✅ Completo | Scripts automáticos setup |

### 🟡 Em Desenvolvimento

| Feature | Status | ETA |
|---------|--------|-----|
| **Testes Integração** | 🟡 Em progresso | v0.3 |
| **Refinamento InfluxDB Pipeline** | 🟡 Optimização | v0.3 |
| **Autenticação 2FA** | 🟡 Design | v0.4 |

### 🔵 Planeados (Backlog)

| Feature | Prioridade | Detalhe |
|---------|-----------|---------|
| **API REST** | 🔴 Alta | Expor dados/controlo via HTTP |
| **Alertas & Notificações** | 🔴 Alta | Email/SMS se I > threshold |
| **Múltiplos Sensores** | 🔴 Alta | Suporte n dispositivos por instalação |
| **Cálculo de Custos** | 🟡 Média | kWh → € baseado em tarifário |
| **Exportação Relatórios** | 🟡 Média | PDF/CSV com dados históricos |
| **Previsão de Consumo** | 🟠 Baixa | ML para trending (ARIMA/Prophet) |
| **Mobile App** | 🟠 Baixa | React Native ou Flutter |
| **Cloud Sync** | 🟠 Baixa | Backup remoto de dados |

---

## Diagrama de Fluxo Completo

```mermaid
graph TD
    subgraph HARDWARE["🔧 HARDWARE LAYER"]
        A["⚡ Condutor AC"]
        B["🧲 Sensor<br/>SCT-013"]
        C["🔊 Op-Amp<br/>Amplifier"]
        D["🎚️ ADC<br/>ESP32"]
    end
    
    subgraph FIRMWARE["🔌 FIRMWARE LAYER"]
        E["Firmware<br/>main.cpp"]
        F["RMS Calc<br/>100 & 2500"]
        G["CSV Format<br/>5.23,5.18,1,5.20"]
    end
    
    subgraph COMM["☁️ COMMUNICATION"]
        H["MQTT Publish<br/>smile-iot/power"]
        I["MQTT Broker<br/>broker.emqx.io"]
        J["MQTT Subscribe<br/>smile-iot/command"]
    end
    
    subgraph BACKEND["🐍 BACKEND LAYER"]
        K["Parser<br/>CSV → Dict"]
        L["Enricher<br/>Add power_W"]
        M["Validator<br/>PostgreSQL"]
    end
    
    subgraph DATABASE["💾 DATABASE LAYER"]
        N["PostgreSQL<br/>Users & RBAC"]
        O["InfluxDB<br/>Série Temporal<br/>90 dias"]
    end
    
    subgraph UI["🎨 PRESENTATION LAYER"]
        P["Streamlit App"]
        Q["Login & Auth"]
        R["Dashboard<br/>Gráficos & KPIs"]
        S["Admin Panel"]
    end
    
    subgraph CLIENT["👥 END-USER"]
        T["Browser<br/>View & Control"]
    end
    
    A -->|0-30A| B
    B -->|0-1V| C
    C -->|0-3.3V| D
    D -->|ADC| E
    E -->|RMS| F
    F -->|CSV| G
    G -->|Publish| H
    H -->|Topic| I
    I -->|Subscribe| K
    
    K -->|Parse| L
    L -->|Enrich| M
    M -->|Write| N
    M -->|Write| O
    
    P -->|Query| Q
    P -->|Query| R
    P -->|Query| S
    
    Q -->|Auth| N
    R -->|Data| O
    R -->|Publish| J
    J -->|Command| I
    I -->|Relay Cmd| E
    
    P -->|HTTP| T
    T -->|Click/View| P
```

---

## Conclusão

SMILE-IoT é um sistema **modular, escalável e seguro** para monitorização de consumo energético. A arquitetura em 4 camadas (Hardware → Firmware → Backend → Dashboard) permite fácil expansão e manutenção.

**Principais características:**
- ⚡ Leitura não-invasiva até 30A AC
- 🔒 Segurança com bcrypt + RBAC + lockout
- 📊 Série temporal com 90 dias retenção
- 🎨 Dashboard interativo em tempo real
- 🔌 Controlo bidirecional de relay
- 🚨 Proteção automática contra overcurrent
- 🐳 Fácil deployment com Docker

---

**Documentação Relacionada:**
- [SPEC.md](SPEC.md) — Especificação técnica detalhada
- [INFLUXDB_IMPLEMENTATION.md](INFLUXDB_IMPLEMENTATION.md) — Detalhes InfluxDB
- [AGENT_README.md](AGENT_README.md) — Documentação de agentes
