// static/js/bgEffect.js
//
// Perlin-flow background effect. The app has a single fixed Terminal theme, so
// this is the only background pattern it renders. Spawned automatically on DOM
// ready; the draw loop self-terminates when the body class it keys off is
// removed (see the guard at the top of draw() in _initPerlinFlow).

import { hexToRgb } from './color/hex.js';

// ── Noise helper for Perlin effects ──
function _bgNoise2d(x, y) { const n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453; return n - Math.floor(n); }
function _bgSmoothNoise(x, y) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
  const a = _bgNoise2d(ix, iy), b = _bgNoise2d(ix + 1, iy), cc = _bgNoise2d(ix, iy + 1), d = _bgNoise2d(ix + 1, iy + 1);
  const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  return a + (b - a) * ux + (cc - a) * uy + (a - b - cc + d) * ux * uy;
}

// ── Perlin Flow — colored particle streams ──
function _initPerlinFlow() {
  if (document.getElementById('perlin-flow-canvas')) return;
  const canvas = document.createElement('canvas');
  canvas.id = 'perlin-flow-canvas';
  canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;';
  // Decorative background effect — hide from assistive tech so screen readers
  // don't announce an empty canvas and axe's "region" rule doesn't flag it.
  canvas.setAttribute('aria-hidden', 'true');
  document.body.prepend(canvas);
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  let W, H, t = 0;
  const particles = [];
  function resize() {
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (particles.length === 0) for (let i = 0; i < 70; i++) particles.push({ x: Math.random() * W, y: Math.random() * H, life: Math.random() });
  }
  resize();
  const _onResize = () => resize();
  window.addEventListener('resize', _onResize);
  function getColor() { const s = getComputedStyle(document.documentElement); return s.getPropertyValue('--bg-effect-color').trim() || s.getPropertyValue('--fg').trim() || '#9cdef2'; }
  function getBg() { return getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#282c34'; }
  let _cachedBg = '', _fadeStyle = '';
  function getFade() {
    const bg = getBg();
    if (bg !== _cachedBg) {
      _cachedBg = bg;
      // Parse hex to rgb for rgba fade
      const { r, g, b } = hexToRgb(bg) || { r: 0, g: 0, b: 0 };
      _fadeStyle = `rgba(${r},${g},${b},0.035)`;
    }
    return _fadeStyle;
  }
  function draw() {
    if (!document.body.classList.contains('bg-pattern-perlin-flow')) { window.removeEventListener('resize', _onResize); canvas.remove(); return; }
    requestAnimationFrame(draw);
    if (document.hidden) return;
    ctx.fillStyle = getFade();
    ctx.fillRect(0, 0, W, H);
    const c = getColor();
    particles.forEach(p => {
      const n = _bgSmoothNoise(p.x * 0.004 + t * 0.0008, p.y * 0.004 + 100);
      const angle = n * Math.PI * 6;
      const speed = 1 + _bgSmoothNoise(p.x * 0.003, p.y * 0.003 + 50) * 1.5;
      p.x += Math.cos(angle) * speed; p.y += Math.sin(angle) * speed; p.life -= 0.001;
      if (p.life <= 0 || p.x < 0 || p.x > W || p.y < 0 || p.y > H) { p.x = Math.random() * W; p.y = Math.random() * H; p.life = 1; }
      ctx.beginPath(); ctx.arc(p.x, p.y, 1, 0, Math.PI * 2);
      ctx.fillStyle = c; ctx.globalAlpha = p.life * 0.14; ctx.fill();
    });
    ctx.globalAlpha = 1;
    t++;
  }
  draw();
}

// The animation is a continuous requestAnimationFrame loop, so it is opt-out
// for anyone who wants the battery back. The pref is read here rather than in
// settings.js because this module loads first and the choice has to be known
// before the loop starts.
function _motionEnabled() {
  try {
    if (localStorage.getItem('zephyrus-bg-effect') === '0') return false;
  } catch (_) { /* private mode / storage disabled — fall through */ }
  try { return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
  catch (_) { return true; }
}

export function startBackgroundEffect() {
  if (document.getElementById('perlin-flow-canvas')) return;
  document.body.classList.add('bg-pattern-perlin-flow');
  // Respect prefers-reduced-motion and the user's toggle: static CSS layer
  // only, no canvas loops.
  if (_motionEnabled()) {
    try { _initPerlinFlow(); } catch (_) {}
  }
}

export function stopBackgroundEffect() {
  document.body.classList.remove('bg-pattern-perlin-flow');
  const canvas = document.getElementById('perlin-flow-canvas');
  if (canvas) canvas.remove();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startBackgroundEffect, { once: true });
} else {
  startBackgroundEffect();
}