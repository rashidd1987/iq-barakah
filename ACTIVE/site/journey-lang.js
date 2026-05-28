/* ============================================================
   journey-lang.js — IQ BARAKAH localization engine v3
   Читает JOURNEY_I18N (data-i18n атрибуты) и
           JOURNEY_TEXT_I18N (полный перевод текстовых узлов)
   ============================================================ */
(function () {
  'use strict';

  var STORAGE_KEY = 'iq_journey_lang';
  var DEFAULT_LANG = 'ru';
  var SUPPORTED    = ['ru', 'en', 'ar', 'tr'];
  var RTL_LANGS    = ['ar'];

  /* ── словарь data-i18n (const не попадает в window — читаем напрямую) ── */
  function getDict() {
    try { if (typeof JOURNEY_I18N !== 'undefined' && JOURNEY_I18N) return JOURNEY_I18N; }
    catch (e) {}
    return (typeof window.JOURNEY_I18N === 'object' && window.JOURNEY_I18N) ? window.JOURNEY_I18N : {};
  }

  /* ── словарь text-node переводов ── */
  function getTextDict() {
    try { if (typeof JOURNEY_TEXT_I18N !== 'undefined' && JOURNEY_TEXT_I18N) return JOURNEY_TEXT_I18N; }
    catch (e) {}
    return (typeof window.JOURNEY_TEXT_I18N === 'object' && window.JOURNEY_TEXT_I18N) ? window.JOURNEY_TEXT_I18N : {};
  }

  /* ── язык из URL имеет приоритет ── */
  function urlLangOverride() {
    try {
      var p = new URLSearchParams(window.location.search);
      var v = p.get('langcheck') || p.get('lang');
      return (v && SUPPORTED.indexOf(v) !== -1) ? v : null;
    } catch (e) { return null; }
  }

  function readLang() {
    var override = urlLangOverride();
    if (override) { try { localStorage.setItem(STORAGE_KEY, override); } catch (e) {} return override; }
    var stored = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    return (SUPPORTED.indexOf(stored) !== -1) ? stored : DEFAULT_LANG;
  }

  function translate(key, lang, dict) {
    var L = dict[lang];
    if (L && Object.prototype.hasOwnProperty.call(L, key)) return L[key];
    var F = dict[DEFAULT_LANG];
    if (F && Object.prototype.hasOwnProperty.call(F, key)) return F[key];
    return null;
  }

  function cleanUrlParams() {
    try {
      var u = new URL(window.location.href);
      if (u.searchParams.has('langcheck') || u.searchParams.has('lang')) {
        u.searchParams.delete('langcheck'); u.searchParams.delete('lang');
        window.history.replaceState({}, '', u.pathname + u.search + u.hash);
      }
    } catch (e) {}
  }

  /* ── text-node scanning ── */
  var _textNodes = [];
  var _observerLock = false;

  function collectTextNodes() {
    _textNodes = [];
    if (!document.body || !window.NodeFilter) return;
    var skip = { SCRIPT:1, STYLE:1, NOSCRIPT:1, TEXTAREA:1, INPUT:1, SELECT:1, OPTION:1 };
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var p = node.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        if (skip[p.tagName]) return NodeFilter.FILTER_REJECT;
        if (p.closest && p.closest('script,style,[data-no-i18n],[data-i18n]'))
          return NodeFilter.FILTER_REJECT;
        var t = (node.nodeValue || '').replace(/\s+/g,' ').trim();
        return t.length > 2 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var node;
    while ((node = walker.nextNode())) {
      if (!node._iqOrig) node._iqOrig = node.nodeValue;
      _textNodes.push(node);
    }
  }

  function applyTextNodes(lang, textDict) {
    if (!textDict || lang === DEFAULT_LANG) {
      /* Restore originals when switching back to RU */
      _textNodes.forEach(function (node) {
        if (node._iqOrig && node.nodeValue !== node._iqOrig) node.nodeValue = node._iqOrig;
      });
      return;
    }
    var dict = textDict[lang] || {};
    _observerLock = true;
    _textNodes.forEach(function (node) {
      var original = node._iqOrig || node.nodeValue;
      var key = original.replace(/\s+/g,' ').trim();
      var translated = dict[key];
      if (!translated && textDict.en) translated = textDict.en[key]; /* EN fallback */
      if (!translated) return;
      var leading  = (original.match(/^\s*/) || [''])[0];
      var trailing = (original.match(/\s*$/) || [''])[0];
      var next = leading + translated + trailing;
      if (node.nodeValue !== next) node.nodeValue = next;
    });
    _observerLock = false;
  }

  /* ── главная функция применения языка ── */
  function applyLang(lang) {
    if (SUPPORTED.indexOf(lang) === -1) lang = DEFAULT_LANG;
    var dict     = getDict();
    var textDict = getTextDict();
    var isRTL    = RTL_LANGS.indexOf(lang) !== -1;
    var root     = document.documentElement;

    root.setAttribute('lang', lang);
    root.setAttribute('dir', isRTL ? 'rtl' : 'ltr');
    root.classList.toggle('lang-rtl', isRTL);
    SUPPORTED.forEach(function (l) { root.classList.toggle('lang-' + l, l === lang); });

    /* data-i18n элементы */
    var nodes = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i++) {
      var el  = nodes[i];
      var val = translate(el.getAttribute('data-i18n'), lang, dict);
      if (val !== null) el.textContent = val;
    }

    /* data-i18n-attr атрибуты: placeholder, title и т.д. */
    var attrNodes = document.querySelectorAll('[data-i18n-attr]');
    for (var j = 0; j < attrNodes.length; j++) {
      (function (node) {
        var spec = node.getAttribute('data-i18n-attr') || '';
        spec.split(',').forEach(function (pair) {
          var parts = pair.split(':');
          if (parts.length === 2) {
            var v = translate(parts[1].trim(), lang, dict);
            if (v !== null) node.setAttribute(parts[0].trim(), v);
          }
        });
      })(attrNodes[j]);
    }

    /* Кнопки-переключатели — поддержка data-lang-switch И data-lang */
    document.querySelectorAll('[data-lang-switch],[data-lang]').forEach(function (btn) {
      var btnLang = btn.getAttribute('data-lang-switch') || btn.getAttribute('data-lang');
      var isActive = btnLang === lang;
      btn.classList.toggle('is-active', isActive);
      btn.classList.toggle('active', isActive);
    });

    /* Перевод текстовых узлов */
    collectTextNodes();
    applyTextNodes(lang, textDict);

    cleanUrlParams();
    window.__iqLang = lang;
    try { document.dispatchEvent(new CustomEvent('iq:langchanged', { detail: { lang: lang } })); }
    catch (e) {}
  }

  /* ── публичный API ── */
  function setJourneyLang(lang) {
    if (SUPPORTED.indexOf(lang) === -1) return;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    applyLang(lang);
  }

  window.applyJourneyLang  = applyLang;
  window.setJourneyLang    = setJourneyLang;
  window.switchLanguage    = setJourneyLang; /* legacy alias */
  window.IQ_LANG = { read: readLang, apply: applyLang, set: setJourneyLang, supported: SUPPORTED };

  /* ── MutationObserver — подхватываем динамически добавленный контент ── */
  function startObserver(lang) {
    if (!window.MutationObserver) return;
    var timer;
    new MutationObserver(function () {
      if (_observerLock) return;
      clearTimeout(timer);
      timer = setTimeout(function () {
        var l = window.__iqLang || DEFAULT_LANG;
        if (l !== DEFAULT_LANG) { collectTextNodes(); applyTextNodes(l, getTextDict()); }
      }, 120);
    }).observe(document.body, { childList: true, subtree: true });
  }

  /* ── init ── */
  function init() {
    var lang = readLang();
    applyLang(lang);
    startObserver(lang);
    /* storage sync across tabs */
    window.addEventListener('storage', function (e) {
      if (e.key === STORAGE_KEY && e.newValue && SUPPORTED.indexOf(e.newValue) !== -1) {
        applyLang(e.newValue);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
