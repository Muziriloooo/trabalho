# Validação — Fases 1 a 4

Executada na nuvem Linux com Python 3.12.14, SQLite e Chromium headless.

| Verificação | Resultado |
| --- | --- |
| Dependências fixadas e `pip check` | Instaladas, sem incompatibilidades |
| Migração `78f63a927cf9` no banco local | Aplicada |
| `flask --app app db check` | Sem divergência entre modelos e migrações |
| `python -m pytest -q` | **122 testes aprovados** |
| Instalação repetida por `scripts/setup.sh` | Aprovada, preservando banco e contas |
| Sintaxe dos scripts shell e JS de monitoramento | Aprovada |
| Upgrade com organizações, usuário e unidade legados | Dados, senha e FKs preservados; sem concessão implícita |
| Downgrade e novo upgrade | Aprovados em banco temporário, nunca no banco de trabalho |
| CRUD e confirmação em navegador | Unidades, câmeras demo e equipe criados e alterados no fluxo |
| Reprodução MP4 sintético em navegador | Quadros avançam, pausa remove a origem, retomada funciona |
| Grade e câmera individual | Layouts, filtro por unidade e seleção individual aprovados |
| HLS fMP4 sintético no navegador | Gateway controlado → relay autenticado → hls.js/MSE → reprodução aprovada |
| Navegador desktop e móvel | 1440 × 1000 e 390 × 844, sem transbordamento da página |
| Escopo e revogação no navegador | Operador vê só a unidade concedida; revogar encerra o player na validação periódica |
| JS/CSP e requisições externas do browser | Nenhum erro inesperado; recursos/segmentos apenas same-origin ou blob |
| Câmera física / MediaMTX remoto real | **Não executado**: nenhum equipamento/gateway/credencial configurado |
| Windows real | **Não executado**: host Linux; script e roteiro fornecidos |
| PostgreSQL, implantação pública, backup operacional | Fora desta validação; necessários antes de produção |

## Cobertura de segurança

- Login/logout, senha scrypt, CSRF, cookies e limites de tentativas.
- Cadastro e edição de unidades, identificadores duplicados, fuso inválido,
  confirmação de desativação e contagem do inventário.
- Tentativas de acessar/alterar IDs de outro cliente ou de unidade sem escopo.
- Roles de plataforma e acesso físico sem acesso implícito a imagens.
- Concessão por unidade e global, supervisor, revogação e desativação de usuário.
- Organização ou unidade inativa e câmera desativada bloqueiam mídia.
- Credenciais cifradas fora do HTML, preservação em edição, remoção explícita,
  chave de produção ausente e impedimento de referências entre clientes.
- Confirmação de exclusão e remoção em cascata do histórico da câmera.
- Fontes demo separadas de reais; status expira e falhas de configuração/TLS
  não são apresentadas como câmera online.
- Adaptador com resposta online/ready, fonte offline, 401/403, 404, redirect,
  timeout, TLS inválido, JSON inválido e conteúdo acima do limite.
- Destinos HTTPS/portas fixados, metadados/loopback recusados, paths arbitrários
  e playlists externas/traversal/chaves remotas rejeitados.
- Namespace de gateway por ID imutável da organização. Escolher outra referência
  não altera o namespace do cliente.
- Playlist e segmentos autorizados por requisição, sem query de destino livre,
  sem credenciais ou origem de gateway no conteúdo devolvido.
- Range do MP4 e Cache-Control no-store. Novas requisições são bloqueadas depois
  da revogação; bytes previamente baixados não podem ser recuperados pelo servidor.

A execução de navegador usou banco e usuários temporários; as senhas aleatórias
ficaram somente na memória do processo. O teste HLS forneceu respostas controladas
do gateway com fragmentos sintéticos gerados por FFmpeg: valida o fluxo do
player e do adaptador, **não comprova acesso a hardware ou rede do cliente**.
Os processos temporários foram encerrados. O banco de desenvolvimento não recebeu
contas, imagens ou cadastros de teste.

Uma falha de renderização no filtro de câmera individual foi encontrada no
navegador, corrigida e coberta por teste de regressão. A última suíte concluiu
122 testes; não houve testes obrigatórios ignorados ou desabilitados.

## Arquivos da entrega

- Modelos, migração aditiva, config, CLI e permissões atualizados.
- Blueprints `organizations`, `sites`, `cameras`, `monitoring` e equipe.
- Serviços de cifra, gateway, persistência e auditoria mínima.
- Templates de formulários, organizações, unidades, equipe, câmeras e players.
- CSS responsivo, JS de monitoramento e hls.js local com licenças.
- Vídeo sintético fora de static e script opcional de geração.
- Testes de inventário/gateway e expansão das verificações de migração e rotas.
- README, `.env.example`, arquitetura, Fase 2 e instruções de gateway atualizados.

Arquivos ignorados `.venv/` e `instance/` são preparação local, nunca enviados ao
Git. Instruções reutilizáveis são salvas no rascunho do ambiente; esse salvamento
não publica o snapshot nem comprova restauração numa tarefa nova. O código pode
ser enviado ao GitHub independentemente da publicação do ambiente da plataforma.
