# Fases 3 e 4 — Câmeras e monitoramento

## Fluxos entregues

O inventário tem cadastro/edição, identificador único por organização, unidade,
nome, fabricante/modelo opcionais, local, protocolo, criador, estado e datas.
Permite pesquisa, filtros, ativação/desativação com confirmação e exclusão por
digitação do identificador. A exclusão remove a credencial cifrada e o histórico,
e deixa um registro mínimo de auditoria. Não existem URLs RTSP no banco da aplicação.

O administrador verifica manualmente uma câmera já cadastrada, autorizada e
ativa. Sem varredura de rede. Demonstração registra resultado demo e nunca
preenche last_seen real. Fontes reais consultam a API do gateway: online atual,
ou ready em versões anteriores. Fonte indisponível registra offline. Problemas
de TLS, timeout, credencial ou configuração registram unknown; não provam que o
hardware está offline. Resultados expiram após 90 segundos sem nova consulta.
O histórico mostra os últimos 100 resultados; não há processo contínuo ou política
automática de retenção nesta fase.

O monitoramento suporta grade 1/4/9, câmera individual pelo inventário, filtro por
unidade, iniciar/pausar/retomar, tela cheia, reconexão limitada e estimativa de
atraso de buffer. Até nove câmeras por consulta: use filtro ou os detalhes para
selecionar outra câmera. Desativar ou revogar acesso bloqueia novas requisições;
a aba interrompe o player na validação periódica, aproximadamente 15 segundos
com navegador ativo. Dados já recebidos podem permanecer em buffers do navegador.

## Demonstração

O MP4 em `sentinela/media/demo.mp4` é sintético, sem pessoas, áudio ou câmera real.
Está fora de static e só é servido por uma câmera demo autorizada no backend.
Não é necessário instalar FFmpeg para reproduzir; ele é opcional para regenerar
esse asset com `scripts/generate-demo.sh`. O arquivo é disponibilizado sob CC0.

## Contrato MediaMTX

Integrado o protocolo HTTP da API v3 e HLS convencional. Referências oficiais:

- https://mediamtx.org/docs/usage/reading
- https://github.com/bluenviron/mediamtx/blob/main/api/openapi.yaml
- https://github.com/bluenviron/mediamtx/blob/main/mediamtx.yml

A implementação não instala ou inicia um gateway de produção. Um operador
qualificado deve provisioná-lo na infraestrutura autorizada do cliente, com:

1. Credenciais RTSP/RTSPS da câmera somente no gerenciador/configuração protegida
   do MediaMTX. Não colocá-las neste repositório, em logs, screenshots ou navegador.
2. HLS **fmp4** (ou mpegts) convencional. Definir `hlsVariant: fmp4`; o padrão
   lowLatency do MediaMTX **não é suportado** pelo relay atual. LL-HLS, playlists
   com parâmetros, chaves remotas e URLs externas são rejeitados.
3. API v3 e HLS sob HTTPS com certificados de uma CA confiável e autenticação.
   Usar certificados válidos ou uma CA privada instalada no trust bundle da
   aplicação. Nunca desativar verificação TLS. API/HLS podem ter terminadores TLS
   privados separados; os endereços configurados abaixo são as origens HTTPS.
4. Um caminho por câmera: `org-ID--REFERENCIA`. ID é o ID imutável da organização
   no banco; REFERENCIA é o campo do cadastro. Exemplo não secreto: para organização
   12 e referência `entrada`, provisionar `org-12--entrada`. A interface mostra o
   prefixo necessário ao cadastrar. O backend aplica esse prefixo automaticamente
   na API e em toda requisição HLS; o usuário não pode selecionar outra organização.
5. Credencial de serviço para leitura HLS e consulta da API, com privilégios mínimos.
   A interface aceita usuário/senha de leitura do gateway; não aceita credenciais
   da câmera. Restrinja também os caminhos e redes na infraestrutura do gateway.
   Sua API fica privada e somente acessível pelo backend autorizado.
