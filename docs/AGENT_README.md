**SMILE-IoT Senior Engineer Agent — README

Resumo
- Agente especializado para apoiar desenvolvimento do SMILE-IoT com foco em firmware, backend, infra e integração IoT.

Como o agente actua (padrões)
- Por defeito gera patches (`apply_patch`) e propõe comandos a correr localmente; NÃO executa ações disruptivas nem faz commits automáticos.
- Para ações disruptivas (reinícios, migrations, uploads de firmware), é necessária a frase de confirmação exata:

  CONFIRMAR: AUTORIZO AÇÕES DISRUPTIVAS

  Responder exactamente com essa string Autoriza o agente a executar passos que modificam serviços/infra. Use com cuidado.

Política de commits
- Padrão: `generate_patch_only` — o agente gera mudanças via patches para revisão.
- Se autorizado, pode criar um branch e preparar commits locais (`create_branch_and_patch`). Auto-commit remoto está desativado por defeito.

Comandos de diagnóstico permitidos (exemplos)
- `journalctl -u <service>`
- `docker logs --since "1h" <container>`
- `docker-compose ps` (leitura)
- `cat` / `tail -n 200` em ficheiros de log dentro do workspace
- `ps aux`, `top -b -n1`, `free -h`
- `ss -tulpn` ou `netstat -tulpn`

Boas práticas de segurança
- Nunca partilhar segredos no repositório.
- Guardar credenciais em variáveis de ambiente ou um Secret Manager.

Exemplos de prompts (PT)
- "Analisa `software/db/postgres_manager.py` e propõe um patch para adicionar hashing de passwords com bcrypt."
- "Colhe os últimos 500 logs do container Influx e resume quaisquer erros detectados."
- "Optimiza o cálculo RMS em `firmware/src/main.cpp` para reduzir uso de CPU no ESP32."

Examples (EN)
- "Audit `firmware/src/main.cpp` for CPU hotspots in RMS calculation and propose a patch."
- "Collect last 500 lines of logs for the influx container and summarize errors."

Autorizações e pipeline de trabalho sugerida
1. Peça ao agente para gerar patchs e abrir um MR/PR manualmente.
2. Execute CI localmente ou no servidor (lint, tests, platformio build).
3. Após revisão, autorize ações disruptivas com a frase de confirmação se necessário.

Contacto / Maintainers
- Lista de responsáveis pode ser adicionada aqui para autorizações rápidas.

Notas
- Este ficheiro pode ser actualizado conforme o agente evolui.
