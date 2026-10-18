# SENTINELA AI

Plataforma de segurança empresarial — **Fases 1 a 10**.

Monólito modular Flask com autenticação local, organizações e unidades,
permissões por unidade, inventário de câmeras, monitoramento, análise de amostras,
central de alertas, controle de acesso simulado, dashboard operacional e relatórios.
A Fase 8 é um protótipo do fluxo 1:1 exclusivamente com dados artificiais;
biometria facial real permanece desativada.
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
- Análise autorizada de movimento/possível obstrução em amostras com área e horário.
- Central de alertas com responsáveis, histórico, justificativas e deduplicação.
- Pessoas, pontos de acesso simulados e credenciais temporárias revogáveis de uso único.
- Protótipo 1:1 com credencial primeiro, referência artificial cifrada, retenção e exclusão.
- Dashboard com indicadores calculados, filtros e gráficos com tabelas acessíveis.
- Relatórios com logo da organização, identificador, responsável e exportação CSV/PDF.
- Migrações que preservam cadastros anteriores e testes de isolamento entre clientes.

**O dashboard agora calcula indicadores a partir do banco**, com escopo, período
e origem. Fontes sintéticas, relatos manuais do YouTube e decisões simuladas
continuam identificados; não são apresentados como câmeras ou acessos físicos reais.
Biometria real e cobranças permanecem desativadas. Relatórios são agregados e autorizados. O cadastro de uma
câmera de demonstração nunca é apresentado como conexão com equipamento real.

## Requisitos

CPython **3.12 de 64 bits** com pip/venv e acesso ao PyPI para instalar dependências.
No Windows, use a edição **x64 (AMD64)**, instale o launcher `py` e abra a pasta no VS Code.
O inicializador verifica o Python existente em `.venv` antes de instalar;
ambientes criados com outra versão/arquitetura precisam ser recriados.
SQLite deve ser 3.35 ou superior para operações atômicas e testes de rollback; o Python 3.12 oficial
atende esse requisito. Não são necessários Node, FFmpeg, Docker, PostgreSQL, Redis,
hardware ou API paga para rodar o modo de demonstração.

Dependências diretas: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login,
Flask-WTF, Flask-Limiter, python-dotenv, Waitress, cryptography, requests, tzdata
(fusos também no Windows), OpenCV headless, ReportLab, Pillow e pytest. `requirements.lock.txt` fixa as versões
transitivas verificadas. Chart.js, Lucide e hls.js são servidos localmente,
com suas licenças. O player opcional do YouTube se conecta a serviços externos somente após o clique.

## Windows / VS Code

Na pasta do projeto, dê **dois cliques em `iniciar.bat`**. O arquivo deve ficar
ao lado de `app.py`, com a pasta `scripts/` completa. Ele cria o ambiente se
necessário, instala/confere dependências, aplica migrações, solicita a conta no
primeiro uso e inicia o servidor, abrindo o navegador. Não depende da execução
de scripts PowerShell. Preserve a janela aberta; use Ctrl+C para encerrar.
Em caso de erro, a janela permanece aberta para você copiar a mensagem.
Os cadastros e usuários existentes são preservados.

Também é possível executar pelo terminal do VS Code:

```powershell
.\iniciar.bat
```

