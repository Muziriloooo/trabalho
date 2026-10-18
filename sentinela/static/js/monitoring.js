'use strict';
const grid = document.querySelector('.monitor-grid');
document.querySelectorAll('[data-layout]').forEach(button => {
  if (button.tagName !== 'BUTTON') return;
  button.addEventListener('click', () => {
    grid.dataset.layout = button.dataset.layout;
    document.querySelectorAll('button[data-layout]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  });
});
document.querySelectorAll('.monitor-tile').forEach(tile => {
  const video = tile.querySelector('video');
  const state = tile.querySelector('.playback-state');
  const start = tile.querySelector('[data-action=start]');
  const pause = tile.querySelector('[data-action=pause]');
  const time = tile.querySelector('.playback-time');
  let hls, retries = 0, retryTimer, revoked = false, stopped = true, epoch = 0;
  const stop = () => {
    epoch++;
    stopped = true;
    clearTimeout(retryTimer);
    hls?.destroy(); hls = null;
    video.pause();
    video.removeAttribute('src'); video.load();
    start.disabled = revoked;
    pause.disabled = true;
  };
  function failed() {
    if (stopped || revoked) return;
    stop();
    start.textContent = 'Reconectar';
    state.hidden = false;
    state.textContent = 'Transmissão indisponível. Verifique a conexão e o gateway.';
    if (retries < 3) {
      retries++;
      state.textContent += ` Nova tentativa ${retries}/3 em ${2 ** retries} segundos.`;
      retryTimer = setTimeout(play, 1000 * (2 ** retries));
    }
  }
  async function play() {
    if (revoked) return;
    stop();
    stopped = false;
    const ownEpoch = epoch;
    state.hidden = false;
    state.textContent = 'Carregando transmissão autorizada…';
    start.disabled = true; pause.disabled = false;
    const source = tile.dataset.source;
    if (tile.dataset.kind !== 'demo' && window.Hls?.isSupported()) {
      hls = new Hls({enableWorker: true, lowLatencyMode: false, maxBufferLength: 6,
        manifestLoadPolicy: {default: {maxTimeToFirstByteMs: 8000, maxLoadTimeMs: 12000, timeoutRetry: null, errorRetry: null}},
      });
      hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) failed(); });
      hls.loadSource(source); hls.attachMedia(video);
    } else if (tile.dataset.kind === 'demo' || video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = source;
    } else {
      stop(); state.textContent = 'Este navegador não oferece reprodução HLS compatível.';
      return;
    }
    try { await video.play(); }
    catch (error) { if (!stopped && ownEpoch === epoch && error.name !== 'AbortError') failed(); }
  }
  start.addEventListener('click', () => { retries = 0; play(); });
  pause.addEventListener('click', () => {
    stop(); start.textContent = 'Retomar'; state.hidden = false;
    state.textContent = 'Visualização interrompida; não há novas requisições de vídeo.';
  });
  tile.querySelector('[data-action=fullscreen]').addEventListener('click', async () => {
    try { await tile.requestFullscreen(); } catch (_) { state.hidden = false; state.textContent = 'Tela cheia indisponível neste navegador.'; }
  });
  video.addEventListener('playing', () => { if (!stopped) { state.hidden = true; } });
  video.addEventListener('waiting', () => { if (!stopped) { state.hidden = false; state.textContent = 'Aguardando dados de vídeo…'; } });
  video.addEventListener('error', failed);
  video.addEventListener('timeupdate', () => {
    if (tile.dataset.kind === 'demo') time.textContent = `Exemplo · posição ${Math.floor(video.currentTime)}s`;
    else if (video.seekable.length) time.textContent = `Atraso no buffer ≈ ${Math.max(0, video.seekable.end(video.seekable.length - 1) - video.currentTime).toFixed(1)}s`;
  });
  async function refreshStatus() {
    try {
      const response = await fetch(tile.dataset.statusUrl, {cache: 'no-store', redirect: 'error'});
      if ([401, 403, 404, 409].includes(response.status)) {
        revoked = true; stop(); state.hidden = false; state.textContent = 'Visualização encerrada: permissão ou disponibilidade alterada.';
        return;
      }
      if (!response.ok) throw new Error('status');
      const data = await response.json();
      if (data.status === 'disabled') { revoked = true; stop(); state.hidden = false; state.textContent = 'Câmera ou unidade desativada.'; return; }
      const labels = {online:'Disponível na última verificação', offline:'Indisponível na última verificação', unknown:'Sem verificação recente', demo:'Vídeo sintético; nenhuma conexão real'};
      tile.querySelector('.source-state').textContent = labels[data.status] || 'Estado desconhecido';
    } catch (_) {
      // Falha na validação de sessão/rede encerra também vídeos de demonstração.
      stop(); state.hidden = false; state.textContent = 'Não foi possível validar sua sessão. Atualize a página.';
    }
  }
  refreshStatus();
  const statusTimer = setInterval(refreshStatus, 15000);
  window.addEventListener('pagehide', () => { clearInterval(statusTimer); stop(); });
});
