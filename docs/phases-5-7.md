# Fases 5–7 — operação e limites

A versão 0.7.0 implementa eventos não identificadores, central de alertas e
controle de acesso empresarial simulado. O teste acordado usa o YouTube
`CKpA7U_wAbw` para reprodução e o MP4 sintético distribuído para análise.

## Análise autorizada

Em Eventos, o administrador configura por câmera: ativação, movimento,
possível obstrução/imagem uniforme, sensibilidade (fração de pixels alterados),
área normalizada X/Y/largura/altura, horários no fuso da unidade, dias e intervalo
mínimo entre eventos iguais. A análise começa desligada e exige confirmação
explícita de autorização da área e do uso de amostra temporária.

O detector OpenCV compara quadros reduzidos a 320 × 180. Movimento exige alteração
em pelo menos duas comparações; possível obstrução exige três quadros escuros ou
quase uniformes. Isso pode sinalizar iluminação, uma parede ou ausência de textura:
é uma indicação para revisão humana, não comprovação de incidente. Movimento
não identifica crime. Não há identificação individual, classificação de pessoas,
rastreamento entre câmeras ou inferência de atributos sensíveis. Não foi incluído
modelo treinado de presença genérica de pessoas.

Cada execução lê até 72 quadros. O limite de dez segundos é conferido entre
leituras, não interrompe um decodificador nativo travado. Para fontes reais,
a tarefa fica na fila e deve ser processada fora do servidor web. O worker
reconfere organização, unidade, câmera, administrador solicitante, política e
horário antes da amostra. Solicitações sem autorização atual ficam como não
executadas. Falha de leitura/processamento cria evento explícito e alerta.

O gateway fornece até dois níveis de playlist HLS convencional e um segmento de
até 12 MiB, além de inicialização opcional de até 1 MiB. As URLs são fixadas pela
instalação; playlists externas, caminhos arbitrários e containers inesperados
são rejeitados. OpenCV usa FFmpeg com protocolos limitados a arquivos locais.
A amostra real fica num diretório temporário privado, removido após análise ou
exceção normal. Encerramento forçado da máquina pode deixar resíduos temporários;
a instalação deve proteger e limpar seu diretório temporário. Nenhum trecho,
screenshot ou frame é guardado no banco, no Git ou enviado a outra IA.

## Fila local

Na raiz do projeto, com o ambiente virtual preparado:

```powershell
.\.venv\Scripts\python.exe -m flask --app app process-analysis --limit 10
```

Linux: `.venv/bin/python -m flask --app app process-analysis --limit 10`.
O comando processa até dez tarefas pendentes e termina. Rode novamente para novos
lotes. Não cria serviço, agendador ou análise contínua. O índice parcial permite
somente uma tarefa pendente/em execução por câmera; a tomada é atômica no banco.

Se um worker cair, uma tarefa pode ficar em execução. **Encerre todos os workers
anteriores** e só então execute `process-analysis --recover-stale --limit 10`.
Isso devolve à fila tarefas em execução há mais de cinco minutos; a confirmação
sobre workers anteriores cabe ao operador da instalação. Não faça recuperação
em paralelo com um worker ativo. Supervisão de processo, limites rígidos de CPU/
memória e recuperação automática ficam pendentes para operação de produção.

## Eventos e alertas

Eventos registram organização/unidade/câmera, tipo, prioridade, data UTC e origem.
Movimento, possível obstrução, falha de análise, falha de integração,
indisponibilidade/reconexão de câmera, erro manual do YouTube e negações repetidas
simuladas podem abrir alertas. Disponibilidade real depende da verificação manual
da câmera; não há varredura de rede. Status demonstrativo não vira status real.
Reprodução/encerramento relatados do YouTube são apenas informativos.

Tipos, origens, status, prioridade e pesquisa permitem localizar eventos/alertas.
Na ocorrência, reconheça antes de colocar em análise ou resolver; resolução e
descarte exigem justificativa. Administração e supervisão podem atribuir um
responsável elegível; operador pode assumir para si e preservar atribuições
existentes. Ocorrências encerradas permanecem para consulta. O sino mostra
pendências no escopo atual a cada 30 segundos. Não envia e-mail, webhook ou mensagem.

A deduplicação usa janela móvel por organização/unidade/câmera/tipo/origem:
o padrão é 60 segundos, configurável por câmera de 10 a 3600 segundos. Erros
manuais do YouTube usam 60 segundos. Negações repetidas usam cinco minutos por
ponto simulado. Apagar câmera desvincula seu ID de eventos existentes e preserva
ocorrências; política e tarefas da câmera são removidas em cascata.

## Controle de acesso simulado

1. Cadastre uma pessoa autorizada e referência interna mínima como administrador.
2. Conceda permissão para uma unidade, com horários e dias no fuso da unidade.
3. Cadastre um ponto simulado da mesma unidade.
4. Emita uma credencial com validade de 1, 5 ou 15 minutos; copie-a imediatamente.
   O texto completo aparece só nessa resposta, com `Cache-Control: no-store`.
5. Apresente o token na tela Controle de Acesso e confirme a simulação.
   O backend verifica estado, validade, permissão e horário antes do consumo.

O token é aleatório, de uso único, com somente seu hash no banco. Nome/matrícula
não autorizam acesso. Revogar, desativar a pessoa ou remover a permissão impede
novas autorizações. Apresentar novamente é negado; o consumo condicional também
impede duas autorizações simultâneas. A tentativa e o motivo ficam no histórico;
o token não é incluído no histórico, auditoria, URL ou HTML posterior.
Nenhum comando é enviado a fechaduras, catracas ou controladoras. Não há biometria.

O cadastro de pessoas e emissão/revogação de permissões/credenciais são exclusivos
do administrador da organização. Operador/supervisor somente simulam nos pontos
das unidades concedidas; usuários de acesso físico/plataforma não recebem acesso
ao console. Todos os formulários de mutação usam sessão, escopo e CSRF.

## Atualização e validação

A migração aditiva `0e0fdb6387b6` é aplicada por `iniciar.bat`/`scripts/setup.sh`.
Faça backup de `instance/` e `.env` antes de atualizar e preserve as chaves locais.
Não faça downgrade no banco de trabalho: reverter esta revisão apaga eventos,
alertas e cadastros/decisões de acesso. Rollbacks são testados em bases temporárias.

Veja [validação](validation.md). Windows real, câmera física, MediaMTX remoto,
reprodução efetiva do YouTube, PostgreSQL e implantação pública não foram
validados. O dashboard foi substituído por cálculos na Fase 9. As Fases 8–10 foram
autorizadas; veja phases-8-10.md. A Fase 11 e seguintes aguardam autorização.
