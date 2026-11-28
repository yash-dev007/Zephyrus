function words(text) {
  return text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

export function createSkillPicker(skills, choose) {
  const panel = document.createElement('section');
  panel.className = 'skill-picker';
  panel.setAttribute('aria-label', 'Skill library');
  panel.innerHTML = `<div class="skill-picker-heading"><strong>Skills</strong><span role="status"></span></div>
    <label class="skill-picker-search">
      <input type="search" aria-label="Search skills" placeholder="Search by name or description" autocomplete="off">
    </label>
    <div class="skill-picker-results"></div>
    <div class="skill-picker-keys"><span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span><span><kbd>Enter</kbd> Choose skill</span></div>`;
  const search = panel.querySelector('input');
  const status = panel.querySelector('[role=status]');
  const results = panel.querySelector('.skill-picker-results');

  const entries = skills.map(skill => {
    const name = skill.name.replace(/[-_]+/g, ' ');
    const title = name.charAt(0).toUpperCase() + name.slice(1);
    const description = skill.help?.trim() || '';
    const repeated = words(title) === words(description);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'skill-picker-row';
    button.title = '/' + skill.name;
    const label = document.createElement('span');
    label.className = 'skill-picker-name';
    label.textContent = repeated ? description : title;
    const copy = document.createElement('span');
    copy.className = 'skill-picker-copy';
    copy.append(label);
    button.append(copy);
    if (description && !repeated) {
      const detail = document.createElement('small');
      detail.textContent = description;
      copy.append(detail);
    }
    if (Number(skill.uses) > 0) {
      const usage = document.createElement('small');
      usage.className = 'skill-picker-usage';
      usage.textContent = `${skill.uses} ${Number(skill.uses) === 1 ? 'use' : 'uses'}`;
      button.append(usage);
    }
    button.addEventListener('click', () => choose(skill));
    return { button, key: words(name + ' ' + description) };
  });
  const render = () => {
    const terms = words(search.value).split(' ').filter(Boolean);
    const matches = entries.filter(entry => terms.every(term => entry.key.includes(term)));
    status.textContent = terms.length ? `${matches.length} of ${entries.length}` : `${entries.length} available`;
    results.replaceChildren(...matches.map(entry => entry.button));
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No matching skills. Try a different search.';
      results.append(empty);
    }
    results.scrollTop = 0;
  };
  search.addEventListener('input', render);
  panel.addEventListener('keydown', e => {
    if (e.isComposing || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const row = e.target.closest('.skill-picker-row');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      (row ? row.nextElementSibling : results.querySelector('button'))?.focus();
    } else if (row && e.key === 'ArrowUp') {
      e.preventDefault();
      (row.previousElementSibling || search).focus();
    } else if (e.target === search && e.key === 'Enter') {
      e.preventDefault();
      results.querySelector('button')?.click();
    }
  });
  render();
  return panel;
}
