# SMILE-IoT: Local Energy Monitoring and Inspection System via IoT

**Última atualização:** Maio 25, 2026  
**Ramo ativo:** `feature/set_sistem_4_prodReady`  
**Versão:** v0.2-beta (Production Ready)

---

## 1. Visão Geral do Projeto

**SMILE-IoT** é um sistema embarcado de prototipagem para monitorização **não-invasiva** do consumo de energia elétrica em corrente alternada (AC). O projeto foi desenvolvido para auditar e perfilar o consumo de equipamentos ou painéis elétricos de forma rápida, segura e económica, **sem necessidade de interrupção de circuitos ou intervenções elétricas complexas**.

O sistema une competências de:
- **Engenharia Elétrica**: Aquisição e condicionamento de sinais analógicos, cálculo de potência
- **Engenharia Informática**: Processamento em microcontrolador, transmissão IoT, visualização em tempo real

**Caso de uso principal**: Inspecção de instalações elétricas, auditorias energéticas, monitorização de consumo em tempo real.

---

## 2. Estado Atual do Projeto

### Rama de Desenvolvimento
- **Rama ativa:** `feature/set_sistem_4_prodReady` (HEAD)
- **Rama principal:** `main` (merged)
- **Última feature implementada:** Sistema preparado para produção com Docker environment completo

### Milestones Completados
1. ✅ **Leitura de sensores SCT-013** (feature/SCT-013_implementation)
2. ✅ **Transmissão MQTT com JSON** (firmware e backend)
3. ✅ **Dashboard Streamlit (multi-page)** — views: `login`, `dashboard`, `admin`
4. ✅ **Integração PostgreSQL** (utilizadores, colunas de email, gestão de passwords)
5. ✅ **Integração InfluxDB** (série temporal de energia)
6. ✅ **Orquestração Docker** (docker-compose para DB + Broker)
7. ✅ **Database managers e configuração Docker** (scripts em `software/db/`)
8. ✅ **Melhorias em utilitários MQTT** (`utils/mqtt_client.py` enhancements)
9. ✅ **Funcionalidades de utilizador**: criação de utilizadores, atualização de password, página de perfil

### Milestones Em Desenvolvimento
- 🟡 TLS/SSL MQTT encryption
- 🟡 Múltiplos sensores por instalação
- 🟡 API REST completa

### Milestones Planeados
- ⭕ API REST completa
- ⭕ Alertas e notificações
- ⭕ Múltiplos sensores por instalação
- ⭕ Cálculo de custos energéticos
- ⭕ Exportação de relatórios

---

## 3. Arquitetura do Sistema

### Diagrama Lógico de Blocos
```
[ AC Electrical Grid @ 230V ] 
       │
       ▼ (Magnetic Field)
┌────────────────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│ 1. SCT-013 Sensor          ├─────►│ 2. Signal         ├─────►│ 3. ESP32         │
│    (Current Transformer    │      │    Conditioning   │      │    (12-bit ADC)  │
│     30A/1V, 0.5s delay)    │      │    (Op-amp)       │      │    RMS Proc.     │
└────────────────────────────┘      └───────────────────┘      └─────────┬────────┘
                                                                        │
                                                    ┌───────────────────┼───────────────────┐
                                                    │                   │                   │
                                                    ▼ (Wi-Fi/MQTT)      │                   │
                                        ┌──────────────────────┐        │                   │
                                        │ 4. MQTT Broker       │        │                   │
                                        │ (EMQX/Mosquitto)     │        │                   │
                                        └──────────┬───────────┘        │                   │
                                                   │                    │                   │
                                                   ▼                    ▼                   ▼
                                    ┌──────────────────────┐  ┌─────────────────┐  ┌──────────────────┐
                                    │ 5. PostgreSQL DB     │  │ 6. InfluxDB     │  │ 7. Streamlit     │
                                    │ (Utilizadores)       │  │ (Série Temporal)│  │    Dashboard     │
                                    └─────────┬────────────┘  └────────┬────────┘  └────────┬─────────┘
                                              │                        │                   │
                                              └────────────┬───────────┴───────────────────┘
                                                           │
                                                           ▼
                                                   ┌──────────────────┐
                                                   │ 8. End User      │
                                                   │ (Browser/Mobile) │
                                                   └──────────────────┘
```

---

## 4. Camada de Perception (Hardware)

