// Read-only, aggregate audit. Never sends data to Firebase or prints user identities.
// node scripts/audit_room_states.cjs private/firebase_backups/<snapshot>.json
const fs = require('node:fs');
const state = require('../room-state.js');
const aliasConfig = require('../room_aliases.json');
const aliases = { ...aliasConfig.aliases };
for (const [target, meta] of Object.entries(aliasConfig.rooms || {})) {
  aliases[state.slug(target)] = state.slug(target);
  for (const name of meta.aliases || []) aliases[state.slug(name)] = state.slug(target);
}
if (!process.argv[2]) throw new Error('Indica una copia local de /users.');
const users = JSON.parse(fs.readFileSync(process.argv[2], 'utf8').replace(/^\uFEFF/, ''));
const report = { accounts: 0, accountsWithDuplicates: 0, duplicateIdentities: 0, conflictingIdentities: 0, roomsWithConflicts: {} };
for (const user of Object.values(users)) {
  if (!user || typeof user !== 'object') continue;
  report.accounts++;
  const raw = user.roomStates || {};
  const normalized = state.normalize(raw, aliases, true);
  let affected = false;
  for (const [key, origins] of Object.entries(normalized.origins)) {
    if (origins.length < 2) continue;
    affected = true;
    report.duplicateIdentities++;
    const records = origins.map(origin => raw[origin]);
    if (records.some(record => record.done) && records.some(record => record.pending)) {
      report.conflictingIdentities++;
      report.roomsWithConflicts[key] = (report.roomsWithConflicts[key] || 0) + 1;
    }
  }
  if (affected) report.accountsWithDuplicates++;
}
console.log(JSON.stringify(report, null, 2));
