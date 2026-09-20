(function () {
  'use strict';

  var POLL_INTERVAL_ACTIVE = 1500;
  var POLL_INTERVAL_IDLE = 6000;
  var THEME_STORAGE_KEY = 'ebook-factory-theme';

  var state = {
    projects: [],
    selectedId: null,
    selectedProject: null,
    providers: [],
    events: [],
    stats: null,
    artifactGroups: [],
    metrics: null,
    pollTimer: null,
    pollInterval: POLL_INTERVAL_ACTIVE,
    statusFilter: 'all',
    searchQuery: '',
    sortMode: 'recent',
    fileFilter: '',
    eventLevelFilter: 'all',
    activeTab: 'workflow',
    wizardStep: 0,
    paletteIndex: 0,
    palettePreviousFocus: null,
    projectDrawerOpen: false,
    expandedStages: {},
    confirmHandler: null,
    settingsDirty: false,
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
    workspaceMetrics: document.getElementById('workspace-metrics'),
    workspacePrimaryAction: document.getElementById('workspace-primary-action'),
    mobilePrimaryAction: document.getElementById('mobile-primary-action'),
    projectMenuButton: document.getElementById('project-menu-button'),
    projectMenu: document.getElementById('project-menu'),
    errorBanner: document.getElementById('error-banner'),
    completionSummary: document.getElementById('completion-summary'),
    stageTimeline: document.getElementById('stage-timeline'),
    eventsLog: document.getElementById('events-log'),
    eventLevelFilter: document.getElementById('event-level-filter'),
    workspaceFiles: document.getElementById('workspace-files'),
    fileFilter: document.getElementById('file-filter'),
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
    settingsHelp: document.getElementById('settings-help'),
    themeToggle: document.getElementById('theme-toggle'),
    previewDialog: document.getElementById('artifact-preview'),
    previewTitle: document.getElementById('artifact-preview-title'),
    previewMeta: document.getElementById('artifact-preview-meta'),
    previewBody: document.getElementById('artifact-preview-body'),
    previewClose: document.getElementById('artifact-preview-close'),
    previewDownload: document.getElementById('artifact-download-link'),
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

  var STAGE_LABELS = {
    strategy: 'Strategia',
    research: 'Research',
    outline: 'Architektura',
    draft: 'Pisanie',
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

  var COMMAND_LABELS = {
    start: 'Start',
    pause: 'Wstrzymaj',
    resume: 'Wznów',
    cancel: 'Anuluj',
    download: 'Pobierz',
  };

  var COMMANDS = [
    { id: 'start', label: 'Uruchom projekt', hint: 'POST /start' },
    { id: 'pause', label: 'Wstrzymaj po bieżącym etapie', hint: 'POST /pause' },
    { id: 'resume', label: 'Wznów projekt', hint: 'POST /resume' },
    { id: 'cancel', label: 'Anuluj projekt', hint: 'POST /cancel' },
    { id: 'download', label: 'Pobierz paczkę ZIP', hint: 'GET /download' },
    { id: 'retry', label: 'Ponów od pierwszego błędu', hint: 'POST /retry' },
    { id: 'duplicate', label: 'Duplikuj projekt', hint: 'POST /duplicate' },
    { id: 'delete', label: 'Usuń projekt', hint: 'DELETE /api/projects' },
    { id: 'new', label: 'Nowy ebook', hint: 'Kreator projektu' },
    { id: 'files', label: 'Pokaż pliki projektu', hint: 'Zakładka Pliki' },
    { id: 'settings', label: 'Edytuj ustawienia', hint: 'PATCH /api/projects' },
    { id: 'theme', label: 'Przełącz motyw', hint: 'Jasny / ciemny' },
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

  function formatDuration(startedAt, finishedAt) {
    if (!startedAt) return '';
    var start = Date.parse(startedAt);
    var end = finishedAt ? Date.parse(finishedAt) : Date.now();
    if (isNaN(start) || isNaN(end) || end < start) return '';
    var seconds = Math.round((end - start) / 1000);
    if (seconds < 60) return seconds + ' s';
    return Math.floor(seconds / 60) + ' min ' + (seconds % 60) + ' s';
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

  async function apiFetch(path, options) {
    var response = await fetch(path, options);
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

  function showToast(message, tone) {
    var toast = document.createElement('p');
    toast.className = 'toast' + (tone ? ' toast-' + tone : '');
    toast.textContent = message;
    el.toastRegion.appendChild(toast);
    window.setTimeout(function () {
      toast.remove();
    }, 3600);
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

  // ----------------------------------------------------------- data loads

  async function loadProjects() {
    try {
      var response = await apiFetch('/api/projects');
      state.projects = await response.json();
      renderProjectList();
    } catch (err) {
      el.projectList.innerHTML =
        '<p class="empty-state">Nie udało się wczytać projektów: ' + escapeHtml(err.message) + '</p>';
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
        '<p class="empty-state">Nie udało się wczytać plików: ' + escapeHtml(err.message) + '</p>';
    }
  }

  async function loadMetrics() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId + '/metrics');
      state.metrics = await response.json();
      renderMetrics();
    } catch (err) {
      state.metrics = null;
      renderMetrics();
    }
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

  function renderProviderStatus(project) {
    var info = providerInfo(project.provider || 'demo');
    var availability = info.available ? 'dostępny' : 'niedostępny lokalnie';
    var text = 'Agent: ' + (PROVIDER_LABELS[info.name] || info.label) + ' · ' + availability;
    el.detailProvider.textContent = text;
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
      button.innerHTML =
        '<span class="project-card-kicker">' + escapeHtml(project.slug || project.id.slice(0, 8)) + '</span>' +
        '<span class="project-card-title">' + escapeHtml(project.title) + '</span>' +
        '<span class="project-card-meta">' + escapeHtml(MODE_LABELS[project.mode] || project.mode) +
        ' · ' + project.progress + '%</span>' +
        '<span class="project-card-progress" aria-hidden="true"><span style="width:' + project.progress + '%"></span></span>' +
        '<span class="project-card-footer">' +
        '<span class="status-chip" data-status="' + project.status + '">' +
        escapeHtml(STATUS_LABELS[project.status] || project.status) + '</span>' +
        '<span class="project-card-time">' + escapeHtml(formatRelative(project.updated_at)) + '</span>' +
        '</span>';
      button.addEventListener('click', function () {
        selectProject(project.id);
      });
      el.projectList.appendChild(button);
    });
  }

  async function selectProject(projectId) {
    state.selectedId = projectId;
    state.events = [];
    state.artifactGroups = [];
    state.metrics = null;
    state.expandedStages = {};
    el.emptyDetail.hidden = true;
    el.projectDetail.hidden = false;
    renderProjectList();
    await refreshDetail();
    await Promise.all([loadArtifacts(), loadMetrics()]);
    closeProjectDrawer();
    startPolling();
  }

  async function refreshDetail() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId);
      var project = await response.json();
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
    if (project.status === 'cancelled') return 'download';
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
    el.progressLabel.textContent = project.progress + '% ukończono';
    el.stageLabel.textContent = stage ? stageLabel(stage.name) : 'Oczekuje na start';
    el.workspacePrimaryAction.textContent = commandLabel(command);
    el.workspacePrimaryAction.dataset.command = command;
    el.mobilePrimaryAction.textContent = commandLabel(command);
    el.mobilePrimaryAction.dataset.command = command;

    el.errorBanner.hidden = !project.error;
    el.errorBanner.textContent = project.error ? 'Błąd: ' + project.error : '';

    renderStages(project.stages || []);
    renderCompletionSummary(project);
    if (!state.settingsDirty) fillSettingsForm(project);
    updateMobileChrome();
  }

  function stageLabel(name) {
    return STAGE_LABELS[name] || name;
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
      head.setAttribute('aria-expanded', String(expanded));
      head.innerHTML =
        '<span class="stage-index">' + String(index + 1).padStart(2, '0') + '</span>' +
        '<span class="stage-name">' + escapeHtml(stageLabel(stage.name)) + '</span>' +
        '<span class="stage-duration">' + escapeHtml(duration) + '</span>' +
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
  }

  // ------------------------------------------------------------ file view

  function visibleArtifactGroups() {
    var query = state.fileFilter.trim().toLowerCase();
    if (!query) return state.artifactGroups;
    return state.artifactGroups.map(function (group) {
      return {
        category: group.category,
        label: group.label,
        files: group.files.filter(function (file) {
          return file.path.toLowerCase().indexOf(query) !== -1;
        }),
      };
    }).filter(function (group) { return group.files.length > 0; });
  }

  function renderFiles() {
    var groups = visibleArtifactGroups();
    if (groups.length === 0) {
      el.workspaceFiles.innerHTML = state.artifactGroups.length
        ? '<p class="empty-state">Żaden plik nie pasuje do filtra.</p>'
        : '<p class="empty-state">Nie ma jeszcze dostępnych plików. Uruchom produkcję.</p>';
      return;
    }
    el.workspaceFiles.innerHTML = groups.map(function (group) {
      var rows = group.files.map(function (file) {
        var actions = (file.previewable
          ? '<button type="button" class="link-button" data-artifact="' + escapeHtml(file.path) + '">Podgląd</button>'
          : '') +
          '<a class="link-button" href="/api/projects/' + encodeURIComponent(state.selectedId) +
          '/artifacts/raw?path=' + encodeURIComponent(file.path) + '&download=true" download>Pobierz</a>';
        return '<div class="file-row" data-kind="' + escapeHtml(file.kind) + '">' +
          '<span class="file-name">' + escapeHtml(file.name) + '</span>' +
          '<span class="file-path">' + escapeHtml(file.path) + '</span>' +
          '<span class="file-size">' + escapeHtml(formatBytes(file.bytes)) + '</span>' +
          '<span class="file-actions">' + actions + '</span>' +
          '</div>';
      }).join('');
      return '<section class="file-group"><h3>' + escapeHtml(group.label) +
        ' <span class="file-group-count">' + group.files.length + '</span></h3>' + rows + '</section>';
    }).join('');
  }

  async function openArtifactPreview(path) {
    if (!state.selectedId) return;
    var rawUrl = '/api/projects/' + encodeURIComponent(state.selectedId) +
      '/artifacts/raw?path=' + encodeURIComponent(path);
    el.previewTitle.textContent = path;
    el.previewDownload.href = rawUrl + '&download=true';
    el.previewBody.innerHTML = '<p class="empty-state">Wczytywanie…</p>';
    if (!el.previewDialog.open) el.previewDialog.showModal();

    var lower = path.toLowerCase();
    var isImage = /\.(png|jpe?g|gif|webp)$/.test(lower);
    if (isImage) {
      el.previewMeta.textContent = 'Podgląd obrazu';
      el.previewBody.innerHTML = '<img class="preview-image" alt="Podgląd: ' +
        escapeHtml(path) + '" src="' + escapeHtml(rawUrl) + '">';
      return;
    }
    try {
      var response = await apiFetch('/api/projects/' + encodeURIComponent(state.selectedId) +
        '/artifacts/preview?path=' + encodeURIComponent(path));
      var payload = await response.json();
      el.previewMeta.textContent = formatBytes(payload.bytes) +
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
    if (state.eventLevelFilter === 'all') return state.events;
    return state.events.filter(function (event) { return event.level === state.eventLevelFilter; });
  }

  function renderEvents() {
    var events = visibleEvents();
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
        '<span class="event-time">' + escapeHtml(formatRelative(event.timestamp)) + '</span>';
      el.eventsLog.appendChild(item);
    });
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
      ? latest.map(function (event) { return '<li>' + escapeHtml(event.message) + '</li>'; }).join('')
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
    });
    el.tabPanels.forEach(function (panel) {
      panel.hidden = panel.id !== 'panel-' + tabName;
    });
    if (tabName === 'files') loadArtifacts();
  }

  // --------------------------------------------------------------- polling

  function desiredInterval() {
    var project = state.selectedProject;
    return project && project.status === 'running' ? POLL_INTERVAL_ACTIVE : POLL_INTERVAL_IDLE;
  }

  function startPolling() {
    stopPolling();
    state.pollInterval = desiredInterval();
    state.pollTimer = window.setInterval(async function () {
      await refreshDetail();
      await loadProjects();
      await loadStats();
      var current = state.projects.find(function (p) { return p.id === state.selectedId; });
      if (current && ['completed', 'failed', 'cancelled'].indexOf(current.status) !== -1) {
        stopPolling();
        await Promise.all([loadArtifacts(), loadMetrics()]);
        renderCompletionSummary(current);
      } else if (desiredInterval() !== state.pollInterval) {
        startPolling();
      }
    }, state.pollInterval);
  }

  function stopPolling() {
    if (state.pollTimer) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  // --------------------------------------------------------------- actions

  async function runAction(path) {
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
    }
  }

  function askConfirmation(message, handler) {
    el.confirmMessage.textContent = message;
    state.confirmHandler = handler;
    el.confirmDialog.showModal();
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
        el.projectDetail.hidden = true;
        el.emptyDetail.hidden = false;
        updateMobileChrome();
        await loadProjects();
        await loadStats();
      } catch (err) {
        showToast('Usuwanie nieudane: ' + err.message, 'error');
      }
    });
  }

  function runComposerCommand(command) {
    if (command === 'new') {
      openNewProjectDialog();
      return;
    }
    if (command === 'theme') {
      toggleTheme();
      return;
    }
    var project = state.selectedProject;
    if (!state.selectedId || !project) {
      showToast('Najpierw wybierz projekt.');
      return;
    }
    if (command === 'download') {
      if (project.status === 'completed') {
        window.location.href = '/api/projects/' + state.selectedId + '/download';
      } else {
        showToast('Pobieranie będzie dostępne po ukończeniu.');
      }
      return;
    }
    if (command === 'files') {
      setActiveTab('files');
      return;
    }
    if (command === 'settings') {
      setActiveTab('settings');
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
    if (command === 'start') runAction('/api/projects/' + state.selectedId + '/start');
    if (command === 'pause') runAction('/api/projects/' + state.selectedId + '/pause');
    if (command === 'resume') runAction('/api/projects/' + state.selectedId + '/resume');
    if (command === 'cancel') runAction('/api/projects/' + state.selectedId + '/cancel');
    if (command === 'retry') runAction('/api/projects/' + state.selectedId + '/retry');
  }

  // -------------------------------------------------------------- settings

  function fillSettingsForm(project) {
    if (!el.settingsForm) return;
    el.settingsForm.elements.title.value = project.title || '';
    el.settingsForm.elements.topic.value = project.topic || '';
    el.settingsForm.elements.mode.value = project.mode || 'guide';
    el.settingsForm.elements.audience.value = project.audience || '';
    el.settingsForm.elements.brand.value = project.brand || '';
    el.settingsForm.elements.tone.value = project.tone || '';
    el.settingsForm.elements.language.value = project.language || 'pl';
    el.settingsForm.elements.chapter_titles.value = (project.chapter_titles || []).join('\n');
    var locked = project.status === 'running';
    Array.from(el.settingsForm.elements).forEach(function (field) { field.disabled = locked; });
    el.settingsHelp.textContent = locked
      ? 'Projekt jest uruchomiony — wstrzymaj go, aby zmienić ustawienia.'
      : 'Ustawienia można zmieniać, gdy projekt nie jest uruchomiony. Zmiany wpływają na kolejne etapy.';
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
      chapter_titles: parseChapterTitles(form.chapter_titles.value),
    };
    try {
      await apiFetch('/api/projects/' + state.selectedId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      el.settingsError.hidden = true;
      state.settingsDirty = false;
      showToast('Ustawienia zapisane.');
      await refreshDetail();
      await loadProjects();
    } catch (err) {
      el.settingsError.hidden = false;
      el.settingsError.textContent = 'Nie udało się zapisać: ' + err.message;
    }
  }

  // ---------------------------------------------------------------- wizard

  function openNewProjectDialog() {
    el.formError.hidden = true;
    el.newProjectForm.reset();
    el.fieldMode.value = 'guide';
    updateModeSummary();
    state.wizardStep = 0;
    renderWizard();
    el.newProjectDialog.showModal();
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
  }

  function renderWizardReview() {
    var data = new FormData(el.newProjectForm);
    var chapters = parseChapterTitles(data.get('chapter_titles'));
    var rows = [
      ['Tytuł', data.get('title')],
      ['Temat', data.get('topic')],
      ['Tryb', MODE_LABELS[data.get('mode')] || data.get('mode')],
      ['Odbiorca', data.get('audience') || 'Nie ustawiono'],
      ['Marka', data.get('brand') || 'Nie ustawiono'],
      ['Ton', data.get('tone') || 'Nie ustawiono'],
      ['Agent', PROVIDER_LABELS[data.get('provider')] || data.get('provider') || 'Demo'],
      ['Struktura', chapters.length ? chapters.length + ' własnych rozdziałów' : 'Struktura presetu trybu'],
      ['Źródła', data.get('source_materials') ? 'Dołączono wklejony tekst' : 'Brak wklejonego tekstu'],
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

  function availableCommands() {
    var query = el.paletteInput.value.trim().toLowerCase();
    return COMMANDS.filter(function (command) {
      return !query || command.id.indexOf(query) !== -1 || command.label.toLowerCase().indexOf(query) !== -1;
    });
  }

  function renderPalette() {
    var commands = availableCommands();
    if (state.paletteIndex >= commands.length) state.paletteIndex = 0;
    el.paletteList.innerHTML = commands.map(function (command, index) {
      return '<li id="palette-command-' + command.id + '" role="option" aria-selected="' +
        String(index === state.paletteIndex) + '" data-command="' + command.id + '">' +
        '<span>' + escapeHtml(command.label) + '</span><span>' + escapeHtml(command.hint) + '</span></li>';
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

  // -------------------------------------------------------------- wiring

  el.workspacePrimaryAction.addEventListener('click', function () {
    runComposerCommand(el.workspacePrimaryAction.dataset.command);
  });
  el.mobilePrimaryAction.addEventListener('click', function () {
    runComposerCommand(el.mobilePrimaryAction.dataset.command);
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
      await runAction('/api/projects/' + project.id + '/start');
    }
  });

  el.settingsForm.addEventListener('submit', saveSettings);
  el.settingsForm.addEventListener('input', function () {
    state.settingsDirty = true;
  });

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
    renderProjectList();
  });
  el.statusFilters.forEach(function (button) {
    button.addEventListener('click', function () {
      state.statusFilter = button.dataset.statusFilter;
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
  el.filesRefresh.addEventListener('click', function () {
    loadArtifacts();
    loadMetrics();
  });
  el.eventLevelFilter.addEventListener('change', function () {
    state.eventLevelFilter = el.eventLevelFilter.value;
    renderEvents();
  });
  el.workspaceFiles.addEventListener('click', function (event) {
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
  el.composerCommands.forEach(function (button) {
    button.addEventListener('click', function () {
      runComposerCommand(button.dataset.command);
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
      if (event.key === '/') {
        event.preventDefault();
        el.projectSearch.focus();
        return;
      }
      if (['1', '2', '3', '4'].indexOf(event.key) !== -1 && state.selectedId) {
        event.preventDefault();
        setActiveTab(['workflow', 'files', 'activity', 'settings'][Number(event.key) - 1]);
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
  el.commandPalette.addEventListener('close', restorePaletteFocus);

  initTheme();
  checkHealth();
  loadProviders();
  loadProjects();
  loadStats();
  setActiveTab('workflow');
  renderPalette();
  updateModeSummary();
  updateMobileChrome();
})();
