# SENTINELA AI

Plataforma de segurança empresarial — **Fases 1 a 4**.

Monólito modular Flask com autenticação local, organizações e unidades,
permissões por unidade, inventário de câmeras e central de monitoramento.
SQLite e vídeo sintético permitem desenvolver e demonstrar o produto sem câmera,
serviço pago ou infraestrutura de mídia. Câmeras reais usam MediaMTX por HTTPS.

## O que funciona

- Login/logout, senhas scrypt, sessões, CSRF, limites de tentativas e páginas de erro.
- Administração de metadados de organizações pela plataforma e edição da própria
  organização pelo seu administrador.
- Cadastro, edição, pesquisa e desativação de unidades com fuso IANA, responsável,
  endereço opcional e contagem real de câmeras.
- Cadastro local de operadores/supervisores, concessão e revogação de acesso a uma
  unidade ou a todas as unidades da organização, desativação de conta.
- Inventário de câmeras: cadastro, edição, filtros, ativação/desativação, exclusão
  confirmada, credenciais cifradas, verificação manual e histórico de disponibilidade.
- Monitoramento autenticado: câmera individual, grade 1/4/9, filtro por unidade,
  pausa, retomada, reconexão limitada, tela cheia e informações de atraso de buffer.
- Vídeo de demonstração sintético e integração HLS convencional com MediaMTX.
- Migrações que preservam os dados da Fase 1 e testes de isolamento entre clientes.

**O dashboard inicial ainda usa dados de exemplo**, claramente identificados, e
não calcula métricas operacionais do inventário. Eventos, alertas, acesso físico,
biometria, relatórios e cobranças continuam nas fases futuras. O cadastro de uma
câmera de demonstração nunca é apresentado como conexão com equipamento real.

## Requisitos

Python **3.12** com pip/venv e acesso ao PyPI para instalar dependências.
No Windows, instalar o Python com o launcher `py` e abrir a pasta no VS Code.
SQLite deve ser 3.35 ou superior para os testes de rollback; o Python 3.12 oficial
atende esse requisito. Não são necessários Node, FFmpeg, Docker, PostgreSQL, Redis,
hardware ou API paga para rodar o modo de demonstração.

Dependências diretas: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login,
Flask-WTF, Flask-Limiter, python-dotenv, Waitress, cryptography, requests, tzdata
(fusos também no Windows) e pytest. `requirements.lock.txt` fixa as versões
transitivas verificadas. Chart.js, Lucide e hls.js são servidos localmente,
com suas licenças; não há CDN em execução.

## Windows / VS Code

No PowerShell, na raiz do projeto:

```powershell
.\scripts\start-windows.ps1
```

O script prepara `.venv`, instala as versões fixadas, aplica as migrações e
solicita o primeiro e-mail e uma senha de 12 a 128 caracteres, oculta e com
confirmação. Não existe conta/senha padrão. Reexecuções preservam os cadastros.
Abra o navegador no endereço local informado pelo servidor na porta 5000.
`Ctrl+C` encerra o servidor; ele não abre o navegador automaticamente.

