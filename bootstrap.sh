#!/usr/bin/env bash
#
# SMILE-IoT System Bootstrap Script
#
# Responsável por:
#   1. Verificar pré-requisitos (Docker, Python)
#   2. Carregar variáveis de ambiente
#   3. Iniciar containers Docker (PostgreSQL, InfluxDB, MQTT Broker)
#   4. Executar inicializadores de DB
#   5. Iniciar a aplicação Streamlit
#
# Uso:
#   bash bootstrap.sh start    # Iniciar sistema
#   bash bootstrap.sh stop     # Parar sistema
#   bash bootstrap.sh logs     # Ver logs
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOFTWARE_DIR="$SCRIPT_DIR/software"
ENV_FILE="$SOFTWARE_DIR/.env"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    print_status "Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose."
        exit 1
    fi
    print_status "Docker Compose found"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 not found. Please install Python 3.8+"
        exit 1
    fi
    print_status "Python3 found"
    
    # Check .env file
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found at $ENV_FILE"
        print_info "Creating .env file from example..."
        if [ -f "$SOFTWARE_DIR/.env.example" ]; then
            cp "$SOFTWARE_DIR/.env.example" "$ENV_FILE"
            print_status ".env file created from example"
        else
            print_error "No .env.example found either"
            exit 1
        fi
    fi
    print_status ".env file exists"
}

load_env() {
    if [ -f "$ENV_FILE" ]; then
        export $(cat "$ENV_FILE" | grep -v '#' | xargs)
        print_status "Environment variables loaded"
    fi
}

start_system() {
    print_info "Starting SMILE-IoT system..."
    
    cd "$SOFTWARE_DIR"
    
    # Start Docker containers
    print_info "Starting Docker containers (PostgreSQL, InfluxDB, MQTT)..."
    docker-compose up -d
    
    print_info "Waiting for services to be ready..."
    sleep 5
    
    # Check container health
    print_info "Checking container status..."
    docker-compose ps
    
    # Initialize Python environment
    print_info "Setting up Python environment..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_status "Virtual environment created"
    fi
    
    source .venv/bin/activate
    pip install -q -r requirements.txt
    print_status "Dependencies installed"
    
    # Initialize databases
    print_info "Initializing databases..."
    
    # Initialize PostgreSQL
    print_info "Initializing PostgreSQL..."
    python3 -c "from db.postgres_manager import get_connection; get_connection().close(); print('PostgreSQL OK')"
    print_status "PostgreSQL initialized"
    
    # Initialize InfluxDB
    print_info "Initializing InfluxDB..."
    python3 -m db.init_influxdb
    print_status "InfluxDB initialized"
    
    print_info ""
    print_status "SMILE-IoT system started successfully!"
    print_info ""
    print_info "Dashboard: http://localhost:8501"
    print_info "PostgreSQL: localhost:5432"
    print_info "InfluxDB: http://localhost:8086"
    print_info "MQTT Broker: localhost:1883"
    print_info ""
    print_info "To start the dashboard, run:"
    print_info "  cd $SOFTWARE_DIR"
    print_info "  source .venv/bin/activate"
    print_info "  streamlit run app.py"
}

stop_system() {
    print_info "Stopping SMILE-IoT system..."
    
    cd "$SOFTWARE_DIR"
    
    docker-compose down
    
    print_status "System stopped"
}

show_logs() {
    cd "$SOFTWARE_DIR"
    
    service="$1"
    if [ -z "$service" ]; then
        # Show all logs
        docker-compose logs -f
    else
        # Show specific service logs
        docker-compose logs -f "$service"
    fi
}

show_status() {
    cd "$SOFTWARE_DIR"
    
    print_info "System Status:"
    docker-compose ps
}

run_tests() {
    print_info "Running tests..."
    
    cd "$SOFTWARE_DIR"
    
    source .venv/bin/activate
    
    # Run InfluxDB tests
    print_info "Running InfluxDB tests..."
    if command -v pytest &> /dev/null; then
        pytest test_influxdb.py -v
    else
        print_error "pytest not found. Install with: pip install pytest"
        exit 1
    fi
}

# Main
case "${1:-start}" in
    start)
        check_prerequisites
        load_env
        start_system
        ;;
    stop)
        load_env
        stop_system
        ;;
    restart)
        load_env
        stop_system
        sleep 2
        start_system
        ;;
    logs)
        load_env
        show_logs "$2"
        ;;
    status)
        load_env
        show_status
        ;;
    test)
        check_prerequisites
        load_env
        run_tests
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|test} [service]"
        exit 1
        ;;
esac
