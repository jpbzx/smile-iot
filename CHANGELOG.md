# Changelog

Todas as alterações relevantes neste repositório serão registadas neste ficheiro.

## Unreleased

### 2026-05-16 — In-progress
- Removido `scripts/reset_local_db.sh` (o script foi eliminado por pedido do maintainer).
- Adicionado suporte inicial para recuperação de password via email:
	- Funções em `software/db/postgres_manager.py`: geração/validação de tokens e reset de password.
	- Helper SMTP: `software/utils/emailer.py` para envio do link de reset.

- Atualizado o inicializador de BD para criar a tabela `password_reset_tokens`.
- Adicionado utilitário `scripts/update_changelog.py` para gerar mensagens de commit candidatas e atualizar `CHANGELOG.md` sem realizar commits.

> Nota: alterações implementadas em ficheiros, sem commit automático — revisão necessária antes de commitar.

### 2026-05-16 — UI
- Adicionada UI de recuperação de password em Streamlit:
	- `software/views/reset_password.py` — formulário de pedido de reset e formulário de definição de nova password via token.
	- `software/app.py` — expõe a página de reset quando o utilizador não está autenticado.

### 2026-05-16 — Update
- Removida a página independente `software/views/reset_password.py` e integrado o fluxo de pedido de reset e uso de token diretamente na `software/views/login.py` para evitar navegação lateral e para melhorar UX e segurança.
- Implementado cooldown por sessão para pedidos de reset e mensagens neutras para evitar user enumeration.

### 2026-05-16 — Fix
- Corrigida referência inválida em `software/app.py` a `views/reset_password.py` (removida). A navegação de login agora mostra apenas `views/login.py` quando não autenticado.

### 2026-05-16 — InfluxDB
- Reescrito `software/db/influx_manager.py` para suportar configuração via variáveis de ambiente, gravação em background com batching, retries com exponential backoff e fallback para ficheiro offline (`./software/data/offline_influx_queue.jsonl`).
- Adicionado snippet demonstrativo `software/db/tests/test_influx_manager.py` para validar comportamento offline.



