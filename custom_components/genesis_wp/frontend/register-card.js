// Register in the scoped registry Home Assistant installs during startup.
export function registerCard(tag, element, metadata) {
  const register = () => {
    const registry = window.customElements;
    if (!registry.get('hui-view')) return false;
    if (!registry.get(tag)) registry.define(tag, element);
    return true;
  };
  if (!register()) {
    const started = Date.now();
    let warned = false;
    const timer = setInterval(() => {
      if (register()) clearInterval(timer);
      else if (!warned && Date.now() - started > 30000) {
        warned = true;
        console.warn(tag + ': waiting for Home Assistant hui-view registry');
      }
    }, 250);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some(card => card.type === tag))
    window.customCards.push({type: tag, ...metadata});
}
