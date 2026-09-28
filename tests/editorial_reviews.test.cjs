const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const { renderEditorialReview } = require('../editorial-review-renderer.js');

const source = '# LA VITRINA\n\n## HISTORIA\n\nPrimer párrafo.\nSegunda línea.\n\n## NUESTRA OPINIÓN\n\n**Intenso** y _elegante_.\n\n- Acierto uno\n- Acierto dos';

test('editorial sections, paragraphs and safe inline format survive', () => {
  const html = renderEditorialReview(source);
  assert.match(html, /<h3>LA VITRINA<\/h3>/);
  assert.match(html, /<h4>HISTORIA<\/h4>/);
  assert.match(html, /<p>Primer párrafo\.<br>Segunda línea\.<\/p>/);
  assert.match(html, /<h4>NUESTRA OPINIÓN<\/h4>/);
  assert.match(html, /<strong>Intenso<\/strong>/);
  assert.match(html, /<ul><li>Acierto uno<\/li><li>Acierto dos<\/li><\/ul>/);
});

test('editorial renderer escapes HTML and preserves old plain text', () => {
  assert.equal(renderEditorialReview('<script>alert(1)</script>'), '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
  assert.equal(renderEditorialReview('Review antigua.'), '<p>Review antigua.</p>');
});

test('SEO wrapper uses the same renderer bytes', () => {
  const run = spawnSync(process.execPath, ['scripts/render_editorial_review.cjs'], { input: source, encoding: 'utf8' });
  assert.equal(run.status, 0);
  assert.equal(run.stdout, renderEditorialReview(source));
});

test('La Vitrina static editorial is self-contained with 285 line breaks and scores', () => {
  const registry = JSON.parse(readFileSync('published_reviews.json', 'utf8')).reviews;
  const record = registry.la_vitrina;
  const review = record.review;
  assert.equal(record.roomKey, 'la_vitrina');
  assert.equal(review.id, 'la-vitrina');
  assert.equal((review.descripcion.match(/\n/g) || []).length, 285);
  for (const heading of ['HISTORIA', 'NUESTRA OPINIÓN', 'VEREDICTO']) {
    assert.ok(review.descripcion.includes(heading));
  }
  assert.deepEqual([review.historia, review.ambientacion, review.jugabilidad, review.gamemaster], [10, 10, 9, 10]);
  assert.equal(review.valoracion, 9.8);
  const html = renderEditorialReview(review.descripcion);
  assert.match(html, /<h[34]>.*HISTORIA.*<\/h[34]>/);
  assert.match(html, /<h[34]>.*NUESTRA OPINIÓN.*<\/h[34]>/);
  assert.ok((html.match(/<p>/g) || []).length > 20);
});
