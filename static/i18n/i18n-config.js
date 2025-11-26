// i18next Configuration for iBasketCal
// Supports Hebrew (RTL) and English (LTR) with auto-detection

const I18N_CONFIG = {
    supportedLngs: ['he', 'en'],
    fallbackLng: 'he',
    detection: {
        order: ['localStorage', 'navigator'],
        lookupLocalStorage: 'ibasketcal-lang',
        caches: ['localStorage']
    },
    backend: {
        loadPath: '/static/i18n/locales/{{lng}}.json'
    },
    ns: ['translation'],
    defaultNS: 'translation',
    debug: false
};

// Initialize i18next with plugins
async function initI18next() {
    return i18next
        .use(i18nextHttpBackend)
        .use(i18nextBrowserLanguageDetector)
        .init(I18N_CONFIG);
}

// Translate a key with optional interpolation
function t(key, options) {
    return i18next.t(key, options);
}

// Get current language
function getCurrentLanguage() {
    return i18next.language || 'he';
}

// Check if current language is RTL
function isRTL() {
    return getCurrentLanguage() === 'he';
}

// Get locale for date formatting
function getLocale() {
    return getCurrentLanguage() === 'he' ? 'he-IL' : 'en-US';
}

// Update document direction and lang attributes
function updateDocumentDirection(lng) {
    const isRtl = lng === 'he';
    document.documentElement.lang = lng;
    document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
    document.body.style.direction = isRtl ? 'rtl' : 'ltr';
}

// Translate all elements with data-i18n attributes
function translatePage() {
    // Text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });

    // Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });

    // Titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        el.title = t(key);
    });

    // Update page title
    document.title = t('page.title');
}

// Change language programmatically
async function changeLanguage(lng) {
    if (!I18N_CONFIG.supportedLngs.includes(lng)) {
        console.warn(`Unsupported language: ${lng}`);
        return;
    }

    await i18next.changeLanguage(lng);
    updateDocumentDirection(lng);
    translatePage();

    // Dispatch event for app.js to re-render dynamic content
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lng } }));
}

// Toggle between Hebrew and English
function toggleLanguage() {
    const current = getCurrentLanguage();
    const next = current === 'he' ? 'en' : 'he';
    changeLanguage(next);
}
