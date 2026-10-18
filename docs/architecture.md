# Arquitetura — Fases 1 a 10

Monólito modular Flask com application factory, SQLite e migrações Alembic.
`app.py` é a entrada WSGI, `config.py` centraliza configuração por ambiente.

| Módulo | Responsabilidade |
| --- | --- |
| auth | Sessão local, login limitado, logout POST e CSRF |
| core | Navegação, validação, escopo por unidade, health e erros |
| dashboard / services/analytics | Indicadores calculados no banco, escopo, filtros, gráficos e tabelas |
| organizations | Metadados de organizações e provisionamento local de equipe/escopos |
| sites | Unidades com cadastro, edição, busca e desativação |
| cameras | Inventário, autorização de operação, cifras e histórico de disponibilidade |
| monitoring | Grade, player sintético/HLS e autorização em cada requisição de mídia |
| services/vault | Credenciais de gateway cifradas com Fernet |
| services/gateway | MediaMTX API v3 e HLS HTTPS, destinos fixos, limites e playlists reescritas |
| events / services/vision / analysis | Política por câmera, análise limitada, fila SQLite e eventos com origem |
| alerts | Ocorrências, responsáveis, histórico, transições e notificações no console |
| access / services/access | Pessoas mínimas, pontos simulados, permissões, tokens de uso único e decisões |
| verification / services/verification | Protótipo 1:1 artificial, política, autorização, cifra, desafio e exclusão |
| reports / services/reports | Snapshots agregados, logo normalizado, CSV/PDF locais e exportação auditada |
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

Sem descoberta de equipamentos, gravação permanente, biometria, controle de
fechadura ou envio de vídeo a serviços externos de IA. A análise autorizada
processa movimento e possível obstrução de amostras limitadas; amostra real
é temporária e descartada ao concluir, inclusive em exceções normais. HLS convencional com
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

### Exemplo público de YouTube

A tela geral de Monitoramento tem um exemplo externo fixo, separado das câmeras.
Seu iframe oficial é criado somente após clique e validação da sessão. CSP libera
apenas https://www.youtube-nocookie.com para frames nessa página, com referrer
strict-origin-when-cross-origin no iframe para identificação do player. O browser
se conecta diretamente ao YouTube; o backend não extrai mídia, não verifica
se está ao vivo e não o inclui no inventário/status de câmeras. Encerrar remove
o iframe; a validação periódica de console também encerra o player se perder
acesso. O vídeo público permanece acessível no YouTube fora da aplicação.

## Operação das Fases 5–7

A revisão `0e0fdb6387b6` adiciona as tabelas operacionais sem alterar os dados
anteriores. AnalysisPolicy pertence à câmera/organização e começa desativada.
AnalysisJob mantém a fila no banco; índice parcial impede duas tarefas ativas
para uma câmera. O worker usa UPDATE condicional para tomar uma tarefa uma vez,
confere autorização atual e executa um lote. Não há agendador contínuo.

SecurityEvent registra unidade, câmera opcional, tipo, origem, motivo e data UTC.
EventGate faz deduplicação por janela móvel em transação; Alert é criado na mesma
transação para prioridades de atenção/crítica. Uma ocorrência encerrada não é
reaberta automaticamente. AlertActivity guarda comentários escapados e autor.
A atualização usa versão para impedir sobrescrita concorrente durante a transação.
O sino consulta somente contagens autorizadas; não há notificações externas.

AccessSubject guarda nome e referência mínima, sem fotos/documentos/biometria.
AccessPermission valida unidade, fuso e janela semanal, inclusive virada da noite.
AccessCredential armazena apenas SHA-256 de token aleatório de 256 bits, com
validade de 1/5/15 minutos e consumo atômico. AccessEvent registra a decisão e o
motivo, sem token. Credenciais revogadas, vencidas ou usadas são negadas; falha
na validação de horário também nega acesso. Três negações no ponto em cinco
minutos geram alerta simulado, limitado por janela de cinco minutos.

Fontes permanecem explícitas: `synthetic`, `gateway`, `youtube_client` (relato
manual) e `access_simulation`. O player do YouTube não fornece quadros ao worker.
Consulte [operação e limites](phases-5-7.md).

## Fases 8–10

`da64a0b27c33` adiciona VerificationPolicy, VerificationEnrollment,
VerificationChallenge, VerificationRecord, OrganizationBranding e ReportRun.
Índices únicos nas entidades de acesso suportam as FKs compostas das novas
referências; são criados antes das tabelas dependentes. O upgrade é aditivo;
rollback remove as novas tabelas e só depois seus índices de suporte. Migração
com acessos/credenciais preenchidos e novos resultados também foi validada.

O verificador aceita exclusivamente fixtures de vetores artificiais: o método
não é um modelo facial treinado. A credencial seleciona uma referência, cifrada
com Fernet em chave exclusiva do teste. Desafio liga organização, ponto, credencial
e operador por dois minutos/uso único. A decisão final reconfirma credencial,
permissão, política e referência em consumo condicional. Resultados não guardam
vetores, pontuações ou capturas. Modo de produção bloqueia este protótipo.

Analytics usa consultas por organização/unidades atuais. Disponibilidade integra
intervalos de verificações por no máximo CAMERA_STATUS_TTL (padrão 90 segundos),
sem interpolar lacunas. Contagens/tendências separam fontes. Tempos de alerta
usam timestamps persistidos. Consulta limitada a 92 dias/100 mil observações
por conjunto; limite excedido é um erro explícito, nunca estatística parcial.

ReportRun preserva o snapshot agregado, escopos cobertos, finalidade, responsável,
data, identificador e logo normalizado, sem template ou relatório individual de
acesso. Consulta/exportação reconferem permissões atuais e autor/admin; auditoria
administrativa exige administrador da organização. Exportação exige POST e CSRF,
registra AuditLog e retorna no-store. CSV neutraliza fórmulas; PDF usa ReportLab
local sem HTML ou recursos remotos. Consulte [critérios e limites](phases-8-10.md).
