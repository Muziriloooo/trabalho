# Validação da Fase 1

Ambiente executado: nuvem Linux, Python 3.12.14, SQLite, Chromium headless.

| Verificação | Resultado |
| --- | --- |
| Instalação das versões fixadas | Concluída |
| `pip check` | Sem dependências incompatíveis |
| Migração inicial no banco local | Aplicada |
| `flask --app app db check` | Nenhuma divergência entre modelos e migração |
| `python -m pytest -q` | **54 testes aprovados** |
| `bash scripts/setup.sh` repetido | Aprovado, sem redefinir contas ou banco |
| `bash -n scripts/setup.sh scripts/start.sh` | Aprovado |
| Inicialização e reinício com `scripts/start.sh` | Waitress iniciou em loopback |
| GET `/health` no servidor real | 200, `status=ok` |
| Navegador desktop 1440 × 1100 | Login, seis cards, dois gráficos, ícones locais, navegação e menu aprovados |
| Navegador móvel 390 × 844 | Sem transbordamento da página; menu, foco, Escape e navegação aprovados |
| Logout no navegador | Retornou ao login |
| Erros JS / CSP durante o fluxo | Nenhum |
| `git diff --check` | Aprovado |
| Execução em Windows real | **Não executada**: máquina Linux, sem Windows/PowerShell |
| Câmeras, biometria, PostgreSQL e produção | Fora da Fase 1; não implementados nem validados |

O fluxo no navegador utilizou uma organização e uma conta temporárias, com senha
aleatória mantida somente em memória durante a execução. Ambas foram removidas
ao terminar. Não há conta padrão ou senha armazenada em arquivos de configuração.
O primeiro usuário de desenvolvimento é criado pelo comando `setup-local`.

O teste automatizado de migrações aplica upgrade, repete upgrade, verifica o
cadastro inicial e sua repetição, faz downgrade somente em banco temporário e
aplica upgrade novamente. Os testes de aplicação usam bancos isolados.

Falhas encontradas durante o desenvolvimento foram corrigidas e revalidadas:
prazo CSRF configurado em segundos, inicialização explícita do limitador em novas
instâncias e nomes acessíveis dos links do menu. O servidor foi reiniciado para
carregar os templates atualizados antes da última validação do navegador.

## Entrega de arquivos

- README substituído por instruções completas.
- Entradas e dependências: `app.py`, `config.py`, `requirements.txt`,
  `requirements.lock.txt`, `.env.example`, `.gitignore`, `pytest.ini`.
- Backend: `sentinela/__init__.py`, `extensions.py`, `models.py`, `cli.py`,
  `auth/routes.py`, `core/{routes,permissions,navigation}.py` e
  `dashboard/routes.py`.
- Interface: templates base, dashboard, login, módulo futuro, erro e macros;
  CSS responsivo; JavaScript de navegação/gráficos; favicon; bundles locais e
  licenças de Chart.js, Lucide e @kurkle/color.
- Migrações: configuração Alembic e revisão inicial `7af3da11c6ea`.
- Testes: `tests/conftest.py`, `test_application.py`, `test_auth.py` e
  `test_schema.py`.
- Scripts: `setup.sh`, `start.sh`, `start-windows.ps1`.
- Documentação: `architecture.md`, `phase-2.md` e este relatório.

Os arquivos locais `.venv/` e `instance/` são saídas de preparação ignoradas pelo
Git. O único arquivo previamente rastreado era o README; sua substituição e os
novos arquivos implementam o pedido explícito de criação da Fase 1.

As instruções reutilizáveis são salvas no rascunho do ambiente. Esse salvamento
não publica o ambiente e não demonstra restauração numa tarefa nova. A publicação
e uma futura verificação de restauração são etapas distintas.
