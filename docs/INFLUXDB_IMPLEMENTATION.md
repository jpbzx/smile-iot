# SMILE-IoT InfluxDB Implementation Guide

**Data:** 22 de Maio de 2026  
**Versão:** 0.3.0  
**Status:** Implementação Completa

---

## 1. Visão Geral

Este documento descreve a implementação completa da **InfluxDB** como sistema de armazenamento de séries temporais para o SMILE-IoT.

### Objetivos
- ✅ Armazenar leituras de energia em tempo real
- ✅ Permitir agregações (horária, diária)
- ✅ Suportar retenção de dados configurável
- ✅ Integração com MQTT e dashboard Streamlit
- ✅ Testes de integração

---

## 2. Arquitetura

### Fluxo de Dados

```
ESP32 (Hardware)
    ↓ (MQTT)
MQTT Broker (EMQX/Mosquitto)
    ↓
mqtt_client.py (subscriber)
    ↓ (Parse JSON)
InfluxDB
    ↓ (Query)
Dashboard (Streamlit)
    ↓
Utilizador (Browser)
```

### Estrutura de Dados

**Measurement:** `energy_reading`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `current_A` | Field (Float) | Corrente em amperes (RMS) |
| `power_W` | Field (Float) | Potência em watts |
| `voltage_V` | Field (Float) | Tensão em volts |
| `device` | Tag (String) | ID do dispositivo |
| `outlet_state` | Tag (String) | Estado: ON ou OFF |

**Bucket:** `energy_data`  
**Organização:** `smile_org`  
**Retenção:** 90 dias (configurável)

---

## 3. Componentes Implementados

### 3.1 `db/influx_manager.py`

**Classe Principal:** `InfluxDBManager`

#### Métodos de Escrita
```python
save_energy_reading(current_a, power_w, voltage_v, outlet_state)
# Escreve uma leitura individual
```

#### Métodos de Leitura
```python
get_readings_since(minutes_back=60, device="SCT-013_ESP32")
# Retorna leituras dos últimos N minutos
# Retorna: List[Dict] com timestamp, current_A, power_W, voltage_V, outlet_state

get_latest_reading(device="SCT-013_ESP32")
# Retorna a leitura mais recente

get_hourly_aggregation(hours_back=24, device="SCT-013_ESP32")
# Agregação por hora (média de potência)
# Retorna: List[Dict] com timestamp, avg_power_W

get_daily_aggregation(days_back=30, device="SCT-013_ESP32")
# Agregação por dia (média diária e energia kWh estimada)
# Retorna: List[Dict] com date, avg_power_W, energy_kWh
```

#### Métodos de Manutenção
```python
test_connection() -> bool
# Verifica conectividade

delete_old_readings(days_old=90, device="SCT-013_ESP32") -> bool
# Remove dados com mais de N dias

close_connection()
# Encerra ligação (ao desligar a app)
```

### 3.2 `db/init_influxdb.py`

Script de inicialização que:
1. Verifica conectividade ao InfluxDB
2. Cria ou obtém o bucket `energy_data`
3. Configura políticas de retenção
4. Valida capacidade de escrita

**Uso:**
```bash
python -m db.init_influxdb
```

**Output:**
```
============================================================
SMILE-IoT InfluxDB Initialization
============================================================

Configuração:
  URL: http://localhost:8086
  Organização: smile_org
  Bucket: energy_data
  Retenção: 90 dias

✓ InfluxDB Health Check: pass
✓ Bucket 'energy_data' já existe
✓ Write capability verificada

============================================================
✓ Inicialização do InfluxDB completada com sucesso!
============================================================
```

### 3.3 Integração no `mqtt_client.py`

Quando uma mensagem MQTT chega:
1. Parse do JSON (formato compacto: `"5.23,5.18,1,5.20"`)
2. Conversão para dicionário
3. **Gravação automática no InfluxDB** (dentro da callback MQTT)

```python
# Dentro de _on_message()
influx_db.save_energy_reading(
    current_a=reading.get("current_A", 0.0),
    power_w=reading.get("power_W", 0.0),
    voltage_v=reading.get("voltage_V", 230.0),
    outlet_state=reading.get("outlet_state", "UNKNOWN")
)
```

### 3.4 Integração no Dashboard (`views/dashboard.py`)

Nova seção "Historical Data" que exibe:

**Controlos:**
- Seletor de período (24h, 48h, 72h, 168h)
- Botão "Refresh History"
- Botão "Clear old data (90+ days)"

**Abas:**
1. **Daily Summary:** Tabela e gráficos de consumo diário (energia kWh)
2. **Hourly Trend:** Gráfico de potência média por hora

---

## 4. Configuração e Deployment

### 4.1 Variáveis de Ambiente (`.env`)

```env
# InfluxDB
INFLUX_URL=http://localhost:8086
INFLUX_ADMIN_TOKEN=5nQc_yy_Tfg_G1Yx3eEN3QEmxwOA2nPCNKz20u-kgauEaciQ2qB9xOQ_sGoa24PwXnca8zSmX5YaLKOKa1dxVA==
INFLUX_ORG=smile_org
INFLUX_BUCKET=energy_data
INFLUX_RETENTION_DAYS=90

# Utilizador InfluxDB (para setup)
INFLUX_USER=admin
INFLUX_PASSWORD=influxdb_password
```

### 4.2 Docker Compose

InfluxDB já está configurado em `docker-compose.yml`:

```yaml
influx_db:
  image: influxdb:2.7
  container_name: smile_influx
  ports:
    - "8086:8086"
  environment:
    - DOCKER_INFLUXDB_INIT_MODE=setup
    - DOCKER_INFLUXDB_INIT_ORG=smile_org
    - DOCKER_INFLUXDB_INIT_BUCKET=energy_data
    - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=...
  volumes:
    - ./data/influx:/var/lib/influxdb2
```

