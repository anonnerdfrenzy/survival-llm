const REPO = 'https://github.com/anonnerdfrenzy/survival-llm';
const LINKS = {
  mac: REPO + '/releases/latest/download/Survival-LLM-mac.zip',
  windows: REPO + '/releases/latest/download/Survival-LLM-windows.zip',
  repo: REPO,
};
const set = (id, url) => {
  const el = document.getElementById(id);
  if (el && url) el.href = url;
};
set('dl-mac', LINKS.mac);
set('dl-mac-2', LINKS.mac);
set('dl-win', LINKS.windows);
set('dl-win-2', LINKS.windows);
set('tests-link', LINKS.repo + '#how-the-models-did');
set('dl-src', LINKS.repo);
set('repo-link', LINKS.repo);
set('sources-link', LINKS.repo + '/blob/main/SOURCES.md');
set('releases-link', LINKS.repo + '/releases');

// Put the download for this visitor's computer first; phones and tablets get told it's for computers.
const ua = navigator.userAgent;
const phone = /iPhone|iPad|Android/i.test(ua) || (navigator.maxTouchPoints > 1 && /Macintosh/.test(ua));
const win = /Windows/i.test(ua),
  mac = /Macintosh|Mac OS X/i.test(ua) && !phone;
const macBtn = document.getElementById('dl-mac'),
  winBtn = document.getElementById('dl-win');
if (win) {
  winBtn.parentNode.insertBefore(winBtn, macBtn);
  macBtn.classList.add('secondary');
} else if (mac) winBtn.classList.add('secondary');
if (phone)
  document.getElementById('device-note').textContent =
    'Survival LLM runs on Mac and Windows computers, not phones. Open this page on your computer to download it.';
