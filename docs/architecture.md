# Arquitetura — Fases 1 a 4

Monólito modular Flask com application factory, SQLite e migrações Alembic.
`app.py` é a entrada WSGI, `config.py` centraliza configuração por ambiente.

| Módulo | Responsabilidade |
| --- | --- |
| auth | Sessão local, login limitado, logout POST e CSRF |
| core | Navegação, validação, escopo por unidade, health e erros |
| dashboard | Indicadores e eventos explicitamente demonstrativos |
| organizations | Metadados de organizações e provisionamento local de equipe/escopos |
| sites | Unidades com cadastro, edição, busca e desativação |
| cameras | Inventário, autorização de operação, cifras e histórico de disponibilidade |
| monitoring | Grade, player sintético/HLS e autorização em cada requisição de mídia |
| services/vault | Credenciais de gateway cifradas com Fernet |
| services/gateway | MediaMTX API v3 e HLS HTTPS, destinos fixos, limites e playlists reescritas |
| services/audit | Registro mínimo de alterações administrativas sem payload de credenciais |

## Modelo e fronteira de cliente

Organization e Site possuem identificador, responsável e estado. Site também
possui endereço opcional, descrição e fuso IANA. User mantém seu papel base,
organização e hash scrypt. RoleAssignment concede operador/supervisor em uma
unidade ou em toda a organização, com concedente e data. A concessão global
inclui unidades futuras; administradores da organização possuem escopo integral.

Toda consulta operacional resolve organização pela sessão. Escopos são
subconsultas EXISTS no backend. Cabeçalhos, formulários e IDs não selecionam a
organização. Cadastros externos ao cliente/unidade visível retornam 404.
O administrador da plataforma só usa rotas separadas de metadados e não ganha
acesso às câmeras de clientes. Não há impersonação ou acesso excepcional.

Câmera inclui organização, unidade, identificador único no cliente, fabricante,
modelo, local, protocolo, caminho do gateway, referência cifrada, estado,
criador, datas de cadastro, verificação e última disponibilidade confirmada.
FKs compostas impedem vínculo entre clientes em Camera, RoleAssignment,
ConnectionSecret e CameraHealthEvent. Índices suportam esses vínculos e consultas.
A unicidade dos escopos impede concessões duplicadas, inclusive o escopo global.

CameraHealthEvent contém somente resultado e código de motivo, sem URL,
senha, imagem ou dados de pessoas. AuditLog registra mudanças e autor; a
interface completa, retenção e proteção contra adulteração ficam para a Fase 11.
O usuário técnico do banco ainda pode alterar essas tabelas; não são logs imutáveis.

## Migração e persistência

A revisão `78f63a927cf9` adiciona tabelas e colunas sem recriar tabelas pai no
upgrade SQLite, preservando contas e registros existentes. Organizações/unidades
legadas recebem identificadores `org-ID` / `site-ID`. Usuários existentes não
ganham escopos de unidade implicitamente. O rollback é destrutivo para as novas
entidades e exige SQLite >=3.35; é testado somente em bases temporárias.
Os testes também fazem upgrade com dados preenchidos, rollback e novo upgrade.

## Mídia

Demonstração: MP4 sintético distribuído fora de static, com requisições Range
somente após autenticação/escopo. Fonte real: o MediaMTX guarda RTSP e faz remux
HLS; Flask autoriza e encaminha requisições limitadas de playlists/segmentos por
HTTPS. O namespace do gateway recebe automaticamente o ID imutável da organização,
impedindo escolher a fonte de outro cliente no cadastro. URLs upstream e
credenciais nunca entram no HTML ou na playlist entregue ao player.

Sem origem de streaming improvisada, descoberta de equipamentos, gravação,
biometria, controle de fechadura ou envio de vídeo a IA. HLS convencional com
fMP4/MPEG-TS é suportado; LL-HLS e chaves remotas em playlists são rejeitados.
Hls.js é distribuído localmente para navegadores com MSE; Safari pode usar HLS
nativo. Atraso exibido é uma estimativa no buffer, não a latência de captura real.

## Segurança e operação

CSRF em mutações, cookies HttpOnly/SameSite, escape Jinja, CSP restritiva com mídia
same-origin/blob, sem CORS aberto. Câmera/microfone do navegador desabilitados.
Credenciais do gateway usam Fernet; a chave fica fora do banco e do Git.
Destinos e portas são escolhidos pelo operador da instalação, separados do
formulário. HTTPS é obrigatório no gateway, TLS/CA e proxies são preservados,
redirecionamentos não são seguidos, nomes de arquivos são restritos, respostas
são limitadas e os motivos de falha são minimizados.

Contadores de tentativas são locais ao processo. Uma verificação de câmera por
10 segundos e até dez por minuto por administrador; nenhuma repetição automática
é feita no servidor. O player faz até três reconexões com espera crescente.
Cada requisição valida os escopos atuais; a aba também revalida em intervalos de
15 segundos. Dados já baixados não podem ser apagados remotamente. Pausa remove
a origem do player e encerra novas requisições. Status manual expira em 90 segundos.

Produção requer chave de sessão, banco explícito e, para credenciais de gateway,
chave de cifra fornecida por um gerenciador seguro. Essa configuração ativa
cookies Secure/HSTS, mas não instala TLS nem configura PostgreSQL. Redis,
PostgreSQL, implantação, backups, MFA e avaliação de segurança operacional ficam
pendentes. Não expor o servidor local de desenvolvimento à internet.
