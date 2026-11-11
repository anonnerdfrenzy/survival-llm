// Keep the existing docs configuration as the single source of formatting rules.
module.exports = JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname, 'docs/.prettierrc'), 'utf8'));
