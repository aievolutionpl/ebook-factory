(function () {
  'use strict';

  var state = {
    projects: [],
    selectedId: null,
    pollTimer: null,
  };

  var el = {
    projectList: document.getElementById('project-list'),
    emptyDetail: document.getElementById('empty-detail'),
    projectDetail: document.getElementById('project-detail'),
    detailTitle: document.getElementById('detail-title'),
    detailMode: document.getElementById('detail-mode'),
    detailMeta: document.getElementById('detail-meta'),
    detailStatus: document.getElementById('detail-status'),
    progressFill: document.getElementById('progress-bar-fill'),
    progressBar: document.getElementById('progress-bar'),
    startButton: document.getElementById('start-button'),
    pauseButton: document.getElementById('pause-button'),
    resumeButton: document.getElementById('resume-button'),
    cancelButton: document.getElementById('cancel-button'),
    downloadLink: document.getElementById('download-link'),
    errorBanner: document.getElementById('error-banner'),
    stageTimeline: document.getElementById('stage-timeline'),
    eventsLog: document.getElementById('events-log'),
    newProjectButton: document.getElementById('new-project-button'),
    newProjectDialog: document.getElementById('new-project-dialog'),
    newProjectForm: document.getElementById('new-project-form'),
    cancelNewProject: document.getElementById('cancel-new-project'),
    formError: document.getElementById('form-error'),
    backToList: document.getElementById('back-to-list'),
    bottomNavButtons: document.querySelectorAll('.bottom-nav-item'),
  };

  var MODE_LABELS = {
    'lead-magnet': 'Lead magnet',
    guide: 'Poradnik ekspercki',
    premium: 'Książka premium',
  };

  var STATUS_LABELS = {
    draft: 'Szkic',
    running: 'W trakcie',
    paused: 'Wstrzymano',
    completed: 'Ukończono',
    failed: 'Błąd',
    cancelled: 'Anulowano',
  };

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

  async function checkHealth() {
    try {
      await apiFetch('/health');
    } catch (err) {
      console.error('Health check failed', err);
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

  function renderProjectList() {
    if (state.projects.length === 0) {
      el.projectList.innerHTML = '<p class="empty-state">Brak projektów. Utwórz pierwszy ebook.</p>';
      return;
    }
    el.projectList.innerHTML = '';
    state.projects.forEach(function (project) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'project-card' + (project.id === state.selectedId ? ' is-selected' : '');
      button.innerHTML =
        '<p class="project-card-title">' + escapeHtml(project.title) + '</p>' +
        '<p class="project-card-meta">' + escapeHtml(MODE_LABELS[project.mode] || project.mode) +
        ' · ' + project.progress + '%</p>' +
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
    startPolling();
  }

  async function refreshDetail() {
    if (!state.selectedId) return;
    try {
      var response = await apiFetch('/api/projects/' + state.selectedId);
      var project = await response.json();
      renderDetail(project);
      var eventsResponse = await apiFetch('/api/projects/' + state.selectedId + '/events');
      renderEvents(await eventsResponse.json());
    } catch (err) {
      el.errorBanner.hidden = false;
      el.errorBanner.textContent = 'Błąd wczytywania projektu: ' + err.message;
    }
  }

  function renderDetail(project) {
    el.detailTitle.textContent = project.title;
    el.detailMode.textContent = MODE_LABELS[project.mode] || project.mode;
    el.detailMeta.textContent = project.topic + ' · ' + (project.audience || 'odbiorca nieokreślony');
    el.detailStatus.dataset.status = project.status;
    el.detailStatus.textContent = STATUS_LABELS[project.status] || project.status;
    el.progressFill.style.transform = 'scaleX(' + (project.progress / 100) + ')';
    el.progressBar.setAttribute('aria-valuenow', String(project.progress));

    el.errorBanner.hidden = !project.error;
    el.errorBanner.textContent = project.error ? 'Błąd: ' + project.error : '';

    var isRunning = project.status === 'running';
    var isPaused = project.status === 'paused';
    var isDraft = project.status === 'draft';
    var isFailed = project.status === 'failed';
    var isTerminal = project.status === 'completed' || project.status === 'cancelled';

    el.startButton.disabled = !(isDraft || isFailed);
    el.pauseButton.disabled = !isRunning;
    el.resumeButton.disabled = !isPaused;
    el.cancelButton.disabled = isTerminal;

    if (project.status === 'completed') {
      el.downloadLink.hidden = false;
      el.downloadLink.href = '/api/projects/' + project.id + '/download';
    } else {
      el.downloadLink.hidden = true;
    }

    renderStages(project.stages || []);
  }

  function mapStageStatus(status) {
    if (status === 'completed') return 'completed';
    if (status === 'running') return 'running';
    if (status === 'failed') return 'failed';
    return 'draft';
  }

  function renderStages(stages) {
    el.stageTimeline.innerHTML = '';
    stages.forEach(function (stage, index) {
      var item = document.createElement('li');
      item.className = 'stage-item';
      item.innerHTML =
        '<span class="stage-index">' + (index + 1) + '</span>' +
        '<span class="stage-name">' + escapeHtml(stage.name) + '</span>' +
        '<span class="status-chip" data-status="' + mapStageStatus(stage.status) + '">' +
        escapeHtml(stage.status) + '</span>';
      el.stageTimeline.appendChild(item);
    });
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
      await refreshDetail();
      await loadProjects();
      startPolling();
    } catch (err) {
      el.errorBanner.hidden = false;
      el.errorBanner.textContent = 'Akcja nieudana: ' + err.message;
    }
  }

  el.startButton.addEventListener('click', function () {
    runAction('/api/projects/' + state.selectedId + '/start');
  });
  el.pauseButton.addEventListener('click', function () {
    runAction('/api/projects/' + state.selectedId + '/pause');
  });
  el.resumeButton.addEventListener('click', function () {
    runAction('/api/projects/' + state.selectedId + '/resume');
  });
  el.cancelButton.addEventListener('click', function () {
    runAction('/api/projects/' + state.selectedId + '/cancel');
  });

  el.newProjectButton.addEventListener('click', function () {
    el.formError.hidden = true;
    el.newProjectForm.reset();
    el.newProjectDialog.showModal();
  });
  el.cancelNewProject.addEventListener('click', function () {
    el.newProjectDialog.close();
  });

  el.newProjectForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    var formData = new FormData(el.newProjectForm);
    var payload = Object.fromEntries(formData.entries());
    try {
      var response = await apiFetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      var project = await response.json();
      el.newProjectDialog.close();
      await loadProjects();
      await selectProject(project.id);
    } catch (err) {
      el.formError.hidden = false;
      el.formError.textContent = 'Nie udało się utworzyć projektu: ' + err.message;
    }
  });

  el.backToList.addEventListener('click', function () {
    el.projectDetail.hidden = true;
    el.emptyDetail.hidden = false;
    stopPolling();
  });

  el.bottomNavButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (button.dataset.nav === 'new') {
        el.newProjectButton.click();
      } else {
        el.projectDetail.hidden = true;
        el.emptyDetail.hidden = false;
        window.scrollTo(0, 0);
      }
    });
  });

  checkHealth();
  loadProjects();
})();
