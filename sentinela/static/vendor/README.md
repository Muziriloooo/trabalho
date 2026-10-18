# Dependências locais do frontend

- Chart.js 4.5.1 — MIT (`CHART-LICENSE.md`).
- Lucide 0.468.0 — ISC (`LUCIDE-LICENSE`).
- O bundle UMD de Chart.js inclui @kurkle/color 0.3.4 — MIT
  (`COLOR-LICENSE.md`).

Arquivos copiados das distribuições npm oficiais, com verificação de integridade
do npm habilitada. `package-lock.json` registra as versões e integridades da
aquisição. A aplicação não faz requisições a CDN e não exige Node/npm para rodar.

Para atualizar conscientemente: instalar as versões desejadas num diretório
temporário com npm (sem scripts), copiar os bundles UMD e licenças e atualizar o
registro de versões/integridades. Revalidar CSP, ícones e gráficos no navegador.

- hls.js 1.6.15 — Apache-2.0 (`HLS-LICENSE` e `APACHE-2.0.txt`).
  Reprodução HLS no navegador; bundle oficial npm, integridade verificada.
