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


