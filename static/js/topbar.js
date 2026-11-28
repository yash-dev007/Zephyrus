// static/js/topbar.js
// Wires the design-v1 topbar to the existing workspace, readiness, tasks, and
// sidebar controls. Kept separate from app.js so the shell layer stays easy to
// review and remove.

import { getWorkspace, openWorkspaceBrowser } from './workspace.js';

function _setProject(path) {
  const nameEl = document.getElementById('topbar-project-name');
  const btn = document.getElementById('topbar-project-btn');
  if (!nameEl || !btn) return;

  const raw = String(path || '').trim();
  if (!raw) {
    nameEl.textContent = 'No project';
    btn.classList.add('is-empty');
    btn.title = 'Choose a project folder';
    return;
  }

  const parts = raw.split(/[\\/]+/).filter(Boolean);
  nameEl.textContent = parts[parts.length - 1] || raw;
  btn.classList.remove('is-empty');
  btn.title = raw;
}

function _setReady(ok) {
  const status = document.getElementById('topbar-status');
  const label = document.getElementById('topbar-status-label');
  if (!status || !label) return;
  status.classList.toggle('is-offline', !ok);
  label.textContent = ok ? 'Ready' : 'Offline';
}

function _checkReady() {
  fetch('/api/health', { credentials: 'same-origin' })
    .then((res) => {
      if (!res.ok) throw new Error('not ready');
      return res.json();
    })
    .then(() => _setReady(true))
    .catch(() => _setReady(false));
}

function _syncPill() {
  const pill = document.getElementById('topbar-session-pill');
  const meta = document.getElementById('current-meta');
  if (!pill || !meta) return;
  const title = (meta.textContent || '').trim();
  pill.classList.toggle('is-empty', !title);
  pill.title = title;
}

function _bindWorkbench() {
  const wbState = document.querySelector('.workbench-state');
  const wbCount = document.querySelector('.workbench-activity span');

  if (wbState && !wbState._topbarBound) {
    wbState._topbarBound = true;
    const syncState = () => {
      const label = document.getElementById('topbar-status-label');
      const status = document.getElementById('topbar-status');
      if (!label) return;
      const text = (wbState.textContent || '').trim();
      label.textContent = text || 'Ready';
      status?.classList.toggle('is-busy', wbState.dataset.busy === 'true');
    };
    new MutationObserver(syncState).observe(wbState, {
      childList: true,
      characterData: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-busy'],
    });
    syncState();
  }

  if (wbCount && !wbCount._topbarBound) {
    wbCount._topbarBound = true;
    const syncCount = () => {
      const badge = document.getElementById('topbar-activity-count');
      if (!badge) return;
      const n = (wbCount.textContent || '').trim();
      badge.textContent = n || '0';
      badge.style.display = n && n !== '0' ? '' : 'none';
    };
    new MutationObserver(syncCount).observe(wbCount, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    syncCount();
  }
}

export function initTopbar() {
  _setProject(getWorkspace());
  _checkReady();

  document.getElementById('topbar-project-btn')?.addEventListener('click', () => {
    openWorkspaceBrowser();
  });

  document.getElementById('topbar-activity-btn')?.addEventListener('click', () => {
    const workbenchActivity = document.querySelector('.workbench-activity');
    if (workbenchActivity) {
      workbenchActivity.click();
      return;
    }
    if (window.tasksModule && typeof window.tasksModule.openTasks === 'function') {
      window.tasksModule.openTasks();
      return;
    }
    document.getElementById('tool-tasks-btn')?.click();
  });

  const toggleSidebar = () => {
    const hamburger = document.getElementById('hamburger-btn');
    if (hamburger) hamburger.click();
  };

  document.getElementById('topbar-panel-btn')?.addEventListener('click', toggleSidebar);
  document.getElementById('topbar-menu-btn')?.addEventListener('click', toggleSidebar);

  const meta = document.getElementById('current-meta');
  if (meta) {
    new MutationObserver(_syncPill).observe(meta, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    _syncPill();
    meta.addEventListener('click', () => {
      document.getElementById('export-dl-btn')?.click();
    });
  }

  // The workspace module calls this whenever the folder changes.
  window._updateTopbarProject = _setProject;

  _bindWorkbench();
  const chatRoot = document.getElementById('chat-container');
  if (chatRoot) {
    new MutationObserver(_bindWorkbench).observe(chatRoot, { childList: true });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTopbar, { once: true });
} else {
  initTopbar();
}