### Sensor de Corrente: SCT-013-030
- **Tipo:** Current Transformer (CT) de efeito de pinca magnética
- **Especificações:**
  - Alcance: 0-30A AC
  - Saída: 0-1V (em carga de 18Ω)
  - Delay: ~0.5s
  - Precisão: ±3% (tipicamente)
- **Aplicação:** Medição não-invasiva sem corte de condutores

### Condicionamento de Sinal
- **Amplificador:** Op-amp (e.g., LM358, TL072)
- **Objectivo:** Amplificar sinal analógico ~0-1V para range do ADC do ESP32 (0-3.3V)
- **Filtro:** Passa-baixo para reduzir ruído RF

### Microcontrolador: ESP32
- **ADC:** 12-bit, ~100 ksps
- **Wi-Fi:** 802.11 b/g/n
- **Conectividade:** Nativa MQTT via bibliotecas (PubSubClient)
- **Processamento:** Cálculo RMS em tempo real, agregação de dados

---

## 5. Camada de Firmware (ESP32 - Arduino)

### Localização
```
firmware/
├── src/
│   └── main.cpp             # Logic principal (leitura SCT, cálculo RMS, envio MQTT)
├── include/                 # Headers
├── lib/                      # Bibliotecas custom
├── platformio.ini           # Configuração PlatformIO
└── test/
```

### Dependências
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
  - bblanchon/ArduinoJson      # Serialização JSON
  - pubsubclient               # Cliente MQTT
  - openenergymonitor/EmonLib  # Cálculo de RMS/Potência
```

### Funcionalidades Implementadas
1. **Leitura ADC:** Amostragem de tensão do SCT-013 a ~10 kHz
2. **Cálculo RMS:** Usando EmonLib para determinar corrente RMS
3. **Encapsulamento JSON:** Pacotes MQTT com corrente e estado de saída
4. **Controlo de Relay:** Recebimento de comandos MQTT para ligar/desligar saída
5. **Proteção de Corrente:** Limite de 15A com desligação automática

### Formato de Dados MQTT (TX)
```json
{
  "current_A": 5.23,
  "outlet_state": "ON"
}
```
**Nota:** `power_W` e `voltage_V` são calculados no backend usando tensão nominal (230V PT).

---

## 6. Camada de Transporte (Network)

### Protocolo MQTT
- **Broker:** Configurável (padrão: `broker.emqx.io`)
- **Port:** 1883 (TCP/MQTT não-criptografado)
- **Topics:**
  - **RX (Dashboard → ESP32):** `smile-iot/command` (comandos: "ON"/"OFF")
  - **TX (ESP32 → Dashboard):** `smile-iot/power` (dados em tempo real)

### Segurança (Atual)
- ⚠️ Sem autenticação MQTT
- ⚠️ Sem criptografia (não usa TLS)
- ⚠️ Broker público (EMQX)
- **TODO:** Implementar autenticação e broker privado

---

## 7. Camada de Aplicação (Software)

### Stack Tecnológico
```
Frontend:        Streamlit (Python, UI reativa)
Backend:         Python + utils (MQTT Subscriber, gerenciamento de estado)
Base de Dados:   PostgreSQL 15 + InfluxDB 2.7
Broker:          MQTT (EMQX/Mosquitto)
Orquestração:    Docker + Docker Compose
```

### Localização do Software
```
software/
├── app.py                   # Streamlit Dashboard (entry point)
├── docker-compose.yml       # Definição de serviços (PostgreSQL, InfluxDB)
├── requirements.txt         # Dependências Python
├── db/
│   ├── __init__.py
│   ├── postgres_manager.py  # ORM/Queries para PostgreSQL
│   └── influx_manager.py    # Client InfluxDB para série temporal
└── utils/
    ├── __init__.py
    ├── mqtt_client.py       # Subscriber MQTT com threads
    ├── database.py          # Helpers de conexão BD
    └── simulated_data.py    # Gerador de dados para testes