### 4.3 Bootstrap Script

Novo script `bootstrap.sh` para inicializar o sistema:

```bash
# Iniciar (Docker + DBs + testes)
bash bootstrap.sh start

# Parar
bash bootstrap.sh stop

# Ver logs
bash bootstrap.sh logs

# Ver status
bash bootstrap.sh status

# Rodar testes
bash bootstrap.sh test
```

---

## 5. Testes de Integração

Ficheiro: `test_influxdb.py`

### Suites de Testes

#### 1. TestInfluxDBConnection
- Verifica saúde do servidor
- Valida configuração carregada

#### 2. TestInfluxDBWrite
- Grava leitura individual
- Grava múltiplas leituras

#### 3. TestInfluxDBRead
- Lê leituras (últimos 60 min, 24h)
- Lê última leitura

#### 4. TestInfluxDBAggregation
- Agregação horária
- Agregação diária

#### 5. TestInfluxDBDataTypes
- Valida tipos numéricos
- Valida strings (outlet_state)

#### 6. TestInfluxDBDataIntegrity
- Ordenação de timestamps
- Validações de valores positivos

### Executar Testes

```bash
cd software

# Tudo
pytest test_influxdb.py -v

# Suite específico
pytest test_influxdb.py::TestInfluxDBConnection -v

# Com output detalhado
pytest test_influxdb.py -v -s
```

---

## 6. Fluxo de Dados Completo

### Ciclo de Escrita

```
1. ESP32 lê sensor SCT-013
   └─ RMS Calculation → Corrente (A)

2. Calcula Potência (P = V × I)

3. Envia MQTT (formato compacto)
   └─ "5.23,5.18,1,5.20"

4. mqtt_client.py recebe
   └─ Faz parse do JSON

5. Grava no InfluxDB
   └─ influx_db.save_energy_reading()

6. Grava em memória (session_state)
   └─ Dashboard atualiza em tempo real
```

### Ciclo de Leitura

```
1. Dashboard carrega página
   └─ Streamlit rerun

2. Obtém dados InfluxDB
   └─ get_hourly_aggregation()
   └─ get_daily_aggregation()

3. Formata em DataFrame pandas

4. Renderiza gráficos (Altair)

5. Utilizador vê histórico
```

---

## 7. Queries InfluxQL Usadas

### Leituras Recentes (últimas 60 min)

```influxql
from(bucket:"energy_data")
|> range(start: -60m)
|> filter(fn: (r) => r._measurement == "energy_reading")
|> filter(fn: (r) => r.device == "SCT-013_ESP32")
|> sort(columns: ["_time"])
```

### Agregação Horária (últimas 24h)

```influxql
from(bucket:"energy_data")
|> range(start: -24h)
|> filter(fn: (r) => r._measurement == "energy_reading")
|> filter(fn: (r) => r.device == "SCT-013_ESP32")
|> filter(fn: (r) => r._field == "power_W")
|> aggregateWindow(every: 1h, fn: mean)
|> sort(columns: ["_time"])
```

### Agregação Diária (últimos 30 dias)

```influxql
from(bucket:"energy_data")
|> range(start: -30d)
|> filter(fn: (r) => r._measurement == "energy_reading")
|> filter(fn: (r) => r._field == "power_W")
|> aggregateWindow(every: 1d, fn: mean)
```

---

## 8. Troubleshooting

### Problema: "InfluxDB connection refused"

**Solução:**
```bash
# Verificar se container está ativo
docker-compose ps

# Ver logs
docker-compose logs influx_db

# Reiniciar
docker-compose restart influx_db
```

### Problema: "Token inválido"

**Solução:**
1. Verificar token em `.env`
2. Regenerar token em InfluxDB UI (http://localhost:8086)
3. Atualizar `.env` e reiniciar

### Problema: "Bucket não existe"

**Solução:**
```bash
python -m db.init_influxdb
# Isto criará o bucket se não existir
```

### Problema: "No data in historical view"

**Solução:**
1. Conectar MQTT e deixar correr durante alguns minutos
2. Dados são persistidos apenas quando há mensagens
3. Ver logs: `docker-compose logs influx_db`

---

## 9. Performance e Otimizações

### Retenção de Dados
- Padrão: 90 dias
- Configurável: `INFLUX_RETENTION_DAYS` em `.env`
- Limpeza automática: `influx_db.delete_old_readings(days_old=90)`

### Índices
- InfluxDB cria automaticamente índices em tags (`device`, `outlet_state`)
- Fields (`current_A`, `power_W`, `voltage_V`) não são indexados por padrão

### Batch Writes
- Escrita atual é síncrona (uma por vez)
- Futuro: considerar batch writes para melhor throughput

---

## 10. Próximas Melhorias

### Milestone v0.4
- [ ] Dashboard avançado com filtros por data
- [ ] Exportação de dados para CSV/Excel
- [ ] Alertas baseados em limiares
- [ ] Cálculo automático de custos (€/kWh)

### Milestone v0.5
- [ ] Suporte a múltiplos sensores
- [ ] API REST para queries customizadas
- [ ] Grafana integration
- [ ] Backup automático

---

## 11. Referências

- [InfluxDB 2.7 Documentation](https://docs.influxdata.com/influxdb/v2.7/)
- [Flux Language Guide](https://docs.influxdata.com/flux/latest/)
- [InfluxDB Python Client](https://github.com/influxdata/influxdb-client-python)

---

**Implementação Completa:** 22 de Maio de 2026  
**Autor:** SMILE-IoT Senior Engineer Agent  
**Status:** ✅ Produção
