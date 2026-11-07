// The interface in other languages. app.js and the server write English; this translates what reaches the page
// (text, and the title, placeholder and aria-label attributes) as it appears, and keeps the English so switching
// language is instant. It never touches what the person or the AI wrote, or library text: answers, questions,
// reasoning, articles, search snippets, source and file names (SKIP below).
//
// Each language is a pack, app/static/lang-<code>.js (see lang-nl.js), loaded after this file:
//   window.i18n.register("xx", ({ tr, NUM }) => ({ exact: {English: "...", ...}, patterns: [[/regex/, "$1 ..."], ...] }));
// exact: whole strings, matched ignoring line breaks and indentation. patterns: for text with numbers or names in it;
// a replacement is a string ($1...) or a function of the match's groups that returns the text, or null for "not
// this one". tr(s) translates a piece inside a pattern (null when unknown); NUM matches a number as the browser
// writes it. Text no rule knows stays English, and the fallbacks below handle "a · b" and "Label: rest" by parts.
// To add a language: write its pack, then add it to core.LANGUAGES (its name in the Language menu), core.LANGUAGE_PROMPTS
// (how the AI should answer) and core.SOURCES_WORDS (its word for "Sources"). The server finds the pack by its name.
(() => {
  "use strict";

  const SKIP = "script, style, textarea, code, pre, .answer, .bubble, .r-thought, .reasoning-body .linklike, "
    + "#reader-body section, .doc-head h2, .src-line:not(.license), .r-title, .r-snip, .r-src, .src, .f-title, .chip, "
    + ".notes, [data-no-tr]";
  const ATTRS = ["title", "placeholder", "aria-label"];

  const NUM = "([\\d.,\\u00a0\\u202f ]+)";
  const packs = {};  // language code -> {exact, patterns}
  let lang = "en";   // the language shown now
  const wanted = document.documentElement.lang;  // the page's language, set by the server: start in it once its pack is in

  function tr(text) {
    const pack = packs[lang];
    if (text == null || !pack) return null;
    const { exact, patterns } = pack;
    const s = String(text).replace(/\s+/g, " ").trim();
    if (!s) return null;
    if (Object.prototype.hasOwnProperty.call(exact, s)) return exact[s];
    for (const [re, to] of patterns) {
      const m = s.match(re);
      if (!m) continue;
      const out = typeof to === "function" ? to(...m) : s.replace(re, to);
      if (out != null) return out;
    }
    // "· Ready." (a piece between two bold names), "Ready to use without internet ·"
    let m = s.match(/^·\s+(.+)$/);
    if (m) { const t = tr(m[1]); return t ? `· ${t}` : null; }
    m = s.match(/^(.+?)\s+·$/);
    if (m) { const t = tr(m[1]); return t ? `${t} ·` : null; }
    // "6 GB download · needs 12 GB of memory (RAM)": each piece on its own
    if (s.includes(" · ")) {
      const parts = s.split(" · "), out = parts.map((p) => tr(p));
      if (out.some((t) => t)) return out.map((t, i) => t || parts[i]).join(" · ");
    }
    // "Read: <title>", "<file name>: <message>"
    m = s.match(/^([^:]{1,40}):\s+(.+)$/s);
    if (m) {
      if (Object.prototype.hasOwnProperty.call(exact, m[1])) return `${exact[m[1]]}: ${m[2]}`;
      const rest = tr(m[2]);
      if (rest) return `${m[1]}: ${rest}`;
    }
    return null;
  }

  // ---------- applying it to the page ----------
  const englishText = new WeakMap();   // text node -> its English
  const written = new WeakMap();       // text node -> the translation this put there
  const englishAttrs = new WeakMap();  // element -> {attribute: {english, shown}}

  function skipped(el) {
    if (!el) return true;
    if (el.closest(".official, .license")) return false;
    return !!el.closest(SKIP);
  }

  function doText(node) {
    if (lang === "en" || skipped(node.parentElement)) return;
    if (written.get(node) === node.data) return;  // ours already
    const out = tr(node.data);
    if (out == null) return;
    const lead = /^\s/.test(node.data) ? " " : "", trail = /\s$/.test(node.data) ? " " : "";
    englishText.set(node, node.data);
    const shown = lead + out + trail;
    written.set(node, shown);
    node.data = shown;
  }

  function doAttrs(el) {
    if (lang === "en" || el.closest("[data-no-tr]")) return;
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (!v) continue;
      const kept = englishAttrs.get(el) || {};
      if (kept[a] && kept[a].shown === v) continue;
      const out = tr(v);
      if (out == null) continue;
      kept[a] = { english: v, shown: out };
      englishAttrs.set(el, kept);
      el.setAttribute(a, out);
    }
  }

  function walk(root) {
    if (root.nodeType === Node.TEXT_NODE) { doText(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    if (skipped(root) && !root.querySelector(".official, .license")) return;  // an answer streaming in, say
    doAttrs(root);
    const it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = it.nextNode(); n; n = it.nextNode()) {
      if (n.nodeType === Node.TEXT_NODE) doText(n); else doAttrs(n);
    }
  }

  function restoreEnglish(root) {
    const it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = it.nextNode(); n; n = it.nextNode()) {
      if (n.nodeType === Node.TEXT_NODE) {
        if (englishText.has(n) && written.get(n) === n.data) n.data = englishText.get(n);
        englishText.delete(n); written.delete(n);
      } else {
        const kept = englishAttrs.get(n);
        if (!kept) continue;
        for (const [a, v] of Object.entries(kept)) if (n.getAttribute(a) === v.shown) n.setAttribute(a, v.english);
        englishAttrs.delete(n);
      }
    }
  }

  const observer = new MutationObserver((records) => {
    if (lang === "en") return;
    for (const r of records) {
      if (r.type === "characterData") doText(r.target);
      else if (r.type === "attributes") doAttrs(r.target);
      else for (const n of r.addedNodes) walk(n);
    }
  });

  function set(next) {
    next = packs[next] ? next : "en";
    if (next === lang) return;
    if (lang !== "en") restoreEnglish(document.body);  // from one translation to another goes through English
    lang = next;
    document.documentElement.lang = next;
    if (next !== "en") walk(document.body);
  }

  // The browser's own question box (folder picker without the app window) gets its question translated too.
  const ownPrompt = window.prompt.bind(window);
  window.prompt = (message, value) => ownPrompt(tr(message) || message, value);

  window.i18n = {
    get lang() { return lang; },
    get languages() { return ["en", ...Object.keys(packs)]; },
    t: (s) => tr(s) || s,
    set,
    register(code, make) {
      packs[code] = make({ tr, NUM });
      if (code === wanted && document.body) set(code);  // the page's own language: show it as soon as it's in
    },
  };
  document.documentElement.lang = "en";  // until its pack registers
  const watch = () => observer.observe(document.body, { subtree: true, childList: true, characterData: true,
    attributes: true, attributeFilter: ATTRS });
  if (document.body) watch(); else document.addEventListener("DOMContentLoaded", watch);
})();
