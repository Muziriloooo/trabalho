# Validação — Fases 1 a 7

Executada na nuvem Linux com Python 3.12.14, SQLite e Chromium headless.
A versão atual é 0.7.0. Os cenários usam bancos e contas temporários; tokens e
senhas de teste ficam na memória, sem contas padrão na instalação.

| Verificação | Resultado |
| --- | --- |
| `bash scripts/setup.sh` completo | Aprovado; instalação, `pip check`, upgrade, db check e suíte |
| Dependências fixadas, incluindo OpenCV headless / NumPy | Instaladas, sem incompatibilidades |
| Migração `0e0fdb6387b6` | Aplicada; nenhuma divergência entre modelos e migrações |
| `python -m pytest -q` | **174 testes aprovados**, nenhum ignorado ou desabilitado |
| Reinício por `scripts/start.sh` | Waitress; `/health` HTTP 200, versão 0.7.0, fase 7; `/login` HTTP 200 |
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
