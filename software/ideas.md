## Requisitos do Sistema Central

O sistema central tem como objetivo a recolha, processamento e visualização de dados IoT.

### 1. Autenticação e Autorização (Concluído/Em Progresso)
* **OAuth2**: Implementação de fluxos de autenticação seguros.
* **RBAC (Role-Based Access Control)**:
    - **Admin**: Acesso total, gestão de utilizadores e dispositivos.
    - **Operator**: Gestão técnica e configuração de parâmetros de otimização.
    - **Viewer**: Acesso apenas de leitura para dashboards e relatórios.
    - **Device**: Credenciais específicas para dispositivos enviarem dados.

---

### 2. Próximos Passos (Pós-RBAC)

Após a implementação do RBAC, o foco deve mudar para a integridade dos dados e a escalabilidade do sistema:

1.  **Audit Logging (Logs de Auditoria)**:
    - Implementar um sistema de registo para todas as ações críticas realizadas (quem alterou um parâmetro de otimização e quando).
2.  **Multi-tenancy**:
    - Garantir que os dados de diferentes clientes/instalações estão isolados ao nível da base de dados ou da aplicação.
3.  **Data Ingestion Pipeline**:
    - **Broker MQTT**: Configurar um broker (ex: Mosquitto) com autenticação via JWT/OAuth2 integrada no RBAC.
    - **API Gateway**: Criar endpoints REST para dispositivos que não suportam MQTT.
4.  **Armazenamento Especializado**:
    - Implementar uma **Time-Series Database** (ex: InfluxDB ou TimescaleDB) para lidar com a alta frequência de dados de sensores.
5.  **Analytics & Optimization Engine**:
    - Integrar os scripts de otimização de energia (P2P/BCADO) como microserviços que consomem dados do sistema central.
6.  **Dashboard Framework**:
    - Escolher e integrar uma ferramenta de visualização (Grafana para métricas técnicas, Streamlit ou Angular para o utilizador final).

---

### 3. Arquitetura de Dados Proposta

*   **Ingestão**: MQTT / HTTPS (com validação de tokens).
*   **Buffer**: Redis ou RabbitMQ para evitar perda de dados em picos de carga.
*   **Processamento**: Worker em Python para limpeza de dados e cálculo de KPIs em tempo real.
*   **Dashboard**: Dashboard Web (Angular) consumindo uma API GraphQL ou REST enriquecida com os dados processados.