"""
SMILE-IoT — InfluxDB data manager.

Responsável por estabelecer a ligação à base de dados de séries temporais
e fornecer métodos para gravar e ler as leituras de energia vindas dos sensores.

Funcionalidades:
  - save_energy_reading(): Gravar nova leitura em tempo real
  - get_readings_since(): Obter leituras dos últimos N minutos/horas
  - get_hourly_aggregation(): Agregação por hora (média, máxima, mínima)
  - get_daily_aggregation(): Agregação por dia
  - delete_old_readings(): Limpeza de dados antigos (retenção)
  - test_connection(): Verificar conectividade
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

# Configurações de ligação (load from env ou use defaults)
INFLUX_CONFIG = {
    "url": os.environ.get("INFLUX_URL", "http://localhost:8086"),
    "token": os.environ.get("INFLUX_ADMIN_TOKEN", "5nQc_yy_Tfg_G1Yx3eEN3QEmxwOA2nPCNKz20u-kgauEaciQ2qB9xOQ_sGoa24PwXnca8zSmX5YaLKOKa1dxVA=="),
    "org": os.environ.get("INFLUX_ORG", "smile_org"),
    "bucket": os.environ.get("INFLUX_BUCKET", "energy_data")
}

class InfluxDBManager:
    def __init__(self):
        """Inicializa a ligação ao InfluxDB."""
        try:
            self.client = InfluxDBClient(
                url=INFLUX_CONFIG["url"], 
                token=INFLUX_CONFIG["token"], 
                org=INFLUX_CONFIG["org"]
            )
            # O modo SYNCHRONOUS garante que a operação de escrita é finalizada antes de avançar
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            self.delete_api = self.client.delete_api()
        except Exception as e:
            print(f"Erro ao inicializar InfluxDBManager: {e}")
            raise

    def test_connection(self) -> bool:
        """Verifica se a ligação ao InfluxDB está ativa."""
        try:
            health = self.client.health()
            return health.status == "pass"
        except Exception as e:
            print(f"Erro ao testar conexão InfluxDB: {e}")
            return False

    def save_energy_reading(self, current_a: float, power_w: float, voltage_v: float, outlet_state: str):
        """Grava uma nova leitura de energia no InfluxDB."""
        try:
            ponto = Point("energy_reading") \
                .tag("device", "SCT-013_ESP32") \
                .tag("outlet_state", str(outlet_state)) \
                .field("current_A", float(current_a)) \
                .field("power_W", float(power_w)) \
                .field("voltage_V", float(voltage_v))

            self.write_api.write(bucket=INFLUX_CONFIG["bucket"], record=ponto)
            
        except Exception as e:
            print(f"Erro ao gravar leitura no InfluxDB: {e}")

    def get_readings_since(self, minutes_back: int = 60, device: str = "SCT-013_ESP32") -> list:
        """
        Retorna leituras dos últimos N minutos.
        
        Args:
            minutes_back: Quantos minutos para trás
            device: ID do dispositivo
        
        Returns:
            Lista de dicts com timestamp, current_A, power_W, voltage_V, outlet_state
        """
        try:
            query = f'''
            from(bucket:"{INFLUX_CONFIG['bucket']}")
            |> range(start: -{minutes_back}m)
            |> filter(fn: (r) => r._measurement == "energy_reading")
            |> filter(fn: (r) => r.device == "{device}")
            |> sort(columns: ["_time"])
            '''
            
            result = self.query_api.query(org=INFLUX_CONFIG["org"], query=query)
            
            readings = []
            for table in result:
                for record in table.records:
                    readings.append({
                        "timestamp": record.get_time(),
                        "field": record.field,
                        "value": record.value,
                        "outlet_state": record.tags.get("outlet_state", "UNKNOWN")
                    })
            
            # Converter para formato mais amigável
            formatted_readings = self._format_readings(readings)
            return formatted_readings
            
        except Exception as e:
            print(f"Erro ao ler leituras do InfluxDB: {e}")
            return []

    def get_hourly_aggregation(self, hours_back: int = 24, device: str = "SCT-013_ESP32") -> list:
        """
        Retorna agregação horária (média, máximo, mínimo de potência).
        
        Args:
            hours_back: Quantas horas para trás
            device: ID do dispositivo
        
        Returns:
            Lista de dicts com hora, avg_power_W, max_power_W, min_power_W
        """
        try:
            query = f'''
            from(bucket:"{INFLUX_CONFIG['bucket']}")
            |> range(start: -{hours_back}h)
            |> filter(fn: (r) => r._measurement == "energy_reading")
            |> filter(fn: (r) => r.device == "{device}")
            |> filter(fn: (r) => r._field == "power_W")
            |> aggregateWindow(every: 1h, fn: mean)
            |> sort(columns: ["_time"])
            '''
            
            result = self.query_api.query(org=INFLUX_CONFIG["org"], query=query)
            
            aggregations = []
            for table in result:
                for record in table.records:
                    aggregations.append({
                        "timestamp": record.get_time(),
                        "avg_power_W": record.value
                    })
            
            return aggregations
            
        except Exception as e:
            print(f"Erro ao ler agregação horária: {e}")
            return []

    def get_daily_aggregation(self, days_back: int = 30, device: str = "SCT-013_ESP32") -> list:
        """
        Retorna agregação diária (média diária de potência e energia consumida).
        
        Args:
            days_back: Quantos dias para trás
            device: ID do dispositivo
        
        Returns:
            Lista de dicts com data, avg_power_W, energy_kWh (estimada)
        """
        try:
            query = f'''
            from(bucket:"{INFLUX_CONFIG['bucket']}")
            |> range(start: -{days_back}d)
            |> filter(fn: (r) => r._measurement == "energy_reading")
            |> filter(fn: (r) => r.device == "{device}")
            |> filter(fn: (r) => r._field == "power_W")
            |> aggregateWindow(every: 1d, fn: mean)
            |> sort(columns: ["_time"])
            '''
            
            result = self.query_api.query(org=INFLUX_CONFIG["org"], query=query)
            
            aggregations = []
            for table in result:
                for record in table.records:
                    # Estimar kWh: média em W → kW, depois × 24h
                    avg_kw = (record.value or 0) / 1000.0
                    energy_kwh = avg_kw * 24  # Simplificação: assume valor constante ao longo do dia
                    
                    aggregations.append({
                        "date": record.get_time(),
                        "avg_power_W": record.value,
                        "energy_kWh": energy_kwh
                    })
            
            return aggregations
            
        except Exception as e:
            print(f"Erro ao ler agregação diária: {e}")
            return []

    def get_latest_reading(self, device: str = "SCT-013_ESP32") -> dict | None:
        """
        Retorna a leitura mais recente.
        
        Returns:
            Dict com timestamp, current_A, power_W, voltage_V, outlet_state ou None
        """
        try:
            readings = self.get_readings_since(minutes_back=1440, device=device)  # últimas 24h
            if readings:
                return readings[-1]  # Última (mais recente)
            return None
        except Exception as e:
            print(f"Erro ao ler última leitura: {e}")
            return None

    def delete_old_readings(self, days_old: int = 90, device: str = "SCT-013_ESP32") -> bool:
        """
        Remove leituras mais antigas que N dias (retenção).
        
        Args:
            days_old: Quantos dias de retenção
            device: ID do dispositivo
        
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_old)
            
            self.delete_api.delete(
                predicate=f'device="{device}" AND _time < {int(cutoff_time.timestamp() * 1e9)}',
                start="1970-01-01T00:00:00Z",
                stop=cutoff_time.isoformat() + "Z",
                bucket=INFLUX_CONFIG["bucket"],
                org=INFLUX_CONFIG["org"]
            )
            
            print(f"Leituras anteriores a {cutoff_time} removidas com sucesso")
            return True
            
        except Exception as e:
            print(f"Erro ao remover leituras antigas: {e}")
            return False

    def _format_readings(self, raw_readings: list) -> list:
        """Formata leituras brutas em dicts agrupados por timestamp."""
        formatted = {}
        for reading in raw_readings:
            ts = reading["timestamp"]
            if ts not in formatted:
                formatted[ts] = {
                    "timestamp": ts,
                    "outlet_state": reading.get("outlet_state", "UNKNOWN")
                }
            
            field = reading["field"]
            value = reading["value"]
            formatted[ts][field] = value
        
        return list(formatted.values())

    def close_connection(self):
        """Encerra a ligação ao InfluxDB (chamar ao desligar a aplicação)."""
        try:
            self.client.close()
        except Exception as e:
            print(f"Erro ao fechar conexão InfluxDB: {e}")

# Instância global pronta a ser usada por outros módulos
influx_db = InfluxDBManager()