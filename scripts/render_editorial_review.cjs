const { renderEditorialReview } = require('../editorial-review-renderer.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => { process.stdout.write(renderEditorialReview(input)); });
