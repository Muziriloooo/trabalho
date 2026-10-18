# Validação — Fases 1 a 10

Executada na nuvem Linux com Python 3.12.14, SQLite e Chromium headless.
A versão atual é 0.10.0; a Fase 8 é um protótipo exclusivamente sintético. Os cenários usam bancos e contas temporários; tokens e
senhas de teste ficam na memória, sem contas padrão na instalação.

| Verificação | Resultado |
| --- | --- |
| `bash scripts/setup.sh` completo | Aprovado; instalação, `pip check`, upgrade, db check e suíte |
| Dependências fixadas, incluindo OpenCV headless / NumPy | Instaladas, sem incompatibilidades |
| Migração `da64a0b27c33` | Aplicada; nenhuma divergência entre modelos e migrações |
| `python -m pytest -q` | **232 testes aprovados**, nenhum ignorado ou desabilitado |
| Reinício por `scripts/start.sh` | Waitress; `/health` HTTP 200, versão 0.10.0, fase 10; `/login` HTTP 200 |
| Upgrade/rollback/novo upgrade em bases temporárias | Aprovados; preservação de contas, senha, unidade, câmera e histórico anteriores |
| MP4 sintético → detector → evento → alerta | Movimento detectado; repetição suprimida por janela móvel |
| Detector estático, ROI e quadros insuficientes | Sem movimento fora da área; imagem uniforme sinalizada; amostra curta falha explicitamente |
| Fila e autorização atual | Tomada única, tarefa ativa única por câmera, fora de horário/estado revogado não processam |
| Falha inesperada de processamento | Tarefa falha e gera evento/alerta, sem mensagem interna sensível |
| HLS fMP4 sintético controlado → amostra → detector | Análise local gerou evento `gateway` e alerta; sem gateway físico |
| Amostra real simulada e limpeza | Container válido decodificado; diretório temporário removido |
| Playlist disfarçada de mídia | Rejeitada antes do decodificador; protocolos de decodificação limitados a arquivos locais |
| Central de Alertas | Filtros, escopo, transições, responsáveis, justificativa e histórico persistidos |
| YouTube: relato manual | Erro gera alerta; deduplicação e unidade autorizada conferidas |
| Acesso simulado | Emissão, permissão/horário, revogação, expiração, negação e histórico aprovados |
| Duas tentativas simultâneas com o mesmo token | **Uma permitida e uma negada** em banco SQLite de arquivo |
| Ausência de token no histórico/HTML posterior | Aprovada; somente hash persistido; resposta de emissão no-store |
| Escopos de clientes/unidades e CSRF | Novas rotas verificadas junto às proteções das fases anteriores |
| Navegador desktop/móvel — fases 5–7 | Análise → alerta reconhecido/resolvido; cadastro/permissão/ponto/token → permitido → reutilização negada |
| Navegador — layout e JS | 1440 × 1000 e 390 × 844; sem transbordamento da página ou erros JS |
| Formulário YouTube no navegador | Relato manual registrado, sem carregar iframe/recurso externo nesse cenário |
| Referência 1:1 artificial cifrada | Comparação somente da identidade declarada; nenhum vetor/score no HTML |
| Política, chave, modelo e autorização da referência | Vencimento/revogação/incompatibilidade negam; produção bloqueia o protótipo |
| Desafio de verificação | Uso único, prazo de dois minutos e vínculo ao operador/ponto |
| Revogação durante comparação | Consumo condicional nega; credencial não é usada |
| Retenção/exclusão | CLI remove conteúdo expirado; editar política apaga referências anteriores |
| Falha 1:1 e alternativa | Mismatch/qualidade/retry não consomem token; alternativa autoriza se a credencial/permissão forem válidas |
| Indicadores calculados | Contagens, fontes, escopos, tempos de alerta, estado recente e gaps testados |
| Disponibilidade observada | Fixture: 150 s online + 90 s offline = 62,5%; média offline 90 s; cobertura 0,28% de um dia |
| Relatórios — sete tipos | Snapshots, filtros, totais, finalidade, geração e exportações auditadas |
| CSV | UTF-8 BOM, campos delimitados e neutralização de fórmulas, inclusive prefixos Unicode |
| PDF | Arquivo gerado e baixado; texto extraído confirma tipo, organização e responsável |
| Logo | PNG/JPEG normalizado, snapshot independente de remoção posterior; inválidos rejeitados |
| Permissões de relatório | Cliente, autor, papel e escopos atuais; revogação bloqueia consulta/exportação |
| Navegador — fases 8–10 | Dashboard com evento sintético real do banco; logo; CSV/PDF; política/cadastro artificial; mismatch/aprovação/replay/exclusão |
| Navegador — gráficos e layout | Chart.js recebeu os dados do banco; desktop/móvel sem transbordamento, erros JS/CSP ou requests externos |
| Biometria facial real / precisão / PAD | **Não implementados ou validados**; o protótipo artificial não habilita coleta real |
| Câmera física / MediaMTX remoto | **Não executado**: nenhum equipamento/gateway/credencial configurado |
| Reprodução efetiva do YouTube informado | **Não confirmada**; consulta pública anterior retornou HTTP 403 nesta nuvem |
| Windows real | **Não executado**: host Linux; `iniciar.bat` e roteiro disponíveis |
| PostgreSQL / implantação pública / hardware de acesso | Não executados; entrega local de desenvolvimento |