```

### Dependências Python
```
streamlit                     # Framework web
paho-mqtt                     # Cliente MQTT
pandas                        # Manipulação de dados
altair                        # Gráficos interativos
numpy                         # Álgebra linear
psycopg2-binary               # Driver PostgreSQL
influxdb-client               # (Implícito via dependências)
jsonschema                    # Validação de dados
GitPython                     # Versionamento
```

### Dashboard Streamlit

#### Componentes da Interface
1. **Sidebar:**
   - Conexão MQTT (host, porta, topic)
   - Botões Connect/Disconnect
   - Status de conexão
   - Janela histórica (30/60/120 min)

2. **Main View - Abas:**
   - **Tempo Real:** Gráficos de corrente, potência, estado de saída (atualização live)
   - **Histórico Diário:** Energia consumida (kWh), custo estimado (€PT)
   - **Configurações:** (TODO) Autenticação, permissões, alertas

#### Dados em Tempo Real
- **Buffer MQTT:** Máximo 100-200 mensagens (configurável)
- **Taxa de envio firmware:** ~1 msg/s (ajustável)
- **Atualização Streamlit:** Refresh a cada 500ms (auto-refresh habilitado)

---

## 8. Infraestrutura (Docker & Bases de Dados)

### Docker Compose
```yaml
services:
  postgres_db:              # Utilizadores, permissões, metadata
    image: postgres:15
    container: smile_postgres
    env: POSTGRES_USER=admin, POSTGRES_PASSWORD=password123
    db: smile_iot_users
    ports: 5432:5432
    volumes: ./data/postgres:/var/lib/postgresql/data

  influx_db:               # Série temporal de dados energéticos
    image: influxdb:2.7
    container: smile_influx
    env: DOCKER_INFLUXDB_INIT_MODE=setup, ORG=smile_org, BUCKET=energy_data
    ports: 8086:8086
    volumes: ./data/influx:/var/lib/influxdb2
```

### Bases de Dados

#### PostgreSQL (Relacional)
- **Uso:** Utilizadores, permissões, metadata de dispositivos
- **Schema (planejado):**
  ```sql
  users (id, email, password_hash, created_at)
  devices (id, user_id, name, location, calibration_factor)
  alerts (id, device_id, threshold_W, enabled)
  ```

#### InfluxDB (Série Temporal)
- **Uso:** Armazenamento de dados históricos de energia
- **Bucket:** `energy_data`
- **Organização:** `smile_org`
- **Retenção:** (TODO - configurar)
- **Medidas (planejadas):**
  ```
  energy_reading {
    current_A,
    power_W,
    voltage_V,
    timestamp,
    outlet_state
  }
  ```

### Inicializadores (Recente)
- Scripts Python em `db/` para criar schema inicial
- Docker entrypoints para setup automático
- (Status: Em testes na rama `feature/docker-and-database`)

---

## 9. Histórico de Desenvolvimento

### Timeline de Commits
| Commit | Descrição | Autor | Branch |
|--------|-----------|-------|--------|
| d1eac23 | Git init | jpbzx | main |
| da99ada | System requirements docs | Santiago Bossa | main |
| d1603f3 | SCT reading logic refactor | jpbzx | feature/SCT-013 |
| 718aed1 | JSON encapsulation + MQTT send | jpbzx | feature/SCT-013 |
| b40b0b0 | Data format to JSON | jpbzx | feature/SCT-013 |
| 1744d8b | **Merge PR #1** (SCT feature) | João Bessa | main |
| 6c1d1e9 | Database implementation (init) | jpbzx | feature/docker |
| cc7c1fb | Docker DB implementation | jpbzx | feature/docker |
| 7a1176c | **Updated requirements.txt** | jpbzx | feature/docker-and-database |
| 3f9fdd6 | [update] .gitignore | jpbzx | feature/docker-and-database |
| adcc0ad | feat: add database managers and docker configuration | jpbzx | feature/docker-and-database |
| 4dccf64 | refactor: migrate app to multi-page streamlit architecture | jpbzx | feature/docker-and-database |
| 9caabb0 | feat: enhance MQTT client utilities | jpbzx | feature/docker-and-database |
| 23a73ad | feat: add multi-page views (login, dashboard, admin) | jpbzx | feature/docker-and-database |
| 16b5ea0 | docs: add system specification document | jpbzx | feature/docker-and-database |
| 65ccd29 | Merge pull request #2 from jpbzx/feature/docker-and-database | João Bessa | main |
| 9845844 | [dev] added an email column for the DB | jpbzx | main/feature/docker-and-database |
| 689f294 | [dev] implementation of logic to add users and update passwords | jpbzx | main/feature/docker-and-database |
| dac7dda | [dev] Profile page, update password, and user creation | jpbzx | feature/docker-and-database |
| 3cfeb56 | [fix] pt -> eng% | jpbzx | feature/docker-and-database |

### Contribuidores
- **jpbzx:** Desenvolvimento principal (hardware + firmware + software)
- **Santiago Bossa:** Documentação de requisitos
- **João Bessa:** Merge de PR, copyright

---

## 10. Dependências e Requisitos do Sistema

### Hardware (BOM - Bill of Materials)
- 1× ESP32 DevKit (Arduino-compatible)
- 1× SCT-013-030 Current Transformer
- 1× Op-amp (LM358 ou TL072)
- 2× Resistor 18Ω (carga de saída CT)
- 1× Resistor 100kΩ (pull-up/filtro)
- 1× Capacitor 10µF (filtro)
- Cabo USB-C para ESP32
- Connectors MDF/terminal

### Software - Requisitos Mínimos
- **Python:** 3.9+
- **Docker:** 20.10+
- **Docker Compose:** 1.29+
- **Broker MQTT:** EMQX/Mosquitto
- **Biblioteca Arduino (PlatformIO):** v6.0+

### Requisitos de Rede
- Wi-Fi 2.4GHz (ESP32 não suporta 5GHz)
- Acesso ao broker MQTT (público ou privado)
- (TODO) Configuração de firewall para isolamento

---

## 11. Instruções de Configuração e Deploy

### Local Development

#### 1. Clonar repositório
```bash
git clone https://github.com/jpbzx/pesta-smile-iot.git
cd pesta-smile-iot
```

#### 2. Iniciar bases de dados (Docker)
```bash
cd software
docker-compose up -d
```
- PostgreSQL estará em `localhost:5432`
- InfluxDB estará em `localhost:8086`

#### 3. Instalar dependências Python
```bash
pip install -r requirements.txt
```

#### 4. Compilar e enviar firmware para ESP32
```bash
cd ../firmware
pio run -t upload
```
(Requer PlatformIO CLI instalado)

#### 5. Iniciar Dashboard
```bash
cd ../software
streamlit run app.py
```
- Dashboard em `http://localhost:8501`

