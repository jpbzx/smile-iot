# SMILE-IoT — Arquitetura Multi-Device

**Versão:** 1.0  
**Data:** Maio 25, 2026  
**Sprint:** 1  

---

## 1. Visão Geral

Este documento descreve a implementação do suporte **multi-device** no sistema SMILE-IoT, permitindo que múltiplos ESP32 (devices) comuniquem simultaneamente com o backend e sejam geridos individualmente através do dashboard.

### Objetivos Alcançados
- ✅ Identificação única de cada ESP32 pelo MAC address
- ✅ Topics MQTT dinâmicos por device
- ✅ Persistência de dados históricos por device no InfluxDB
- ✅ Gestão de devices via PostgreSQL (registo, permissões, configuração)
- ✅ Interface de administração para registo e atribuição de devices
- ✅ Seletor de device no dashboard com filtragem de dados em tempo real
- ✅ Comandos MQTT direcionados a devices específicos

---

## 2. Arquitetura de Comunicação

### 2.1 Topics MQTT Dinâmicos

Cada ESP32 utiliza **topics únicos** baseados no seu MAC address:

```
TX (ESP32 → Backend):  smile-iot/power/<MAC_ADDRESS>
RX (Backend → ESP32):  smile-iot/control/<MAC_ADDRESS>
```

**Exemplo:**
```
Device MAC: A4:CF:12:34:56:78
TX Topic:   smile-iot/power/A4CF12345678
RX Topic:   smile-iot/control/A4CF12345678
```

### 2.2 Subscrição com Wildcard

O backend subscreve a **todos os devices** usando wildcard MQTT:

```
Subscribe: smile-iot/power/+
```

O símbolo `+` representa **qualquer device_id**, permitindo receber dados de múltiplos ESP32 numa única subscrição.

---

## 3. Payload JSON Estendido

### 3.1 Formato de Envio (ESP32 → Backend)

```json
{
  "device_id": "A4CF12345678",
  "current_A": 5.23,
  "outlet_state": "ON",
  "timestamp": "2026-05-25T14:32:15Z"  // Opcional (gerado no backend se ausente)
}
```

**Campos obrigatórios:**
- `device_id`: MAC address do ESP32 (sem ':')
- `current_A`: Corrente RMS em Amperes
- `outlet_state`: Estado da tomada (`"ON"` ou `"OFF"`)

**Campos calculados no backend:**
- `power_W`: Calculado como `current_A × 230V` (tensão nominal PT)
- `voltage_V`: Fixo em 230V (pode ser medido no futuro)

### 3.2 Formato de Comandos (Backend → ESP32)

```
Payload: "ON"  ou  "OFF"
Topic:   smile-iot/control/<device_id>
```

---

## 4. Schema PostgreSQL

### 4.1 Tabela `dispositivos`

Armazena informações de cada ESP32 registado no sistema.

```sql
CREATE TABLE dispositivos (
    id SERIAL PRIMARY KEY,
    mac_address VARCHAR(50) UNIQUE NOT NULL,
    nome_apresentacao VARCHAR(100) NOT NULL,
    limite_corrente DECIMAL(5,2) DEFAULT 15.0
);
```

**Campos:**
- `id`: Identificador único interno
- `mac_address`: MAC do ESP32 (normalizado para uppercase sem ':')
- `nome_apresentacao`: Nome amigável (ex: "Tomada Cozinha")
- `limite_corrente`: Limite de corrente em Amperes (padrão: 15.0A)

### 4.2 Tabela `acessos_dispositivos`

Relaciona utilizadores e devices, controlando permissões de acesso.

```sql
CREATE TABLE acessos_dispositivos (
    user_id INTEGER REFERENCES utilizadores(id) ON DELETE CASCADE,
    device_id INTEGER REFERENCES dispositivos(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, device_id)
);
```

**Política de Permissões:**
- **Utilizadores comuns:** Vêem apenas devices aos quais têm acesso explícito
- **Administradores:** Vêem todos os devices do sistema

---

## 5. Armazenamento em InfluxDB

### 5.1 Measurement `energy_reading`

