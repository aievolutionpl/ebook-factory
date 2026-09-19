(function () {
  'use strict';

  var state = {
    projects: [],
    selectedId: null,
    selectedProject: null,
    providers: [],
    events: [],
    pollTimer: null,
    statusFilter: 'all',
    searchQuery: '',
    activeTab: 'workflow',
    wizardStep: 0,
    paletteIndex: 0,
    palettePreviousFocus: null,
    projectDrawerOpen: false,
  };

  var el = {
    projectList: document.getElementById('project-list'),
    projectRail: document.getElementById('sidebar-nav'),
    projectDrawerBackdrop: document.getElementById('project-drawer-backdrop'),
    projectCount: document.getElementById('project-count'),
    projectSearch: document.getElementById('project-search'),
    statusFilters: document.querySelectorAll('[data-status-filter]'),
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
    workspacePrimaryAction: document.getElementById('workspace-primary-action'),
    mobilePrimaryAction: document.getElementById('mobile-primary-action'),
    errorBanner: document.getElementById('error-banner'),
    completionSummary: document.getElementById('completion-summary'),
    stageTimeline: document.getElementById('stage-timeline'),
    eventsLog: document.getElementById('events-log'),
    workspaceFiles: document.getElementById('workspace-files'),
    inspectorPanel: document.getElementById('inspector-panel'),
    inspectorProviderStatus: document.getElementById('inspector-provider-status'),
    inspectorToggle: document.getElementById('inspector-sheet-toggle'),
    inspectorOutputs: document.getElementById('inspector-outputs'),
    inspectorSources: document.getElementById('inspector-sources'),
    inspectorActivity: document.getElementById('inspector-activity'),
    inspectorDownloadLink: document.getElementById('inspector-download-link'),
    newProjectButton: document.getElementById('new-project-button'),
    railNewProjectButton: document.getElementById('rail-new-project-button'),
    emptyNewProjectButton: document.getElementById('empty-new-project-button'),
    newProjectDialog: document.getElementById('new-project-dialog'),
    newProjectForm: document.getElementById('new-project-form'),
    cancelNewProject: document.getElementById('cancel-new-project'),
    formError: document.getElementById('form-error'),
    sourceFilesInput: document.getElementById('field-source-files'),
    fieldProvider: document.getElementById('field-provider'),
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
    toastRegion: document.getElementById('toast-region'),
  };

  var MODE_LABELS = {
    'lead-magnet': 'Lead magnet',
    guide: 'Poradnik ekspercki',
    premium: 'Książka premium',
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
  ];

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value === null || value === undefined ? '' : String(value);
    return div.innerHTML;
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

  function showToast(message) {
    var toast = document.createElement('p');
    toast.className = 'toast';
    toast.textContent = message;
    el.toastRegion.appendChild(toast);
    window.setTimeout(function () {
      toast.remove();
    }, 3200);
  }

  async function checkHealth() {
    try {
      await apiFetch('/health');
    } catch (err) {
      showToast('Kontrola stanu nie powiodła się: ' + err.message);
    }
  }

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

  async function loadProviders() {
    try {
      var response = await apiFetch('/api/providers');
      state.providers = await response.json();
      renderProviderOptions();
      if (state.selectedProject) renderProviderStatus(state.selectedProject);
    } catch (err) {
      state.providers = [{ name: 'demo', label: 'Demo', available: true }];
      renderProviderOptions();
      showToast('Nie udało się wczytać statusu agentów: ' + err.message);
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

  function filteredProjects() {
    var query = state.searchQuery.trim().toLowerCase();
    return state.projects.filter(function (project) {
      var matchesStatus = state.statusFilter === 'all' || project.status === state.statusFilter;
      var haystack = [project.title, project.topic, project.status, project.mode].join(' ').toLowerCase();
      return matchesStatus && (!query || haystack.indexOf(query) !== -1);
    });
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
        '<span class="status-chip" data-status="' + project.status + '">' +
        escapeHtml(STATUS_LABELS[project.status] || project.status) + '</span>';
      button.addEventListener('click', function () {
        selectProject(project.id);
      });
      el.projectList.appendChild(button);
    });
  }

  async function selectProject(projectId) {
    state.selectedId = projectId;
    el.emptyDetail.hidden = true;
    el.projectDetail.hidden = false;
    renderProjectList();
    await refreshDetail();
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
      var eventsResponse = await apiFetch('/api/projects/' + state.selectedId + '/events');
      state.events = await eventsResponse.json();
      renderEvents(state.events);
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
    if (project.status === 'completed') return 'download';
    if (project.status === 'cancelled') return 'download';
    return 'start';
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
    el.workspacePrimaryAction.textContent = COMMAND_LABELS[command] || command;
    el.workspacePrimaryAction.dataset.command = command;
    el.mobilePrimaryAction.textContent = COMMAND_LABELS[command] || command;
    el.mobilePrimaryAction.dataset.command = command;

    el.errorBanner.hidden = !project.error;
    el.errorBanner.textContent = project.error ? 'Błąd: ' + project.error : '';

    renderStages(project.stages || []);
    renderFiles(project);
    renderCompletionSummary(project);
    updateMobileChrome();
  }

  function stageLabel(name) {
    return STAGE_LABELS[name] || name;
  }

  function renderCompletionSummary(project) {
    if (project.status !== 'completed') {
      el.completionSummary.hidden = true;
      el.completionSummary.innerHTML = '';
      return;
    }
    el.completionSummary.hidden = false;
    el.completionSummary.innerHTML =
      '<h2>Projekt gotowy do pobrania</h2>' +
      '<p>Pakiet ZIP zawiera PDF, EPUB, okładkę, materiały marketingowe i raport jakości.</p>' +
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
      item.className = 'stage-item';
      item.innerHTML =
        '<span class="stage-index">' + String(index + 1).padStart(2, '0') + '</span>' +
        '<span class="stage-name">' + escapeHtml(stageLabel(stage.name)) + '</span>' +
        '<span class="status-chip" data-status="' + mapStageStatus(stage.status) + '">' +
        escapeHtml(STATUS_LABELS[mapStageStatus(stage.status)] || stage.status) + '</span>';
      el.stageTimeline.appendChild(item);
    });
  }

  function renderFiles(project) {
    var outputs = outputItems(project);
    var sources = sourceItems(project);
    var items = outputs.concat(sources);
    if (items.length === 0) {
      el.workspaceFiles.innerHTML = '<p class="empty-state">Nie ma jeszcze dostępnych plików.</p>';
      return;
    }
    el.workspaceFiles.innerHTML = items.map(function (item) {
      return '<div class="file-row"><span>' + escapeHtml(item.name) + '</span><span>' +
        escapeHtml(item.meta) + '</span></div>';
    }).join('');
  }

  function outputItems(project) {
    if (!project || project.status !== 'completed') {
      return [{ name: 'Paczka ZIP', meta: 'Dostępna po ukończeniu' }];
    }
    return [
      { name: 'book.pdf', meta: 'Wynik budowania' },
      { name: 'book.epub', meta: 'Wynik budowania' },
      { name: 'cover.png', meta: 'Wynik projektu' },
      { name: 'marketing pack', meta: 'Oferta, landing, posty, reklamy' },
      { name: 'delivery.zip', meta: 'Gotowe' },
    ];
  }

  function sourceItems(project) {
    var hasMaterials = Boolean(project && project.source_materials);
    return [
      { name: 'Wklejone materiały źródłowe', meta: hasMaterials ? 'Dołączone' : 'Brak wklejonych materiałów' },
      { name: 'Przesłane pliki', meta: 'Zapisane przez istniejące API uploadu' },
    ];
  }

  function renderEvents(events) {
    if (events.length === 0) {
      el.eventsLog.innerHTML = '<li>Brak zdarzeń.</li>';
      return;
    }
    el.eventsLog.innerHTML = '';
    events.slice().reverse().forEach(function (event) {
      var item = document.createElement('li');
      item.textContent = '[' + event.level + '] ' + event.message;
      el.eventsLog.appendChild(item);
    });
  }

  function renderInspector(project, events) {
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
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = window.setInterval(async function () {
      await refreshDetail();
      await loadProjects();
      var current = state.projects.find(function (p) { return p.id === state.selectedId; });
      if (current && ['completed', 'failed', 'cancelled'].indexOf(current.status) !== -1) {
        stopPolling();
      }
    }, 2000);
  }

  function stopPolling() {
    if (state.pollTimer) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function runAction(path) {
    try {
      await apiFetch(path, { method: 'POST' });
      showToast('Akcja przyjęta.');
      await refreshDetail();
      await loadProjects();
      startPolling();
    } catch (err) {
      el.errorBanner.hidden = false;
      el.errorBanner.textContent = 'Akcja nieudana: ' + err.message;
      showToast('Akcja nieudana: ' + err.message);
    }
  }

  function runComposerCommand(command) {
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
    if (command === 'start') runAction('/api/projects/' + state.selectedId + '/start');
    if (command === 'pause') runAction('/api/projects/' + state.selectedId + '/pause');
    if (command === 'resume') runAction('/api/projects/' + state.selectedId + '/resume');
    if (command === 'cancel') runAction('/api/projects/' + state.selectedId + '/cancel');
  }

  function openNewProjectDialog() {
    el.formError.hidden = true;
    el.newProjectForm.reset();
    el.fieldMode.value = 'guide';
    state.wizardStep = 0;
    renderWizard();
    el.newProjectDialog.showModal();
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
    if (review) renderWizardReview();
  }

  function renderWizardReview() {
    var data = new FormData(el.newProjectForm);
    var rows = [
      ['Tytuł', data.get('title')],
      ['Temat', data.get('topic')],
      ['Tryb', MODE_LABELS[data.get('mode')] || data.get('mode')],
      ['Odbiorca', data.get('audience') || 'Nie ustawiono'],
      ['Marka', data.get('brand') || 'Nie ustawiono'],
      ['Ton', data.get('tone') || 'Nie ustawiono'],
      ['Agent', PROVIDER_LABELS[data.get('provider')] || data.get('provider') || 'Demo'],
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

  function renderPalette() {
    var query = el.paletteInput.value.trim().toLowerCase();
    var commands = COMMANDS.filter(function (command) {
      return !query || command.id.indexOf(query) !== -1 || command.label.toLowerCase().indexOf(query) !== -1;
    });
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
    });
  });

  el.newProjectForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    var selectedFiles = el.sourceFilesInput && el.sourceFilesInput.files
      ? Array.from(el.sourceFilesInput.files)
      : [];
    var formData = new FormData(el.newProjectForm);
    formData.delete('source_files');
    var payload = Object.fromEntries(formData.entries());
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
      } catch (err) {
        el.errorBanner.hidden = false;
        el.errorBanner.textContent =
          'Projekt utworzony, ale przesyłanie plików źródłowych nie powiodło się: ' + err.message;
        showToast('Przesyłanie źródeł nie powiodło się.');
      }
    }
  });

  el.backToList.addEventListener('click', function () {
    openProjectDrawer();
  });
  el.projectSearch.addEventListener('input', function () {
    state.searchQuery = el.projectSearch.value;
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
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openPalette();
    }
    if (event.key === 'Escape' && el.commandPalette.open) {
      event.preventDefault();
      closePalette();
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

  checkHealth();
  loadProviders();
  loadProjects();
  setActiveTab('workflow');
  renderPalette();
  updateMobileChrome();
})();