6. `record: false`, playback e serviços não utilizados desativados; armazenamento
   em disco do vídeo não é habilitado pela aplicação. Segmentos temporários de
   HLS exigem política operacional de memória/retenção no próprio gateway.
7. Isolamento de rede, controle de destinos RTSP e portas do gateway. A aplicação
   não descobre dispositivos nem provisiona fontes por API administrativa.

Configuração da aplicação (endereços ilustrativos, sem credenciais):

```dotenv
MEDIA_GATEWAY_HLS_URL=https://media.empresa.example
MEDIA_GATEWAY_API_URL=https://media-api.empresa.example
MEDIA_GATEWAY_ALLOWED_HOSTS=media.empresa.example,media-api.empresa.example
MEDIA_GATEWAY_ALLOWED_PORTS=443
```

URLs precisam ser origens HTTPS sem usuário, senha, query ou path. A lista deve
conter exatamente os hosts necessários. Loopback, endereços link-local/metadata,
multicast e destinos não autorizados são recusados. Os formulários aceitam
somente referências alfanuméricas com hífen/sublinhado. Credenciais novas são
cifradas; campos vazios preservam a credencial salva. Para removê-la, use a opção
explícita. Em produção, fornecer uma chave Fernet real em CAMERA_ENCRYPTION_KEY
por um gerenciador de segredos fora do Git; placeholders de proxy não são chaves.
No desenvolvimento, a chave local é criada somente ao precisar cifrar uma credencial.

Em uma nuvem gerenciada, mantenha o proxy e as CAs injetadas; autorize também os
domínios do gateway nas configurações de rede e use VPN da plataforma quando
necessário. Esta implementação usa HTTPS por requests e não necessita abrir
RTSP/TCP na máquina da aplicação. A rede do gateway é que precisa alcançar as
câmeras autorizadas. Não existe gateway ou credencial real configurados nesta entrega.

## Limites e verificações

O backend consulta GET `/v3/paths/get/org-ID--REFERENCIA` e lê online (ou ready
legado). HLS usa `/org-ID--REFERENCIA/index.m3u8` e arquivos relativos convencionais.
Playlists são reescritas para rotas autenticadas, inclusive URI de inicialização;
segmentos e playlists repetem a verificação de usuário, organização, unidade e estado.
O browser recebe apenas URLs da própria aplicação, nunca a origem do gateway.

Redirects não são seguidos. Conexão/read usam timeout de 3/8 segundos e orçamento
checado durante a leitura; respostas são limitadas a 64 KiB de saúde, 256 KiB de
playlist e 12 MiB de segmento. Configure segmentos pequenos no gateway, por
exemplo 1–2 segundos e limite de 8 MiB. Vídeo H.264 é uma escolha compatível com a
maioria dos browsers; o adaptador não transcodifica nem garante todos os codecs.
A versão atual carrega cada segmento em memória com limite; o dimensionamento
multiusuário e o relay de produção de alta capacidade exigem revisão de implantação.

O player faz no máximo três reconexões com espera de 2/4/8 segundos. A verificação
manual respeita intervalo de 10 segundos e dez tentativas por minuto/administrador.
Não há worker de reconexão infinita. A aplicação não expõe uma transmissão pública,
não grava câmeras e não envia vídeo para serviços de IA. Para clientes remotos,
HTTPS também é necessário na aplicação; loopback HTTP serve somente ao
desenvolvimento local.

Validação executada com vídeo sintético e respostas controladas do gateway,
incluindo 401/403, 404, redirects, TLS, timeout, indisponibilidade, reconexão,
manifests maliciosos, conteúdo excessivo e revogação por segmento. Uma instalação
física de câmera/MediaMTX e execução em Windows real ainda precisam de ensaio no
ambiente do cliente antes de qualquer declaração de prontidão operacional.