O script PowerShell anterior continua disponível como alternativa:

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
.\.venv\Scripts\python.exe scripts/check_python.py
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app setup-local
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 app:app
```

Não precisa ativar `.venv`. O servidor de desenvolvimento fica em loopback.
**Execução em Windows real permanece sem validação** nesta máquina Linux.

## Erro do NumPy: compilador não encontrado

Se aparecer `Preparing metadata`, Meson e `Unknown compiler(s)` ao instalar
NumPy 2.2.6, o pip tentou compilar a biblioteca por não encontrar uma wheel
compatível. Python/arquitetura diferentes do requisito ou configuração do índice
podem causar isso. Não é necessário instalar compilador para o ambiente suportado.

Feche o servidor e abra um terminal PowerShell na pasta do projeto. Primeiro,
confira a instalação que será usada para criar o novo ambiente:

```powershell
py -3.12 -c "import sys, struct, sysconfig; print(sys.version); print(struct.calcsize('P') * 8); print(sysconfig.get_platform())"
```

O resultado precisa indicar **3.12**, **64** e **win-amd64**. Se não houver essa
instalação, instale o [Python 3.12 para Windows x64](https://www.python.org/downloads/release/python-31210/)
e reabra o terminal. Em seguida, renomeie o ambiente antigo, preservando-o:

```powershell
Rename-Item -Path .venv -NewName (".venv-antiga-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe scripts/check_python.py
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.lock.txt
```

Execute um comando por vez e prossiga somente se terminar sem erro. Não precisa
ativar `.venv`. Preserve `instance/` e `.env`; banco, contas e chaves ficam fora
do ambiente virtual. Depois de instalar com sucesso, abra `iniciar.bat`.

A opção `--only-binary=:all:` impede tentativa de compilação. Se aparecer
`No matching distribution found` mesmo com Python 3.12 x64 confirmado, confira
o nome do pacote na mensagem e o índice de pacotes configurado; envie esse erro
para diagnóstico. Não remova a opção nem desative TLS para contornar a falha.

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

GET `/health` deve retornar HTTP 200 com `status=ok`, `version=0.10.0`, `phase=10`.
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
A análise vem desativada e exige autorização explícita por câmera. Não há
gravação permanente, identificação de pessoas ou envio de vídeo a serviços de IA.
O processamento de amostras reais usa arquivo temporário privado, removido ao concluir.

## Papéis e organizações

| Perfil | Permissões nestas fases |
| --- | --- |
| Administrador da plataforma | Criar/editar/desativar metadados de organizações; sem acesso a inventários ou imagens |
| Administrador da organização | Gerir organização, unidades, câmeras, equipe, análise e credenciais; tratar alertas e simular acesso |
| Supervisor / operador | Consultar câmeras/eventos, tratar alertas e simular acesso nos escopos concedidos |
| Usuário de acesso físico | Sem acesso ao console de monitoramento |

A organização vem da sessão, nunca de `organization_id` enviado por formulário.
IDs de outro cliente ou de unidade sem escopo retornam 404. Cadastros administrativos exigem administrador da organização;
tratamento de alertas e decisões simuladas também permitem operadores no seu escopo.
Todas as mutações exigem CSRF. Chaves estrangeiras compostas também
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
Range de vídeo, desativação, revogação, migrações, preservação de dados legados,
detecção sintética, deduplicação, fila, alertas, horários e consumo concorrente de token.
Não execute downgrade no banco de trabalho: os testes de rollback usam bases
temporárias, e reverter as Fases 2–4 remove os respectivos dados.

## Estrutura e limites

`sentinela/{auth,core,dashboard,organizations,sites,cameras,monitoring,events,alerts,access,verification,reports}` contêm os
blueprints; `services/` contém auditoria mínima, persistência, cofre, gateway,
detecção não identificadora, fila, eventos, autorização de acesso,
verificação sintética, cálculos operacionais e exportações locais.
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
As Fases 8–10 estão autorizadas; a Fase 8 é exclusivamente um protótipo sintético.
A Fase 11 e seguintes aguardam nova autorização.

## Transmissão pública do YouTube para teste

Na página **Monitoramento**, sem filtros de unidade/câmera, está disponível o
vídeo informado pelo usuário: `https://www.youtube.com/watch?v=CKpA7U_wAbw`.
Clique **Carregar transmissão** para abrir o player oficial incorporado ou
**Abrir no YouTube** para assistir diretamente no site. Não é necessário criar
uma unidade, câmera IP, gateway ou chave de API para esse exemplo.

O player externo só é carregado após o clique e usa youtube-nocookie.com. O
navegador faz conexão com o YouTube; o vídeo não é baixado, extraído ou gravado
pelo backend. **Encerrar player** remove a incorporação. A sessão é revalidada
periodicamente; perder acesso encerra o player da página. O vídeo continua sendo
público no YouTube e é separado do inventário e das métricas de câmeras.

O canal pode encerrar a transmissão, restringir região/idade ou bloquear a
incorporação. A interface não afirma que o vídeo está ao vivo ou disponível;
nesses casos, use o link externo e as mensagens do player oficial. Esta inclusão
não conecta a câmera doméstica iCSee. Os testes locais verificam incorporação e
controles com um iframe controlado; a consulta pública ao YouTube nesta nuvem
retornou HTTP 403, sem confirmação de reprodução da transmissão real.

## Fases 5–7: testar análise, alertas e acesso

1. Como administrador, cadastre uma unidade e uma câmera de **Demonstração**.
2. Em **Eventos → Configurar análise**, ative a análise, mantenha inicialmente a
   área inteira e confirme a autorização. Em **Analisar amostra**, escolha
   execução imediata, confirme e execute. O movimento do vídeo sintético gera
   evento e alerta, ambos identificados como sintéticos. Repetições dentro do
   intervalo configurado não geram novos alertas.
3. Na **Central de Alertas**, abra **Providências**, atribua responsável e
   reconheça o alerta. Depois coloque em análise ou resolva com justificativa.
   O sino mostra pendências do seu escopo e atualiza a cada 30 segundos.
4. Em **Pessoas Autorizadas**, cadastre uma pessoa e conceda permissão por unidade
   e horário. Em **Controle de Acesso**, crie um ponto simulado dessa unidade.
   Emita uma credencial temporária pela página de pessoas, copie o código exibido
   uma única vez e use-o em **Simular tentativa**. A primeira tentativa válida
   permite o acesso simulado; reapresentar o código é negado. Nome e matrícula
   nunca autorizam a entrada. Não há acionamento de hardware.
5. Em **Monitoramento**, teste o player do YouTube informado e registre o resultado
   observado, escolhendo a unidade responsável. Erro relatado gera alerta;
   reprodução confirmada e encerramento geram eventos informativos. Esses são
   relatos manuais, sem verificação automática ou análise de imagens do YouTube.

**Teste escolhido:** YouTube para reprodução e vídeo sintético para análise.
Os detectores implementados reconhecem movimento e possível obstrução/imagem
uniforme. Não existe detector de pessoas treinado/validado nesta entrega.

Para processar amostras enfileiradas, mantenha o site aberto e execute em outro
terminal na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m flask --app app process-analysis --limit 10
```

Linux: `.venv/bin/python -m flask --app app process-analysis --limit 10`.
O comando processa um lote e termina; não existe agendador contínuo nesta fase.
Fontes reais sempre usam essa fila, com gateway configurado e autorização por
câmera. Veja [Fases 5–7: operação e limites](docs/phases-5-7.md).

Para atualizar uma instalação Windows, feche o servidor, faça backup de
`instance/` e `.env`, atualize os arquivos do projeto incluindo `migrations/`,
`requirements.lock.txt`, `scripts/` e `iniciar.bat`. Preserve os dados e chaves
locais. Abra novamente **iniciar.bat** para instalar as dependências e aplicar
as migrações aditivas. Não copie apenas `app.py`.

## Fases 8–10: verificação de teste, dashboard e relatórios

**A Fase 8 não habilita reconhecimento facial real.** O módulo valida o fluxo de
verificação 1:1 com vetores artificiais, sem receber fotos ou vídeos. Não procura
pessoas em uma galeria, não usa imagens do YouTube ou de câmeras de vigilância e
não aciona hardware. Não foi validada precisão facial ou proteção contra fraude.

1. Como administrador, abra **Verificação 1:1 (teste) → Gerenciar referências de
   teste → Configurar política de teste**. Documente as referências da avaliação
   e a alternativa, escolha retenção de 1–30 dias e habilite somente o teste
   artificial. Registrar referências não comprova adequação para biometria real.
2. Cadastre uma referência sintética cifrada para uma pessoa previamente
   cadastrada, com registro de autorização do teste. Emita uma credencial de uso
   único em **Pessoas Autorizadas** e mantenha a permissão de unidade/horário.
3. Apresente o token em **Verificação 1:1 (teste)**. Após validação, escolha uma
   amostra artificial correspondente, diferente, de baixa qualidade ou incompleta.
   Uma aprovação simulada consome a credencial; reprovação permite usar o método
   não biométrico. Há limite temporário de três verificações por credencial em
   dez minutos. A referência pode ser revogada/excluída imediatamente.
4. No **Dashboard**, filtre até 92 dias, unidade e fonte. Câmeras reais sem
   verificação recente ficam como desconhecidas. Disponibilidade é estimada
   apenas nos intervalos observados; ausência de dados não significa online.
5. Em **Relatórios**, escolha tipo, período, unidade/fonte e finalidade. Gere o
   snapshot e exporte por **CSV** ou **PDF**. O administrador pode cadastrar logo
   PNG/JPEG. Acesso é agregado, sem nomes ou credenciais; auditoria administrativa
   é restrita ao administrador. Revogar escopo bloqueia os snapshots afetados.

Para remover referências artificiais expiradas ou invalidadas, execute diariamente:

```powershell
.\.venv\Scripts\python.exe -m flask --app app purge-verification-tests
```

Linux: `.venv/bin/python -m flask --app app purge-verification-tests`.
O comando é um lote; configure sua execução periódica na instalação. Alterar a
política exclui as referências anteriores e exige novo cadastro. A expiração já
bloqueia o uso, mesmo antes da limpeza. Preserve `instance/verification-test-key`
com as demais chaves locais, fora do Git. O modo sintético é bloqueado em produção.

Veja [Fases 8–10: critérios, fórmulas e limites](docs/phases-8-10.md).
