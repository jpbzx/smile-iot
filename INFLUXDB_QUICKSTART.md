# SMILE-IoT InfluxDB: Quick Start Guide

## 📦 Pré-requisitos

- Docker & Docker Compose
- Python 3.8+
- Git

## 🚀 Instalação Rápida

### 1. Clonar/atualizar repositório
```bash
cd /home/bzxs/pesta/pesta-smile-iot
git pull origin feature/docker-and-database
```

### 2. Configurar variáveis de ambiente
```bash
cd software
cp .env.example .env  # Se .env não existir

# Editar .env e verificar:
# - INFLUX_URL, INFLUX_ADMIN_TOKEN, INFLUX_ORG, INFLUX_BUCKET
# - INFLUX_RETENTION_DAYS=90 (padrão)
```

### 3. Iniciar sistema
```bash
# Voltar à raiz do projeto
cd /home/bzxs/pesta/pesta-smile-iot

# Rodar bootstrap script
bash bootstrap.sh start

# Isto irá:
# ✓ Verificar pré-requisitos
# ✓ Iniciar containers Docker (PostgreSQL, InfluxDB, MQTT)
# ✓ Criar venv Python
# ✓ Instalar dependências
# ✓ Inicializar bases de dados
```

### 4. Iniciar Dashboard
```bash
cd software
source .venv/bin/activate
streamlit run app.py

# Abrir: http://localhost:8501
```

## 📊 Testar Integração InfluxDB

```bash
cd software
source .venv/bin/activate

# Rodar testes de integração
pytest test_influxdb.py -v

# Ou via bootstrap
bash ../bootstrap.sh test
```

## 🔍 Monitorar Sistema

```bash
# Ver status dos containers
bash bootstrap.sh status

# Ver logs (todos)
bash bootstrap.sh logs

# Ver logs específicos
bash bootstrap.sh logs influx_db
bash bootstrap.sh logs postgres_db
```

## 🛑 Parar Sistema

```bash
bash bootstrap.sh stop
```

## 📝 Estrutura de Dados (InfluxDB)

**Measurement:** `energy_reading`

```json
{
  "timestamp": "2026-05-22T10:30:45Z",
  "device": "SCT-013_ESP32",
  "outlet_state": "ON",
  "current_A": 5.23,
  "power_W": 1203.0,
  "voltage_V": 230.0
}
```

## 🔌 MQTT Topic Format

**Topic:** `smile-iot/power`

**Payload (compacto):** `"5.23,5.18,1,5.20"`
- `5.23` = Current Fast (100 samples, A)
- `5.18` = Current Precise (2500 samples, A)
- `1` = Outlet State (1=ON, 0=OFF)
- `5.20` = Average current (5s, A)

## 📋 Checklist de Deployment

- [ ] `.env` configurado
- [ ] Docker rodando: `docker-compose ps` (3 containers)
- [ ] InfluxDB acessível: `curl http://localhost:8086/health`
- [ ] PostgreSQL acessível: `psql -h localhost -U admin -d smile_iot_users`
- [ ] MQTT Broker acessível: `docker-compose logs emqx` (ou mosquitto)
- [ ] Testes passando: `pytest test_influxdb.py -v`
- [ ] Dashboard carrega: `http://localhost:8501`

## 🔗 Endpoints Importantes

| Serviço | URL | Credenciais |
|---------|-----|-----------|
| Dashboard Streamlit | http://localhost:8501 | Login via UI |
| InfluxDB UI | http://localhost:8086 | admin / (sem password) |
| PostgreSQL | localhost:5432 | Var env DB_USER/DB_PASSWORD |
| MQTT Broker | localhost:1883 | (sem auth por padrão) |

## 📚 Documentação Completa

Ver `docs/INFLUXDB_IMPLEMENTATION.md` para:
- Arquitetura detalhada
- API de classes Python
- Exemplos de queries
- Troubleshooting
- Roadmap de melhorias

## ❓ Problemas Comuns

### InfluxDB connection refused
```bash
docker-compose restart influx_db
sleep 3
python -m db.init_influxdb
```

### Token inválido
```bash
# Regenerar token em:
# http://localhost:8086 → Admin → Tokens
# Atualizar .env e reiniciar
docker-compose restart influx_db
```

### Sem dados históricos
```bash
# Precisa conectar MQTT primeiro
# No dashboard: Sidebar → "Connect"
# Deixar correr alguns minutos
# Dashboard → Historical Data deve aparecer
```

## 🆘 Support

```bash
# Ver logs de erro
docker-compose logs -f influx_db

# Verificar conectividade
python3 -c "from db.influx_manager import influx_db; print(influx_db.test_connection())"

# Health check geral
bash bootstrap.sh status
```

---

**Implementação:** 22 de Maio de 2026 | **v0.3.0**