Cada leitura de energia é gravada com **tags e fields**:

**Tags (indexed):**
- `device_id`: MAC address do ESP32
- `outlet_state`: Estado da tomada (`"ON"`, `"OFF"`)

**Fields:**
- `current_A`: Corrente em Amperes (float)
- `power_W`: Potência em Watts (float)
- `voltage_V`: Tensão em Volts (float, padrão 230V)

**Timestamp:** Gerado automaticamente pelo InfluxDB (UTC)

### 5.2 Query de Dados por Device

Exemplo de query Flux para obter dados históricos de um device específico:

```flux
from(bucket: "energy_data")
    |> range(start: -1h)
    |> filter(fn: (r) => r["_measurement"] == "energy_reading")
    |> filter(fn: (r) => r["device_id"] == "A4CF12345678")
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

---

## 6. Funções de Gestão de Devices

### 6.1 PostgreSQL Manager (`db/postgres_manager.py`)

Novas funções implementadas:

| Função | Descrição |
|--------|-----------|
| `register_device(mac, nome, limite)` | Regista um novo ESP32 na base de dados |
| `get_all_devices()` | Retorna lista de todos os devices registados |
| `get_device_by_mac(mac)` | Obtém informações de um device específico |
| `update_device_name(mac, novo_nome)` | Atualiza o nome de apresentação |
| `grant_device_access(user_id, device_id)` | Concede acesso de um utilizador a um device |
| `get_user_devices(user_id)` | Retorna devices acessíveis por um utilizador |

### 6.2 InfluxDB Manager (`db/influx_manager.py`)

Funções atualizadas:

| Função | Descrição |
|--------|-----------|
| `save_energy_reading(device_id, current_a, power_w, voltage_v, outlet_state)` | Grava leitura com device_id como tag |
| `query_device_data(device_id, time_range)` | Consulta dados históricos de um device específico |

### 6.3 MQTT Client (`utils/mqtt_client.py`)

Funções novas/modificadas:

| Função | Descrição |
|--------|-----------|
| `_on_connect(...)` | Subscreve automaticamente a `smile-iot/power/+` (wildcard) |
| `_on_message(...)` | Extrai `device_id` do payload e grava no InfluxDB |
| `publish_device_command(device_id, command)` | Envia comando para device específico |

---

## 7. Interface de Utilizador

### 7.1 Dashboard (`views/dashboard.py`)

**Novas funcionalidades:**

1. **Seletor de Device (Sidebar)**
   - Dropdown com devices acessíveis pelo utilizador
   - Opção "[Todos os Devices]" para visualização agregada
   - Filtragem automática de dados MQTT pelo device selecionado

2. **Filtragem de Dados em Tempo Real**
   - Mensagens MQTT filtradas pelo `device_id`
   - Gráficos e KPIs exibem apenas dados do device ativo

3. **Comandos Direcionados**
   - Botões ON/OFF enviam comandos apenas para o device selecionado
   - Topic de comando construído dinamicamente: `smile-iot/control/<device_id>`
   - Comandos desabilitados quando "[Todos os Devices]" está selecionado

### 7.2 Painel de Administração (`views/admin_panel.py`)

**Novas funcionalidades:**

1. **Registar Device**
   - Formulário para adicionar novos ESP32
   - Campos: MAC address, nome de apresentação, limite de corrente
   - Validação de MAC address (aceita formatos com ou sem ':')

2. **Listar Devices**
   - Exibição de todos os devices registados
   - Edição de nomes de apresentação
   - Visualização de MAC address e limite de corrente

3. **Gerir Acessos**
   - Atribuição de devices a utilizadores específicos
   - Seleção de utilizador e device via dropdowns
   - Validação de acessos duplicados

---

## 8. Fluxo de Operação

### 8.1 Registo de Novo Device

1. **Administrador acede ao painel de admin**
2. **Preenche formulário "Registar Device":**
   - MAC address do ESP32
   - Nome amigável (ex: "Tomada Sala")
   - Limite de corrente (padrão: 15A)
3. **Sistema normaliza MAC address** (remove ':', converte para uppercase)
4. **Device é gravado na tabela `dispositivos`**

### 8.2 Atribuição de Acesso a Utilizador

1. **Administrador acede ao tab "Gerir Acessos"**
2. **Seleciona utilizador e device**
3. **Sistema cria entrada na tabela `acessos_dispositivos`**
4. **Utilizador pode agora visualizar e controlar o device**

### 8.3 Conexão do ESP32

1. **ESP32 inicia e conecta ao Wi-Fi**
2. **Obtém o próprio MAC address via `WiFi.macAddress()`**
3. **Constrói topics dinâmicos:**
   ```cpp
   pub_topic = "smile-iot/power/" + MAC
   sub_topic = "smile-iot/control/" + MAC
   ```
4. **Conecta ao broker MQTT e subscreve a `sub_topic`**
5. **Publica leituras de energia no `pub_topic` a cada 1s**

### 8.4 Visualização no Dashboard

1. **Utilizador autentica-se no dashboard**
2. **Sistema carrega lista de devices acessíveis:**
   - Admin: Todos os devices
   - User: Apenas devices com permissão explícita
3. **Utilizador seleciona device no dropdown**
4. **Dashboard filtra mensagens MQTT pelo `device_id`**
5. **Gráficos e KPIs atualizam em tempo real (auto-refresh 5s)**

### 8.5 Envio de Comando

1. **Utilizador seleciona device específico no dropdown**
2. **Clica em botão "TURN ON" ou "TURN OFF"**
3. **Dashboard invoca `publish_device_command(device_id, "ON")`**
4. **MQTT client publica mensagem no topic:**
   ```
   Topic:   smile-iot/control/A4CF12345678
   Payload: "ON"
   ```
5. **ESP32 recebe comando e atualiza estado do relay**

---

## 9. Considerações de Segurança

### 9.1 Implementado
- ✅ **MAC address único por device** (impossível duplicar no mesmo broker)
- ✅ **Controlo de permissões PostgreSQL** (users só vêem devices autorizados)
- ✅ **Normalização de MAC address** (previne inconsistências)
- ✅ **Queries parametrizadas** (proteção contra SQL injection)

### 9.2 TODO (Riscos Ativos)
- ⚠️ **MQTT sem TLS:** Comunicação não criptografada
- ⚠️ **MQTT sem autenticação:** Qualquer cliente pode publicar/subscrever
- ⚠️ **Broker público (EMQX):** Exposição a ataques externos
- ⚠️ **Sem validação de origem:** Device spoofing possível

**Recomendações para produção:**
1. Implementar **MQTT com TLS** (port 8883)
2. Ativar **autenticação MQTT** (username/password por device)
3. Migrar para **broker privado** (Mosquitto local)
4. Implementar **ACLs MQTT** (restringir topics por device)

---

## 10. Testes e Validação

### 10.1 Cenários de Teste

| Teste | Status | Notas |
|-------|--------|-------|
| Registo de device com MAC válido | ✅ | Normalização funcionando |
| Registo de device duplicado | ✅ | UniqueViolation tratado |
| Conexão de múltiplos ESP32 ao broker | 🔶 | Requer hardware físico |
| Filtragem de dados por device no dashboard | 🔶 | Requer dados de múltiplos devices |
| Envio de comando para device específico | 🔶 | Requer ESP32 ativo |
| Permissões de acesso por utilizador | ✅ | Queries testadas |

**Legenda:**
- ✅ Testado e validado
- 🔶 Requer hardware ou ambiente de produção
- ❌ Não testado

### 10.2 Testes Unitários (Recomendados)

```bash
# PostgreSQL Manager
pytest software/tests/test_postgres_devices.py

