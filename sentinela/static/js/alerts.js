'use strict';
const alertSummary = document.querySelector('[data-alert-summary]');
if (alertSummary) {
  async function refreshAlertCount() {
    try {
      const response = await fetch(alertSummary.dataset.alertSummary, {cache:'no-store', redirect:'error'});
      if (!response.ok) return;
      const data = await response.json();
      const counter = alertSummary.querySelector('.alert-counter');
      counter.textContent = data.pending > 99 ? '99+' : String(data.pending);
      counter.hidden = data.pending === 0;
      alertSummary.setAttribute('aria-label', `Central de alertas: ${data.pending} pendentes no seu escopo`);
    } catch (_) { /* A navegação continua disponível se a sessão/rede falhar. */ }
  }
  refreshAlertCount();
  const timer = setInterval(refreshAlertCount, 30000);
  window.addEventListener('pagehide', () => clearInterval(timer));
}
