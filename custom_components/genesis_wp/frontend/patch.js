// DHF-REQ: genesis-wp-ha/requirement-22
// Render diffing for shadow roots. A hass update must not replace the element under the
// pointer, or the click that should open more-info is lost: a node replaced between
// mousedown and mouseup sends the click to a common ancestor instead. patch() keeps the DOM
// when the markup is unchanged and otherwise reconciles it in place: text and attribute
// values are updated, and a node whose shape changed (different node name or type) is
// replaced on its own, so its siblings and ancestors (the tab strip, the clicked value) stay.
const KEEP = {DETAILS: ['open']};

// Opt-in diagnostics: localStorage genesis_wp_debug = 1 logs renders, routes and clicks.
export function debug(...args) {
  let on = false;
  try { on = globalThis.localStorage?.getItem('genesis_wp_debug') === '1'; } catch { on = false; }
  if (on) console.debug('[genesis-wp]', ...args);
}

const adopt = (live, node) => live.ownerDocument?.importNode ? live.ownerDocument.importNode(node, true) : node;

// Reconciles live's children with next's. Returns how many nodes were replaced, added or
// removed; 0 means every existing node was kept.
export function morph(live, next) {
  const a = [...live.childNodes], b = [...next.childNodes];
  let changed = 0;
  for (let i = 0; i < b.length; i++) {
    const n = a[i], m = b[i];
    if (!n) { live.appendChild(adopt(live, m)); changed++; continue; }
    if (n.nodeType !== m.nodeType || n.nodeName !== m.nodeName) { live.replaceChild(adopt(live, m), n); changed++; continue; }
    if (n.nodeType !== 1) {
      if (n.nodeValue !== m.nodeValue) n.nodeValue = m.nodeValue;
      continue;
    }
    const keep = KEEP[n.nodeName] || [];
    for (const {name} of [...n.attributes])
      if (!m.hasAttribute(name) && !keep.includes(name)) n.removeAttribute(name);
    for (const {name, value} of [...m.attributes])
      if (n.getAttribute(name) !== value) n.setAttribute(name, value);
    changed += morph(n, m);
  }
  for (let i = b.length; i < a.length; i++) { live.removeChild(a[i]); changed++; }
  return changed;
}

// Returns 'unchanged', 'first' (initial innerHTML) or the number of nodes morph() swapped.
export function patch(root, html) {
  if (root.__genesisHtml === html) return 'unchanged';
  const first = root.__genesisHtml === undefined;
  root.__genesisHtml = html;
  if (first || typeof document === 'undefined') { root.innerHTML = html; return 'first'; }
  const template = document.createElement('template');
  template.innerHTML = html;
  return morph(root, template.content);
}
