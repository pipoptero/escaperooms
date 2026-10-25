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

  function editorialBlocks(value) {
    const blocks = [];
    let paragraph = [];
    let list = [];
    function flushParagraph() {
      if (paragraph.length) blocks.push({
        kind: 'paragraph', source: paragraph.join('\n'),
        html: `<p>${paragraph.map(inline).join('<br>')}</p>`
      });
      paragraph = [];
    }
    function flushList() {
      if (list.length) blocks.push({
        kind: 'list', source: list.map(item => item.raw).join('\n'),
        html: `<ul>${list.map(item => `<li>${inline(item.text)}</li>`).join('')}</ul>`
      });
      list = [];
    }
    String(value ?? '').replace(/\r\n?/g, '\n').split('\n').forEach(rawLine => {
      const line = rawLine.trim();
      if (!line) { flushParagraph(); flushList(); return; }
      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      const candidate = line.replace(/^[^A-Za-zÁÉÍÓÚÜÑ]+/u, '');
      if (heading || HEADINGS.has(candidate.toUpperCase())) {
        flushParagraph(); flushList();
        const tag = !heading || heading[1].length === 1 ? 'h3' : heading[1].length === 4 ? 'h5' : 'h4';
        blocks.push({kind: 'heading', source: line,
          html: `<${tag}>${inline(heading ? heading[2] : line)}</${tag}>`});
        return;
      }
      if (/^---+$/.test(line)) { flushParagraph(); flushList(); blocks.push({kind: 'divider', source: line, html: '<hr>'}); return; }
      const bullet = line.match(/^[-•]\s+(.+)$/);
      if (bullet) { flushParagraph(); list.push({raw: line, text: bullet[1]}); return; }
      flushList();
      paragraph.push(line);
    });
    flushParagraph(); flushList();
    return blocks;
  }

  function renderEditorialReview(value) {
    return editorialBlocks(value).map(block => block.html).join('');
  }

  function codePointLength(value) { return Array.from(value).length; }

  function clipAtWord(value, maxChars) {
    const chars = Array.from(value);
    if (chars.length <= maxChars) return value;
    const prefix = chars.slice(0, maxChars).join('');
    const sentenceBoundaries = [...prefix.matchAll(/[.!?…](?=\s|$)/gu)];
    const sentence = sentenceBoundaries[sentenceBoundaries.length - 1];
    if (sentence && sentence.index >= Math.floor(maxChars * .55))
      return prefix.slice(0, sentence.index + sentence[0].length).trimEnd();
    const word = prefix.lastIndexOf(' ');
    return (word >= Math.floor(maxChars * .55) ? prefix.slice(0, word) : prefix).trimEnd();
  }

  function excerptEditorialReview(value, maxChars = 720) {
    const source = String(value ?? '').replace(/\r\n?/g, '\n').trim();
    const limit = Math.max(1, Math.floor(Number(maxChars) || 720));
    if (codePointLength(source) <= limit) return {text: source, truncated: false};
    const blocks = editorialBlocks(source);
    const selected = [];
    let used = 0;
    let clipped = false;
    for (const block of blocks) {
      const separator = selected.length ? 2 : 0;
      const available = limit - used - separator;
      if (available <= 0) break;
      if (codePointLength(block.source) <= available) {
        selected.push(block.source);
        used += separator + codePointLength(block.source);
        continue;
      }
      // Prefer whole blocks. A very long first block may use a word/sentence boundary.
      if (!selected.length || used < Math.floor(limit * .55)) {
        let piece = '';
        if (block.kind === 'list') {
          for (const line of block.source.split('\n')) {
            const next = piece ? `${piece}\n${line}` : line;
            if (codePointLength(next) > available) break;
            piece = next;
          }
        }
        piece ||= clipAtWord(block.source, available);
        if (piece) selected.push(piece);
        clipped = true;
      }
      break;
    }
    return {text: selected.join('\n\n'), truncated: clipped || selected.length < blocks.length};
  }

  const api = { renderEditorialReview, excerptEditorialReview };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.TheVaultEditorialReview = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
