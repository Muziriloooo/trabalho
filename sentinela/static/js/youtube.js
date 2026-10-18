'use strict';
const youtubePanel = document.querySelector('.youtube-panel');
if (youtubePanel) {
  const stage = youtubePanel.querySelector('.youtube-stage');
  const placeholder = stage.querySelector('.youtube-placeholder');
  const start = youtubePanel.querySelector('[data-youtube-action=start]');
  const stopButton = youtubePanel.querySelector('[data-youtube-action=stop]');
  const message = youtubePanel.querySelector('.youtube-message');
  let player = null, pending = false, sessionTimer = null, generation = 0;
  function stop(text) {
    generation++;
    clearInterval(sessionTimer);
    sessionTimer = null;
    player?.remove(); player = null;
    pending = false;
    placeholder.hidden = false;
    start.disabled = false;
    stopButton.disabled = true;
    message.textContent = text;
  }
  async function validSession() {
    try {
      const response = await fetch(youtubePanel.dataset.sessionUrl, {cache: 'no-store', redirect: 'error'});
      if (!response.ok) return false;
      const data = await response.json();
      return data.status === 'public' && data.video_id === youtubePanel.dataset.youtubeId;
    } catch (_) { return false; }
  }
  start.addEventListener('click', async () => {
    if (pending || player) return;
    const ownGeneration = ++generation;
    pending = true; start.disabled = true;
    message.textContent = 'Validando a sessão…';
    if (!await validSession()) {
      if (generation === ownGeneration) stop('Não foi possível validar a sessão. Atualize a página e entre novamente.');
      return;
    }
    if (generation !== ownGeneration) return;
    const videoId = youtubePanel.dataset.youtubeId;
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
      stop('Identificador de vídeo inválido.'); return;
    }
    player = document.createElement('iframe');
    player.title = 'Player oficial do YouTube — transmissão pública';
    player.referrerPolicy = 'strict-origin-when-cross-origin';
    player.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    player.allowFullscreen = true;
    player.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&playsinline=1&rel=0`;
    placeholder.hidden = true;
    stage.append(player);
    pending = false; stopButton.disabled = false;
    message.textContent = 'Player externo carregado. Use os controles do YouTube. Se a transmissão estiver indisponível, tente “Abrir no YouTube”.';
    sessionTimer = setInterval(async () => {
      if (!await validSession() && generation === ownGeneration) stop('Player encerrado: sessão ou permissão indisponível.');
    }, 15000);
  });
  stopButton.addEventListener('click', () => stop('Player encerrado. Clique em Carregar transmissão para assistir novamente.'));
  window.addEventListener('pagehide', () => stop('Player encerrado.'));
}
