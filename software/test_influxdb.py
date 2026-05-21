"""
SMILE-IoT InfluxDB Integration Tests

Testes para validar:
  - Conexão ao InfluxDB
  - Escrita de dados
  - Leitura de dados
  - Agregações

Uso:
  pytest test_influxdb.py -v
  ou
  python -m pytest test_influxdb.py -v
"""

import pytest
import time
from datetime import datetime, timedelta
from db.influx_manager import influx_db, INFLUX_CONFIG


class TestInfluxDBConnection:
    """Testes de conectividade ao InfluxDB."""
    
    def test_connection_health(self):
        """Verifica se consegue conectar ao InfluxDB."""
        assert influx_db.test_connection() == True, "InfluxDB não está acessível"
    
    def test_config_loaded(self):
        """Verifica se configuração foi carregada."""
        assert INFLUX_CONFIG["url"], "URL não configurada"
        assert INFLUX_CONFIG["token"], "Token não configurado"
        assert INFLUX_CONFIG["org"], "Organização não configurada"
        assert INFLUX_CONFIG["bucket"], "Bucket não configurado"


class TestInfluxDBWrite:
    """Testes de escrita de dados."""
    
    def test_save_single_reading(self):
        """Escreve uma leitura e valida sem erro."""
        try:
            influx_db.save_energy_reading(
                current_a=5.5,
                power_w=1265.0,
                voltage_v=230.0,
                outlet_state="ON"
            )
            # Dar um tempo para a escrita ser processada
            time.sleep(1)
            assert True, "Leitura gravada com sucesso"
        except Exception as e:
            pytest.fail(f"Erro ao gravar leitura: {e}")
    
    def test_save_multiple_readings(self):
        """Escreve múltiplas leituras."""
        for i in range(5):
            try:
                influx_db.save_energy_reading(
                    current_a=3.0 + (i * 0.5),
                    power_w=690.0 + (i * 115.0),
                    voltage_v=230.0,
                    outlet_state="ON" if i % 2 == 0 else "OFF"
                )
                time.sleep(0.2)
            except Exception as e:
                pytest.fail(f"Erro ao gravar leitura {i}: {e}")
        
        assert True, "Múltiplas leituras gravadas"


class TestInfluxDBRead:
    """Testes de leitura de dados."""
    
    def test_get_readings_since(self):
        """Lê leituras dos últimos 60 minutos."""
        try:
            readings = influx_db.get_readings_since(minutes_back=60)
            # Pode ser lista vazia (sem dados) ou com dados
            assert isinstance(readings, list), "Resultado não é uma lista"
        except Exception as e:
            pytest.fail(f"Erro ao ler leituras: {e}")
    
    def test_get_readings_with_custom_window(self):
        """Lê leituras com janela de tempo customizada."""
        try:
            readings = influx_db.get_readings_since(minutes_back=1440)  # 24h
            assert isinstance(readings, list), "Resultado não é uma lista"
        except Exception as e:
            pytest.fail(f"Erro ao ler leituras: {e}")
    
    def test_get_latest_reading(self):
        """Lê a leitura mais recente."""
        try:
            reading = influx_db.get_latest_reading()
            # Pode ser None (sem dados) ou dict (com dados)
            assert reading is None or isinstance(reading, dict), "Formato inválido"
        except Exception as e:
            pytest.fail(f"Erro ao ler última leitura: {e}")


class TestInfluxDBAggregation:
    """Testes de agregação de dados."""
    
    def test_get_hourly_aggregation(self):
        """Lê agregação horária."""
        try:
            aggregation = influx_db.get_hourly_aggregation(hours_back=24)
            assert isinstance(aggregation, list), "Resultado não é uma lista"
            
            # Validar estrutura se houver dados
            if aggregation:
                for item in aggregation:
                    assert "timestamp" in item, "Campo 'timestamp' ausente"
                    assert "avg_power_W" in item, "Campo 'avg_power_W' ausente"
        except Exception as e:
            pytest.fail(f"Erro ao ler agregação horária: {e}")
    
    def test_get_daily_aggregation(self):
        """Lê agregação diária."""
        try:
            aggregation = influx_db.get_daily_aggregation(days_back=7)
            assert isinstance(aggregation, list), "Resultado não é uma lista"
            
            # Validar estrutura se houver dados
            if aggregation:
                for item in aggregation:
                    assert "date" in item, "Campo 'date' ausente"
                    assert "avg_power_W" in item, "Campo 'avg_power_W' ausente"
                    assert "energy_kWh" in item, "Campo 'energy_kWh' ausente"
        except Exception as e:
            pytest.fail(f"Erro ao ler agregação diária: {e}")


class TestInfluxDBDataTypes:
    """Testes de tipos de dados e validação."""
    
    def test_numeric_fields_are_floats(self):
        """Valida que os campos numéricos são floats."""
        try:
            readings = influx_db.get_readings_since(minutes_back=120)
            
            if readings:
                for reading in readings:
                    if "current_A" in reading:
                        assert isinstance(reading["current_A"], (int, float)), \
                            f"current_A não é numérico: {type(reading['current_A'])}"
                    if "power_W" in reading:
                        assert isinstance(reading["power_W"], (int, float)), \
                            f"power_W não é numérico: {type(reading['power_W'])}"
                    if "voltage_V" in reading:
                        assert isinstance(reading["voltage_V"], (int, float)), \
                            f"voltage_V não é numérico: {type(reading['voltage_V'])}"
        except Exception as e:
            pytest.fail(f"Erro ao validar tipos: {e}")
    
    def test_outlet_state_is_string(self):
        """Valida que outlet_state é string."""
        try:
            readings = influx_db.get_readings_since(minutes_back=120)
            
            if readings:
                for reading in readings:
                    if "outlet_state" in reading:
                        assert isinstance(reading["outlet_state"], str), \
                            f"outlet_state não é string: {type(reading['outlet_state'])}"
        except Exception as e:
            pytest.fail(f"Erro ao validar outlet_state: {e}")


class TestInfluxDBDataIntegrity:
    """Testes de integridade e consistência dos dados."""
    
    def test_readings_are_sorted_by_timestamp(self):
        """Valida que as leituras estão ordenadas por timestamp."""
        try:
            readings = influx_db.get_readings_since(minutes_back=120)
            
            if len(readings) > 1:
                for i in range(len(readings) - 1):
                    assert readings[i]["timestamp"] <= readings[i+1]["timestamp"], \
                        "Leituras não estão ordenadas por timestamp"
        except Exception as e:
            pytest.fail(f"Erro ao validar ordenação: {e}")
    
    def test_current_values_are_positive(self):
        """Valida que valores de corrente são positivos."""
        try:
            readings = influx_db.get_readings_since(minutes_back=120)
            
            for reading in readings:
                if "current_A" in reading:
                    assert reading["current_A"] >= 0, \
                        f"Corrente negativa: {reading['current_A']}"
        except Exception as e:
            pytest.fail(f"Erro ao validar corrente: {e}")
    
    def test_power_values_are_positive(self):
        """Valida que valores de potência são positivos."""
        try:
            readings = influx_db.get_readings_since(minutes_back=120)
            
            for reading in readings:
                if "power_W" in reading:
                    assert reading["power_W"] >= 0, \
                        f"Potência negativa: {reading['power_W']}"
        except Exception as e:
            pytest.fail(f"Erro ao validar potência: {e}")


if __name__ == "__main__":
    # Rodar testes
    pytest.main([__file__, "-v", "-s"])
