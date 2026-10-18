# Fases 8–10 — fluxo 1:1 sintético, indicadores e relatórios

Versão 0.10.0. As três fases foram autorizadas pelo usuário. O YouTube continua
exclusivamente como player e observação manual; a análise usa vídeo sintético
ou gateway autorizado. Não há extração de imagens do YouTube.

## Fase 8: alcance e bloqueios

O módulo implementa o **fluxo de verificação 1:1 em protótipo artificial**.
Não inclui reconhecimento facial de pessoas reais. Os vetores são números
aleatórios sem vínculo com imagens ou características humanas. A opção de
amostra correspondente/diferente é uma fixture explícita; não mede precisão
facial nem resistência a fraude. Não há busca 1:N, galeria de desconhecidos,
comparação de vigilância com funcionários, lista de suspeitos, rastreamento,
classificação sensível ou coleta de imagens.

Não existe botão/configuração para ativar biometria real. O protótipo também
recusa operação em ambiente de produção, independentemente da chave configurada.
Permissões do navegador continuam bloqueando câmera e microfone. Receber imagens
não faz parte das rotas de verificação; uploads nessas rotas são rejeitados.

Antes de uma futura ativação real, permanecem pendentes: avaliação jurídica e
base legal apropriada (sem presumir consentimento suficiente no trabalho),
necessidade/proporcionalidade, RIPD quando cabível, revisão trabalhista,
responsáveis, retenção/exclusão, alternativa efetiva, terminal autorizado,
modelo licenciado e versionado, qualidade de captura, avaliação de falsas
aceitações/rejeições sob condições representativas e diferenças de desempenho,
e proteção contra apresentação fraudulenta validada. Não houve avaliação de
pessoas/grupos nesta entrega. Piscar ou mover a cabeça não é usado como prova de vida.

A política registra finalidade, responsável, referências das avaliações,
alternativa, retenção e limiar do comparador **de teste**. Esses registros são
preparação do fluxo, sem certificação jurídica ou técnica. Só o administrador
configura política e cria/apaga referências com autorização documentada do teste.

### Fluxo implementado

1. O operador apresenta uma credencial válida em ponto dentro do seu escopo.
2. O backend confere credencial, cadastro ativo, permissão e horário no fuso da
   unidade. Resolve exclusivamente o cadastro declarado pelo token, sem procurar
   outras identidades.
3. Exige política habilitada e referência artificial vigente, autorizada,
   cifrada e da versão atual. Cria desafio de dois minutos ligado à sessão do
   operador, ponto e credencial. O token apresentado não é guardado no desafio.
4. A fixture de captura é selecionada explicitamente: correspondente, diferente,
   qualidade insuficiente ou captura incompleta. A comparação usa somente a
   referência declarada e o limiar sintético. Não captura nem guarda imagem.
5. O desafio é tomado uma única vez. A decisão reconfirma permissões e o estado
   da credencial; no consumo atômico também exige política/referência ainda
   válidas. Revogar durante a comparação impede a autorização.
6. Resultado aprovado consome a credencial de uso único e registra **acesso
   simulado**. Falha de comparação/qualidade não consome o token; a alternativa
   não biométrica da Fase 7 continua disponível, com revisão autorizada.

Após três registros em dez minutos para uma credencial, novas verificações
ficam temporariamente limitadas. Isso não desativa a pessoa nem bloqueia
permanentemente o método alternativo. Rotas também têm limites por usuário.
Resultados minimizados incluem aprovado/não aprovado, qualidade insuficiente,
nova tentativa, cadastro indisponível, credencial inválida e método alternativo.
Não mostram pontuação, vetor ou conteúdo cifrado.

### Proteção e exclusão

Referências artificiais usam Fernet com chave separada do cofre de câmeras.
`BIOMETRIC_TEST_KEY` pode fornecer chave de teste válida; no desenvolvimento,
a ausência gera `instance/verification-test-key`, fora do Git. Chave indisponível,
modelo diferente, política alterada, vencimento ou revogação negam a verificação.
Não se usam hashes comuns para comparar ou alegar anonimização de biometria.
Embeddings reais poderiam continuar sendo dados biométricos sensíveis, mas não
são coletados por este protótipo.

Retenção é de 1–30 dias; vencimento impede uso imediatamente. Editar a política
apaga conteúdo das referências anteriores e exige recadastro. **Revogar e excluir**
remove imediatamente ciphertext e referência de autorização no banco ativo;
mantém apenas metadados mínimos e o registro administrativo. Isso não garante
apagamento forense de páginas SQLite, WAL ou backups: eliminação física e ciclo
de backups precisam de política operacional antes de qualquer dado real.

Execute diariamente, na raiz:

```powershell
.\.venv\Scripts\python.exe -m flask --app app purge-verification-tests
```

Linux: `.venv/bin/python -m flask --app app purge-verification-tests`.
A rotina remove conteúdo expirado/revogado/incompatível e desafios vencidos há
mais de um dia; executa uma vez e termina. Agendamento fica com a instalação.

## Fase 9: fórmulas e escopo

