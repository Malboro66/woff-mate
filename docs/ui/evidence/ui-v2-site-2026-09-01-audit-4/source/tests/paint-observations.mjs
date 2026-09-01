// Read-only DOM collector. Contrast is evaluated separately from actual
// texture crops; a textured surface is never treated as its flat CSS color.
export async function observePaint(tab) {
  return tab.playwright.evaluate(() => {
    const normalize = value => (value ?? "").replace(/\s+/g, " ").trim();
    const rect = element => { const r = element.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; };
    const indices = new Map();
    const layers = [];
    const chain = element => {
      if (!element) return null;
      if (indices.has(element)) return indices.get(element);
      const parent = chain(element.parentElement);
      const style = getComputedStyle(element);
      const index = layers.length;
      indices.set(element, index);
      layers.push({ parent, selector: `${element.tagName.toLowerCase()}.${element.className}`, rect: rect(element),
        background: style.backgroundColor, image: style.backgroundImage, size: style.backgroundSize,
        position: style.backgroundPosition, repeat: style.backgroundRepeat, origin: style.backgroundOrigin,
        border: [style.borderLeftWidth, style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth].map(Number.parseFloat),
        shadow: style.boxShadow, opacity: style.opacity, blend: style.backgroundBlendMode, filter: style.filter });
      return index;
    };
    const root = document.querySelector('.fixture-panel') ?? document.querySelector('.app-shell');
    const text = [...root.querySelectorAll('*')].filter(el => {
      const r = el.getBoundingClientRect(), s = getComputedStyle(el);
      return r.width > 1 && r.height > 1 && s.display !== 'none' && s.visibility !== 'hidden' &&
        !el.closest('[aria-hidden="true"],[hidden],.announcement') &&
        [...el.childNodes].some(node => node.nodeType === 3 && normalize(node.textContent));
    }).map(el => ({ text: normalize([...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ')).slice(0, 160),
      layer: chain(el), rect: rect(el), color: getComputedStyle(el).color,
      size: Number.parseFloat(getComputedStyle(el).fontSize), weight: getComputedStyle(el).fontWeight }));
    const shell = document.querySelector('.app-shell');
    const controls = [...root.querySelectorAll('button,a[href],select,input')].filter(el => {
      const r = el.getBoundingClientRect(), s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.borderTopStyle === 'solid' && Number.parseFloat(s.borderTopWidth) > 0 && s.borderTopColor !== 'rgba(0, 0, 0, 0)';
    }).map(el => ({ name: el.getAttribute('aria-label') || normalize(el.textContent), layer: chain(el), rect: rect(el), color: getComputedStyle(el).borderTopColor }));
    return { screen: shell.dataset.screenId, state: shell.dataset.fixtureState, profile: shell.dataset.fixtureViewport, layers, text, controls };
  });
}
