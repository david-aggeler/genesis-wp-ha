// DHF-REQ: genesis-wp-ha/requirement-22
// Render diffing for shadow roots. A hass update must not replace the element under the
// pointer, or the click that should open more-info is lost. patch() keeps the DOM when the
// markup is unchanged, and when only text or attribute values changed it updates them in
// place. A structural change (different element shape) falls back to a full replace.
const KEEP = {DETAILS: ['open']};

export function morph(live, next) {
  const a = live.childNodes, b = next.childNodes;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const n = a[i], m = b[i];
    if (n.nodeType !== m.nodeType || n.nodeName !== m.nodeName) return false;
    if (n.nodeType !== 1) {
      if (n.nodeValue !== m.nodeValue) n.nodeValue = m.nodeValue;
      continue;
    }
    const keep = KEEP[n.nodeName] || [];
    for (const {name} of [...n.attributes])
      if (!m.hasAttribute(name) && !keep.includes(name)) n.removeAttribute(name);
    for (const {name, value} of [...m.attributes])
      if (n.getAttribute(name) !== value) n.setAttribute(name, value);
    if (!morph(n, m)) return false;
  }
  return true;
}

// Returns true when the DOM was replaced, false when it was kept or patched in place.
export function patch(root, html) {
  if (root.__genesisHtml === html) return false;
  const first = root.__genesisHtml === undefined;
  root.__genesisHtml = html;
  if (!first && typeof document !== 'undefined') {
    const template = document.createElement('template');
    template.innerHTML = html;
    if (morph(root, template.content)) return false;
  }
  root.innerHTML = html;
  return true;
}