O dashboard usa dados do banco e não contém mais os indicadores fictícios 24/21/3.
Filtros cobrem até 92 dias, unidade autorizada e origem; datas são UTC, com final
inclusivo na interface e intervalo semiaberto no backend. Unidade/fonte inválida
é rejeitada, sem substituir silenciosamente por todo o escopo.

- **Inventário/estado atual:** total no filtro de fonte, online/offline real
  somente com verificação recente, desconhecido, demonstração ativa e desativada.
  `last_seen_at` informa última comunicação confirmada; demo não preenche essa data.
- **Disponibilidade observada:** cada observação online/offline vale de seu horário
  até o menor entre próxima observação, 90 segundos (`CAMERA_STATUS_TTL`), fim do
  período e agora. Observação anterior ao início pode contribuir se ainda vigente.
  Unknown/demo não entram no denominador. Taxa = segundos online / segundos
  observados online+offline. Sem observações retorna **Sem dados**, não 0% ou 100%.
- **Cobertura:** segundos observados / duração elegível do período para a câmera.
  Lacunas, inclusive entre verificações manuais, não são tratadas como online.
  Não é uma medição contínua de SLA ou garantia de disponibilidade.
- **Indisponibilidade média observada:** média dos blocos offline contíguos
  efetivamente observados. Gaps desconhecidos não prolongam indisponibilidade.
  Falhas por período contam verificações offline/inconclusivas no intervalo.
- **Alertas:** coorte pela data de criação no período, com estado atual na geração;
  pendentes = novo/reconhecido/em análise. Tempos médios usam reconhecimento menos
  criação e resolução menos criação, em segundos; descarte não conta como resolução.
  Uma resolução posterior ao intervalo ainda pode compor o tempo da coorte.
- **Acesso:** tentativas, permitidas/negadas e falhas de validação/infraestrutura
  agregadas. Tudo permanece simulado, sem ranking pessoal ou produtividade.

Gráficos locais Chart.js: linha temporal de eventos/tentativas, barras por unidade,
disponibilidade por câmera, tipos de alerta e comparação mensal dentro do período
selecionado. Tabelas apresentam os mesmos dados sem JavaScript. Há até 30 câmeras
no gráfico/tabela resumida e 20 eventos recentes; relatórios atendem maior detalhe.
Uma seleção que cruza meses permite comparar os meses; períodos parciais não são
extrapolados para o mês inteiro. O cálculo tem limite explícito de 100 mil
observações por conjunto; exceder pede reduzir o período/unidade.

## Fase 10: relatórios profissionais

Disponíveis: disponibilidade observada, falhas técnicas, alertas, eventos por
unidade, tempos de reconhecimento/resolução, resumo de acesso e auditoria
administrativa. Cada snapshot contém identificador aleatório, organização,
responsável, data UTC da geração, finalidade, período, filtro de fonte, totais,
tabela e notas metodológicas. O conteúdo não muda quando os registros operacionais
mudam; gerar novamente produz novo snapshot.

Até 5000 linhas por tabela; truncamento é informado e totais continuam abrangendo
o escopo selecionado. Reduza período/unidade para detalhar mais. Auditoria
administrativa é exclusiva do administrador e abrange a organização inteira,
sem filtro de unidade/fonte, pois o log legado não possui esses vínculos.

O administrador pode fornecer logo PNG/JPEG de até 48 KiB e 512 × 512 pixels.
A imagem é decodificada, normalizada para PNG sem metadados e copiada no snapshot;
SVG, animação, dimensões excessivas e conteúdo inválido são rejeitados. Sem logo
personalizado, o PDF usa cabeçalho textual. Sem URLs ou imagens remotas no gerador.

CSV usa UTF-8 com BOM, campos corretamente delimitados e neutralização de fórmulas.
PDF usa ReportLab local, cabeçalho/logo, tabelas paginadas, identificador e notas.
Downloads exigem POST/CSRF, conferem permissões atuais e são auditados. Conteúdo
é no-store. Só o autor ou administrador pode acessar um relatório; todos os
escopos presentes no snapshot devem continuar autorizados, inclusive para logo
armazenado e exportação. Revogação bloqueia novos downloads; bytes recebidos
anteriormente não podem ser recuperados do dispositivo do usuário.

Relatórios de acesso agrupam por unidade/ponto/decisão/motivo/método, sem nomes,
matrículas, tokens, histórico pessoal ou templates. Relatórios pessoais de acesso
não são oferecidos nesta fase. Auditoria inclui IDs internos de autores e ações
mínimas, com acesso administrativo e finalidade; não inclui payload de credenciais.

## Atualização e limitações operacionais

Feche o site e faça backup de `instance/` e `.env` antes de atualizar. Preserve
as chaves e cadastros locais, atualize fontes, lockfile, migrações e scripts e
abra `iniciar.bat`. A migração `da64a0b27c33` é aditiva e preserva a Fase 7.
Não faça downgrade no banco de trabalho: remove os novos cadastros e relatórios.
Testes de rollback usam apenas bases temporárias.

Windows real, PostgreSQL, hardware, modelo facial real, precisão/PAD, restauração
operacional e implantação pública não foram validados. A entrega é para ambiente
local de desenvolvimento. As fases anteriores de análise/YouTube mantêm seus
limites documentados. A Fase 11 e seguintes aguardam autorização.
