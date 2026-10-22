IMPLANTAÇÕES 2026 · VERSÃO PRO (REDESIGN COMPLETO)
==================================================

Esta versão melhora as CINCO ÁREAS EXISTENTES. Nenhuma tela nova foi criada:
1. Visão geral
2. Financeiro
3. Segmentos & operação
4. Mapa & clientes
5. Base de dados

MELHORIAS
- Identidade visual azul-marinho e dourado redesenhada, tipografia e números mais legíveis.
- Indicadores, gráficos e tabelas com visual atualizado e melhor responsividade.
- Busca GLOBAL de cliente no bloco de filtros. Aplica-se às cinco áreas.
- Gráficos interativos: clique em mês, segmento ou filial para filtrar.
- No celular, os gráficos podem ser deslizados horizontalmente.
- Mapa vetorial offline (sem requisições de tiles/erros 403), zoom e regiões selecionáveis.
- Modo de apresentação no cabeçalho (sair com Esc); botão para imprimir a tela.
- Navegação por teclado em elementos de gráficos e tecla F para focar busca de clientes.
- A planilha original NÃO é modificada pelo dashboard; os dados são normalizados para exibição.

MODO PREVIA E VERSÃO CONECTADA
- PREVIA_SEM_INSTALAR.html: abre no navegador sem servidor. CONTÉM UMA FOTOGRAFIA ESTÁTICA dos dados do Excel no momento da geração. Mudanças no Excel NÃO aparecem na prévia.
- iniciar_windows.bat: inicia o servidor local. Esse modo recebe atualizações do Excel salvo na pasta dados e permite Importar Excel.
- A planilha atualizada é reprocessada após salvar ou usar o botão de atualização. O sistema verifica alterações a cada 30 s.
- No modo conectado, 'Importar Excel' SUBSTITUI a planilha da pasta dados. Faça cópia de segurança.

PAINEL DE IMPLANTAÇÕES 2026
==========================

COMO ABRIR NO WINDOWS
1. Extraia o arquivo ZIP para uma pasta do computador.
2. Tenha Python 3.9 ou mais recente instalado (python.org).
3. Dê dois cliques em "iniciar_windows.bat".
4. O navegador abrirá em http://localhost:8765
5. Mantenha a janela do terminal aberta enquanto usa o painel.

COMO MANTER O EXCEL VINCULADO
- O arquivo conectado está em dados/IMPLANTAÇÕES 2026.xlsx
- Você pode editar esse arquivo diretamente no Excel e salvar.
- O site detecta mudanças a cada 30 segundos (também há botão Atualizar).
- OU use o botão "Importar Excel" no site para trocar o arquivo vinculado.
- O servidor usa a primeira aba e espera estas colunas (A:M):
  MES E ANO | CLIENTE | FILIAL | SEGMENTO | TARGET | TOTAL GASTO |
  CUSTO EVITADO | DATA da NOTIFICAÇÃO | DATA IMPLANTAÇÃO |
  DIAS UTEIS | STATUS | QTD. EFETIVO | VISITA TÉCNICA
- A importação no site substitui o arquivo conectado: preserve um backup se necessário.

MÉTRICAS
- Implantações: registros da planilha com CLIENTE preenchido.
- Clientes únicos: nomes distintos (não são os mesmos que implantações).
- Efetivo: soma dos valores numéricos em QTD. EFETIVO.
- Target / Gasto / Economia: somatório das respectivas colunas.
- Lead time: média de DIAS UTEIS nos registros com cliente e prazo >= 0.
  Linhas vazias com fórmulas retornando 0 não entram no cálculo.
- Visita: SIM / NÃO / Não informado são categorias distintas.
- Nomes de filiais repetidos por erros de digitação são normalizados somente
  no painel, nunca no Excel original.

LIMITAÇÕES IMPORTANTES
- A página fica disponível somente neste computador por segurança (localhost).
- Não cria uma integração automática com Google Sheets ou Looker Studio.
- O Excel precisa ter valores calculados e salvos; fórmulas não são recalculadas
  pelo servidor (se mudar fórmulas, abra/salve a planilha no Excel).
- Os gráficos e filtros funcionam localmente sem internet.
- O site não substitui o Excel, usa-o como fonte de dados.

ARQUIVOS
app.py              servidor e leitura do Excel (sem bibliotecas extras)
static/index.html    interface
static/style.css     identidade visual
static/app.js        gráficos, filtros, tabelas e exportação CSV
dados/               planilha vinculada

Produzido para servir como protótipo funcional e extensível.

NOVO: MAPA & CLIENTES
- Acesse o menu "Mapa & clientes" para explorar o território de atuação.
- Tabela cliente × efetivo, busca, paginação, filtros por mês, filial e segmento, e
  mapa com marcadores agrupados quando estiverem muito próximos.
- Clique na bolha para selecionar uma região; clique no registro para localizar a filial.
- Os círculos são posicionados por sede/capital de referência da FILIAL, não pelo
  endereço real da implantação (o Excel original não tem endereço/latitude/longitude).
- A visualização geográfica agora é 100% offline com contornos de países reais
  do conjunto cartográfico Natural Earth (domínio público).
- Não usa serviços externos de tiles e não apresenta erro 403 de OSM.
- O mapa mostra países, limites e algumas cidades de referência, mas NÃO
  tem ruas detalhadas como Google Maps. Os pontos e todos os filtros seguem
  interativos mesmo sem internet.
- Os dados dos clientes NÃO são enviados a um provedor de mapas.


CORREÇÃO DO MAPA (v2)
--------------------
O mapa vetorial não reutiliza mais o mesmo wrap de longitude dos marcadores.
Isso evita faixas horizontais artificiais e preenchimentos sobrepostos ao Brasil.
Se estiver com a versão antiga aberta, feche a guia, substitua os arquivos e
reabra o navegador. Atualize com Ctrl + F5 se necessário.


INTEGRACAO GOOGLE PLANILHAS PRIVADO
----------------------------------
Leia LEIA-ME-GOOGLE.txt para configurar a nova fonte opcional.
