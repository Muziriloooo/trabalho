# SENTINELA AI

Plataforma de segurança empresarial — **Fase 1: fundação e layout**.

Aplicação Flask funcional com login local, SQLite, migrações, layout Dark Premium,
navegação responsiva e dashboard com **dados de exemplo**. Nenhuma câmera está
conectada. Não há análise de vídeo, biometria, cobrança nem acionamento de hardware.
Os módulos futuros estão explicitamente identificados como não implementados.

## Requisitos

- Python **3.12**, incluindo pip e venv. No Windows, instalar o Python com o launcher
  `py` e abrir a pasta do projeto no VS Code.
- Internet apenas para instalar os pacotes Python do PyPI na primeira execução.
- Sem câmera, API paga, Node, Docker, Redis ou PostgreSQL para esta fase.

As dependências diretas estão em `requirements.txt`; `requirements.lock.txt`
fixa também as versões transitivas verificadas. Chart.js e Lucide são distribuídos
localmente com suas licenças em `sentinela/static/vendor/`.

## Windows / VS Code

No terminal PowerShell aberto na raiz do projeto:

```powershell
.\scripts\start-windows.ps1
```

O script prepara `.venv`, instala as versões fixadas, aplica as migrações e solicita
o primeiro e-mail e uma senha de 12 a 128 caracteres, com entrada oculta e
confirmação. Não existe conta ou senha padrão. Execuções posteriores preservam o
banco e os usuários. Depois da mensagem de que o servidor iniciou na porta 5000,
abra o navegador nesse endereço local. `Ctrl+C` encerra o servidor.

Se a política do PowerShell impedir scripts, use os comandos individuais abaixo
sem precisar alterar a política do sistema:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app setup-local
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 app:app
```

Não é necessário ativar o ambiente virtual. O servidor usa somente loopback e não
abre portas públicas. Ele não abre automaticamente o navegador.

## Linux / ambiente na nuvem

Na raiz do checkout:

```bash
bash scripts/setup.sh
.venv/bin/python -m flask --app app setup-local
bash scripts/start.sh
```

`setup.sh` instala as versões fixadas, verifica dependências, aplica e confere
migrações e executa os testes. Pode ser repetido sem recriar contas ou apagar
dados. `start.sh` reaplica migrações pendentes e inicia Waitress em loopback.
Os processos precisam ser reiniciados quando uma tarefa ou máquina for retomada.

Para conferir a saúde local, faça uma requisição GET ao caminho `/health`, na
porta 5000: deve retornar `{"phase":1,"status":"ok","version":"0.1.0"}`.
Um banco sem as tabelas básicas retorna 503. A página `/` exige autenticação.

## Primeiro uso e demonstração

1. Crie o administrador com `setup-local` e entre com as credenciais escolhidas.
2. Veja os seis indicadores demonstrativos e os gráficos de linha e barras.
   As tabelas acessíveis contêm os mesmos valores dos gráficos.
3. Consulte os quatro eventos de exemplo; seus horários são fixos.
4. Explore os onze módulos futuros. Não existem botões de cadastro ou ações
   operacionais fictícias nessas páginas.
5. Recolha o menu no desktop. No celular, abra o menu, navegue por teclado e use
   Escape para fechá-lo.
6. Encerre a sessão pelo botão Sair, que usa POST protegido por CSRF.

## Configuração e dados locais

`.env.example` descreve as opções; copiá-lo para `.env` é opcional no
desenvolvimento. Variáveis já exportadas têm prioridade.

| Variável | Padrão / efeito |
| --- | --- |
| `SENTINELA_ENV` | `development`; aceita também `production` |
| `DATABASE_URL` | SQLite em `instance/sentinela.db` |
| `SECRET_KEY` | Chave aleatória local em `instance/dev-secret` |

`instance/`, `.env` e `.venv/` são ignorados pelo Git. Não compartilhe banco,
chave ou senhas no repositório. A chave persiste entre reinícios e protege as
sessões; sua troca invalida as sessões existentes. A pasta instance do Windows
deve permanecer restrita à conta local.

Os modelos iniciais são Organization, Site e User. O cadastro inicial cria somente
uma organização local e seu administrador. As métricas do dashboard são fixtures
de apresentação e não são calculadas a partir desse banco.

## Testes e migrações

```powershell
# Windows
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flask --app app db check
```

```bash
# Linux
.venv/bin/python -m pytest -q
.venv/bin/python -m flask --app app db check
```

Os testes usam bancos isolados; não apagam o banco de desenvolvimento.
A suíte cobre login/logout, CSRF, limite de tentativas, papéis, organização
inativa, sessão revogada, cabeçalhos, escape HTML, rotas, assets locais,
erros 403/404/500, constraints e upgrade/downgrade de migrações em banco temporário.

Nunca execute downgrade no banco de trabalho para testar migrações: a migração
inicial remove as tabelas ao ser revertida. Use os testes isolados.

## Estrutura

```text
app.py / config.py       Entrada WSGI e configuração por ambiente
sentinela/
  __init__.py           Application factory e inicialização
  models.py             Entidades iniciais
  extensions.py         Banco, sessão, migrações, CSRF e limites
  cli.py                Primeiro administrador local
  auth/                 Login e logout
  core/                 Permissões, health e navegação
  dashboard/            Fixtures demonstrativas
  templates/            Layout, componentes, login, erros e páginas
  static/               CSS, JavaScript, ícones e Chart.js locais
migrations/             Schema versionado
tests/                  Testes automatizados da Fase 1
scripts/                Instalação e inicialização Linux e Windows
docs/                   Arquitetura, validação e plano da Fase 2
```

## Limitações e riscos

Esta entrega prepara desenvolvimento e demonstração local. Não está aprovada
para produção ou dados reais de clientes. Não foram implementados CRUDs,
permissões por unidade, isolamento SaaS completo, auditoria persistente, MFA,
recuperação de senha, backup, Redis ou integração PostgreSQL. O limite de login
é local ao processo e reinicia com ele. O modo production exige chave e banco
explícitos e habilita cookies Secure, mas TLS e implantação ainda exigem trabalho.

Um usuário de acesso físico e o superadministrador da plataforma não recebem
acesso automático ao console de organizações. A segurança e o isolamento dos
recursos operacionais deverão ser testados conforme forem implementados.

Validação executada na nuvem Linux com Python 3.12. O roteiro Windows foi
fornecido, mas a execução em Windows real ainda precisa ser validada nesse sistema.

Veja [arquitetura e limites](docs/architecture.md),
[evidências da validação](docs/validation.md) e o
[plano detalhado da Fase 2](docs/phase-2.md). A Fase 2 depende de autorização.
