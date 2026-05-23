"""
SMILE-IoT — InfluxDB data manager.

Responsável por estabelecer a ligação à base de dados de séries temporais
e fornecer métodos para gravar as leituras de energia vindas dos sensores.
"""

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configurações de ligação (match c/ docker-compose.yml)
INFLUX_CONFIG = {
    "url": "http://localhost:8086",
    "token": "5nQc_yy_Tfg_G1Yx3eEN3QEmxwOA2nPCNKz20u-kgauEaciQ2qB9xOQ_sGoa24PwXnca8zSmX5YaLKOKa1dxVA==",
    "org": "smile_org",
    "bucket": "energy_data"
}

class InfluxDBManager:
    def __init__(self):
        """Inicializa a ligação ao InfluxDB."""
        self.client = InfluxDBClient(
            url=INFLUX_CONFIG["url"], 
            token=INFLUX_CONFIG["token"], 
            org=INFLUX_CONFIG["org"]
        )
        # O modo SYNCHRONOUS garante que a operação de escrita é finalizada antes de avançar
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def save_energy_reading(self, current_a: float, power_w: float, voltage_v: float, outlet_state: str):
        try:
            ponto = Point("energy_reading") \
                .tag("device", "SCT-013_ESP32") \
                .tag("outlet_state", str(outlet_state)) \
                .field("current_A", float(current_a)) \
                .field("power_W", float(power_w)) \
                .field("voltage_V", float(voltage_v))

            self.write_api.write(bucket=INFLUX_CONFIG["bucket"], record=ponto)
            
        except Exception as e:
            # Em caso de falha de conexão ou gravação, mostramos o erro mas não quebramos o programa
            print(f"Erro ao gravar leitura no InfluxDB: {e}")

    def close_connection(self):
        #its called when the aplication stops
        self.client.close()

# Instância global pronta a ser usada por outros módulos
influx_db = InfluxDBManager()