(() => {
  document.addEventListener('click', event => {
    const button = event.target.closest?.('.sp-visit-play');
    if (!button || button.disabled) return;
    const video = button.closest('figure')?.querySelector('.sp-visit-video');
    const src = button.dataset.videoSrc;
    if (!video || !src) return;
    button.disabled = true;
    video.src = src;
    video.load();
    Promise.resolve(video.play()).then(() => {
      button.hidden = true;
      video.focus({ preventScroll: true });
    }).catch(() => {
      button.disabled = false;
      button.textContent = '▶ Reintentar vídeo';
    });
  }, true);

  document.addEventListener('play', event => {
    if (!event.target.matches?.('.sp-visit-video')) return;
    document.querySelectorAll('.sp-visit-video').forEach(video => {
      if (video !== event.target) video.pause();
    });
  }, true);
})();
