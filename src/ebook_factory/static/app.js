(function () {
  'use strict';

  var POLL_INTERVAL_ACTIVE = 1500;
  var POLL_INTERVAL_IDLE = 6000;
  var TICK_INTERVAL = 1000;
  var RELATIVE_REFRESH_TICKS = 15;
  var MAX_TOASTS = 4;
  var THEME_STORAGE_KEY = 'ebook-factory-theme';
  var PREFS_STORAGE_KEY = 'ebook-factory-prefs';

  var state = {
    projects: [],
    selectedId: null,
    selectedProject: null,
    providers: [],
    events: [],
    stats: null,
    artifactGroups: [],
    metrics: null,
    readability: null,
    readabilityLoaded: false,
    pollTimer: null,
    pollInterval: POLL_INTERVAL_ACTIVE,
    tickTimer: null,
    tickCount: 0,
    statusFilter: 'all',
    searchQuery: '',
    sortMode: 'recent',
    fileFilter: '',
    fileSort: 'path',
    eventLevelFilter: 'all',
    eventQuery: '',
    activeTab: 'workflow',
    wizardStep: 0,
    paletteIndex: 0,
    palettePreviousFocus: null,
    projectDrawerOpen: false,
    expandedStages: {},
    confirmHandler: null,
    settingsDirty: false,
    settingsSnapshot: null,
    previewWrap: true,
    previewText: '',
    connection: 'online',
    failureStreak: 0,
    lastSyncAt: null,
    actionInFlight: false,
    lastStatus: null,
  };

  var el = {
    projectList: document.getElementById('project-list'),
    projectRail: document.getElementById('sidebar-nav'),
    projectDrawerBackdrop: document.getElementById('project-drawer-backdrop'),
    projectCount: document.getElementById('project-count'),
    projectSearch: document.getElementById('project-search'),
    projectSort: document.getElementById('project-sort'),
    statusFilters: document.querySelectorAll('[data-status-filter]'),
    statRunning: document.getElementById('stat-running'),
    statCompleted: document.getElementById('stat-completed'),
    statFailed: document.getElementById('stat-failed'),
    emptyDetail: document.getElementById('empty-detail'),
    projectDetail: document.getElementById('project-detail'),
    detailTitle: document.getElementById('detail-title'),
    detailMode: document.getElementById('detail-mode'),
    detailMeta: document.getElementById('detail-meta'),
    detailProvider: document.getElementById('detail-provider'),
    detailStatus: document.getElementById('detail-status'),
    progressFill: document.getElementById('progress-bar-fill'),
    progressBar: document.getElementById('progress-bar'),
    progressLabel: document.getElementById('workspace-progress-label'),
    stageLabel: document.getElementById('workspace-stage-label'),
    stageStrip: document.getElementById('stage-strip'),
    workspaceTiming: document.getElementById('workspace-timing'),
    workspaceMetrics: document.getElementById('workspace-metrics'),
    qualitySummary: document.getElementById('quality-summary'),
    qualityRefresh: document.getElementById('quality-refresh'),
    qualityHero: document.getElementById('quality-hero'),
    qualityDial: document.getElementById('quality-dial'),
    qualityScore: document.getElementById('quality-score'),
    qualityGrade: document.getElementById('quality-grade'),
    qualityVerdict: document.getElementById('quality-verdict'),
    qualityDelta: document.getElementById('quality-delta'),
    qualityTrackFill: document.getElementById('quality-track-fill'),
    qualityConfig: document.getElementById('quality-config'),
    qualityMetrics: document.getElementById('quality-metrics'),
    qualityFindings: document.getElementById('quality-findings'),
    qualityFindingsHeading: document.getElementById('quality-findings-heading'),
    qualityChapters: document.getElementById('quality-chapters'),
    qualityChaptersHeading: document.getElementById('quality-chapters-heading'),
    workspacePrimaryAction: document.getElementById('workspace-primary-action'),
    mobilePrimaryAction: document.getElementById('mobile-primary-action'),
    projectMenuButton: document.getElementById('project-menu-button'),
    projectMenu: document.getElementById('project-menu'),
    errorBanner: document.getElementById('error-banner'),
    completionSummary: document.getElementById('completion-summary'),
    stageTimeline: document.getElementById('stage-timeline'),
    eventsLog: document.getElementById('events-log'),
    eventLevelFilter: document.getElementById('event-level-filter'),
    eventSearch: document.getElementById('event-search'),
    eventsSummary: document.getElementById('events-summary'),
    eventsCopy: document.getElementById('events-copy'),
    eventsDownload: document.getElementById('events-download'),
    workspaceFiles: document.getElementById('workspace-files'),
    fileFilter: document.getElementById('file-filter'),
    fileSort: document.getElementById('file-sort'),
    filesSummary: document.getElementById('files-summary'),
    filesRefresh: document.getElementById('files-refresh'),
    inspectorPanel: document.getElementById('inspector-panel'),
    inspectorToggle: document.getElementById('inspector-sheet-toggle'),
    inspectorProviderStatus: document.getElementById('inspector-provider-status'),
    inspectorOutputs: document.getElementById('inspector-outputs'),
    inspectorSources: document.getElementById('inspector-sources'),
    inspectorActivity: document.getElementById('inspector-activity'),
    inspectorDownloadLink: document.getElementById('inspector-download-link'),
    inspectorSourceFiles: document.getElementById('inspector-source-files'),
    newProjectButton: document.getElementById('new-project-button'),
    railNewProjectButton: document.getElementById('rail-new-project-button'),
    emptyNewProjectButton: document.getElementById('empty-new-project-button'),
    newProjectDialog: document.getElementById('new-project-dialog'),
    newProjectForm: document.getElementById('new-project-form'),
    cancelNewProject: document.getElementById('cancel-new-project'),
    formError: document.getElementById('form-error'),
    sourceFilesInput: document.getElementById('field-source-files'),
    fieldProvider: document.getElementById('field-provider'),
    fieldChapterTitles: document.getElementById('field-chapter-titles'),
    fieldWritingStyle: document.getElementById('field-writing-style'),
    fieldHumanizeLevel: document.getElementById('field-humanize-level'),
    fieldAutostart: document.getElementById('field-autostart'),
    modeSummary: document.getElementById('mode-summary'),
    wizardProgress: document.getElementById('wizard-progress'),
    backToList: document.getElementById('back-to-list'),
    bottomNavButtons: document.querySelectorAll('.bottom-nav-item'),
    bottomInspectorButton: document.querySelector('[data-nav="inspector"]'),
    tabButtons: document.querySelectorAll('[role="tab"][data-tab]'),
    tabPanels: document.querySelectorAll('[role="tabpanel"]'),
    composer: document.getElementById('command-composer'),
    composerCommands: document.querySelectorAll('[data-command]'),
    paletteOpenButton: document.getElementById('palette-open-button'),
    commandPalette: document.getElementById('command-palette'),
    paletteInput: document.getElementById('command-palette-input'),
    paletteList: document.getElementById('command-palette-list'),
    wizardSteps: document.querySelectorAll('.wizard-step'),
    wizardStatus: document.getElementById('wizard-status'),
    wizardBack: document.getElementById('wizard-back'),
    wizardNext: document.getElementById('wizard-next'),
    wizardReview: document.getElementById('wizard-review'),
    submitNewProject: document.getElementById('submit-new-project'),
    presetButtons: document.querySelectorAll('[data-preset]'),
    fieldMode: document.getElementById('field-mode'),
    settingsForm: document.getElementById('settings-form'),
    settingsError: document.getElementById('settings-error'),
    settingsSave: document.getElementById('settings-save'),
    settingsReset: document.getElementById('settings-reset'),
    settingsDirtyBadge: document.getElementById('settings-dirty'),
    settingsHelp: document.getElementById('settings-help'),
    themeToggle: document.getElementById('theme-toggle'),
    shortcutsButton: document.getElementById('shortcuts-button'),
    shortcutsDialog: document.getElementById('shortcuts-dialog'),
    shortcutsClose: document.getElementById('shortcuts-close'),
    connectionStatus: document.getElementById('connection-status'),
    connectionStatusText: document.getElementById('connection-status-text'),
    previewDialog: document.getElementById('artifact-preview'),
    previewTitle: document.getElementById('artifact-preview-title'),
    previewMeta: document.getElementById('artifact-preview-meta'),
    previewBody: document.getElementById('artifact-preview-body'),
    previewClose: document.getElementById('artifact-preview-close'),
    previewDownload: document.getElementById('artifact-download-link'),
    previewCopy: document.getElementById('artifact-copy'),
    previewWrap: document.getElementById('preview-wrap'),
    confirmDialog: document.getElementById('confirm-dialog'),
    confirmMessage: document.getElementById('confirm-dialog-message'),
    confirmAccept: document.getElementById('confirm-dialog-accept'),
    confirmCancel: document.getElementById('confirm-dialog-cancel'),
    toastRegion: document.getElementById('toast-region'),
  };

  var MODE_LABELS = {
    'lead-magnet': 'Lead magnet',
    guide: 'Poradnik ekspercki',
    premium: 'Książka premium',
  };

  var MODE_SUMMARIES = {
    'lead-magnet': 'Lead magnet: 5 rozdziałów, 15-30 stron.',
    guide: 'Poradnik ekspercki: 8 rozdziałów, 40-100 stron.',
    premium: 'Książka premium: 14 rozdziałów, 150-300 stron.',
  };

  var PROVIDER_LABELS = {
    demo: 'Demo',
    'codex-cli': 'Codex CLI',
    'claude-code': 'Claude Code',
  };

  var WRITING_STYLE_LABELS = {
    practical: 'Praktyczny',
    narrative: 'Narracyjny',
    expert: 'Ekspercki',
  };

  var HUMANIZE_LEVEL_LABELS = {
    off: 'Humanizacja wyłączona',
    light: 'Humanizacja lekka',
    standard: 'Humanizacja standardowa',
    strong: 'Humanizacja mocna',
  };

  var STAGE_LABELS = {
    strategy: 'Strategia',
    research: 'Research',
    outline: 'Architektura',
    draft: 'Pisanie',
    humanize: 'Humanizacja',
    edit: 'Redakcja',
    fact_check: 'Weryfikacja faktów',
    design: 'Projekt okładki',
    publish: 'Publikacja',
    marketing: 'Marketing',
    qa: 'Kontrola jakości',
    delivery: 'Paczka końcowa',
  };

  var STAGE_HINTS = {
    strategy: 'Obietnica, pozycjonowanie i zakres materiału.',
    research: 'Notatki i ślad źródeł do późniejszej weryfikacji.',
    outline: 'Struktura rozdziałów i cele każdego z nich.',
    draft: 'Pierwsza wersja treści wszystkich rozdziałów.',
    humanize: 'Usunięcie śladów maszynowego pisania i raport czytelności.',
    edit: 'Scalenie rozdziałów w spójny manuskrypt.',
    fact_check: 'Zebranie twierdzeń liczbowych do potwierdzenia.',
    design: 'Okładka w wersji PNG i SVG.',
    publish: 'Skład PDF i EPUB ze stroną tytułową oraz spisem treści.',
    marketing: 'Oferta, landing, posty i warianty reklam.',
    qa: 'Automatyczne kontrole jakości paczki.',
    delivery: 'Pakowanie wszystkiego do ZIP z sumami kontrolnymi.',
  };

  var STATUS_LABELS = {
    draft: 'Szkic',
    running: 'W trakcie',
    paused: 'Wstrzymane',
    completed: 'Gotowe',
    failed: 'Błąd',
    cancelled: 'Anulowane',
  };

  var KIND_LABELS = {
    text: 'TXT',
    markdown: 'MD',
    json: 'JSON',
    html: 'HTML',
    image: 'IMG',
    pdf: 'PDF',
    epub: 'EPUB',
    archive: 'ZIP',
    binary: 'BIN',
  };

  var COMMAND_LABELS = {
    start: 'Start',
    pause: 'Wstrzymaj',
    resume: 'Wznów',
    cancel: 'Anuluj',
    download: 'Pobierz',
  };

  var CONNECTION_LABELS = {
    online: 'Połączono',
    degraded: 'Serwer nie odpowiada',
    offline: 'Brak połączenia',
  };

  // Every palette entry declares when it makes sense, so the palette never
  // offers an action the current project cannot accept.
  var COMMANDS = [
    {
      id: 'start',
      label: 'Uruchom projekt',
      hint: 'POST /start',
      keys: '',
      when: function (project) {
        return project && ['draft', 'paused', 'failed'].indexOf(project.status) !== -1;
      },
      reason: 'Uruchomić można projekt w szkicu, wstrzymany albo zatrzymany błędem.',
    },
    {
      id: 'pause',
      label: 'Wstrzymaj po bieżącym etapie',
      hint: 'POST /pause',
      keys: '',
      when: function (project) { return project && project.status === 'running'; },
      reason: 'Wstrzymać można tylko projekt w trakcie.',
    },
    {
      id: 'resume',
      label: 'Wznów projekt',
      hint: 'POST /resume',
      keys: '',
      when: function (project) { return project && project.status === 'paused'; },
      reason: 'Wznowić można tylko wstrzymany projekt.',
    },
    {
      id: 'cancel',
      label: 'Anuluj projekt',
      hint: 'POST /cancel',
      keys: '',
      when: function (project) {
        return project && ['draft', 'running', 'paused'].indexOf(project.status) !== -1;
      },
      reason: 'Anulować można projekt w szkicu, w trakcie lub wstrzymany.',
    },
    {
      id: 'download',
      label: 'Pobierz paczkę ZIP',
      hint: 'GET /download',
      keys: '',
      when: function (project) { return project && project.status === 'completed'; },
      reason: 'Paczka powstaje na ostatnim etapie produkcji.',
    },
    {
      id: 'retry',
      label: 'Ponów od pierwszego błędu',
      hint: 'POST /retry',
      keys: '',
      when: function (project) {
        return project && ['failed', 'cancelled', 'paused'].indexOf(project.status) !== -1;
      },
      reason: 'Ponowić można tylko zatrzymany projekt.',
    },
    {
      id: 'duplicate',
      label: 'Duplikuj projekt',
      hint: 'POST /duplicate',
      keys: '',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    {
      id: 'delete',
      label: 'Usuń projekt',
      hint: 'DELETE /api/projects',
      keys: '',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    { id: 'new', label: 'Nowy ebook', hint: 'Kreator projektu', keys: 'N', when: function () { return true; } },
    {
      id: 'files',
      label: 'Pokaż pliki projektu',
      hint: 'Zakładka Pliki',
      keys: '2',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    {
      id: 'quality',
      label: 'Pokaż ocenę tekstu',
      hint: 'Zakładka Tekst',
      keys: '3',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    {
      id: 'settings',
      label: 'Edytuj ustawienia',
      hint: 'PATCH /api/projects',
      keys: '5',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    {
      id: 'refresh',
      label: 'Odśwież dane projektu',
      hint: 'Ponowne pobranie stanu',
      keys: 'R',
      when: function (project) { return Boolean(project); },
      reason: 'Najpierw wybierz projekt.',
    },
    { id: 'theme', label: 'Przełącz motyw', hint: 'Jasny / ciemny', keys: '', when: function () { return true; } },
    { id: 'shortcuts', label: 'Pokaż skróty klawiszowe', hint: 'Podręczny spis', keys: '?', when: function () { return true; } },
  ];

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value === null || value === undefined ? '' : String(value);
    return div.innerHTML;
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return '—';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' kB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function formatNumber(value) {
    if (value === null || value === undefined) return '—';
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function formatSeconds(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) return '';
    var rounded = Math.max(0, Math.round(seconds));
    if (rounded < 60) return rounded + ' s';
    var minutes = Math.floor(rounded / 60);
    if (minutes < 60) return minutes + ' min ' + (rounded % 60) + ' s';
    return Math.floor(minutes / 60) + ' godz. ' + (minutes % 60) + ' min';
  }

  function formatDuration(startedAt, finishedAt) {
    if (!startedAt) return '';
    var start = Date.parse(startedAt);
    var end = finishedAt ? Date.parse(finishedAt) : Date.now();
    if (isNaN(start) || isNaN(end) || end < start) return '';
    return formatSeconds((end - start) / 1000);
  }

  function formatRelative(isoString) {
    var parsed = Date.parse(isoString);
    if (isNaN(parsed)) return '';
    var diff = Math.round((Date.now() - parsed) / 1000);
    if (diff < 60) return 'przed chwilą';
    if (diff < 3600) return Math.floor(diff / 60) + ' min temu';
    if (diff < 86400) return Math.floor(diff / 3600) + ' godz. temu';
    return Math.floor(diff / 86400) + ' dni temu';
  }

  function formatAbsolute(isoString) {
    var parsed = Date.parse(isoString);
    if (isNaN(parsed)) return '';
    var date = new Date(parsed);
    function pad(value) { return String(value).padStart(2, '0'); }
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) +
      ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes()) + ':' + pad(date.getSeconds());
  }

  // ------------------------------------------------------------ preferences

  function readPrefs() {
    try {
      return JSON.parse(window.localStorage.getItem(PREFS_STORAGE_KEY) || '{}') || {};
    } catch (err) {
      return {};
    }
  }

  function writePrefs(patch) {
    var prefs = readPrefs();
    Object.keys(patch).forEach(function (key) { prefs[key] = patch[key]; });
    try {
      window.localStorage.setItem(PREFS_STORAGE_KEY, JSON.stringify(prefs));
    } catch (err) {
      /* storage may be unavailable in private mode; prefs stay in memory */
    }
  }

  function initPrefs() {
    var prefs = readPrefs();
    if (prefs.sortMode) {
      state.sortMode = prefs.sortMode;
      el.projectSort.value = prefs.sortMode;
    }
    if (prefs.statusFilter) {
      state.statusFilter = prefs.statusFilter;
      el.statusFilters.forEach(function (button) {
        button.classList.toggle('is-active', button.dataset.statusFilter === prefs.statusFilter);
      });
    }
    if (prefs.fileSort) {
      state.fileSort = prefs.fileSort;
      el.fileSort.value = prefs.fileSort;
    }
    if (typeof prefs.previewWrap === 'boolean') {
      state.previewWrap = prefs.previewWrap;
      el.previewWrap.checked = prefs.previewWrap;
    }
  }

  // ------------------------------------------------------------- networking

  function setConnection(nextState) {
    if (state.connection !== nextState) {
      state.connection = nextState;
      el.connectionStatus.dataset.state = nextState;
      el.connectionStatusText.textContent = CONNECTION_LABELS[nextState] || nextState;
    }
    updateConnectionTitle();
  }

  function updateConnectionTitle() {
    var synced = state.lastSyncAt ? 'ostatnia synchronizacja: ' + formatRelative(state.lastSyncAt) : 'brak synchronizacji';
    el.connectionStatus.title = (CONNECTION_LABELS[state.connection] || state.connection) + ' · ' + synced;
  }

  async function apiFetch(path, options) {
    var response;
    try {
      response = await fetch(path, options);
    } catch (networkError) {
      state.failureStreak += 1;
      setConnection(window.navigator.onLine === false ? 'offline' : 'degraded');
      var wrapped = new Error('brak odpowiedzi serwera');
      wrapped.offline = true;
      throw wrapped;
    }
    state.failureStreak = 0;
    state.lastSyncAt = new Date().toISOString();
    setConnection('online');
    if (!response.ok) {
      var detail = response.statusText;
      try {
        var body = await response.json();
        if (body && body.detail) detail = body.detail;
      } catch (err) {
        /* response had no JSON body; keep statusText */
      }
      var error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return response;
  }

  async function copyText(value) {
    try {
      if (window.navigator.clipboard && window.navigator.clipboard.writeText) {
        await window.navigator.clipboard.writeText(value);
        return true;
      }
    } catch (err) {
      /* fall through to the textarea fallback below */
    }
    try {
      var area = document.createElement('textarea');
      area.value = value;
      area.setAttribute('readonly', 'readonly');
      area.className = 'sr-only';
      document.body.appendChild(area);
      area.select();
      var copied = document.execCommand('copy');
      area.remove();
      return copied;
    } catch (err) {
      return false;
    }
  }

  function downloadTextFile(filename, content) {
    var blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  // ------------------------------------------------------------------ toasts

  function showToast(message, tone) {
    var existing = Array.from(el.toastRegion.children).find(function (node) {
      return node.dataset.message === message;
    });
    if (existing) {
      var counter = existing.querySelector('.toast-count');
      var repeats = Number(existing.dataset.repeats || '1') + 1;
      existing.dataset.repeats = String(repeats);
      if (counter) counter.textContent = '×' + repeats;
      else existing.querySelector('.toast-text').insertAdjacentHTML(
        'afterend', '<span class="toast-count">×' + repeats + '</span>');
      window.clearTimeout(Number(existing.dataset.timer));
      existing.dataset.timer = String(window.setTimeout(function () {
        existing.remove();
      }, tone === 'error' ? 9000 : 3600));
      return;
    }

    while (el.toastRegion.children.length >= MAX_TOASTS) {
      el.toastRegion.firstElementChild.remove();
    }

    var toast = document.createElement('div');
    toast.className = 'toast' + (tone ? ' toast-' + tone : '');
    toast.dataset.message = message;
    toast.dataset.repeats = '1';
    toast.innerHTML = '<span class="toast-text"></span>' +
      '<button type="button" class="toast-dismiss" aria-label="Zamknij powiadomienie">×</button>';
    toast.querySelector('.toast-text').textContent = message;
    toast.querySelector('.toast-dismiss').addEventListener('click', function () {
      window.clearTimeout(Number(toast.dataset.timer));
      toast.remove();
    });
    el.toastRegion.appendChild(toast);
    toast.dataset.timer = String(window.setTimeout(function () {
      toast.remove();
    }, tone === 'error' ? 9000 : 3600));
  }

  async function checkHealth() {
    try {
      await apiFetch('/health');
    } catch (err) {
      showToast('Kontrola stanu nie powiodła się: ' + err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- theme

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    el.themeToggle.setAttribute('aria-pressed', String(theme === 'light'));
    el.themeToggle.textContent = theme === 'light' ? 'Ciemny' : 'Jasny';
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (err) {
      /* storage may be unavailable in private mode; theme still applies */
    }
  }

  function initTheme() {
    var stored = null;
    try {
      stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    } catch (err) {
      stored = null;
    }
    applyTheme(stored === 'light' || stored === 'dark' ? stored : 'dark');
  }

  function toggleTheme() {
    applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
  }

  // --------------------------------------------------------------- layout

  function isMobileViewport() {
    return window.matchMedia('(max-width: 767px)').matches;
  }

  function openProjectDrawer() {
    state.projectDrawerOpen = true;
    el.projectRail.classList.add('is-open');
    el.projectRail.setAttribute('aria-modal', isMobileViewport() ? 'true' : 'false');
    el.projectDrawerBackdrop.hidden = !isMobileViewport();
  }

  function closeProjectDrawer() {
    state.projectDrawerOpen = false;
    el.projectRail.classList.remove('is-open');
    el.projectRail.setAttribute('aria-modal', 'false');
    el.projectDrawerBackdrop.hidden = true;
  }

  function setInspectorOpen(open) {
    el.inspectorPanel.classList.toggle('is-open', open);
    el.inspectorToggle.setAttribute('aria-expanded', String(open));
  }

  function setProjectMenuOpen(open) {
    el.projectMenu.hidden = !open;
    el.projectMenuButton.setAttribute('aria-expanded', String(open));
  }

  function updateMobileChrome() {
    var hasProject = Boolean(state.selectedId && state.selectedProject);
    document.body.classList.toggle('has-selected-project', hasProject);
    document.body.classList.toggle('has-no-selected-project', !hasProject);
    el.mobilePrimaryAction.hidden = !hasProject;
    el.inspectorPanel.hidden = !hasProject;
    if (el.bottomInspectorButton) el.bottomInspectorButton.disabled = !hasProject;
    if (!hasProject) {
      setInspectorOpen(false);
      if (isMobileViewport()) openProjectDrawer();
    } else if (isMobileViewport()) {
      closeProjectDrawer();
    }
  }

  // Polling rebuilds list markup, so keyboard focus is restored by key after
  // every re-render instead of being dropped on the floor.
  function captureFocusKey(container) {
    var active = document.activeElement;
    if (!active || !container.contains(active)) return null;
    var holder = active.closest('[data-focus-key]');
    return holder ? holder.dataset.focusKey : null;
  }

  function restoreFocusKey(container, key) {
    if (!key) return;
    var target = container.querySelector('[data-focus-key="' + key.replace(/"/g, '\\"') + '"]');
    if (target) target.focus();
  }

  function setBusy(button, busy) {
    if (!button) return;
    button.classList.toggle('is-busy', Boolean(busy));
    button.disabled = Boolean(busy);
    if (busy) button.setAttribute('aria-busy', 'true');
    else button.removeAttribute('aria-busy');
  }

  // ----------------------------------------------------------- data loads

  async function loadProjects() {
    try {
      var response = await apiFetch('/api/projects');
      state.projects = await response.json();
      renderProjectList();
    } catch (err) {
      el.projectList.innerHTML =
        '<p class="empty-state">Nie udało się wczytać projektów: ' + escapeHtml(err.message) +
        '</p><button type="button" class="btn btn-secondary" data-retry="projects">Spróbuj ponownie</button>';
    }
  }

  async function loadStats() {
    try {
      var response = await apiFetch('/api/stats');
      state.stats = await response.json();
      el.statRunning.textContent = String(state.stats.running || 0);
      el.statCompleted.textContent = String(state.stats.completed || 0);
      el.statFailed.textContent = String(state.stats.failed || 0);
    } catch (err) {
      /* stats are decorative; the project list is the source of truth */
    }
  }

  async function loadProviders() {
    try {
      var response = await apiFetch('/api/providers');
      state.providers = await response.json();
      renderProviderOptions();
      if (state.selectedProject) renderProviderStatus(state.selectedProject);
    } catch (err) {
      state.providers = [{ name: 'demo', label: 'Demo', available: true }];
      renderProviderOptions();
      showToast('Nie udało się wczytać statusu agentów: ' + err.message, 'error');
    }
  }

  async function loadBuildInfo() {
    var slot = document.getElementById('build-info');
    if (!slot) return;
    try {
      var response = await apiFetch('/api/version');
      var info = await response.json();
      slot.textContent = 'Ebook Factory ' + info.version + ' — licencja ' + info.license;
    } catch (err) {
      /* the static footer text already states the license */
    }
  }

  async function loadArtifacts() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId + '/artifacts');
      var payload = await response.json();
      state.artifactGroups = payload.groups || [];
      renderFiles();
      renderInspector(state.selectedProject, state.events);
    } catch (err) {
      el.workspaceFiles.innerHTML =
        '<p class="empty-state">Nie udało się wczytać plików: ' + escapeHtml(err.message) +
        '</p><button type="button" class="btn btn-secondary" data-retry="files">Spróbuj ponownie</button>';
    }
  }

  async function loadMetrics() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId + '/metrics');
      state.metrics = await response.json();
      renderMetrics();
      // The completion card quotes the metrics, so it is re-rendered as soon
      // as real numbers arrive instead of keeping the generic fallback copy.
      if (state.selectedProject) renderCompletionSummary(state.selectedProject);
    } catch (err) {
      state.metrics = null;
      renderMetrics();
    }
  }

  async function loadReadability() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId + '/readability');
      state.readability = await response.json();
      state.readabilityLoaded = true;
    } catch (err) {
      state.readability = null;
      state.readabilityLoaded = true;
    }
    renderQuality();
  }

  function scoreTone(score) {
    if (score === null || score === undefined) return 'unknown';
    if (score <= 15) return 'good';
    if (score <= 35) return 'ok';
    if (score <= 60) return 'warn';
    return 'bad';
  }

  function renderQuality() {
    var payload = state.readability;
    var after = payload && payload.after;
    if (!after) {
      el.qualityHero.hidden = true;
      el.qualityMetrics.hidden = true;
      el.qualityFindings.innerHTML = '';
      el.qualityFindingsHeading.hidden = true;
      el.qualityChapters.innerHTML = '';
      el.qualityChaptersHeading.hidden = true;
      el.qualitySummary.textContent = state.readabilityLoaded
        ? 'Brak rozdziałów do oceny — uruchom produkcję, aby zobaczyć ślad AI.'
        : 'Wczytywanie oceny tekstu…';
      return;
    }

    var target = payload.target || 35;
    var score = after.ai_score;
    var tone = scoreTone(score);
    el.qualityHero.hidden = false;
    el.qualityDial.dataset.tone = tone;
    el.qualityDial.setAttribute('aria-label', 'Ślad AI: ' + score + ' na 100');
    el.qualityScore.textContent = score;
    el.qualityGrade.textContent = 'Ocena: ' + (after.grade || '—');
    el.qualityVerdict.textContent = score <= target
      ? 'Tekst czyta się jak pisany przez człowieka'
      : 'Tekst nadal brzmi szablonowo';
    el.qualityTrackFill.style.width = Math.max(2, Math.min(100, score)) + '%';
    el.qualityTrackFill.dataset.tone = tone;

    var before = payload.before;
    if (before && typeof before.ai_score === 'number') {
      var delta = before.ai_score - score;
      el.qualityDelta.textContent = 'Przed humanizacją ' + before.ai_score + ' → po ' + score +
        (delta > 0 ? ' (−' + delta + ' punktów)' : ' (nie było czego poprawiać)') +
        ' · cel: ' + target + ' lub mniej';
    } else {
      el.qualityDelta.textContent = 'Cel: ' + target + ' lub mniej. Ocena liczona na żywo z rozdziałów na dysku.';
    }

    var configParts = [];
    if (payload.style_label) configParts.push('Styl: ' + payload.style_label);
    if (payload.level_label) configParts.push('Humanizacja: ' + payload.level_label.toLowerCase());
    if (payload.total_changes) configParts.push(payload.total_changes + ' automatycznych poprawek');
    el.qualityConfig.textContent = configParts.join(' · ');

    el.qualitySummary.textContent = payload.source === 'humanize-stage'
      ? 'Wynik z etapu humanizacji. Pełny raport: qa/humanize-report.md.'
      : 'Ocena policzona na żywo z rozdziałów zapisanych w workspace.';

    var cards = [
      ['Średnie zdanie', after.avg_sentence_words + ' słowa'],
      ['Rytm zdań', formatScore(after.burstiness) + ' (cel 0.38+)'],
      ['Słownictwo', formatScore(after.lexical_diversity)],
      ['Długie zdania', Math.round((after.long_sentence_ratio || 0) * 100) + '%'],
      ['Zdania', formatNumber(after.sentences)],
      ['Akapity', formatNumber(after.paragraphs)],
    ];
    el.qualityMetrics.hidden = false;
    el.qualityMetrics.innerHTML = cards.map(function (card) {
      return '<div class="metric-card"><dt>' + escapeHtml(card[0]) + '</dt><dd>' +
        escapeHtml(String(card[1])) + '</dd></div>';
    }).join('');

    var findings = after.findings || [];
    el.qualityFindingsHeading.hidden = findings.length === 0;
    el.qualityFindings.innerHTML = findings.length
      ? findings.map(function (finding) {
          var amount = finding.measure || (finding.count + '×');
          var example = (finding.examples && finding.examples.length)
            ? '<p class="finding-example">' + escapeHtml(finding.examples[0]) + '</p>'
            : '';
          return '<li class="finding" data-severity="' + escapeHtml(finding.severity) + '">' +
            '<div class="finding-head"><span class="finding-label">' + escapeHtml(finding.label) +
            '</span><span class="finding-amount">' + escapeHtml(amount) + '</span></div>' +
            '<p class="finding-hint">' + escapeHtml(finding.hint) + '</p>' + example + '</li>';
        }).join('')
      : '<li class="finding" data-severity="low"><div class="finding-head">' +
        '<span class="finding-label">Brak wykrytych śladów maszynowego pisania</span></div></li>';

    var chapters = payload.chapters || [];
    el.qualityChaptersHeading.hidden = chapters.length === 0;
    el.qualityChapters.innerHTML = chapters.map(function (row) {
      var rowTone = scoreTone(row.after);
      return '<div class="chapter-score" data-tone="' + rowTone + '">' +
        '<span class="chapter-score-title">' + escapeHtml(row.title) + '</span>' +
        '<span class="chapter-score-value">' + escapeHtml(String(row.before)) + ' → ' +
        escapeHtml(String(row.after)) + '</span>' +
        '<span class="chapter-score-meta">' + escapeHtml(String(row.changes)) + ' popr.</span>' +
        '</div>';
    }).join('');
  }

  function formatScore(value) {
    if (value === null || value === undefined) return '—';
    return Number(value).toFixed(2);
  }

  function providerInfo(name) {
    return state.providers.find(function (provider) { return provider.name === name; }) || {
      name: name || 'demo',
      label: PROVIDER_LABELS[name] || name || 'Demo',
      available: name === 'demo',
    };
  }

  function renderProviderOptions() {
    if (!el.fieldProvider) return;
    var selected = el.fieldProvider.value || 'demo';
    Array.from(el.fieldProvider.options).forEach(function (option) {
      var info = providerInfo(option.value);
      option.textContent = (PROVIDER_LABELS[option.value] || info.label) +
        (info.available ? '' : ' — niedostępny lokalnie');
      option.disabled = option.value !== 'demo' && !info.available;
    });
    el.fieldProvider.value = el.fieldProvider.querySelector('option[value="' + selected + '"]:not(:disabled)')
      ? selected
      : 'demo';
  }

  function writingSetupLabel(project) {
    if (!project) return '';
    var style = WRITING_STYLE_LABELS[project.writing_style] || project.writing_style;
    var level = HUMANIZE_LEVEL_LABELS[project.humanize_level] || project.humanize_level;
    return 'Styl: ' + style + ' · ' + level;
  }

  function renderProviderStatus(project) {
    var info = providerInfo(project.provider || 'demo');
    var availability = info.available ? 'dostępny' : 'niedostępny lokalnie';
    var text = 'Agent: ' + (PROVIDER_LABELS[info.name] || info.label) + ' · ' + availability;
    el.detailProvider.textContent = text + ' · ' + writingSetupLabel(project);
    el.inspectorProviderStatus.textContent = text;
    el.inspectorProviderStatus.dataset.available = info.available ? 'true' : 'false';
  }

  // --------------------------------------------------------- project list

  function sortProjects(projects) {
    var sorted = projects.slice();
    if (state.sortMode === 'title') {
      sorted.sort(function (a, b) { return a.title.localeCompare(b.title, 'pl'); });
    } else if (state.sortMode === 'progress') {
      sorted.sort(function (a, b) { return b.progress - a.progress; });
    } else if (state.sortMode === 'created') {
      sorted.sort(function (a, b) { return String(b.created_at).localeCompare(String(a.created_at)); });
    } else {
      sorted.sort(function (a, b) { return String(b.updated_at).localeCompare(String(a.updated_at)); });
    }
    return sorted;
  }

  function filteredProjects() {
    var query = state.searchQuery.trim().toLowerCase();
    var matching = state.projects.filter(function (project) {
      var matchesStatus = state.statusFilter === 'all' || project.status === state.statusFilter;
      var haystack = [project.title, project.topic, project.status, project.mode].join(' ').toLowerCase();
      return matchesStatus && (!query || haystack.indexOf(query) !== -1);
    });
    return sortProjects(matching);
  }

  function renderProjectList() {
    var projects = filteredProjects();
    var focusKey = captureFocusKey(el.projectList);
    el.projectCount.textContent = String(projects.length);
    if (state.projects.length === 0) {
      el.projectList.innerHTML = '<p class="empty-state">Brak projektów. Utwórz pierwszy ebook.</p>';
      return;
    }
    if (projects.length === 0) {
      el.projectList.innerHTML = '<p class="empty-state">Brak projektów dla tego filtra.</p>';
      return;
    }
    el.projectList.innerHTML = '';
    projects.forEach(function (project) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'project-card' + (project.id === state.selectedId ? ' is-selected' : '');
      button.dataset.focusKey = 'project:' + project.id;
      button.setAttribute('aria-current', project.id === state.selectedId ? 'true' : 'false');
      button.innerHTML =
        '<span class="project-card-kicker">' + escapeHtml(project.slug || project.id.slice(0, 8)) + '</span>' +
        '<span class="project-card-title">' + escapeHtml(project.title) + '</span>' +
        '<span class="project-card-meta">' + escapeHtml(MODE_LABELS[project.mode] || project.mode) +
        ' · ' + project.progress + '%</span>' +
        '<span class="project-card-progress" aria-hidden="true"><span style="width:' + project.progress + '%"></span></span>' +
        '<span class="project-card-footer">' +
        '<span class="status-chip" data-status="' + project.status + '">' +
        escapeHtml(STATUS_LABELS[project.status] || project.status) + '</span>' +
        '<span class="project-card-time" data-live-relative="' + escapeHtml(project.updated_at) + '" title="' +
        escapeHtml(formatAbsolute(project.updated_at)) + '">' +
        escapeHtml(formatRelative(project.updated_at)) + '</span>' +
        '</span>';
      button.addEventListener('click', function () {
        selectProject(project.id);
      });
      el.projectList.appendChild(button);
    });
    restoreFocusKey(el.projectList, focusKey);
  }

  function moveProjectFocus(delta) {
    var cards = Array.from(el.projectList.querySelectorAll('.project-card'));
    if (!cards.length) return;
    var current = cards.indexOf(document.activeElement.closest('.project-card'));
    var next = current === -1 ? 0 : (current + delta + cards.length) % cards.length;
    cards[next].focus();
  }

  async function selectProject(projectId) {
    if (!(await confirmDiscardSettings())) return;
    state.selectedId = projectId;
    state.events = [];
    state.artifactGroups = [];
    state.metrics = null;
    state.readability = null;
    state.readabilityLoaded = false;
    state.expandedStages = {};
    state.settingsDirty = false;
    state.settingsSnapshot = null;
    state.lastStatus = null;
    el.emptyDetail.hidden = true;
    el.projectDetail.hidden = false;
    renderProjectList();
    await refreshDetail();
    await Promise.all([loadArtifacts(), loadMetrics(), loadReadability()]);
    closeProjectDrawer();
    startPolling();
  }

  async function refreshDetail() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId);
      var project = await response.json();
      announceStatusChange(project);
      state.selectedProject = project;
      renderDetail(project);
      var lastId = state.events.length ? state.events[state.events.length - 1].id : null;
      var eventsUrl = '/api/projects/' + state.selectedId + '/events' +
        (lastId ? '?after_id=' + encodeURIComponent(lastId) : '');
      var eventsResponse = await apiFetch(eventsUrl);
      var incoming = await eventsResponse.json();
      state.events = lastId ? state.events.concat(incoming) : incoming;
      renderEvents();
      renderInspector(project, state.events);
    } catch (err) {
      el.errorBanner.hidden = false;
      el.errorBanner.textContent = 'Błąd wczytywania projektu: ' + err.message;
    }
  }

  async function refreshAll() {
    await refreshDetail();
    await Promise.all([
      loadProjects(), loadStats(), loadArtifacts(), loadMetrics(), loadReadability(),
    ]);
    showToast('Dane projektu odświeżone.');
  }

  function announceStatusChange(project) {
    var previous = state.lastStatus;
    state.lastStatus = project.status;
    if (!previous || previous === project.status) return;
    if (project.status === 'completed') showToast('Projekt „' + project.title + '” jest gotowy.');
    if (project.status === 'failed') showToast('Projekt „' + project.title + '” zakończył się błędem.', 'error');
  }

  function currentStage(project) {
    var stages = project.stages || [];
    return stages.find(function (stage) { return stage.status === 'running'; }) ||
      stages.find(function (stage) { return stage.status !== 'completed'; }) ||
      stages[stages.length - 1];
  }

  function primaryCommandFor(project) {
    if (!project) return 'start';
    if (project.status === 'running') return 'pause';
    if (project.status === 'paused') return 'resume';
    if (project.status === 'failed') return 'retry';
    if (project.status === 'completed') return 'download';
    // The API refuses a plain start after a cancel, so the contextual action
    // offers the replay that the backend does accept.
    if (project.status === 'cancelled') return 'retry';
    return 'start';
  }

  function commandLabel(command) {
    if (command === 'retry') return 'Ponów';
    return COMMAND_LABELS[command] || command;
  }

  function renderDetail(project) {
    var stage = currentStage(project);
    var command = primaryCommandFor(project);
    el.detailTitle.textContent = project.title;
    el.detailMode.textContent = MODE_LABELS[project.mode] || project.mode;
    el.detailMeta.textContent = project.topic + ' · ' + (project.audience || 'odbiorca nieokreślony');
    renderProviderStatus(project);
    el.detailStatus.dataset.status = project.status;
    el.detailStatus.textContent = STATUS_LABELS[project.status] || project.status;
    el.progressFill.style.transform = 'scaleX(' + (project.progress / 100) + ')';
    el.progressBar.setAttribute('aria-valuenow', String(project.progress));
    el.progressBar.setAttribute('aria-valuetext', project.progress + '% ukończono');
    el.progressLabel.textContent = project.progress + '% ukończono';
    el.stageLabel.textContent = stage ? stageLabel(stage.name) : 'Oczekuje na start';
    el.workspacePrimaryAction.textContent = commandLabel(command);
    el.workspacePrimaryAction.dataset.command = command;
    el.mobilePrimaryAction.textContent = commandLabel(command);
    el.mobilePrimaryAction.dataset.command = command;

    el.errorBanner.hidden = !project.error;
    el.errorBanner.textContent = project.error ? 'Błąd: ' + project.error : '';

    renderStages(project.stages || []);
    renderStageStrip(project.stages || []);
    renderTiming(project);
    renderCompletionSummary(project);
    updateDocumentTitle(project);
    if (!state.settingsDirty) fillSettingsForm(project);
    updateMobileChrome();
  }

  function updateDocumentTitle(project) {
    if (project && project.status === 'running') {
      document.title = project.progress + '% · ' + project.title + ' — Ebook Factory';
    } else {
      document.title = 'Ebook Factory — workspace produkcji';
    }
  }

  function stageLabel(name) {
    return STAGE_LABELS[name] || name;
  }

  function renderStageStrip(stages) {
    if (!stages.length) {
      el.stageStrip.innerHTML = '';
      return;
    }
    el.stageStrip.innerHTML = stages.map(function (stage) {
      var mapped = mapStageStatus(stage.status);
      return '<li class="stage-strip-item" data-stage-status="' + mapped + '" title="' +
        escapeHtml(stageLabel(stage.name) + ' — ' + (STATUS_LABELS[mapped] || stage.status)) + '"></li>';
    }).join('');
  }

  // Remaining time is estimated from how long this project's own completed
  // stages actually took, so it stays honest for every mode and provider.
  function estimateRemainingSeconds(project) {
    var stages = project.stages || [];
    var durations = [];
    stages.forEach(function (stage) {
      if (stage.status !== 'completed' || !stage.started_at || !stage.finished_at) return;
      var span = Date.parse(stage.finished_at) - Date.parse(stage.started_at);
      if (!isNaN(span) && span >= 0) durations.push(span / 1000);
    });
    if (durations.length < 2) return null;
    var average = durations.reduce(function (sum, value) { return sum + value; }, 0) / durations.length;
    var pending = stages.filter(function (stage) {
      return stage.status !== 'completed' && stage.status !== 'failed';
    }).length;
    if (!pending) return null;
    var running = stages.find(function (stage) { return stage.status === 'running'; });
    var elapsed = running && running.started_at
      ? Math.max(0, (Date.now() - Date.parse(running.started_at)) / 1000)
      : 0;
    return Math.max(0, pending * average - elapsed);
  }

  function renderTiming(project) {
    var stages = project.stages || [];
    if (!stages.length) {
      el.workspaceTiming.hidden = true;
      el.workspaceTiming.textContent = '';
      return;
    }
    var done = stages.filter(function (stage) { return stage.status === 'completed'; }).length;
    var parts = ['Etap ' + Math.min(done + (project.status === 'running' ? 1 : 0), stages.length) +
      ' z ' + stages.length];
    var running = stages.find(function (stage) { return stage.status === 'running'; });
    if (running && running.started_at) {
      parts.push('bieżący etap: ' + formatDuration(running.started_at, null));
    }
    if (project.status === 'running') {
      var eta = estimateRemainingSeconds(project);
      if (eta !== null) parts.push('pozostało ok. ' + formatSeconds(eta));
    }
    el.workspaceTiming.hidden = false;
    el.workspaceTiming.textContent = parts.join(' · ');
  }

  function renderMetrics() {
    var metrics = state.metrics;
    if (!metrics || !metrics.chapters) {
      el.workspaceMetrics.hidden = true;
      el.workspaceMetrics.innerHTML = '';
      return;
    }
    var cards = [
      ['Rozdziały', formatNumber(metrics.chapters)],
      ['Słowa', formatNumber(metrics.words)],
      ['Strony (szac.)', formatNumber(metrics.estimated_pages)],
      ['Czas czytania', metrics.reading_minutes + ' min'],
      ['Pliki', formatNumber(metrics.artifacts)],
      ['Rozmiar', formatBytes(metrics.total_bytes)],
    ];
    if (typeof metrics.ai_score === 'number') {
      cards.splice(4, 0, ['Ślad AI', metrics.ai_score + '/100']);
    }
    el.workspaceMetrics.hidden = false;
    el.workspaceMetrics.innerHTML = cards.map(function (card) {
      return '<div class="metric-card"><dt>' + escapeHtml(card[0]) + '</dt><dd>' +
        escapeHtml(card[1]) + '</dd></div>';
    }).join('');
  }

  function renderCompletionSummary(project) {
    if (project.status !== 'completed') {
      el.completionSummary.hidden = true;
      el.completionSummary.innerHTML = '';
      return;
    }
    var metrics = state.metrics;
    var summary = metrics && metrics.chapters
      ? metrics.chapters + ' rozdziałów · ' + formatNumber(metrics.words) + ' słów · ok. ' +
        metrics.estimated_pages + ' stron'
      : 'Pakiet ZIP zawiera PDF, EPUB, okładkę, materiały marketingowe i raport jakości.';
    if (metrics && typeof metrics.ai_score === 'number') {
      summary += ' · ślad AI ' + metrics.ai_score + '/100' +
        (metrics.readability_grade ? ' (' + metrics.readability_grade + ')' : '');
    }
    el.completionSummary.hidden = false;
    el.completionSummary.innerHTML =
      '<h2>Projekt gotowy do pobrania</h2>' +
      '<p>' + escapeHtml(summary) + '</p>' +
      '<a class="btn btn-primary" href="/api/projects/' + encodeURIComponent(project.id) + '/download">Pobierz paczkę ZIP</a>';
  }

  function mapStageStatus(status) {
    if (status === 'completed') return 'completed';
    if (status === 'running') return 'running';
    if (status === 'failed') return 'failed';
    if (status === 'paused') return 'paused';
    return 'draft';
  }

  function renderStages(stages) {
    if (stages.length === 0) {
      el.stageTimeline.innerHTML = '<li class="empty-state">Etapy procesu pojawią się tutaj.</li>';
      return;
    }
    var focusKey = captureFocusKey(el.stageTimeline);
    el.stageTimeline.innerHTML = '';
    stages.forEach(function (stage, index) {
      var item = document.createElement('li');
      var mapped = mapStageStatus(stage.status);
      var expanded = Boolean(state.expandedStages[stage.name]);
      item.className = 'stage-item' + (expanded ? ' is-expanded' : '');
      item.dataset.stageStatus = mapped;
      var duration = formatDuration(stage.started_at, stage.finished_at);
      var artifacts = stage.artifact_paths || [];

      var head = document.createElement('button');
      head.type = 'button';
      head.className = 'stage-head';
      head.dataset.focusKey = 'stage:' + stage.name;
      head.setAttribute('aria-expanded', String(expanded));
      head.innerHTML =
        '<span class="stage-index">' + String(index + 1).padStart(2, '0') + '</span>' +
        '<span class="stage-name">' + escapeHtml(stageLabel(stage.name)) + '</span>' +
        (artifacts.length
          ? '<span class="stage-artifact-count" title="Artefakty etapu">' + artifacts.length + '</span>'
          : '') +
        '<span class="stage-duration"' +
        (stage.status === 'running' && stage.started_at
          ? ' data-live-duration="' + escapeHtml(stage.started_at) + '"'
          : '') +
        '>' + escapeHtml(duration) + '</span>' +
        '<span class="status-chip" data-status="' + mapped + '">' +
        escapeHtml(STATUS_LABELS[mapped] || stage.status) + '</span>';
      head.addEventListener('click', function () {
        state.expandedStages[stage.name] = !state.expandedStages[stage.name];
        renderStages(stages);
      });
      item.appendChild(head);

      var detail = document.createElement('div');
      detail.className = 'stage-detail';
      detail.hidden = !expanded;
      var rows = ['<p class="stage-hint">' + escapeHtml(STAGE_HINTS[stage.name] || '') + '</p>'];
      if (stage.message) {
        rows.push('<p class="stage-message">' + escapeHtml(stage.message) + '</p>');
      }
      if (stage.started_at) {
        rows.push('<p class="stage-meta">Start: ' + escapeHtml(formatAbsolute(stage.started_at)) +
          (stage.finished_at ? ' · Koniec: ' + escapeHtml(formatAbsolute(stage.finished_at)) : '') + '</p>');
      }
      if (stage.attempts) {
        rows.push('<p class="stage-meta">Próby: ' + stage.attempts + '</p>');
      }
      if (artifacts.length) {
        rows.push('<ul class="stage-artifacts">' + artifacts.map(function (path) {
          return '<li><button type="button" class="link-button" data-artifact="' +
            escapeHtml(path) + '">' + escapeHtml(path) + '</button></li>';
        }).join('') + '</ul>');
      }
      detail.innerHTML = rows.join('');
      item.appendChild(detail);
      el.stageTimeline.appendChild(item);
    });
    restoreFocusKey(el.stageTimeline, focusKey);
  }

  // ------------------------------------------------------------ file view

  function sortArtifactFiles(files) {
    var sorted = files.slice();
    if (state.fileSort === 'name') {
      sorted.sort(function (a, b) { return a.name.localeCompare(b.name, 'pl'); });
    } else if (state.fileSort === 'size') {
      sorted.sort(function (a, b) { return (b.bytes || 0) - (a.bytes || 0); });
    } else if (state.fileSort === 'modified') {
      sorted.sort(function (a, b) { return (b.modified_at || 0) - (a.modified_at || 0); });
    } else {
      sorted.sort(function (a, b) { return a.path.localeCompare(b.path, 'pl'); });
    }
    return sorted;
  }

  // The API classifies broadly (text/archive/binary); the badge shows the real
  // extension so an .epub never reads as a plain ZIP.
  function fileBadge(file) {
    var match = /\.([a-z0-9]{1,5})$/i.exec(file.name || file.path || '');
    if (match) return match[1].toUpperCase();
    return KIND_LABELS[file.kind] || String(file.kind || '').toUpperCase();
  }

  function visibleArtifactGroups() {
    var query = state.fileFilter.trim().toLowerCase();
    return state.artifactGroups.map(function (group) {
      var files = query
        ? group.files.filter(function (file) { return file.path.toLowerCase().indexOf(query) !== -1; })
        : group.files;
      return { category: group.category, label: group.label, files: sortArtifactFiles(files) };
    }).filter(function (group) { return group.files.length > 0; });
  }

  function renderFilesSummary(groups) {
    var count = groups.reduce(function (sum, group) { return sum + group.files.length; }, 0);
    var bytes = groups.reduce(function (sum, group) {
      return sum + group.files.reduce(function (inner, file) { return inner + (file.bytes || 0); }, 0);
    }, 0);
    el.filesSummary.textContent = count
      ? count + ' plików · ' + formatBytes(bytes)
      : '';
  }

  function renderFiles() {
    var groups = visibleArtifactGroups();
    renderFilesSummary(groups);
    if (groups.length === 0) {
      el.workspaceFiles.innerHTML = state.artifactGroups.length
        ? '<p class="empty-state">Żaden plik nie pasuje do filtra.</p>'
        : '<p class="empty-state">Nie ma jeszcze dostępnych plików. Uruchom produkcję.</p>';
      return;
    }
    el.workspaceFiles.innerHTML = groups.map(function (group) {
      var groupBytes = group.files.reduce(function (sum, file) { return sum + (file.bytes || 0); }, 0);
      var rows = group.files.map(function (file) {
        var actions = (file.previewable || file.kind === 'image' || file.kind === 'pdf'
          ? '<button type="button" class="link-button" data-artifact="' + escapeHtml(file.path) + '">Podgląd</button>'
          : '') +
          '<button type="button" class="link-button" data-copy-path="' + escapeHtml(file.path) +
          '" title="Skopiuj ścieżkę pliku">Kopiuj ścieżkę</button>' +
          '<a class="link-button" href="/api/projects/' + encodeURIComponent(state.selectedId) +
          '/artifacts/raw?path=' + encodeURIComponent(file.path) + '&download=true" download>Pobierz</a>';
        return '<div class="file-row" data-kind="' + escapeHtml(file.kind) + '">' +
          '<span class="file-name"><span class="file-kind">' + escapeHtml(fileBadge(file)) + '</span>' +
          escapeHtml(file.name) + '</span>' +
          '<span class="file-path">' + escapeHtml(file.path) + '</span>' +
          '<span class="file-size">' + escapeHtml(formatBytes(file.bytes)) + '</span>' +
          '<span class="file-actions">' + actions + '</span>' +
          '</div>';
      }).join('');
      return '<section class="file-group"><h3>' + escapeHtml(group.label) +
        ' <span class="file-group-count">' + group.files.length + ' · ' +
        escapeHtml(formatBytes(groupBytes)) + '</span></h3>' + rows + '</section>';
    }).join('');
  }

  function applyPreviewWrap() {
    el.previewBody.classList.toggle('is-nowrap', !state.previewWrap);
  }

  async function openArtifactPreview(path) {
    if (!state.selectedId) return;
    var rawUrl = '/api/projects/' + encodeURIComponent(state.selectedId) +
      '/artifacts/raw?path=' + encodeURIComponent(path);
    state.previewText = '';
    el.previewTitle.textContent = path;
    el.previewDownload.href = rawUrl + '&download=true';
    el.previewCopy.disabled = true;
    el.previewBody.innerHTML = '<p class="empty-state">Wczytywanie…</p>';
    applyPreviewWrap();
    if (!el.previewDialog.open) el.previewDialog.showModal();

    var lower = path.toLowerCase();
    var isImage = /\.(png|jpe?g|gif|webp)$/.test(lower);
    if (isImage) {
      el.previewMeta.textContent = 'Podgląd obrazu';
      el.previewBody.innerHTML = '<img class="preview-image" alt="Podgląd: ' +
        escapeHtml(path) + '" src="' + escapeHtml(rawUrl) + '">';
      return;
    }
    if (/\.pdf$/.test(lower)) {
      el.previewMeta.textContent = 'Podgląd PDF';
      el.previewBody.innerHTML = '<iframe class="preview-frame" title="Podgląd: ' +
        escapeHtml(path) + '" src="' + escapeHtml(rawUrl) + '"></iframe>';
      return;
    }
    try {
      var response = await apiFetch('/api/projects/' + encodeURIComponent(state.selectedId) +
        '/artifacts/preview?path=' + encodeURIComponent(path));
      var payload = await response.json();
      state.previewText = payload.text || '';
      el.previewCopy.disabled = false;
      var lines = state.previewText.split('\n').length;
      el.previewMeta.textContent = formatBytes(payload.bytes) + ' · ' + lines + ' wierszy' +
        (payload.truncated ? ' · podgląd skrócony' : '');
      el.previewBody.innerHTML = '<pre class="preview-text">' + escapeHtml(payload.text) + '</pre>';
    } catch (err) {
      el.previewMeta.textContent = '';
      el.previewBody.innerHTML = '<p class="empty-state">Nie można wyświetlić podglądu: ' +
        escapeHtml(err.message) + '. Użyj pobierania.</p>';
    }
  }

  // ---------------------------------------------------------------- events

  function visibleEvents() {
    var query = state.eventQuery.trim().toLowerCase();
    return state.events.filter(function (event) {
      var matchesLevel = state.eventLevelFilter === 'all' || event.level === state.eventLevelFilter;
      var matchesQuery = !query || String(event.message).toLowerCase().indexOf(query) !== -1;
      return matchesLevel && matchesQuery;
    });
  }

  function renderEvents() {
    var events = visibleEvents();
    var errors = state.events.filter(function (event) { return event.level === 'error'; }).length;
    el.eventsSummary.textContent = state.events.length
      ? events.length + ' z ' + state.events.length + ' zdarzeń · błędy: ' + errors
      : '';
    var scrollTop = el.eventsLog.scrollTop;
    if (events.length === 0) {
      el.eventsLog.innerHTML = '<li>Brak zdarzeń.</li>';
      return;
    }
    el.eventsLog.innerHTML = '';
    events.slice().reverse().forEach(function (event) {
      var item = document.createElement('li');
      item.dataset.level = event.level;
      item.innerHTML = '<span class="event-level">' + escapeHtml(event.level) + '</span>' +
        '<span class="event-message">' + escapeHtml(event.message) + '</span>' +
        '<span class="event-time" data-live-relative="' + escapeHtml(event.timestamp) + '" title="' +
        escapeHtml(formatAbsolute(event.timestamp)) + '">' +
        escapeHtml(formatRelative(event.timestamp)) + '</span>';
      el.eventsLog.appendChild(item);
    });
    el.eventsLog.scrollTop = scrollTop;
  }

  function eventLogText() {
    return visibleEvents().map(function (event) {
      return '[' + formatAbsolute(event.timestamp) + '] ' +
        String(event.level).toUpperCase() + ' ' + event.message;
    }).join('\n');
  }

  function outputItems(project) {
    if (!project) return [];
    var delivery = state.artifactGroups.find(function (group) { return group.category === 'delivery'; });
    if (delivery && delivery.files.length) {
      return delivery.files.slice(0, 8).map(function (file) {
        return { name: file.name, meta: formatBytes(file.bytes) };
      });
    }
    if (project.status !== 'completed') {
      return [{ name: 'Paczka ZIP', meta: 'Dostępna po ukończeniu' }];
    }
    return [{ name: 'delivery.zip', meta: 'Gotowe' }];
  }

  function sourceItems(project) {
    var sources = state.artifactGroups.find(function (group) { return group.category === 'sources'; });
    var items = [];
    items.push({
      name: 'Wklejone materiały źródłowe',
      meta: project && project.source_materials ? 'Dołączone' : 'Brak wklejonych materiałów',
    });
    if (sources && sources.files.length) {
      sources.files.forEach(function (file) {
        items.push({ name: file.name, meta: formatBytes(file.bytes) });
      });
    } else {
      items.push({ name: 'Przesłane pliki', meta: 'Brak przesłanych plików' });
    }
    return items;
  }

  function renderInspector(project, events) {
    if (!project) return;
    el.inspectorOutputs.innerHTML = outputItems(project).map(function (item) {
      return '<li><span>' + escapeHtml(item.name) + '</span><span>' + escapeHtml(item.meta) + '</span></li>';
    }).join('');
    el.inspectorSources.innerHTML = sourceItems(project).map(function (item) {
      return '<li><span>' + escapeHtml(item.name) + '</span><span>' + escapeHtml(item.meta) + '</span></li>';
    }).join('');
    var latest = events.slice().reverse().slice(0, 4);
    el.inspectorActivity.innerHTML = latest.length
      ? latest.map(function (event) {
        return '<li><span>' + escapeHtml(event.message) + '</span><span data-live-relative="' +
          escapeHtml(event.timestamp) + '">' + escapeHtml(formatRelative(event.timestamp)) + '</span></li>';
      }).join('')
      : '<li>Brak aktywności.</li>';
    if (project.status === 'completed') {
      el.inspectorDownloadLink.hidden = false;
      el.inspectorDownloadLink.href = '/api/projects/' + project.id + '/download';
    } else {
      el.inspectorDownloadLink.hidden = true;
      el.inspectorDownloadLink.href = '#';
    }
  }

  function setActiveTab(tabName) {
    state.activeTab = tabName;
    el.tabButtons.forEach(function (button) {
      var active = button.dataset.tab === tabName;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
    el.tabPanels.forEach(function (panel) {
      panel.hidden = panel.id !== 'panel-' + tabName;
    });
    if (tabName === 'files') loadArtifacts();
    if (tabName === 'quality') loadReadability();
  }

  // --------------------------------------------------------------- polling

  function desiredInterval() {
    var project = state.selectedProject;
    return project && project.status === 'running' ? POLL_INTERVAL_ACTIVE : POLL_INTERVAL_IDLE;
  }

  // A recursive timeout - not setInterval - so a slow response can never
  // stack overlapping refreshes on top of each other.
  function startPolling() {
    stopPolling();
    if (!state.selectedId || document.hidden) return;
    state.pollInterval = desiredInterval();
    state.pollTimer = window.setTimeout(pollOnce, state.pollInterval);
  }

  async function pollOnce() {
    state.pollTimer = null;
    if (!state.selectedId || document.hidden) return;
    await refreshDetail();
    await loadProjects();
    await loadStats();
    var current = state.projects.find(function (p) { return p.id === state.selectedId; });
    if (current && ['completed', 'failed', 'cancelled'].indexOf(current.status) !== -1) {
      await Promise.all([loadArtifacts(), loadMetrics(), loadReadability()]);
      renderCompletionSummary(current);
      stopPolling();
      return;
    }
    startPolling();
  }

  function stopPolling() {
    if (state.pollTimer) {
      window.clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
  }

  // Timestamps and the running-stage clock tick locally, so the workspace
  // stays live between network refreshes.
  function startTicker() {
    if (state.tickTimer) return;
    state.tickTimer = window.setInterval(function () {
      state.tickCount += 1;
      document.querySelectorAll('[data-live-duration]').forEach(function (node) {
        node.textContent = formatDuration(node.dataset.liveDuration, null);
      });
      if (state.selectedProject && state.selectedProject.status === 'running') {
        renderTiming(state.selectedProject);
      }
      if (state.tickCount % RELATIVE_REFRESH_TICKS === 0) {
        document.querySelectorAll('[data-live-relative]').forEach(function (node) {
          node.textContent = formatRelative(node.dataset.liveRelative);
        });
        updateConnectionTitle();
      }
    }, TICK_INTERVAL);
  }

  // --------------------------------------------------------------- actions

  async function runAction(path, button) {
    if (state.actionInFlight) return;
    state.actionInFlight = true;
    setBusy(button, true);
    try {
      await apiFetch(path, { method: 'POST' });
      showToast('Akcja przyjęta.');
      await refreshDetail();
      await loadProjects();
      await loadStats();
      startPolling();
    } catch (err) {
      el.errorBanner.hidden = false;
      el.errorBanner.textContent = 'Akcja nieudana: ' + err.message;
      showToast('Akcja nieudana: ' + err.message, 'error');
    } finally {
      state.actionInFlight = false;
      setBusy(button, false);
    }
  }

  function askConfirmation(message, handler) {
    el.confirmMessage.textContent = message;
    state.confirmHandler = handler;
    el.confirmDialog.showModal();
  }

  function confirmDiscardSettings() {
    if (!state.settingsDirty) return Promise.resolve(true);
    return new Promise(function (resolve) {
      askConfirmation(
        'Masz niezapisane zmiany ustawień. Odrzucić je i przejść dalej?',
        function () { state.settingsDirty = false; resolve(true); }
      );
      el.confirmDialog.addEventListener('close', function once() {
        el.confirmDialog.removeEventListener('close', once);
        if (state.settingsDirty) resolve(false);
      });
    });
  }

  async function duplicateCurrentProject() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId + '/duplicate', { method: 'POST' });
      var clone = await response.json();
      showToast('Projekt zduplikowany.');
      await loadProjects();
      await selectProject(clone.id);
    } catch (err) {
      showToast('Duplikowanie nieudane: ' + err.message, 'error');
    }
  }

  function deleteCurrentProject() {
    if (!state.selectedId || !state.selectedProject) return;
    var title = state.selectedProject.title;
    askConfirmation('Usunąć projekt „' + title + '” wraz z wszystkimi wygenerowanymi plikami? Tej operacji nie można cofnąć.', async function () {
      try {
        await apiFetch('/api/projects/' + state.selectedId, { method: 'DELETE' });
        showToast('Projekt usunięty.');
        stopPolling();
        state.selectedId = null;
        state.selectedProject = null;
        state.artifactGroups = [];
        state.metrics = null;
        state.settingsDirty = false;
        el.projectDetail.hidden = true;
        el.emptyDetail.hidden = false;
        updateDocumentTitle(null);
        updateMobileChrome();
        await loadProjects();
        await loadStats();
      } catch (err) {
        showToast('Usuwanie nieudane: ' + err.message, 'error');
      }
    });
  }

  function commandById(id) {
    return COMMANDS.find(function (command) { return command.id === id; });
  }

  function runComposerCommand(command, button) {
    if (command === 'new') {
      openNewProjectDialog();
      return;
    }
    if (command === 'theme') {
      toggleTheme();
      return;
    }
    if (command === 'shortcuts') {
      openShortcuts();
      return;
    }
    var project = state.selectedProject;
    if (!state.selectedId || !project) {
      showToast('Najpierw wybierz projekt.');
      return;
    }
    var definition = commandById(command);
    if (definition && definition.when && !definition.when(project)) {
      showToast(definition.reason || 'Ta komenda jest teraz niedostępna.');
      return;
    }
    if (command === 'download') {
      window.location.href = '/api/projects/' + state.selectedId + '/download';
      return;
    }
    if (command === 'files') {
      setActiveTab('files');
      return;
    }
    if (command === 'quality') {
      setActiveTab('quality');
      return;
    }
    if (command === 'settings') {
      setActiveTab('settings');
      return;
    }
    if (command === 'refresh') {
      refreshAll();
      return;
    }
    if (command === 'duplicate') {
      duplicateCurrentProject();
      return;
    }
    if (command === 'delete') {
      deleteCurrentProject();
      return;
    }
    if (command === 'start') runAction('/api/projects/' + state.selectedId + '/start', button);
    if (command === 'pause') runAction('/api/projects/' + state.selectedId + '/pause', button);
    if (command === 'resume') runAction('/api/projects/' + state.selectedId + '/resume', button);
    if (command === 'cancel') runAction('/api/projects/' + state.selectedId + '/cancel', button);
    if (command === 'retry') runAction('/api/projects/' + state.selectedId + '/retry', button);
  }

  // -------------------------------------------------------------- settings

  function settingsValues() {
    var form = el.settingsForm.elements;
    return {
      title: form.title.value,
      topic: form.topic.value,
      mode: form.mode.value,
      audience: form.audience.value,
      brand: form.brand.value,
      tone: form.tone.value,
      language: form.language.value,
      writing_style: form.writing_style.value,
      humanize_level: form.humanize_level.value,
      chapter_titles: form.chapter_titles.value,
    };
  }

  function fillSettingsForm(project) {
    if (!el.settingsForm) return;
    el.settingsForm.elements.title.value = project.title || '';
    el.settingsForm.elements.topic.value = project.topic || '';
    el.settingsForm.elements.mode.value = project.mode || 'guide';
    el.settingsForm.elements.audience.value = project.audience || '';
    el.settingsForm.elements.brand.value = project.brand || '';
    el.settingsForm.elements.tone.value = project.tone || '';
    el.settingsForm.elements.language.value = project.language || 'pl';
    el.settingsForm.elements.writing_style.value = project.writing_style || 'practical';
    el.settingsForm.elements.humanize_level.value = project.humanize_level || 'standard';
    el.settingsForm.elements.chapter_titles.value = (project.chapter_titles || []).join('\n');
    var locked = project.status === 'running';
    Array.from(el.settingsForm.elements).forEach(function (field) { field.disabled = locked; });
    el.settingsHelp.textContent = locked
      ? 'Projekt jest uruchomiony — wstrzymaj go, aby zmienić ustawienia.'
      : 'Ustawienia można zmieniać, gdy projekt nie jest uruchomiony. Zmiany wpływają na kolejne etapy.';
    state.settingsSnapshot = JSON.stringify(settingsValues());
    state.settingsDirty = false;
    updateSettingsDirty();
  }

  function updateSettingsDirty() {
    var dirty = state.settingsSnapshot !== null &&
      JSON.stringify(settingsValues()) !== state.settingsSnapshot;
    state.settingsDirty = dirty;
    el.settingsDirtyBadge.hidden = !dirty;
    el.settingsReset.disabled = !dirty;
    el.settingsSave.disabled = !dirty ||
      (state.selectedProject && state.selectedProject.status === 'running');
  }

  function resetSettingsForm() {
    if (!state.selectedProject) return;
    fillSettingsForm(state.selectedProject);
    el.settingsError.hidden = true;
    showToast('Przywrócono zapisane ustawienia.');
  }

  function parseChapterTitles(value) {
    return String(value || '')
      .split('\n')
      .map(function (line) { return line.trim(); })
      .filter(function (line) { return line.length > 0; });
  }

  async function saveSettings(event) {
    event.preventDefault();
    if (!state.selectedId) return;
    var form = el.settingsForm.elements;
    var payload = {
      title: form.title.value.trim(),
      topic: form.topic.value.trim(),
      mode: form.mode.value,
      audience: form.audience.value,
      brand: form.brand.value,
      tone: form.tone.value,
      language: form.language.value,
      writing_style: form.writing_style.value,
      humanize_level: form.humanize_level.value,
      chapter_titles: parseChapterTitles(form.chapter_titles.value),
    };
    setBusy(el.settingsSave, true);
    try {
      await apiFetch('/api/projects/' + state.selectedId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      el.settingsError.hidden = true;
      state.settingsDirty = false;
      state.settingsSnapshot = null;
      showToast('Ustawienia zapisane.');
      await refreshDetail();
      await loadProjects();
    } catch (err) {
      el.settingsError.hidden = false;
      el.settingsError.textContent = 'Nie udało się zapisać: ' + err.message;
    } finally {
      setBusy(el.settingsSave, false);
      updateSettingsDirty();
    }
  }

  // ---------------------------------------------------------------- wizard

  function openNewProjectDialog() {
    el.formError.hidden = true;
    el.newProjectForm.reset();
    el.fieldMode.value = 'guide';
    el.presetButtons.forEach(function (preset) {
      preset.classList.toggle('is-selected', preset.dataset.preset === 'guide');
    });
    updateModeSummary();
    state.wizardStep = 0;
    renderWizard();
    el.newProjectDialog.showModal();
    focusWizardStep();
  }

  function updateModeSummary() {
    if (!el.modeSummary) return;
    el.modeSummary.textContent = MODE_SUMMARIES[el.fieldMode.value] || '';
  }

  function renderWizard() {
    el.wizardSteps.forEach(function (step) {
      step.hidden = Number(step.dataset.step) !== state.wizardStep;
    });
    var review = state.wizardStep === 3;
    var labels = ['Cel i format', 'Odbiorca i marka', 'Źródła i ustawienia', 'Sprawdź przed wysłaniem'];
    el.wizardStatus.textContent = review ? 'Sprawdź przed wysłaniem' : 'Krok ' + (state.wizardStep + 1) + ' z 3: ' + labels[state.wizardStep];
    el.wizardBack.hidden = state.wizardStep === 0;
    el.wizardNext.hidden = review;
    el.submitNewProject.hidden = !review;
    if (el.wizardProgress) {
      Array.from(el.wizardProgress.children).forEach(function (dot, index) {
        dot.classList.toggle('is-active', index <= state.wizardStep);
      });
    }
    if (review) renderWizardReview();
    if (el.newProjectDialog.open) focusWizardStep();
  }

  function focusWizardStep() {
    if (state.wizardStep === 3) return;
    var firstField = el.wizardSteps[state.wizardStep].querySelector('input, select, textarea');
    if (firstField) firstField.focus();
  }

  function renderWizardReview() {
    var data = new FormData(el.newProjectForm);
    var chapters = parseChapterTitles(data.get('chapter_titles'));
    var files = el.sourceFilesInput && el.sourceFilesInput.files ? el.sourceFilesInput.files.length : 0;
    var rows = [
      ['Tytuł', data.get('title')],
      ['Temat', data.get('topic')],
      ['Tryb', MODE_LABELS[data.get('mode')] || data.get('mode')],
      ['Język', data.get('language') || 'pl'],
      ['Odbiorca', data.get('audience') || 'Nie ustawiono'],
      ['Marka', data.get('brand') || 'Nie ustawiono'],
      ['Ton', data.get('tone') || 'Nie ustawiono'],
      ['Styl pisania', WRITING_STYLE_LABELS[data.get('writing_style')] || 'Praktyczny'],
      ['Humanizacja', HUMANIZE_LEVEL_LABELS[data.get('humanize_level')] || 'Humanizacja standardowa'],
      ['Agent', PROVIDER_LABELS[data.get('provider')] || data.get('provider') || 'Demo'],
      ['Struktura', chapters.length ? chapters.length + ' własnych rozdziałów' : 'Struktura presetu trybu'],
      ['Źródła', data.get('source_materials') ? 'Dołączono wklejony tekst' : 'Brak wklejonego tekstu'],
      ['Pliki źródłowe', files ? files + ' plików do przesłania' : 'Brak plików'],
    ];
    el.wizardReview.innerHTML = rows.map(function (row) {
      return '<dt>' + escapeHtml(row[0]) + '</dt><dd>' + escapeHtml(row[1]) + '</dd>';
    }).join('');
  }

  function nextWizardStep() {
    if (state.wizardStep < 2) {
      var visible = el.wizardSteps[state.wizardStep];
      var required = visible.querySelectorAll('[required]');
      for (var i = 0; i < required.length; i += 1) {
        if (!required[i].reportValidity()) return;
      }
    }
    state.wizardStep = Math.min(3, state.wizardStep + 1);
    renderWizard();
  }

  async function uploadSourceFiles(projectId, files) {
    var uploadData = new FormData();
    files.forEach(function (file) {
      uploadData.append('files', file);
    });
    await apiFetch('/api/projects/' + projectId + '/sources', {
      method: 'POST',
      body: uploadData,
    });
  }

  // --------------------------------------------------------------- palette

  // Subsequence match: "pobz" still finds "Pobierz paczkę ZIP".
  function fuzzyMatches(haystack, needle) {
    if (!needle) return true;
    var index = 0;
    for (var i = 0; i < haystack.length && index < needle.length; i += 1) {
      if (haystack[i] === needle[index]) index += 1;
    }
    return index === needle.length;
  }

  // Lower score wins: a prefix hit outranks a substring hit, which outranks a
  // loose subsequence hit, so "pob" leads with "Pobierz paczkę ZIP".
  function matchScore(command, query) {
    if (!query) return 0;
    var label = command.label.toLowerCase();
    var haystack = (command.id + ' ' + command.label + ' ' + command.hint).toLowerCase();
    if (label.indexOf(query) === 0 || command.id.indexOf(query) === 0) return 0;
    if (label.indexOf(query) !== -1) return 1;
    if (haystack.indexOf(query) !== -1) return 2;
    if (fuzzyMatches(haystack, query)) return 3;
    return -1;
  }

  function availableCommands() {
    var query = el.paletteInput.value.trim().toLowerCase();
    var project = state.selectedProject;
    var matching = COMMANDS.map(function (command) {
      return {
        id: command.id,
        label: command.label,
        hint: command.hint,
        keys: command.keys,
        score: matchScore(command, query),
        enabled: command.when ? Boolean(command.when(project)) : true,
        reason: command.reason,
      };
    }).filter(function (command) { return command.score !== -1; });
    matching.sort(function (a, b) {
      if (a.enabled !== b.enabled) return Number(b.enabled) - Number(a.enabled);
      return a.score - b.score;
    });
    return matching;
  }

  function renderPalette() {
    var commands = availableCommands();
    if (state.paletteIndex >= commands.length) state.paletteIndex = 0;
    if (commands.length === 0) {
      el.paletteList.innerHTML = '<li class="palette-empty">Brak komend dla tego zapytania.</li>';
      return;
    }
    el.paletteList.innerHTML = commands.map(function (command, index) {
      return '<li id="palette-command-' + command.id + '" role="option" aria-selected="' +
        String(index === state.paletteIndex) + '" data-command="' + command.id + '"' +
        (command.enabled ? '' : ' aria-disabled="true" class="is-disabled"') + '>' +
        '<span>' + escapeHtml(command.label) + '</span><span>' +
        escapeHtml(command.enabled ? command.hint : command.reason || 'Niedostępne') +
        (command.keys ? ' <kbd>' + escapeHtml(command.keys) + '</kbd>' : '') + '</span></li>';
    }).join('');
    var active = commands[state.paletteIndex];
    if (active) el.paletteInput.setAttribute('aria-activedescendant', 'palette-command-' + active.id);
  }

  function openPalette() {
    state.palettePreviousFocus = document.activeElement;
    state.paletteIndex = 0;
    el.paletteInput.value = '';
    renderPalette();
    el.commandPalette.showModal();
    el.paletteInput.focus();
  }

  function restorePaletteFocus() {
    if (state.palettePreviousFocus && typeof state.palettePreviousFocus.focus === 'function') {
      state.palettePreviousFocus.focus();
    }
    state.palettePreviousFocus = null;
  }

  function closePalette() {
    el.commandPalette.close();
  }

  function openShortcuts() {
    if (!el.shortcutsDialog.open) el.shortcutsDialog.showModal();
  }

  // -------------------------------------------------------------- wiring

  el.workspacePrimaryAction.addEventListener('click', function () {
    runComposerCommand(el.workspacePrimaryAction.dataset.command, el.workspacePrimaryAction);
  });
  el.mobilePrimaryAction.addEventListener('click', function () {
    runComposerCommand(el.mobilePrimaryAction.dataset.command, el.mobilePrimaryAction);
  });
  el.newProjectButton.addEventListener('click', openNewProjectDialog);
  el.railNewProjectButton.addEventListener('click', openNewProjectDialog);
  el.emptyNewProjectButton.addEventListener('click', openNewProjectDialog);
  el.cancelNewProject.addEventListener('click', function () {
    el.newProjectDialog.close();
  });
  el.wizardNext.addEventListener('click', nextWizardStep);
  el.wizardBack.addEventListener('click', function () {
    state.wizardStep = Math.max(0, state.wizardStep - 1);
    renderWizard();
  });
  el.presetButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      el.fieldMode.value = button.dataset.preset;
      el.presetButtons.forEach(function (preset) { preset.classList.remove('is-selected'); });
      button.classList.add('is-selected');
      updateModeSummary();
    });
  });
  el.fieldMode.addEventListener('change', function () {
    el.presetButtons.forEach(function (preset) {
      preset.classList.toggle('is-selected', preset.dataset.preset === el.fieldMode.value);
    });
    updateModeSummary();
  });

  el.newProjectForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    var selectedFiles = el.sourceFilesInput && el.sourceFilesInput.files
      ? Array.from(el.sourceFilesInput.files)
      : [];
    var autostart = el.fieldAutostart ? el.fieldAutostart.checked : false;
    var formData = new FormData(el.newProjectForm);
    formData.delete('source_files');
    var payload = Object.fromEntries(formData.entries());
    payload.chapter_titles = parseChapterTitles(payload.chapter_titles);
    var project;
    setBusy(el.submitNewProject, true);
    try {
      var response = await apiFetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      project = await response.json();
      showToast('Projekt utworzony.');
    } catch (err) {
      el.formError.hidden = false;
      el.formError.textContent = 'Nie udało się utworzyć projektu: ' + err.message;
      return;
    } finally {
      setBusy(el.submitNewProject, false);
    }

    el.newProjectDialog.close();
    await loadProjects();
    await selectProject(project.id);

    if (selectedFiles.length > 0) {
      try {
        await uploadSourceFiles(project.id, selectedFiles);
        showToast('Pliki źródłowe przesłane.');
        await refreshDetail();
        await loadArtifacts();
      } catch (err) {
        el.errorBanner.hidden = false;
        el.errorBanner.textContent =
          'Projekt utworzony, ale przesyłanie plików źródłowych nie powiodło się: ' + err.message;
        showToast('Przesyłanie źródeł nie powiodło się.', 'error');
        return;
      }
    }

    if (autostart) {
      await runAction('/api/projects/' + project.id + '/start', el.workspacePrimaryAction);
    }
  });

  el.settingsForm.addEventListener('submit', saveSettings);
  el.settingsForm.addEventListener('input', updateSettingsDirty);
  el.settingsForm.addEventListener('change', updateSettingsDirty);
  el.settingsReset.addEventListener('click', resetSettingsForm);

  el.inspectorSourceFiles.addEventListener('change', async function () {
    var files = Array.from(el.inspectorSourceFiles.files || []);
    if (!files.length || !state.selectedId) return;
    try {
      await uploadSourceFiles(state.selectedId, files);
      showToast('Pliki źródłowe przesłane.');
      el.inspectorSourceFiles.value = '';
      await refreshDetail();
      await loadArtifacts();
    } catch (err) {
      showToast('Przesyłanie nieudane: ' + err.message, 'error');
    }
  });

  el.backToList.addEventListener('click', function () {
    openProjectDrawer();
  });
  el.projectSearch.addEventListener('input', function () {
    state.searchQuery = el.projectSearch.value;
    renderProjectList();
  });
  el.projectSort.addEventListener('change', function () {
    state.sortMode = el.projectSort.value;
    writePrefs({ sortMode: state.sortMode });
    renderProjectList();
  });
  el.projectList.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveProjectFocus(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveProjectFocus(-1);
    }
  });
  el.projectList.addEventListener('click', function (event) {
    var retry = event.target.closest('[data-retry="projects"]');
    if (retry) loadProjects();
  });
  el.statusFilters.forEach(function (button) {
    button.addEventListener('click', function () {
      state.statusFilter = button.dataset.statusFilter;
      writePrefs({ statusFilter: state.statusFilter });
      el.statusFilters.forEach(function (filter) { filter.classList.remove('is-active'); });
      button.classList.add('is-active');
      renderProjectList();
    });
  });
  el.tabButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      setActiveTab(button.dataset.tab);
    });
  });
  el.fileFilter.addEventListener('input', function () {
    state.fileFilter = el.fileFilter.value;
    renderFiles();
  });
  el.fileSort.addEventListener('change', function () {
    state.fileSort = el.fileSort.value;
    writePrefs({ fileSort: state.fileSort });
    renderFiles();
  });
  el.filesRefresh.addEventListener('click', function () {
    loadArtifacts();
    loadMetrics();
  });
  el.qualityRefresh.addEventListener('click', function () {
    loadReadability();
    loadMetrics();
  });
  el.eventLevelFilter.addEventListener('change', function () {
    state.eventLevelFilter = el.eventLevelFilter.value;
    renderEvents();
  });
  el.eventSearch.addEventListener('input', function () {
    state.eventQuery = el.eventSearch.value;
    renderEvents();
  });
  el.eventsCopy.addEventListener('click', async function () {
    var copied = await copyText(eventLogText());
    showToast(copied ? 'Log skopiowany do schowka.' : 'Nie udało się skopiować logu.', copied ? null : 'error');
  });
  el.eventsDownload.addEventListener('click', function () {
    var slug = state.selectedProject ? state.selectedProject.slug || state.selectedProject.id : 'projekt';
    downloadTextFile(slug + '-log.txt', eventLogText());
  });
  el.workspaceFiles.addEventListener('click', async function (event) {
    var retry = event.target.closest('[data-retry="files"]');
    if (retry) {
      loadArtifacts();
      return;
    }
    var copyTrigger = event.target.closest('[data-copy-path]');
    if (copyTrigger) {
      var copied = await copyText(copyTrigger.dataset.copyPath);
      showToast(copied ? 'Ścieżka skopiowana.' : 'Nie udało się skopiować ścieżki.', copied ? null : 'error');
      return;
    }
    var trigger = event.target.closest('[data-artifact]');
    if (!trigger) return;
    openArtifactPreview(trigger.dataset.artifact);
  });
  el.stageTimeline.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-artifact]');
    if (!trigger) return;
    openArtifactPreview(trigger.dataset.artifact);
  });
  el.previewClose.addEventListener('click', function () {
    el.previewDialog.close();
  });
  el.previewCopy.addEventListener('click', async function () {
    var copied = await copyText(state.previewText);
    showToast(copied ? 'Treść skopiowana do schowka.' : 'Nie udało się skopiować treści.', copied ? null : 'error');
  });
  el.previewWrap.addEventListener('change', function () {
    state.previewWrap = el.previewWrap.checked;
    writePrefs({ previewWrap: state.previewWrap });
    applyPreviewWrap();
  });
  el.confirmCancel.addEventListener('click', function () {
    state.confirmHandler = null;
    el.confirmDialog.close();
  });
  el.confirmAccept.addEventListener('click', function () {
    var handler = state.confirmHandler;
    state.confirmHandler = null;
    el.confirmDialog.close();
    if (handler) handler();
  });
  el.projectMenuButton.addEventListener('click', function () {
    setProjectMenuOpen(el.projectMenu.hidden);
  });
  el.projectMenu.addEventListener('click', function (event) {
    var item = event.target.closest('[data-action]');
    if (!item) return;
    setProjectMenuOpen(false);
    var action = item.dataset.action;
    if (action === 'edit') setActiveTab('settings');
    else runComposerCommand(action);
  });
  document.addEventListener('click', function (event) {
    if (el.projectMenu.hidden) return;
    if (el.projectMenu.contains(event.target) || el.projectMenuButton.contains(event.target)) return;
    setProjectMenuOpen(false);
  });
  el.themeToggle.addEventListener('click', toggleTheme);
  el.shortcutsButton.addEventListener('click', openShortcuts);
  el.shortcutsClose.addEventListener('click', function () {
    el.shortcutsDialog.close();
  });
  el.composerCommands.forEach(function (button) {
    button.addEventListener('click', function () {
      runComposerCommand(button.dataset.command, button);
    });
  });
  el.composer.addEventListener('submit', function (event) {
    event.preventDefault();
  });
  el.inspectorToggle.addEventListener('click', function () {
    setInspectorOpen(!el.inspectorPanel.classList.contains('is-open'));
  });
  el.bottomNavButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (button.dataset.nav === 'new') {
        openNewProjectDialog();
      } else if (button.dataset.nav === 'inspector') {
        if (state.selectedId) el.inspectorToggle.click();
      } else {
        openProjectDrawer();
      }
    });
  });
  el.projectDrawerBackdrop.addEventListener('click', closeProjectDrawer);

  el.paletteOpenButton.addEventListener('click', openPalette);
  el.paletteInput.addEventListener('input', function () {
    state.paletteIndex = 0;
    renderPalette();
  });
  el.paletteInput.addEventListener('keydown', function (event) {
    var options = el.paletteList.querySelectorAll('[data-command]');
    if (event.key === 'Escape') {
      event.preventDefault();
      closePalette();
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      state.paletteIndex = options.length ? (state.paletteIndex + 1) % options.length : 0;
      renderPalette();
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      state.paletteIndex = options.length ? (state.paletteIndex - 1 + options.length) % options.length : 0;
      renderPalette();
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      var active = options[state.paletteIndex];
      if (active) {
        runComposerCommand(active.dataset.command);
        closePalette();
      }
    }
  });
  el.paletteList.addEventListener('click', function (event) {
    var item = event.target.closest('[data-command]');
    if (!item) return;
    runComposerCommand(item.dataset.command);
    closePalette();
  });
  document.addEventListener('keydown', function (event) {
    var typing = ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(event.target.tagName) !== -1;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openPalette();
      return;
    }
    if (!typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
      if (event.key === 'n') {
        event.preventDefault();
        openNewProjectDialog();
        return;
      }
      if (event.key === '?') {
        event.preventDefault();
        openShortcuts();
        return;
      }
      if (event.key === 'r' && state.selectedId) {
        event.preventDefault();
        refreshAll();
        return;
      }
      if (event.key === '/') {
        event.preventDefault();
        el.projectSearch.focus();
        return;
      }
      if (['1', '2', '3', '4', '5'].indexOf(event.key) !== -1 && state.selectedId) {
        event.preventDefault();
        setActiveTab(
          ['workflow', 'files', 'quality', 'activity', 'settings'][Number(event.key) - 1]
        );
        return;
      }
    }
    if (event.key === 'Escape' && el.commandPalette.open) {
      event.preventDefault();
      closePalette();
    } else if (event.key === 'Escape' && !el.projectMenu.hidden) {
      event.preventDefault();
      setProjectMenuOpen(false);
    } else if (event.key === 'Escape' && el.inspectorPanel.classList.contains('is-open')) {
      event.preventDefault();
      setInspectorOpen(false);
    } else if (event.key === 'Escape' && state.projectDrawerOpen) {
      event.preventDefault();
      closeProjectDrawer();
    }
  });
  window.addEventListener('resize', updateMobileChrome);
  window.addEventListener('beforeunload', function (event) {
    if (!state.settingsDirty) return undefined;
    event.preventDefault();
    event.returnValue = '';
    return '';
  });
  window.addEventListener('online', function () {
    setConnection('online');
    startPolling();
  });
  window.addEventListener('offline', function () { setConnection('offline'); });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      stopPolling();
      return;
    }
    if (state.selectedId) {
      refreshDetail();
      startPolling();
    }
  });
  el.commandPalette.addEventListener('close', restorePaletteFocus);

  initTheme();
  initPrefs();
  checkHealth();
  loadProviders();
  loadBuildInfo();
  loadProjects();
  loadStats();
  setActiveTab('workflow');
  renderPalette();
  updateModeSummary();
  updateMobileChrome();
  updateSettingsDirty();
  applyPreviewWrap();
  startTicker();
})();