Se a política do PowerShell impedir scripts, execute individualmente, sem mudar
as políticas do sistema:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app setup-local
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 app:app
```

Não precisa ativar `.venv`. O servidor de desenvolvimento fica em loopback.
**Execução em Windows real permanece sem validação** nesta máquina Linux.

## Linux / nuvem

Na raiz do checkout:

```bash
bash scripts/setup.sh
.venv/bin/python -m flask --app app setup-local
bash scripts/start.sh
```

`setup.sh` instala, confere dependências, aplica/confere migrações e executa os
testes. Pode ser repetido sem apagar o banco. `start.sh` inicia Waitress em
loopback, na porta 5000. Reinicie os processos ao retomar uma tarefa ou após
alterar código/templates; as migrações não são executadas ao importar a aplicação.

GET `/health` deve retornar HTTP 200 com `status=ok`, `version=0.4.0`, `phase=4`.
Uma base sem o schema necessário retorna 503. O console exige autenticação.

## Demonstração sem hardware

1. Crie a primeira conta com `setup-local` e faça login.
2. Em **Minha organização**, confira nome, identificador e responsável.
3. Em **Unidades**, cadastre um local ativo com fuso `America/Sao_Paulo`.
4. Em **Câmeras**, cadastre uma fonte **Demonstração — vídeo sintético**, associe
   a unidade, descreva o local e confirme a autorização.
5. Abra os detalhes e clique **Verificar disponibilidade**. O histórico registra
   uma demonstração; não preenche última disponibilidade real.
6. Abra **Monitoramento** e clique **Iniciar**. Teste pausa, retomada, layouts e
   tela cheia. A pausa interrompe a carga do vídeo e descarta o buffer do player.
7. Em **Usuários**, cadastre um operador e conceda somente a unidade desejada.
   Numa segunda sessão, confira seu inventário e monitoramento restritos.
8. Revogue o escopo na sessão de administrador. Novas requisições de mídia são
   negadas; a página aberta interrompe o player na próxima validação de sessão,
   em até aproximadamente 15 segundos se o navegador estiver ativo.

Bytes já recebidos pelo navegador não podem ser recuperados pelo servidor.
A aplicação não grava transmissões, não captura pessoas e não envia vídeo a IA.

## Papéis e organizações

| Perfil | Permissões nestas fases |
| --- | --- |
| Administrador da plataforma | Criar/editar/desativar metadados de organizações; sem acesso a inventários ou imagens |
| Administrador da organização | Gerir a própria organização, unidades, câmeras e equipe; visualizar suas unidades |
| Supervisor / operador | Somente consultar e reproduzir câmeras nos escopos concedidos |
| Usuário de acesso físico | Sem acesso ao console de monitoramento |

A organização vem da sessão, nunca de `organization_id` enviado por formulário.
IDs de outro cliente ou de unidade sem escopo retornam 404. Alterações exigem
administrador da organização e CSRF. Chaves estrangeiras compostas também
impedem associar câmera, unidade, credencial ou escopo de clientes diferentes.
Operadores antigos preservam sua conta ao migrar, mas precisam de uma concessão
explícita para acessar as novas unidades. Administradores não podem conceder
acesso a clientes alheios.

Para provisionar contas administrativas como operador da instalação:

```bash
.venv/bin/python -m flask --app app create-account --platform
.venv/bin/python -m flask --app app create-account --organization IDENTIFICADOR
```

No Windows, substitua o executável por `.\.venv\Scripts\python.exe`. O comando
solicita a senha no terminal. Crie a organização pelo administrador da plataforma
antes de provisionar seu administrador. Ele não recebe acesso automático por
administrar metadados; não há impersonação ou acesso excepcional nesta entrega.

## Câmeras reais e gateway

Consulte [configuração do MediaMTX](docs/media-gateway.md). O adaptador está
implementado e foi validado com respostas controladas; **nenhuma câmera física
ou instalação remota de MediaMTX foi conectada nesta execução**.

A aplicação não abre RTSP diretamente. O gateway, administrado na infraestrutura
autorizada, guarda a URL e as credenciais da câmera e fornece HLS com TLS e
controle de acesso. A aplicação mantém somente a referência ao caminho e,
quando necessário, a credencial cifrada de leitura do gateway.

Cada organização tem namespace imutável `org-ID--REFERENCIA` no gateway.
Os destinos HTTPS e portas precisam ser autorizados na configuração do servidor;
não podem ser alterados pelo formulário de câmera. Credenciais, URLs RTSP e
endereços internos não são enviados ao player. Playlists e segmentos passam
pelas mesmas permissões do backend em cada requisição.

## Configuração e chaves

`.env.example` descreve as variáveis. Copiar para `.env` é opcional no modo local;
valores já exportados têm prioridade. Não coloque valores secretos no Git.

- `SENTINELA_ENV`: development (padrão) ou production.
- `DATABASE_URL`: SQLite em `instance/sentinela.db` por padrão.
- `SECRET_KEY`: aleatória em `instance/dev-secret` no desenvolvimento.
- `CAMERA_ENCRYPTION_KEY`: chave Fernet válida, exigida ao salvar/decriptar
  credenciais de gateway em produção. No desenvolvimento, uma chave é gerada em
  `instance/camera-key` quando necessário.
- `MEDIA_GATEWAY_HLS_URL`, `MEDIA_GATEWAY_API_URL`,
  `MEDIA_GATEWAY_ALLOWED_HOSTS`, `MEDIA_GATEWAY_ALLOWED_PORTS`: opcionais para demo;
  obrigatórios para usar fontes reais conforme a documentação do gateway.

`.env`, `.venv/` e `instance/` são ignorados pelo Git. Proteja a pasta instance no
Windows pelas permissões da conta. Backup de credenciais cifradas também precisa
preservar a chave de maneira separada e protegida; trocar a chave sem recifrar os
dados torna as credenciais existentes indisponíveis. Nunca use um placeholder
proxy como se fosse a chave Fernet real.

## Testes

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m flask --app app db check
```

No Windows, use `.\.venv\Scripts\python.exe`. Os testes usam bases isoladas.
Cobrem autenticação, CSRF, papéis, escopos, isolamento, CRUD, cifras, restrições
SSRF, TLS/timeout, respostas de gateway, reescrita de HLS, autorização de segmentos,
Range de vídeo, desativação, revogação, migrações e preservação de dados legados.
Não execute downgrade no banco de trabalho: os testes de rollback usam bases
temporárias, e reverter as Fases 2–4 remove os respectivos dados.

## Estrutura e limites

`sentinela/{auth,core,dashboard,organizations,sites,cameras,monitoring}` contêm os
blueprints; `services/` contém auditoria mínima, persistência, cofre e gateway.
`media/` guarda o vídeo sintético fora de static. Templates e recursos locais
mantêm o layout responsivo. `migrations/`, `tests/`, `scripts/` e `docs/` completam
a entrega. Não foram criados módulos vazios para funcionalidades futuras.

Esta instalação é de desenvolvimento. HTTPS público, implantação PostgreSQL,
Redis, MFA, recuperação de senha, backup/restauração operacional e auditoria
completa ainda precisam das fases correspondentes e validação antes de produção.
Contadores de tentativas são locais ao processo. O histórico de câmeras é manual;
não há varredura de rede nem verificador contínuo. A integração HLS não promete
latência zero e não substitui um gateway de mídia preparado para produção.

Veja [arquitetura](docs/architecture.md), [Fase 2](docs/phase-2.md),
[Fases 3 e 4 / gateway](docs/media-gateway.md) e [validação](docs/validation.md).
A Fase 5 e as seguintes dependem de nova autorização.
