// The workbench is a view of the current transcript, never a second run store.
export function initWorkbench({ getWorkspace, openWorkspaceBrowser }) {
  const root = document.getElementById('chat-container');
  const history = document.getElementById('chat-history');
  if (!root || !history || document.getElementById('workbench-bar')) return;
  const bar = document.createElement('div');
  bar.id = 'workbench-bar';
  bar.className = 'workbench-bar';
  bar.innerHTML = `<button type="button" class="workbench-workspace" aria-label="Choose workspace"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 7V5h6l2 2h10v12H3Z"/></svg><span>Choose workspace</span><span aria-hidden="true">⌄</span></button><span class="workbench-state" role="status">Ready</span><button type="button" class="workbench-activity" aria-haspopup="dialog">Activity <span>0</span></button>`;
  root.querySelector('.chat-top-bar').after(bar);
  const workspaceButton = bar.querySelector('.workbench-workspace');
  workspaceButton.addEventListener('click', openWorkspaceBrowser);
  const state = bar.querySelector('.workbench-state');
  const activityButton = bar.querySelector('.workbench-activity');
  const drawer = document.createElement('dialog');
  drawer.className = 'workbench-drawer';
  drawer.setAttribute('aria-labelledby', 'workbench-activity-title');
  drawer.innerHTML = `<header><div><h2 id="workbench-activity-title">Session activity</h2><p>Commands and results in this conversation.</p></div><button type="button" class="workbench-close" aria-label="Close activity">×</button></header><div class="workbench-filters"><input type="search" aria-label="Search tool activity" placeholder="Find a command or tool…"><label><input type="checkbox"> Errors only</label></div><p class="workbench-summary" role="status"></p><div class="workbench-activity-list"></div>`;
  document.body.append(drawer);
  const search = drawer.querySelector('input[type=search]');
  const errorsOnly = drawer.querySelector('input[type=checkbox]');
  const list = drawer.querySelector('.workbench-activity-list');
  const summary = drawer.querySelector('.workbench-summary');
  let busy = !!window.__zephyrusChatBusy;
  let scheduled = false;
  let lastSignature = '';
  let lastNodes = [];
  let returningToTool = false;
  const nodes = () => [...history.querySelectorAll('.agent-thread-node')];
  const describe = node => ({
    name: node.querySelector('.agent-thread-tool')?.textContent.trim() || 'Tool',
    command: node.querySelector('.agent-thread-preview')?.textContent.trim()
      || node.querySelector('.agent-thread-cmd')?.textContent.trim() || '',
    status: node.classList.contains('running') ? 'Running'
      : node.classList.contains('error') ? 'Error'
      : node.querySelector('.agent-thread-status')?.textContent.trim() || 'Finished',
  });
  function renderActivity() {
    const all = nodes();
    const query = search.value.trim().toLowerCase();
    const visible = all.map(node => ({ node, ...describe(node) })).filter(item =>
      (!errorsOnly.checked || item.status === 'Error')
      && `${item.name} ${item.command}`.toLowerCase().includes(query));
    summary.textContent = `${visible.length} of ${all.length} tool calls`;
    // Avoid replacing focused rows for unrelated transcript/token updates.
    const signature = JSON.stringify(visible.map(({ name, command, status }) => [name, command, status]));
    if (signature === lastSignature && list.childElementCount
        && visible.length === lastNodes.length && visible.every((item, i) => item.node === lastNodes[i])) return;
    lastSignature = signature;
    lastNodes = visible.map(item => item.node);
    list.replaceChildren();
    if (!visible.length) {
      const empty = document.createElement('p');
      empty.className = 'workbench-empty';
      empty.textContent = all.length ? 'No matching activity. Try another search or turn off the error filter.'
        : 'Tool activity appears here when the agent reads files, runs commands, or makes changes.';
      list.append(empty);
    }
    visible.forEach(({ node, name, command, status }) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'workbench-activity-row';
      row.dataset.status = status.toLowerCase();
      row.setAttribute('aria-label', `${name}: ${status}. Show in conversation`);
      const heading = document.createElement('span');
      heading.className = 'workbench-row-heading';
      heading.textContent = name;
      const badge = document.createElement('span');
      badge.className = 'workbench-row-status';
      badge.textContent = status;
      const preview = document.createElement('code');
      preview.textContent = command || 'Show tool output';
      row.append(heading, badge, preview);
      row.addEventListener('click', () => {
        returningToTool = true;
        drawer.close();
        node.classList.add('open');
        const target = node.querySelector('.agent-thread-header') || node;
        target.setAttribute('tabindex', '0');
        target.setAttribute('aria-expanded', 'true');
        target.focus({ preventScroll: true });
        node.scrollIntoView({ block: 'center', behavior: 'instant' });
      });
      list.append(row);
    });
  }
  function update() {
    scheduled = false;
    const path = getWorkspace();
    const chatMode = document.getElementById('mode-chat-btn')?.classList.contains('active');
    const researchMode = !!document.getElementById('research-toggle')?.checked;
    const intro = document.querySelector('.workbench-intro');
    root.classList.toggle('workspace-ready', !!path);
    if (intro) intro.hidden = !!path || !!chatMode || researchMode;
    workspaceButton.querySelector('span').textContent = path
      ? path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || path : 'Choose workspace';
    workspaceButton.title = path || 'Choose a project folder for file tools';
    workspaceButton.disabled = !!chatMode;
    const folderButton = document.getElementById('workbench-choose-folder');
    if (folderButton) folderButton.textContent = path ? 'Change project folder' : 'Choose project folder';
    const folderHint = document.querySelector('.workbench-start > span');
    if (folderHint) folderHint.textContent = path ? 'Project selected. Describe your task below.' : 'Give the agent a place to work';
    if (chatMode) workspaceButton.title = 'Switch to Agent mode to use a workspace';
    const all = nodes();
    const running = all.filter(node => node.classList.contains('running')).length;
    const errors = all.filter(node => node.classList.contains('error')).length;
    const status = busy ? (running ? `Running ${running} tool${running === 1 ? '' : 's'}` : 'Working…') : 'Ready';
    if (state.textContent !== status) state.textContent = status;
    state.dataset.busy = String(busy);
    activityButton.querySelector('span').textContent = String(all.length);
    activityButton.setAttribute('aria-label', `Session activity: ${all.length} tool calls, ${errors} errors`);
    activityButton.dataset.errors = String(errors > 0);
    if (drawer.open) renderActivity();
  }
  function schedule() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(update); }
  }
  new MutationObserver(schedule).observe(history, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  window.addEventListener('zephyrus:chat-busy-change', event => { busy = !!event.detail?.active; schedule(); });
  document.addEventListener('overflow-state-change', schedule);
  activityButton.addEventListener('click', () => { lastSignature = ''; renderActivity(); drawer.showModal(); search.focus(); });
  drawer.querySelector('.workbench-close').addEventListener('click', () => drawer.close());
  drawer.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); drawer.close(); }
  });
  drawer.addEventListener('click', event => { if (event.target === drawer) {
    const rect = drawer.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) drawer.close();
  }});
  drawer.addEventListener('close', () => {
    if (!returningToTool) activityButton.focus();
    returningToTool = false;
  });
  search.addEventListener('input', renderActivity);
  errorsOnly.addEventListener('change', renderActivity);
  document.querySelectorAll('[data-workbench-prompt]').forEach(button => button.addEventListener('click', () => {
    const input = document.getElementById('message');
    if (!input) return;
    input.value = input.value.trim() ? `${input.value}\n\n${button.dataset.workbenchPrompt}` : button.dataset.workbenchPrompt;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  }));
  document.getElementById('workbench-choose-folder')?.addEventListener('click', openWorkspaceBrowser);
  update();
}
