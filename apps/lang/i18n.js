(function () {
  const DEFAULT_LOCALE = document.documentElement.getAttribute('lang') || 'zh-CN';

  function applyTranslations(pageKey, options = {}) {
    const { locale = DEFAULT_LOCALE } = options;
    const allLocales = window.I18N_TRANSLATIONS || {};
    const pageTranslations = allLocales[locale] && allLocales[locale][pageKey];

    if (!pageTranslations) {
      if (window.console && console.warn) {
        console.warn('[i18n] Missing translations for page "' + pageKey + '" and locale "' + locale + '".');
      }
      return;
    }

    if (pageTranslations.metaTitle) {
      document.title = pageTranslations.metaTitle;
    }

    Object.keys(pageTranslations).forEach((key) => {
      if (key === 'metaTitle') {
        return;
      }
      const elements = document.querySelectorAll('[data-i18n="' + key + '"]');
      elements.forEach((element) => {
        const value = pageTranslations[key];
        if (typeof value === 'string') {
          element.textContent = value;
        }
      });
    });
  }

  window.applyTranslations = applyTranslations;
})();
