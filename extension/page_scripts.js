// Injected into pages via chrome.scripting.executeScript (never loaded as a
// normal content script). Two entry points: summarizePage() builds the
// grouped-forms/visible-flag DOM summary that decide_next_action.py expects,
// executeAction(action) runs one action from the fixed enum.
//
// Must stay self-contained — executeScript serializes the function and runs
// it inside the target page/frame, so it can't close over anything from the
// extension's own scope.

function sentinelIsVisible(el) {
  if (!el.isConnected) return false;
  const style = getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
  if (!el.offsetParent && style.position !== 'fixed') return false;

  // CSS-visible isn't the same as actually reachable — a page dimmed
  // behind a modal overlay still passes every check above. Sample the
  // element's own center point and require the topmost thing rendered
  // there to be this element (or a descendant of it, e.g. an icon/span
  // inside a button); anything else means an overlay/dialog is actually
  // covering it.
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  if (cx >= 0 && cy >= 0 && cx <= window.innerWidth && cy <= window.innerHeight) {
    const topEl = document.elementFromPoint(cx, cy);
    if (topEl && topEl !== el && !el.contains(topEl)) return false;
  }

  return true;
}

function sentinelDescribeField(el) {
  let label = null;
  if (el.labels && el.labels.length) label = el.labels[0].innerText.trim();
  else if (el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
  return {
    tag: el.tagName.toLowerCase(),
    type: el.type || null,
    name: el.name || null,
    id: el.id || null,
    placeholder: el.placeholder || null,
    label,
    visible: sentinelIsVisible(el),
  };
}

function sentinelDescribeButton(el) {
  return {
    text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
    visible: sentinelIsVisible(el),
  };
}

// Dedup preferring a visible copy over a hidden one with the same key —
// this is the fix for the session-6 bug where a hidden duplicate form was
// silently winning over the real visible one.
function sentinelDedup(items, keyFn) {
  const map = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!key) continue;
    const existing = map.get(key);
    if (!existing || (!existing.visible && item.visible)) {
      map.set(key, item);
    }
  }
  return Array.from(map.values());
}

// Known naming conventions across modal/popup/consent libraries (Bootstrap,
// Magnific Popup, SweetAlert, react-modal, cookie-consent widgets, and
// site-specific "capture form" patterns like Adzuna's) — checked against
// class, id, AND data-js/data-testid, since sites split naming across any
// of these (e.g. class="apply-capture-form" but data-js="apply-capture-overlay").
const MODAL_KEYWORDS = [
  'modal', 'popup', 'overlay', 'dialog', 'lightbox', 'drawer', 'mfp-',
  'swal', 'sweetalert', 'consent', 'cookie', 'gdpr', 'capture-form',
  'capture-overlay', 'interstitial', 'backdrop',
];
const MODAL_ATTR_SELECTOR = [
  '[role="dialog"]', '[role="alertdialog"]', '[aria-modal="true"]',
  ...MODAL_KEYWORDS.flatMap((k) => [
    `[class*="${k}" i]`, `[id*="${k}" i]`, `[data-js*="${k}" i]`, `[data-testid*="${k}" i]`,
  ]),
].join(', ');

// Fallback for overlays with no recognizable naming at all (common with
// utility-CSS frameworks like Tailwind, e.g. class="fixed inset-0 z-40
// bg-black/50" — zero modal-ish words anywhere). Flags any fixed/absolute
// element that's either a near-full-viewport backdrop or an edge-anchored
// banner with a high z-index, purely from computed layout, no names needed.
function sentinelLooksLikeStructuralOverlay(el) {
  const style = getComputedStyle(el);
  if (style.position !== 'fixed' && style.position !== 'absolute') return false;
  const zIndex = parseInt(style.zIndex, 10);
  if (isNaN(zIndex) || zIndex < 10) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const coversViewport = rect.width >= window.innerWidth * 0.85 && rect.height >= window.innerHeight * 0.4;
  const isEdgeBanner = (rect.top <= 0 || rect.bottom >= window.innerHeight) && rect.width >= window.innerWidth * 0.85;
  return coversViewport || isEdgeBanner;
}