#### 6. Conectar Dashboard ao MQTT
- Na sidebar, inserir broker host, porta e topic
- Clicar "Connect"
- Confirmar status: "Connected to the Broker!"

---

## 12. Próximas Etapas (TODO)

### Curto Prazo (v0.3)
- [ ] Testes de inicializadores de base de dados
- [ ] Implementar persistência InfluxDB de dados históricos
- [ ] Adicionar autenticação básica (username/password) no Dashboard
- [ ] Validação de dados MQTT (schema JSON)

### Médio Prazo (v0.4)
- [ ] API REST (FastAPI/Flask) separada do Dashboard
- [ ] Suporte a múltiplos sensores por instalação
- [ ] Alertas por threshold (ex: se power > 5kW, notificar)
- [ ] Cálculo de custos energéticos (tarifa PT configurável)
- [ ] Exportação de dados (CSV, PDF)

### Longo Prazo (v1.0)
- [ ] Segurança MQTT (TLS + autenticação)
- [ ] Broker MQTT privado (Mosquitto on-premise)
- [ ] Machine Learning para previsão de consumo
- [ ] Integração com contador inteligente (IEC 60870-5-104)
- [ ] App mobile (React Native ou Flutter)
- [ ] Banco de dados de curva de carga histórica

---

## 13. Testes e Validação

### Testes Unitários (Hardware)
- [ ] Calibração do SCT-013 (amplitude de sinal vs corrente real)
- [ ] Precisão do cálculo RMS (±3% com multímetro)
- [ ] Latência de transmissão MQTT (<2s)

### Testes de Integração
- [ ] Fluxo end-to-end: Sensor → ESP32 → MQTT → Dashboard
- [ ] Ligação/desligação de saída via dashboard
- [ ] Persistência de dados em InfluxDB após restart

### Testes de Aceitação (UAT)
- [ ] Monitorização de instalação real por 24h
- [ ] Validação de dados contra contador elétrico
- [ ] Auditoria de segurança (credenciais, criptografia)

---

## 14. Documentação Relacionada

- [README.md](../README.md) – Instruções de instalação rápida
- [Esqueleto do Sistema](./SMILE-IoT_esqueleto.md) – Diagrama funcional
- [CHANGELOG.md](../CHANGELOG.md) – Histórico de releases (em construção)

---

## 15. Notas Importantes para IA (NotebookLM/Gemini)

Este documento foi gerado como referência para IA e sistemas de análise (e.g., Google NotebookLM, Gemini, ChatGPT). Serve como contexto anexável para:
- Continuação de conversa sobre features
- Análise de arquitectura
- Sugestões de otimização
- Debugging remoto
- Code review assistido

**Última atualização automática:** Maio 16, 2026, 14:30 UTC