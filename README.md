# Dashboard de Implantações 2026 — Grupo Souza Lima

Painel executivo com cinco áreas: Visão Geral, Financeiro, Segmentos & Operação, Mapa & Clientes e Base de Dados. Tema claro, logo fornecido pela organização, filtros compartilhados e apresentação em tela cheia.

## Iniciar

No Windows, execute `iniciar_windows.bat` e abra http://localhost:8765. Mantenha o terminal aberto. Após atualizar os arquivos, reinicie o servidor e use Ctrl+F5 no navegador.

Em Linux, use um ambiente virtual, instale `requirements-google.txt` e execute `python app.py --no-browser`. O servidor existente usa a biblioteca padrão Python (`ThreadingHTTPServer`), sem migração de arquitetura ou novas dependências de aplicação.

Preserve `config_google.json`, `segredos/google_service_account.json` e os arquivos de `dados/`. A conexão Google permanece somente leitura, com resolução automática da aba e cache de 30 segundos. A alternativa Excel, importação e download continuam disponíveis quando essa fonte está configurada. Credenciais nunca devem entrar no Git.

## Definição dos indicadores

- Uma implantação representa uma linha com cliente preenchido, conforme a regra original. Não há deduplicação automática de implantações nem inferência de conclusão pelo status.
- Clientes distintos são contados pelo nome sem espaços nas extremidades e sem distinção entre maiúsculas e minúsculas; não equivale a identificação por CNPJ.
- Efetivo e valores financeiros somam os campos numéricos disponíveis. Ausentes, erros de fórmula e valores não finitos permanecem nulos; zero informado é preservado. Totais podem ser parciais quando a base tem campos ausentes.
- Lead time é a média dos dias úteis numéricos não negativos informados na planilha. Não calcula feriados nem substitui campos vazios por zero.
- Comparação mensal usa o mês calendário anterior com os mesmos filtros; sem registros comparáveis, informa indisponibilidade.
- O mapa usa referências aproximadas das filiais, nunca endereços de clientes, e mantém agrupamento, zoom e movimentação sem serviços de mapas externos.
- A Base de Dados exibe as 13 colunas, com datas brasileiras e CSV filtrado. A planilha de origem não é modificada pelo redesenho.
- Cartões e barras de indicadores abrem a Base de Dados. Barras de mês e filial aplicam o respectivo recorte antes de abrir; os demais cartões mantêm os filtros globais já selecionados.

Falhas de atualização mantêm a última leitura na memória da página com aviso explícito. A primeira leitura malsucedida mostra erro, sem dados fictícios. A prévia HTML antiga continua sendo uma fotografia estática independente; use o servidor para o visual atualizado e a sincronização.

## Validação do redesenho

`python -m unittest discover -s tests -v` verifica números inválidos, datas, campos ausentes, zeros e linhas descartadas. `node --check static/app.js` verifica sintaxe JavaScript.

Com o servidor iniciado e Playwright/Chromium disponíveis no ambiente de teste, `python tests/browser_dashboard.py` executa testes com dados sintéticos interceptados somente no navegador: cinco áreas, filtros, paginação, CSV, 13 colunas, mapa, indisponibilidade/recuperação, apresentação, base vazia e 5.000 registros. Verifica larguras de 390, 768, 1366 e 1920 pixels. Não envia fixtures à planilha e não lê credenciais.

Validação realizada em Chromium/Linux. A leitura real Google foi bem-sucedida, retornando 678 registros no momento do teste. Isso comprova acesso naquele momento, não disponibilidade futura. Windows, outros navegadores e projeção em televisão física não foram testados nesta sessão.