function sentinelDescribeModal(el, buttonKey, detectedVia) {
  const buttons = Array.from(el.querySelectorAll('button, input[type="submit"], [role="button"]')).map(sentinelDescribeButton);
  const links = Array.from(el.querySelectorAll('a')).map((a) => ({
    text: (a.innerText || '').trim(),
    href: a.href,
    visible: sentinelIsVisible(a),
  }));
  return {
    class: el.className || null,
    detected_via: detectedVia,
    visible: sentinelIsVisible(el),
    buttons: sentinelDedup(buttons, buttonKey),
    links: sentinelDedup(links, buttonKey),
  };
}

function summarizePage() {
  const fieldKey = (f) => `${f.tag}|${f.type}|${f.name || f.id || ''}`;
  const buttonKey = (b) => b.text ? b.text.toLowerCase() : null;

  // Modal/popup/overlay detection, two layers: named (ARIA + known class/id/
  // data-js keywords across common libraries) and structural (fixed/absolute
  // + high z-index + backdrop-or-banner-shaped, for sites with no
  // recognizable naming at all, e.g. bare Tailwind utility classes).
  const namedMatches = Array.from(document.querySelectorAll(MODAL_ATTR_SELECTOR)).map((el) => ({ el, via: 'known_pattern' }));
  const structuralMatches = Array.from(document.querySelectorAll('body *'))
    .filter(sentinelLooksLikeStructuralOverlay)
    .map((el) => ({ el, via: 'structural' }));

  const seen = new Set();
  const modalCandidates = [];
  for (const m of [...namedMatches, ...structuralMatches]) {
    if (seen.has(m.el)) continue;
    seen.add(m.el);
    modalCandidates.push(m);
  }
  const modalRoots = modalCandidates.filter(
    (m) => !modalCandidates.some((other) => other.el !== m.el && other.el.contains(m.el))
  );
  const modals = modalRoots.map((m) => sentinelDescribeModal(m.el, buttonKey, m.via));

  const forms = Array.from(document.querySelectorAll('form')).map((form) => {
    const fields = Array.from(form.querySelectorAll('input, select, textarea')).map(sentinelDescribeField);
    const submitButtons = Array.from(form.querySelectorAll('button, input[type="submit"]')).map(sentinelDescribeButton);
    return {
      visible: sentinelIsVisible(form),
      fields: sentinelDedup(fields, fieldKey),
      submit_buttons: sentinelDedup(submitButtons, buttonKey),
    };
  });

  const allFields = Array.from(document.querySelectorAll('input, select, textarea'));
  const looseFields = sentinelDedup(
    allFields.filter((el) => !el.closest('form')).map(sentinelDescribeField),
    fieldKey
  );

  const allButtons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'));
  const looseButtons = sentinelDedup(
    allButtons.filter((el) => !el.closest('form')).map(sentinelDescribeButton),
    buttonKey
  );

  const links = sentinelDedup(
    Array.from(document.querySelectorAll('a')).map((el) => ({
      text: (el.innerText || '').trim(),
      href: el.href,
      visible: sentinelIsVisible(el),
    })),
    buttonKey
  ).slice(0, 50);

  return {
    url: location.href,
    title: document.title,
    modals,
    forms,
    loose_fields: looseFields,
    buttons: looseButtons,
    links,
  };
}

// action: { type: click|fill|select|dismiss|wait|navigate, target, value }
function executeAction(action) {
  function findTarget(target) {
    const candidates = Array.from(
      document.querySelectorAll('button, a, input, select, textarea, [role="button"]')
    );
    const norm = (s) => (s || '').trim().toLowerCase();
    const t = norm(target);
    if (!t) return null;

    let exact = null;
    let partial = null;
    for (const el of candidates) {
      if (!sentinelIsVisible(el)) continue;
      const text = norm(
        el.innerText || el.value || el.placeholder ||
        el.getAttribute('aria-label') || el.name
      );
      if (!text) continue;
      if (text === t && !exact) exact = el;
      else if (!partial && (text.includes(t) || t.includes(text))) partial = el;
    }
    return exact || partial;
  }

  if (action.type === 'wait') {
    return { ok: true };
  }

  const el = findTarget(action.target);
  if (!el && action.type !== 'navigate') {
    return { ok: false, error: 'target_not_found' };
  }

  switch (action.type) {
    case 'click':
    case 'dismiss':
      el.click();
      return { ok: true };
    case 'fill':
      el.focus();
      el.value = action.value || '';
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: true };
    case 'select':
      el.value = action.value || '';
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: true };
    case 'navigate':
      location.href = action.value || action.target;
      return { ok: true };
    default:
      return { ok: false, error: 'unknown_action_type' };
  }
}