# InfluxDB Manager
pytest software/tests/test_influx_multidevice.py

# MQTT Client
pytest software/tests/test_mqtt_wildcard.py
```

---

## 11. Comandos de Diagnóstico

### 11.1 Verificar Devices Registados

```bash
# Via PostgreSQL CLI
docker exec -it smile_postgres psql -U admin -d smile_iot_users -c "SELECT * FROM dispositivos;"

# Via Python
cd software && python3 -c "from db.postgres_manager import get_all_devices; print(get_all_devices())"
```

### 11.2 Consultar Dados de Device no InfluxDB

```bash
# Via InfluxDB CLI (dentro do container)
docker exec -it smile_influx influx query '
from(bucket:"energy_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r.device_id == "A4CF12345678")
  |> limit(n:10)
'
```

### 11.3 Testar Publicação MQTT Manual

```bash
# Publicar leitura de teste (simular ESP32)
mosquitto_pub -h broker.emqx.io -t "smile-iot/power/A4CF12345678" -m '{"device_id":"A4CF12345678","current_A":5.5,"outlet_state":"ON"}'

# Subscrever a todos os devices (simular backend)
mosquitto_sub -h broker.emqx.io -t "smile-iot/power/+"

# Enviar comando para device específico
mosquitto_pub -h broker.emqx.io -t "smile-iot/control/A4CF12345678" -m "ON"
```

---

## 12. Migração de Sistema Legado

### 12.1 Passos para Atualizar Sistema Existente

1. **Backup de Dados:**
   ```bash
   # PostgreSQL
   docker exec smile_postgres pg_dump -U admin smile_iot_users > backup_pre_multidevice.sql
   
   # InfluxDB
   docker exec smile_influx influx backup /tmp/backup -t <TOKEN>
   docker cp smile_influx:/tmp/backup ./influx_backup
   ```

2. **Atualizar Schema PostgreSQL:**
   ```bash
   cd software
   python3 -c "from db.postgres_manager import init_db; init_db()"
   ```
   - Tabelas `dispositivos` e `acessos_dispositivos` são criadas automaticamente (IF NOT EXISTS)

3. **Registo Manual de Devices Legado:**
   ```python
   from db.postgres_manager import register_device
   
   # Exemplo: device existente sem multi-device support
   register_device("A4CF12345678", "Device Principal (Legado)", 15.0)
   ```

4. **Upload de Firmware Atualizado:**
   ```bash
   cd firmware
   pio run -t upload
   ```
   - Novo firmware envia `device_id` no payload automaticamente

5. **Atualizar Dashboard e Backend:**
   ```bash
   cd software
   pip install -r requirements.txt  # Dependências já devem estar OK
   streamlit run app.py
   ```

---

## 13. Próximos Passos (Roadmap)

### Sprint 2 (Sugerido)
- [ ] Implementar TLS MQTT (port 8883)
- [ ] Adicionar autenticação MQTT por device
- [ ] Migrar para broker MQTT privado (Mosquitto)
- [ ] Implementar ACLs MQTT (restringir topics por device)

### Sprint 3 (Sugerido)
- [ ] Auto-discovery de devices (ESP32 envia mensagem de "hello")
- [ ] Dashboard com mapa de localização de devices
- [ ] Alertas por device (threshold excedido)
- [ ] Histórico de eventos por device (on/off, overcurrent)

### Sprint 4 (Sugerido)
- [ ] API REST para gestão de devices
- [ ] Mobile app (React Native ou Flutter)
- [ ] Exportação de relatórios por device (PDF/CSV)
- [ ] Análise de consumo energético comparativa entre devices

---

## 14. Referências

- **MQTT Wildcard Subscriptions:** [https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/)
- **InfluxDB Tags vs Fields:** [https://docs.influxdata.com/influxdb/v2.7/reference/key-concepts/data-elements/](https://docs.influxdata.com/influxdb/v2.7/reference/key-concepts/data-elements/)
- **ESP32 MAC Address:** [https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/misc_system_api.html](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/misc_system_api.html)
- **Streamlit Multi-Page Apps:** [https://docs.streamlit.io/library/get-started/multipage-apps](https://docs.streamlit.io/library/get-started/multipage-apps)

---

## 15. Contacto e Suporte

- **Repositório:** [https://github.com/jpbzx/pesta-smile-iot](https://github.com/jpbzx/pesta-smile-iot)
- **Autor principal:** jpbzx
- **Branch ativa:** `feature/set_sistem_4_prodReady`

---

**Documento gerado automaticamente em:** Maio 25, 2026  
**Versão do sistema:** v0.3.0-multidevice
