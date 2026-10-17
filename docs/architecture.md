# Arquitetura da Fase 1

Monólito modular Flask com application factory em `sentinela/__init__.py`.

| Área | Responsabilidade atual |
| --- | --- |
| `auth` | Sessão local, login e logout POST com CSRF |
| `core` | Navegação, permissões do console, health check e páginas futuras |
| `dashboard` | Apresentação de fixtures demonstrativas, sem telemetria real |
| `models.py` | Organization, Site e User |
| `extensions.py` | SQLAlchemy, migrações, sessões, CSRF e limites |
| `templates/components` | Macros de ícones, indicadores e badges |
| `static` | CSS responsivo, JS e dependências frontend locais |
| `migrations` | Evolução versionada e reversível do schema |
| `tests` | Rotas, segurança da fundação, banco e migrações |

## Dados e fronteiras

Organization contém o estado da organização. Site exige organização, nome,
fuso e status. User armazena e-mail único normalizado no cadastro local, hash
scrypt, organização, papel e estado ativo. O banco aplica chaves estrangeiras,
índices e constraints. Datas de criação são geradas em UTC.

Os perfis organization_admin, supervisor e operator de organizações ativas
podem consultar o console demonstrativo. access_user e platform_admin recebem
403: administração global não concede acesso automático ao console de clientes.
Desativar um usuário invalida seu acesso nas próximas requisições.

Há um papel por usuário nesta fase; permissões por unidade, RoleAssignment e
acesso excepcional temporário ficam para fases posteriores. Não há API de
cadastro nem seleção de organização fornecida pelo navegador. O cabeçalho usa
somente a organização do usuário autenticado. As fixtures do dashboard são
iguais para todos e não são dados de um cliente real. A fundação **não constitui
uma implementação completa de isolamento SaaS**; sua validação operacional é
critério da Fase 2 antes de adicionar recursos de clientes.

## Inicialização e configuração

`app.py` oferece a entrada WSGI. `.env` é carregado da raiz sem sobrescrever
variáveis já exportadas. `SENTINELA_ENV` aceita development ou production.
Desenvolvimento usa SQLite e uma chave aleatória persistida em
`instance/dev-secret`, ignorada pelo Git. Não versionar essa chave ou o banco.
No Windows, proteger a pasta instance com as permissões da conta local.

Produção exige SECRET_KEY (pelo menos 32 caracteres) e DATABASE_URL explícitos
e ativa cookies Secure e HSTS. Essa configuração não instala TLS, não integra
PostgreSQL e não declara o produto pronto para produção. O driver PostgreSQL
e a implantação serão acrescentados e testados na fase correspondente.

Migrações são aplicadas explicitamente antes do servidor. Importar a aplicação
não cria tabelas nem contas. `/health` retorna 503 se as tabelas básicas estão
ausentes, e 200 após as migrações. Não expõe configurações ou detalhes de erros.

## Segurança e limites atuais

- Sem senha padrão, autorregistro público, recuperação ou MFA nesta fase.
- CSRF em todos os POSTs, cookies HttpOnly e SameSite=Lax, sessão de oito horas.
- Login limitado a cinco POSTs por minuto por endereço remoto. O contador fica
  na memória do processo; reinícios o apagam. Distribuição com Redis e limitação
  por identidade exigem trabalho adicional antes de exposição pública.
- Nenhum ProxyFix ou cabeçalho de origem é confiado automaticamente.
- Jinja faz escape de HTML. CSP permite somente recursos locais; proíbe
  enquadramento, scripts inline e objetos. Câmera e microfone do navegador estão
  desativados para a Fase 1.
- O servidor local usa somente loopback e debug desativado. Não expor essa
  instalação de desenvolvimento à internet.
- Não há auditoria persistente de autenticação, reset de senha, backup,
  restauração, testes PostgreSQL ou revisão de vulnerabilidades de produção.
- `/health` é uma verificação básica, sem métricas sensíveis.
- Não há módulos biométricos, processamento de vídeo, workers ou serviços pagos.

## Evolução planejada

Manter os blueprints desacoplados e adicionar serviços e repositórios quando
existir lógica de domínio que justifique essas camadas. Não há diretórios vazios
para módulos futuros. Workers Redis/RQ ou Celery serão processos independentes
quando os eventos assíncronos forem implementados. Vídeo exigirá gateway
autenticado com TLS e validação de destinos no servidor, sem URLs RTSP no cliente.
Biometria permanecerá separada de câmera genérica e limitada à verificação 1:1
nas fases autorizadas.