## Verificações anteriores mantidas na suíte

Autenticação, senhas scrypt, CSRF, cookies, limites de tentativas, inventário,
duplicidades, fuso IANA, autorização em cada requisição, papéis e escopos,
revogação, organizações/unidades/câmeras inativas, cofre Fernet, FKs entre clientes,
SSRF, TLS, timeouts, redirects recusados, respostas limitadas, reescrita de HLS,
URLs/credenciais fora do conteúdo do player, Range e Cache-Control continuam
cobertos. A suíte atual inclui esses cenários.

Nas Fases 2–4 o Chromium também validou CRUD de unidades/câmeras/equipe, concessão
e revogação de escopo, avanço real do MP4, pausa/retomada, layouts e HLS fMP4
sintético pelo relay e hls.js/MSE. Esses testes de navegador anteriores não
comprovam conexão com hardware; os processos e bancos temporários foram removidos.

O cenário anterior do YouTube usou iframe controlado para verificar carregamento
após clique, ID `CKpA7U_wAbw`, referrer, ausência de cookies da aplicação no request
externo, encerramento/reabertura, sessão e layout. A suíte continua verificando
CSP, autenticação, ID/link e ausência de iframe antes do clique. Não houve
extração, download ou análise dos quadros da transmissão do YouTube.

## Alcance das evidências

O teste HLS de análise gerou fragmentos sintéticos com FFmpeg, forneceu-os como
respostas controladas do gateway, executou o decodificador OpenCV e confirmou
no banco o evento/alerta. É evidência do caminho de processamento, sem prova de
acesso à rede/câmera do cliente. O detector implementado cobre movimento e
possível obstrução/imagem uniforme; não inclui modelo de presença de pessoas.

O navegador percorreu as telas reais em servidor temporário, incluindo emissão
e consumo do token. Também conferiu que o campo fica vazio após a decisão e
que o token não reaparece no HTML. Não houve erro JavaScript nem requisição
externa no cenário das fases 5–7. A configuração da transmissão real é opcional;
o teste acordado separa reprodução YouTube de análise sintética.

Arquivos locais `.venv/`, `instance/` e `.env` permanecem fora do Git. A revisão
de configuração do ambiente salva instalação/instruções, sem executar ou publicar
um snapshot. Publicação do ambiente e envio de código ao GitHub são operações
distintas. Uma tarefa nova ainda precisa validar a restauração e iniciar processos.

## Evidência específica das Fases 8–10

A execução completa de `scripts/setup.sh` concluiu em **232 testes**, nenhum
ignorado/desabilitado. Inclui 58 novos cenários, além dos 174 anteriores. A
migração foi testada com credencial e acesso da Fase 7, novo cadastro sintético,
comparação, relatório, rollback da revisão nova e upgrade novamente. Acesso
anterior e estado de consumo da credencial permaneceram preservados. Esse
rollback ocorreu apenas em arquivo temporário.

O teste Chromium das Fases 8–10 gerou um evento a partir do MP4 sintético pelo
fluxo real de análise e conferiu a série de dados do Chart.js. Cadastrou logo,
gerou relatório, baixou CSV/PDF e extraiu o texto do PDF com `pdftotext`, confirmando
organização, tipo e responsável. Percorreu política/cadastro artificial, referência
cifrada, desafio, amostra diferente, amostra correspondente, token já usado e
exclusão. Senha/token ficaram na memória do processo e arquivos/banco temporários
foram removidos no fim. Não houve imagem de pessoa real ou acesso ao YouTube
nesse cenário.

O que passou é o protótipo do fluxo 1:1 e seu comparador artificial; isso **não é
validação facial**, prova de vida, estudo de precisão, conformidade legal ou
avaliação de diferenças entre grupos. Essas etapas, modelo/terminal real e
política operacional continuam pendentes antes de qualquer futura ativação real.
