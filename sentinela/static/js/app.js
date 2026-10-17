/* Interações locais; nenhum dado ou credencial é enviado a terceiros. */
'use strict';
if (window.lucide) window.lucide.createIcons();
const toggle = document.getElementById('menu-toggle');
const overlay = document.getElementById('sidebar-overlay');
const mobile = window.matchMedia('(max-width: 800px)');
const sidebar = document.getElementById('sidebar');
const shell = document.querySelector('.app-shell');
function updateMenu() {
  const open = mobile.matches ? document.body.classList.contains('menu-open') : !document.body.classList.contains('menu-collapsed');
  if (toggle) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Recolher menu' : 'Abrir menu');
  }
  if (overlay) overlay.hidden = !(mobile.matches && open);
  if (shell) shell.inert = mobile.matches && open;
  if (sidebar) {
    if (mobile.matches && open) {
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
    }
  }
}
toggle?.addEventListener('click', () => {
  document.body.classList.toggle(mobile.matches ? 'menu-open' : 'menu-collapsed');
  updateMenu();
  if (mobile.matches && document.body.classList.contains('menu-open')) document.getElementById('menu-close').focus();
});
function closeMenu() {
  document.body.classList.remove('menu-open');
  updateMenu();
  toggle?.focus();
}
overlay?.addEventListener('click', closeMenu);
document.getElementById('menu-close')?.addEventListener('click', closeMenu);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && document.body.classList.contains('menu-open')) closeMenu();
  if (event.key === 'Tab' && mobile.matches && document.body.classList.contains('menu-open')) {
    const links = [...sidebar.querySelectorAll('a, button')];
    const first = links[0];
    const last = links[links.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
mobile.addEventListener('change', updateMenu);
updateMenu();
document.getElementById('login-form')?.addEventListener('submit', (event) => {
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  button.querySelector('span').textContent = 'Entrando…';
  document.getElementById('login-progress').textContent = 'Autenticando sua conta.';
});
window.addEventListener('pageshow', () => {
  const button = document.querySelector('.login-submit');
  if (button) { button.disabled = false; button.querySelector('span').textContent = 'Entrar no console'; }
});
