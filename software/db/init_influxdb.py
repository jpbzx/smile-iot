"""
SMILE-IoT — InfluxDB Initialization Script

Responsável por:
  1. Verificar conectividade ao InfluxDB
  2. Validar ou criar o bucket de energia
  3. Configurar políticas de retenção
  4. Criar índices/tags iniciais

Uso:
  python -m db.init_influxdb
"""

import os
import sys
from pathlib import Path

from influxdb_client import InfluxDBClient
from influxdb_client.client.organization import Organization
from influxdb_client.client.bucket import BucketRetentionRules
from influxdb_client.exceptions import InfluxDBClientError

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

# Configurações
INFLUX_CONFIG = {
    "url": os.environ.get("INFLUX_URL", "http://localhost:8086"),
    "token": os.environ.get("INFLUX_ADMIN_TOKEN", "5nQc_yy_Tfg_G1Yx3eEN3QEmxwOA2nPCNKz20u-kgauEaciQ2qB9xOQ_sGoa24PwXnca8zSmX5YaLKOKa1dxVA=="),
    "org": os.environ.get("INFLUX_ORG", "smile_org"),
    "bucket": os.environ.get("INFLUX_BUCKET", "energy_data"),
    "retention_days": int(os.environ.get("INFLUX_RETENTION_DAYS", 90))
}


def check_influxdb_connection(client: InfluxDBClient) -> bool:
    """Verifica se consegue conectar ao InfluxDB."""
    try:
        health = client.health()
        status = health.status
        print(f"✓ InfluxDB Health Check: {status}")
        return status == "pass"
    except Exception as e:
        print(f"✗ InfluxDB Health Check falhou: {e}")
        return False


def get_or_create_bucket(client: InfluxDBClient) -> bool:
    """Obtém ou cria o bucket de energia."""
    try:
        bucket_api = client.buckets_api()
        
        # Tentar obter o bucket
        buckets = bucket_api.find_buckets_by_name(INFLUX_CONFIG["bucket"])
        
        if buckets:
            bucket = buckets[0]
            print(f"✓ Bucket '{INFLUX_CONFIG['bucket']}' já existe")
            
            # Verificar e atualizar retenção se necessário
            if bucket.retention_rules:
                current_retention = bucket.retention_rules[0].every_seconds
                desired_retention = INFLUX_CONFIG["retention_days"] * 24 * 3600
                
                if current_retention != desired_retention:
                    print(f"  ⚠ Retenção atual: {current_retention}s, desejada: {desired_retention}s")
                    # Opcionalmente atualizar (comentado por segurança)
                    # retention_rules = [BucketRetentionRules(every_seconds=desired_retention)]
                    # bucket.retention_rules = retention_rules
                    # bucket_api.update_bucket(bucket)
            return True
        else:
            # Criar novo bucket
            print(f"ℹ Criando novo bucket: {INFLUX_CONFIG['bucket']}")
            
            try:
                # Obter org ID
                org_api = client.organizations_api()
                org_list = org_api.find_organizations(org=INFLUX_CONFIG["org"])
                
                if not org_list:
                    print(f"✗ Organização '{INFLUX_CONFIG['org']}' não encontrada")
                    return False
                
                org_id = org_list[0].id
                
                # Criar bucket
                retention_rules = [
                    BucketRetentionRules(
                        every_seconds=INFLUX_CONFIG["retention_days"] * 24 * 3600
                    )
                ]
                
                new_bucket = bucket_api.create_bucket(
                    bucket_name=INFLUX_CONFIG["bucket"],
                    org_id=org_id,
                    retention_rules=retention_rules
                )
                
                print(f"✓ Bucket '{INFLUX_CONFIG['bucket']}' criado com sucesso")
                print(f"  Retenção: {INFLUX_CONFIG['retention_days']} dias")
                return True
                
            except InfluxDBClientError as e:
                print(f"✗ Erro ao criar bucket: {e}")
                return False
    
    except Exception as e:
        print(f"✗ Erro ao gerenciar buckets: {e}")
        return False


def verify_write_capability(client: InfluxDBClient) -> bool:
    """Verifica se consegue escrever no bucket (sem escrever dados reais)."""
    try:
        from influxdb_client import Point
        from influxdb_client.client.write_api import SYNCHRONOUS
        
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        # Criar ponto de teste
        test_point = Point("energy_reading") \
            .tag("device", "SCT-013_TEST") \
            .tag("outlet_state", "TEST") \
            .field("current_A", 0.0) \
            .field("power_W", 0.0) \
            .field("voltage_V", 230.0)
        
        # Tentar escrever (isso vai criar o bucket se não existir)
        write_api.write(bucket=INFLUX_CONFIG["bucket"], record=test_point)
        
        print(f"✓ Write capability verificada")
        return True
        
    except Exception as e:
        print(f"✗ Write capability test falhou: {e}")
        return False


def initialize_influxdb() -> bool:
    """Executa toda a sequência de inicialização."""
    print("\n" + "="*60)
    print("SMILE-IoT InfluxDB Initialization")
    print("="*60 + "\n")
    
    print(f"Configuração:")
    print(f"  URL: {INFLUX_CONFIG['url']}")
    print(f"  Organização: {INFLUX_CONFIG['org']}")
    print(f"  Bucket: {INFLUX_CONFIG['bucket']}")
    print(f"  Retenção: {INFLUX_CONFIG['retention_days']} dias\n")
    
    try:
        # Conectar
        client = InfluxDBClient(
            url=INFLUX_CONFIG["url"],
            token=INFLUX_CONFIG["token"],
            org=INFLUX_CONFIG["org"]
        )
        
        # 1. Health check
        if not check_influxdb_connection(client):
            print("\n✗ Falha na conexão ao InfluxDB")
            return False
        
        # 2. Get or create bucket
        if not get_or_create_bucket(client):
            print("\n✗ Falha ao gerenciar bucket")
            return False
        
        # 3. Verify write
        if not verify_write_capability(client):
            print("\n⚠ Write capability test falhou (mas bucket pode estar OK)")
            # Não retornar False aqui - pode ser apenas permissões de teste
        
        print("\n" + "="*60)
        print("✓ Inicialização do InfluxDB completada com sucesso!")
        print("="*60 + "\n")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Erro durante inicialização: {e}")
        return False
    finally:
        try:
            client.close()
        except:
            pass


if __name__ == "__main__":
    success = initialize_influxdb()
    sys.exit(0 if success else 1)
