// DHF-REQ: genesis-wp-ha/requirement-35
const tag = 'genesis-wp-panel';

if (!customElements.get(tag)) {
  let panel;
  try {
    // Named imports in the view turn missing dependency exports into a load error.
    ({GenesisWpPanel: panel} = await import('./genesis-wp-panel-view.js'));
    if (typeof panel !== 'function') {
      throw new TypeError('Missing GenesisWpPanel export');
    }
  } catch (error) {
    console.error('Genesis WP panel failed to load', error);
    panel = class extends HTMLElement {
      constructor() {
        super();
        this.attachShadow({mode: 'open'}).innerHTML =
          '<p role="alert" style="padding: 16px; color: var(--primary-text-color)">' +
          'Genesis WP panel failed to load. Reload the page with Ctrl+Shift+R (on a phone, clear the app cache)' +
          '</p>';
      }
    };
  }

  // Home Assistant may load the same element from another URL while the view loads.
  if (!customElements.get(tag)) {
    customElements.define(tag, panel);
  }
}
