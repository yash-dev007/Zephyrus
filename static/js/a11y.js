// Accessibility enhancements for keyboard + screen-reader users.
//
// Several primary controls in Zephyrus are authored as click-only <div>s
// (most notably the whole sidebar navigation: New Chat, Search, Brain,
// Calendar, Compare, Cookbook, Deep Research, Gallery, Library, Notes,
// Tasks, Theme, plus the account row). <div>s are not in the tab order and
// are not announced as buttons, so keyboard and screen-reader users cannot
// reach or operate them.
//
// This module enhances those rows in place — making them focusable
// (tabindex=0), announcing them as buttons when it's safe to do so, and
// activating them with Enter / Space — without changing how they look or
// how they behave for mouse users. The visible focus ring already exists in
// style.css (`.list-item:focus-visible`); it simply never fired because the
// rows were never focusable.

(function () {
  'use strict';

  // Click-as-button rows we want reachable by keyboard.
  var ROW_SELECTOR = ['#sidebar .list-item', '#user-bar-profile'].join(',');

  // Native interactive descendants. If a row contains one of these we must
  // NOT give the row role="button" — a button inside a button is invalid
  // (axe "nested-interactive") and confuses screen readers. Such rows still
  // become focusable + Enter/Space-activatable, just without the role.
  var NESTED_INTERACTIVE =
    'a[href],button,input,select,textarea,[contenteditable="true"],[tabindex]:not([tabindex="-1"])';

  function enhanceRow(el) {
    if (!el || el.nodeType !== 1 || el.dataset.a11yEnhanced === '1') return;
    var tag = el.tagName;
    // Leave genuine native controls alone.
    if (tag === 'BUTTON' || tag === 'A' || tag === 'INPUT' ||
        tag === 'SELECT' || tag === 'TEXTAREA') return;

    el.dataset.a11yEnhanced = '1';
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    el.setAttribute('data-a11y-activatable', '1');

    if (!el.querySelector(NESTED_INTERACTIVE) && !el.hasAttribute('role')) {
      el.setAttribute('role', 'button');
    }

    // Guarantee an accessible name. Visible text normally supplies it; fall
    // back to the title attribute for icon-only rows.
    if (!el.getAttribute('aria-label') &&
        !(el.textContent || '').trim() &&
        el.getAttribute('title')) {
      el.setAttribute('aria-label', el.getAttribute('title'));
    }
  }

  function enhanceAll(root) {
    (root || document).querySelectorAll(ROW_SELECTOR).forEach(enhanceRow);
  }

  // ---- Modal dialogs -----------------------------------------------------
  // Zephyrus modals are plain <div class="modal-content"> boxes. Marking
  // them as ARIA dialogs lets screen readers announce them as dialogs and
  // exempts their content from the "all content in landmarks" rule. We also
  // normalize the modal title to heading level 2 (one below the page <h1>)
  // so heading order stays valid no matter which tag the markup uses.
  var titleSeq = 0;
  // Each modal "kind" is a container selector plus where to find its title
  // heading. Standard modals use .modal-content/.modal-header; the docked
  // Notes pane uses its own markup.
  var MODAL_KINDS = [
    {
      sel: '.modal-content',
      heading: '.modal-header h1, .modal-header h2, .modal-header h3, ' +
               '.modal-header h4, .modal-header h5, .modal-header h6'
    },
    { sel: '.notes-pane', heading: '.notes-pane-title' }
  ];
  var MODAL_SEL = MODAL_KINDS.map(function (k) { return k.sel; }).join(',');

  function enhanceModal(mc, headingSel) {
    if (!mc || mc.nodeType !== 1 || mc.dataset.a11yDialog === '1') return;
    mc.dataset.a11yDialog = '1';
    if (!mc.hasAttribute('role')) mc.setAttribute('role', 'dialog');
    if (!mc.hasAttribute('aria-modal')) mc.setAttribute('aria-modal', 'true');

    var heading = headingSel && mc.querySelector(headingSel);
    if (heading) {
      if (!heading.id) heading.id = 'a11y-modal-title-' + (++titleSeq);
      if (!mc.hasAttribute('aria-labelledby')) {
        mc.setAttribute('aria-labelledby', heading.id);
      }
      // Modal titles sit one level below the page <h1>; normalize so heading
      // order stays valid regardless of the tag the markup happens to use.
      if (!heading.hasAttribute('aria-level')) heading.setAttribute('aria-level', '2');
    }
  }

  function enhanceModals(root) {
    var scope = root || document;
    MODAL_KINDS.forEach(function (k) {
      scope.querySelectorAll(k.sel).forEach(function (mc) { enhanceModal(mc, k.heading); });
    });
  }

  function headingSelFor(el) {
    for (var i = 0; i < MODAL_KINDS.length; i++) {
      if (el.matches(MODAL_KINDS[i].sel)) return MODAL_KINDS[i].heading;
    }
    return null;
  }

  // Delegated keyboard activation. We only act when the focused element is
  // itself an enhanced row (keydown targets the focused element), so a press
  // on a nested native button is left to the browser's own handling.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
    var el = e.target;
    if (!el || !el.matches || !el.matches('[data-a11y-activatable]')) return;
    e.preventDefault(); // Space would otherwise scroll the page
    el.click();
  });

  // ---- Focus containment -------------------------------------------------
  // spec.md names this as a functional invariant: "Modals open, close, trap
  // focus, and restore it." Before this, Escape closed every overlay but Tab
  // walked straight out of the panel into the sidebar after half a dozen stops
  // (Settings never took focus at all), so the focus rings the rest of the app
  // draws were unreachable exactly where keyboard use matters most.
  //
  // There is no single "open a modal" function to hook — seventeen call sites
  // across nine modules just do `classList.remove('hidden')`, and five windows
  // are created fresh each time. So the stack is derived from the DOM rather
  // than from the open path: an observer watches for the class/style writes
  // that open and close a window, and a reconcile pass diffs the open set.
  // That is the same observer the dialog-marking above already uses.
  // `.notes-pane-backdrop` is deliberately absent: it is a full-viewport
  // `pointer-events: none` positioning wrapper that exists at every viewport,
  // and the Notes rail is a docked pane by design decision — the chat stays
  // usable beside it — so trapping focus there would be wrong even on mobile.
  var DIALOG_SEL = [
    '.modal',
    '.modal-overlay',
    '.search-overlay',
    '.styled-confirm-overlay',
    '.attach-crop-panel'
  ].join(',');
  // Classes that mean "this window is not accepting interaction". `.hidden` is
  // the app's own convention; `.modal-minimized` is what modalManager applies
  // when a window is docked to the rail.
  var CLOSED_CLASSES = ['hidden', 'modal-minimized'];
  // Everything that can hold a tab stop. `[tabindex="-1"]` is excluded by the
  // attribute test; the rest is filtered by box size below, which is what
  // catches a control inside a collapsed panel.
  var FOCUSABLE_SEL = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    'summary',
    '[contenteditable=""]',
    '[contenteditable="true"]',
    '[tabindex]'
  ].join(',');
  var TEXT_ENTRY_SEL = 'input:not([type="hidden"]),textarea,select,[contenteditable=""]';

  var openStack = [];              // open dialogs, in the order they opened
  var openers = new WeakMap();    // dialog -> the element focused before it opened
  var lastOutsideFocus = null;     // most recent focus target outside any dialog
  var lastTrigger = null;          // the control actually pressed, + when
  var reconcileQueued = false;
  // A press starts a short window in which it is still the reason a dialog is
  // opening. Compare fetches its model list before building the picker, so the
  // gap between the click and the window is a network round trip; anything
  // longer than this and the press is stale.
  var TRIGGER_TTL_MS = 4000;

  function isOpenDialog(el) {
    if (!el || !el.isConnected) return false;
    for (var i = 0; i < CLOSED_CLASSES.length; i++) {
      if (el.classList.contains(CLOSED_CLASSES[i])) return false;
    }
    var cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    var r = el.getBoundingClientRect();
    return !(r.width === 0 && r.height === 0);
  }

  function isTextEntry(el) {
    return !!el && el.matches && el.matches(TEXT_ENTRY_SEL);
  }

  function tabbables(root) {
    var found = root.querySelectorAll(FOCUSABLE_SEL);
    var out = [];
    for (var i = 0; i < found.length; i++) {
      var el = found[i];
      if (el.disabled) continue;
      if (el.getAttribute('tabindex') === '-1') continue;
      if (el.getAttribute('aria-hidden') === 'true') continue;
      // A control inside a collapsed sub-panel is not reachable by Tab either.
      if (el.closest('.hidden, .modal-minimized')) continue;
      var r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      out.push(el);
    }
    return out;
  }

  // The panel is what a screen reader treats as the dialog body; the container
  // around it is the scrim. Focusing the panel directly is the last resort for
  // a window with no controls at all (a pure confirmation), and it needs a
  // tabindex to be focusable.
  function panelOf(root) {
    var panel = root.querySelector('.modal-content, .notes-pane, .search-box');
    if (panel) return panel;
    return root.classList && root.classList.contains('modal-content') ? root : null;
  }

  function focusPanel(panel) {
    if (!panel) return false;
    if (!panel.hasAttribute('tabindex')) panel.setAttribute('tabindex', '-1');
    panel.focus();
    return panel === document.activeElement;
  }

  function topDialog() {
    return openStack.length ? openStack[openStack.length - 1] : null;
  }

  function insideOpenDialog(el) {
    for (var i = 0; i < openStack.length; i++) {
      if (openStack[i] && openStack[i].contains(el)) return true;
    }
    return false;
  }

  // The nearest enclosing dialog that is currently accepting interaction.
  // Asked of the DOM rather than of openStack because a module that focuses
  // its own first field does it synchronously, before the reconcile pass has
  // run — at that moment the window is on screen but not yet on the stack, and
  // a stack-only test would mistake the window's own field for page chrome.
  function openDialogAncestor(el) {
    if (!el || !el.closest) return null;
    var d = el.closest(DIALOG_SEL);
    return d && isOpenDialog(d) ? d : null;
  }

  // The element to send focus back to when a window closes, in descending order
  // of how well it answers "what did the user just press?":
  //   1. the control they pressed, if the window is still the consequence of
  //      that press. This has to outrank document.activeElement, because a
  //      module can legitimately move focus while it sets itself up — the
  //      Compare flow focuses the composer before it opens its model picker —
  //      and the promise of the invariant is that focus goes back to the
  //      trigger, not to wherever the module happened to leave it.
  //   2. whatever last held focus outside a window.
  // Never something inside a window: Gallery focuses its own search field
  // synchronously, so "activeElement" is the field that is about to be
  // destroyed, and restoring to it would be a no-op.
  function currentOpener() {
    if (lastTrigger &&
        (typeof performance === 'undefined' || performance.now() - lastTrigger.at < TRIGGER_TTL_MS) &&
        lastTrigger.el.isConnected && !openDialogAncestor(lastTrigger.el)) {
      var trigger = lastTrigger.el;
      lastTrigger = null;
      return trigger;
    }
    var ae = document.activeElement;
    if (ae && ae !== document.body && ae !== document.documentElement && !openDialogAncestor(ae)) {
      return ae;
    }
    if (lastOutsideFocus && lastOutsideFocus.isConnected && !openDialogAncestor(lastOutsideFocus)) {
      return lastOutsideFocus;
    }
    return null;
  }

  // Move focus into a freshly opened window. Anything the module already
  // focused (Gallery's search field, the palette's input) is left alone, so
  // this never overrides a deliberate choice — it only fills the gap for the
  // windows that used to leave focus on the nav row that opened them.
  //
  // Where it lands depends on what kind of window it is. A search-shaped
  // window (Gallery, Cookbook, Library, Tasks) starts in its field, because
  // that is the only thing the user came there to do. A nav-shaped one
  // (Settings is a stack of tabs behind a vertical list) starts on that nav,
  // because dropping the caret into a select three screens down would mean
  // Shift-Tabbing back out to reach the tabs at all.
  var DIALOG_NAV_SEL = '.settings-nav-item,.memory-tab,.gallery-tab,.lib-tab,' +
    '.cookbook-tab,.cal-view-toggle,.notes-view-toggle,[role="tablist"] > *';

  function focusIntoDialog(dialog) {
    var ae = document.activeElement;
    if (ae && dialog.contains(ae)) return;
    var list = tabbables(dialog);
    if (!list.length) { focusPanel(panelOf(dialog)); return; }
    var target = list[0];
    var nav = dialog.querySelector(DIALOG_NAV_SEL);
    if (nav && list.indexOf(nav) !== -1) {
      target = nav;
    } else {
      for (var i = 0; i < list.length; i++) {
        if (isTextEntry(list[i])) { target = list[i]; break; }
      }
    }
    target.focus();
  }

  // Bottom-to-top. Two rules, both of which the DOM alone cannot answer: a
  // dialog that contains another open dialog is underneath it (a confirm over
  // a tool window, the image cropper over the gallery), and among siblings the
  // higher z-index is on top. modalManager hands out a monotonic z from a
  // bring-to-front counter, so this follows the user's own stacking order.
  function dialogOrder(a, b) {
    if (a === b) return 0;
    if (a.contains(b)) return 1;
    if (b.contains(a)) return -1;
    var za = parseInt(getComputedStyle(a).zIndex, 10);
    var zb = parseInt(getComputedStyle(b).zIndex, 10);
    if (Number.isFinite(za) && Number.isFinite(zb) && za !== zb) return za - zb;
    return 0;
  }

  function reconcileDialogs() {
    reconcileQueued = false;
    var live = [];
    var candidates = document.querySelectorAll(DIALOG_SEL);
    for (var i = 0; i < candidates.length; i++) {
      if (isOpenDialog(candidates[i])) live.push(candidates[i]);
    }
    live.sort(dialogOrder);

    // Captured before anything moves, so a stack that opens in one frame
    // (a tool window plus its model overlay) still records what the user
    // actually clicked.
    var passOpener = currentOpener();
    var prevTop = topDialog();
    var prevTopOpener = prevTop ? openers.get(prevTop) : null;
    var closedTopmost = false;
    var added = false;

    for (var j = 0; j < live.length; j++) {
      if (openStack.indexOf(live[j]) !== -1) continue;
      openers.set(live[j], passOpener);
      added = true;
    }
    for (var s = openStack.length - 1; s >= 0; s--) {
      if (live.indexOf(openStack[s]) !== -1) continue;
      if (openStack[s] === prevTop) closedTopmost = true;
      openers.delete(openStack[s]);
    }
    openStack = live;

    if (closedTopmost) {
      if (live.length) {
        // An inner window closed and a tool window is still up — hand focus
        // back to that window. focusIntoDialog is a no-op when focus is already
        // inside it, so this cannot steal from a control the user has reached.
        focusIntoDialog(topDialog());
      } else {
        // Nothing is modal any more, so focus returns to whatever opened the
        // window — the restore half of the invariant in spec.md.
        var opener = prevTopOpener;
        if (opener && opener.isConnected && typeof opener.focus === 'function') {
          opener.focus();
        }
      }
    } else if (added) {
      focusIntoDialog(topDialog());
    }
  }

  function queueReconcile() {
    if (reconcileQueued) return;
    reconcileQueued = true;
    requestAnimationFrame(reconcileDialogs);
  }

  // Tab is contained at the boundaries. Capture phase so a module that stops
  // propagation on keydown cannot let focus walk out of the panel.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab') return;
    var top = topDialog();
    if (!top) return;
    var list = tabbables(top);
    if (!list.length) {
      e.preventDefault();
      focusPanel(panelOf(top));
      return;
    }
    var ae = document.activeElement;
    if (!ae || !top.contains(ae) || list.indexOf(ae) === -1) {
      e.preventDefault();
      list[0].focus();
      return;
    }
    var idx = list.indexOf(ae);
    if (e.shiftKey && idx === 0) {
      e.preventDefault();
      list[list.length - 1].focus();
    } else if (!e.shiftKey && idx === list.length - 1) {
      e.preventDefault();
      list[0].focus();
    }
  }, true);

  // Safety net for focus that arrives from outside without a Tab key — a
  // programmatic .focus(), a browser find-on-page jump, a restored session.
  // Also the bookkeeping that makes restore work: the last focus target that
  // landed on page chrome rather than inside a window is the thing that
  // window has to hand focus back to.
  document.addEventListener('focusin', function (e) {
    var t = e.target;
    if (!openDialogAncestor(t)) lastOutsideFocus = t;
    var top = topDialog();
    if (!top) return;
    if (top.contains(t)) return;
    var list = tabbables(top);
    if (list.length) list[0].focus();
    else focusPanel(panelOf(top));
  });

  // A pointer press or a keyboard activation is the other way a dialog gets
  // opened, and it is the one the restore has to answer for. On some rows the
  // press target is a child of the control rather than the control itself.
  function noteTrigger(target) {
    var t = target;
    if (!t || !t.closest) return;
    var opener = t.closest('a[href],button,input,select,textarea,summary,[tabindex],[data-a11y-activatable]');
    if (!opener) return;
    lastTrigger = { el: opener, at: typeof performance === 'undefined' ? 0 : performance.now() };
    lastOutsideFocus = opener;
  }

  document.addEventListener('mousedown', function (e) { noteTrigger(e.target); }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') noteTrigger(e.target);
  }, true);

  function mutationTouchesDialog(rec) {
    if (rec.type === 'attributes') {
      var t = rec.target;
      return !!(t && t.nodeType === 1 &&
        t.matches(DIALOG_SEL + ',.modal-content,.notes-pane,.modal-header'));
    }
    var nodes = rec.addedNodes.length ? rec.addedNodes : rec.removedNodes;
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (n.nodeType !== 1) continue;
      if (n.matches && n.matches(DIALOG_SEL)) return true;
      if (n.querySelector && n.querySelector(DIALOG_SEL)) return true;
    }
    return false;
  }

  function watchDialogs() {
    if (!('MutationObserver' in window)) return;
    new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        if (mutationTouchesDialog(muts[i])) { queueReconcile(); return; }
      }
    }).observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style']
    });
  }

  function init() {
    enhanceAll(document);
    enhanceModals(document);
    watchDialogs();
    reconcileDialogs();

    // Sidebar content is re-rendered as the user navigates (session lists,
    // tool sub-rows, etc.). Watch for new rows and enhance them too.
    var sidebar = document.getElementById('sidebar');
    if (sidebar && 'MutationObserver' in window) {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var added = muts[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches(ROW_SELECTOR)) enhanceRow(n);
            if (n.querySelectorAll) enhanceAll(n);
          }
        }
      }).observe(sidebar, { childList: true, subtree: true });
    }

    // Some modals (Notes, Tasks, …) are injected at runtime, usually as
    // direct children of <body>. Catch those without paying for a deep
    // subtree observer over the whole document.
    if ('MutationObserver' in window) {
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var added = muts[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType !== 1) continue;
            if (n.matches && n.matches(MODAL_SEL)) enhanceModal(n, headingSelFor(n));
            if (n.querySelector && n.querySelector(MODAL_SEL)) enhanceModals(n);
          }
        }
      }).observe(document.body, { childList: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
