/** Decorative shared loader. Its caller supplies the accessible status label. */
export function createIndicator(size = 72) {
  const pixels = Number.isFinite(size) && size > 0 ? size : 72;
  const indicator = document.createElement('span');
  indicator.className = 'zeph-banter-loader';
  indicator.setAttribute('aria-hidden', 'true');
  indicator.style.setProperty('--zeph-loader-size', `${pixels}px`);
  indicator.style.setProperty('--zeph-loader-scale', String(pixels / 72));
  const boxes = document.createElement('span');
  boxes.className = 'zeph-banter-loader__boxes';
  for (let i = 0; i < 9; i++) {
    const box = document.createElement('span');
    box.className = 'zeph-banter-loader__box';
    boxes.appendChild(box);
  }
  indicator.appendChild(boxes);
  return indicator;
}
