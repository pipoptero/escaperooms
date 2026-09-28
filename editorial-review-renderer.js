(function (root) {
  'use strict';

  const HEADINGS = new Set([
    'HISTORIA', 'AMBIENTACIÓN', 'AMBIENTACION', 'JUGABILIDAD', 'GAME MASTER',
    'EN RESUMEN', 'NUESTRA OPINIÓN', 'NUESTRA OPINION', 'DATOS IMPORTANTES',
    'VALORACIÓN THE VAULT', 'VALORACION THE VAULT', 'VEREDICTO THE VAULT',
    'THE VAULT SCORE'
  ]);

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function inline(value) {
    return escapeHtml(value)
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/__([^_\n]+)__/g, '<u>$1</u>')
      .replace(/_([^_\n]+)_/g, '<em>$1</em>');
  }

  function renderEditorialReview(value) {
    const output = [];
    let paragraph = [];
    let list = [];
    function flushParagraph() {
      if (paragraph.length) output.push(`<p>${paragraph.map(inline).join('<br>')}</p>`);
      paragraph = [];
    }
    function flushList() {
      if (list.length) output.push(`<ul>${list.map(item => `<li>${inline(item)}</li>`).join('')}</ul>`);
      list = [];
    }
    String(value ?? '').replace(/\r\n?/g, '\n').split('\n').forEach(rawLine => {
      const line = rawLine.trim();
      if (!line) { flushParagraph(); flushList(); return; }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      const candidate = line.replace(/^[^A-Za-zÁÉÍÓÚÜÑ]+/u, '');
      if (heading || HEADINGS.has(candidate.toUpperCase())) {
        flushParagraph(); flushList();
        const tag = !heading || heading[1].length === 1 ? 'h3' : 'h4';
        output.push(`<${tag}>${inline(heading ? heading[2] : line)}</${tag}>`);
        return;
      }
      if (/^---+$/.test(line)) { flushParagraph(); flushList(); output.push('<hr>'); return; }
      const bullet = line.match(/^[-•]\s+(.+)$/);
      if (bullet) { flushParagraph(); list.push(bullet[1]); return; }
      flushList();
      paragraph.push(line);
    });
    flushParagraph(); flushList();
    return output.join('');
  }

  const api = { renderEditorialReview };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.TheVaultEditorialReview = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
