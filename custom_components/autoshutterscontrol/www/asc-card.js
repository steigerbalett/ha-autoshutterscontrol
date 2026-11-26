// AutoShuttersControl for HA: dashboard cards. Plain web components, no build step.
//
//   type: custom:autoshutterscontrol-card         all or selected covers
//   type: custom:autoshutterscontrol-cover-card   one cover
//
// Loaded on every page by the integration. The data comes from the websocket
// command autoshutterscontrol/summary, the drives are ordinary cover services.

let VERSION = "";
try {
  VERSION = new URL(import.meta.url).searchParams.get("v") || "";
} catch (_err) {
  VERSION = "";
}

const TEXTS = {
  en: {
    name: "AutoShuttersControl",
    name_cover: "AutoShuttersControl cover",
    description: "Covers with position, target, reason and the next drives.",
    description_cover: "One cover with position, target, reason and the next drives.",
    not_loaded: "AutoShuttersControl is not loaded.",
    no_covers: "No covers.",
    unknown_cover: "This cover is not part of AutoShuttersControl.",
    target: "Target",
    because: "Not driven because",
    next_up: "Opens",
    next_down: "Closes",
    automatic: "Automatic",
    manual: "Manual",
    manual_until: "manual until",
    paused: "pause",
    simulation: "simulation",
    open: "Open",
    stop: "Stop",
    close: "Close",
    apply: "Drive to target",
    lockout: "The door is open. Close anyway?",
    lockout_yes: "Close",
    lockout_no: "Cancel",
    opening: "opening",
    closing: "closing",
    window: "Window",
    // Editor
    title: "Title",
    covers: "Covers (empty: all)",
    entity: "Cover",
    layout: "Layout",
    layout_grid: "Grid",
    layout_list: "List",
    layout_compact: "Compact",
    show_times: "Show next drives",
    show_reason: "Show target and reason",
    show_buttons: "Show buttons",
    show_automatic: "Show automatic switch",
    confirm_lockout: "Ask before closing at an open door",
  },
  de: {
    name: "AutoShuttersControl",
    name_cover: "AutoShuttersControl Rollladen",
    description: "Rollläden mit Position, Ziel, Begründung und den nächsten Fahrten.",
    description_cover: "Ein Rollladen mit Position, Ziel, Begründung und den nächsten Fahrten.",
    not_loaded: "AutoShuttersControl ist nicht geladen.",
    no_covers: "Keine Rollläden.",
    unknown_cover: "Dieser Rollladen gehört nicht zu AutoShuttersControl.",
    target: "Ziel",
    because: "Nicht gefahren wegen",
    next_up: "Öffnet",
    next_down: "Schließt",
    automatic: "Automatik",
    manual: "Hand",
    manual_until: "von Hand bis",
    paused: "Pause",
    simulation: "Simulation",
    open: "Öffnen",
    stop: "Stopp",
    close: "Schließen",
    apply: "Zum Ziel fahren",
    lockout: "Die Tür ist offen. Trotzdem schließen?",
    lockout_yes: "Schließen",
    lockout_no: "Abbrechen",
    opening: "öffnet",
    closing: "schließt",
    window: "Fenster",
    title: "Titel",
    covers: "Rollläden (leer: alle)",
    entity: "Rollladen",
    layout: "Aussehen",
    layout_grid: "Raster",
    layout_list: "Liste",
    layout_compact: "Kompakt",
    show_times: "Nächste Fahrten zeigen",
    show_reason: "Ziel und Begründung zeigen",
    show_buttons: "Knöpfe zeigen",
    show_automatic: "Schalter Automatik zeigen",
    confirm_lockout: "Vor dem Schließen bei offener Tür fragen",
  },
};

function lang(hass) {
  return (hass?.locale?.language || hass?.language || navigator.language || "en").slice(0, 2);
}

function texts(hass) {
  return TEXTS[lang(hass)] || TEXTS.en;
}

function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

// --- shared data -------------------------------------------------------------
// One request for all cards on the page, at most every 2 seconds.

const store = { data: null, error: null, time: 0, pending: null, listeners: new Set() };

async function fetchSummary(hass, force = false) {
  if (store.pending) return store.pending;
  if (!force && store.data && Date.now() - store.time < 2000) return store.data;
  store.pending = hass
    .callWS({ type: "autoshutterscontrol/summary" })
    .then((data) => {
      store.data = data;
      store.error = null;
      return data;
    })
    .catch((err) => {
      store.error = err?.message || String(err);
      return null;
    })
    .finally(() => {
      store.time = Date.now();
      store.pending = null;
      store.listeners.forEach((fn) => fn());
    });
  return store.pending;
}

// --- the shutter -------------------------------------------------------------

function shutterSvg(position, target, awning, moving) {
  const pos = Math.max(0, Math.min(100, Number(position ?? 0)));
  if (awning) {
    // Seen from the side: the cloth goes out with the position
    const len = 10 + pos * 0.8;
    const tx = target === null || target === undefined ? null : 10 + Number(target) * 0.8;
    return `
      <svg viewBox="0 0 100 70" class="shutter" aria-hidden="true">
        <rect x="2" y="4" width="6" height="62" rx="1" class="wall"/>
        <rect x="6" y="6" width="8" height="6" rx="2" class="box"/>
        <line x1="10" y1="10" x2="${len}" y2="${10 + pos * 0.25}" class="cloth ${moving}"/>
        <line x1="10" y1="40" x2="${len}" y2="${10 + pos * 0.25}" class="arm"/>
        ${tx === null ? "" : `<circle cx="${tx}" cy="${10 + Number(target) * 0.25}" r="2.2" class="target"/>`}
      </svg>`;
  }
  // Seen from the front: 0 % closed, 100 % open
  const top = 10;
  const height = 54;
  const curtain = (height * (100 - pos)) / 100;
  const slats = [];
  for (let y = top + curtain - 4; y > top; y -= 4.5) {
    slats.push(`<line x1="12" x2="88" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="slat"/>`);
  }
  const ty =
    target === null || target === undefined
      ? null
      : top + (height * (100 - Math.max(0, Math.min(100, Number(target))))) / 100;
  return `
    <svg viewBox="0 0 100 70" class="shutter" aria-hidden="true">
      <rect x="8" y="4" width="84" height="64" rx="3" class="frame"/>
      <rect x="12" y="${top}" width="76" height="${height}" class="glass"/>
      <line x1="50" x2="50" y1="${top}" y2="${top + height}" class="mullion"/>
      <g class="curtain ${moving}">
        <rect x="12" y="${top}" width="76" height="${curtain.toFixed(1)}" class="cloth"/>
        ${slats.join("")}
      </g>
      <rect x="6" y="2" width="88" height="8" rx="2" class="box"/>
      ${ty === null ? "" : `<line x1="4" x2="96" y1="${ty.toFixed(1)}" y2="${ty.toFixed(1)}" class="target"/>`}
    </svg>`;
}

const STYLE = `
  :host { display: block; }
  ha-card { padding: 12px; overflow: hidden; }
  .title { font-size: 18px; font-weight: 500; margin: 2px 4px 10px; }
  .grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  .list, .compact { display: grid; gap: 6px; }
  .cover { border: 1px solid var(--divider-color); border-radius: 10px; padding: 8px;
    display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .list .cover { flex-direction: row; align-items: center; gap: 10px; }
  .compact .cover { flex-direction: row; align-items: center; gap: 8px; padding: 4px 8px; border: 0;
    border-bottom: 1px solid var(--divider-color); border-radius: 0; }
  .single .cover { border: 0; padding: 0; }
  .shutter { width: 100%; max-height: 120px; }
  .list .shutter { width: 64px; flex: none; }
  .compact .shutter { width: 34px; flex: none; }
  .single .shutter { max-height: 160px; }
  .info { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
  .compact .info { flex-direction: row; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .name { font-weight: 500; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pos { font-size: 22px; font-weight: 400; }
  .compact .pos { font-size: 14px; }
  .line { font-size: 12px; color: var(--secondary-text-color); }
  .flag { font-size: 12px; color: var(--warning-color, #db7c00); }
  .block { font-size: 12px; color: var(--error-color, #db4437); }
  .row { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  button { font: inherit; font-size: 13px; cursor: pointer; border-radius: 8px; padding: 4px 8px;
    border: 1px solid var(--divider-color); background: var(--card-background-color, #fff);
    color: var(--primary-text-color); min-width: 34px; }
  button:hover { border-color: var(--primary-color); }
  button.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  button.warn { background: var(--error-color, #db4437); color: #fff; border-color: transparent; }
  .confirm { font-size: 13px; padding: 6px; border-radius: 8px;
    background: rgba(219, 68, 55, .12); display: flex; flex-direction: column; gap: 6px; }
  .frame { fill: var(--secondary-background-color, #eee); stroke: var(--divider-color); }
  .glass { fill: rgba(120, 170, 220, .25); }
  .mullion { stroke: var(--divider-color); stroke-width: 1; }
  .box, .wall { fill: var(--secondary-text-color); opacity: .55; }
  .cloth { fill: var(--primary-color); opacity: .85; stroke: var(--primary-color); stroke-width: 3; stroke-linecap: round; }
  .arm { stroke: var(--secondary-text-color); stroke-width: 1.2; }
  .slat { stroke: rgba(0, 0, 0, .25); stroke-width: .8; }
  .curtain rect { transition: height .8s ease; }
  .curtain.opening, .curtain.closing, .cloth.opening, .cloth.closing { animation: asc-pulse 1.2s ease-in-out infinite; }
  @keyframes asc-pulse { 50% { opacity: .55; } }
  .target { stroke: var(--warning-color, #db7c00); stroke-width: 1.4; stroke-dasharray: 3 2; fill: var(--warning-color, #db7c00); }
  .err { color: var(--error-color, #db4437); padding: 8px; }
`;

// --- the cards ---------------------------------------------------------------

class AscBaseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._confirm = null;
    this._states = {};
    this._listener = () => this._render();
    this.shadowRoot.addEventListener("click", (ev) => this._click(ev));
  }

  setConfig(config) {
    this._config = { ...this.defaults(), ...(config || {}) };
    this._render();
  }

  defaults() {
    return {
      layout: "grid",
      show_times: true,
      show_reason: true,
      show_buttons: true,
      show_automatic: true,
      confirm_lockout: true,
    };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // A member changed its state: fetch again (the store throttles)
    let changed = first;
    for (const c of this._covers() || []) {
      const state = hass.states[c.entity_id];
      if (this._states[c.entity_id] !== state) {
        this._states[c.entity_id] = state;
        changed = true;
      }
      for (const id of Object.values(c.entities || {})) {
        if (id && this._states[id] !== hass.states[id]) {
          this._states[id] = hass.states[id];
          changed = true;
        }
      }
    }
    if (changed) {
      fetchSummary(hass);
      this._render();
    }
  }

  connectedCallback() {
    store.listeners.add(this._listener);
    this._timer = window.setInterval(() => this._hass && fetchSummary(this._hass, true), 30000);
    if (this._hass) fetchSummary(this._hass);
    this._render();
  }

  disconnectedCallback() {
    store.listeners.delete(this._listener);
    window.clearInterval(this._timer);
  }

  getCardSize() {
    const n = (this._covers() || []).length || 1;
    if (this._config?.layout === "compact") return 1 + n;
    if (this._config?.layout === "list") return 1 + 2 * n;
    return 1 + 3 * Math.ceil(n / 3);
  }

  _position(c) {
    // Live position from the state of the cover, otherwise from the summary
    const state = this._hass?.states[c.entity_id];
    const raw = state?.attributes?.current_position;
    if (raw === undefined || raw === null) return c.position;
    return c.invert ? 100 - raw : raw;
  }

  _moving(c) {
    const state = this._hass?.states[c.entity_id]?.state;
    return state === "opening" || state === "closing" ? state : "";
  }

  _time(iso) {
    if (!iso) return "–";
    const date = new Date(iso);
    const today = new Date();
    const sameDay = date.toDateString() === today.toDateString();
    const opts = sameDay
      ? { hour: "2-digit", minute: "2-digit" }
      : { weekday: "short", hour: "2-digit", minute: "2-digit" };
    return date.toLocaleString(this._hass?.locale?.language || "en", opts);
  }

  _coverHtml(c) {
    const t = texts(this._hass);
    const cfg = this._config;
    const pos = this._position(c);
    const moving = this._moving(c);
    const pct = pos === null || pos === undefined ? "–" : `${Math.round(pos)} %`;
    const lines = [];
    if (cfg.show_reason) {
      const target =
        c.target_position === null || c.target_position === undefined
          ? esc(c.target)
          : `${esc(c.target)} ${Math.round(c.target_position)} %`;
      lines.push(`<span class="line">${t.target}: ${target}${c.target_reason ? ` · ${esc(c.target_reason)}` : ""}</span>`);
      if (c.blocked_by) lines.push(`<span class="block">${t.because}: ${esc(c.blocked_by)}</span>`);
    }
    if (cfg.show_times && cfg.layout !== "compact") {
      lines.push(
        `<span class="line">${t.next_up} ${this._time(c.next_up)} · ${t.next_down} ${this._time(c.next_down)}</span>`,
      );
    }
    const flags = [];
    if (moving) flags.push(t[moving]);
    if (c.override_until) flags.push(`${t.manual_until} ${this._time(c.override_until)}`);
    if (c.paused) flags.push(t.paused);
    if (c.simulation) flags.push(t.simulation);
    if (c.window && c.lockout_now) flags.push(`${t.window}: ${esc(c.window)}`);
    if (flags.length) lines.push(`<span class="flag">${flags.join(" · ")}</span>`);

    const id = esc(c.entity_id);
    let controls = "";
    if (cfg.show_buttons) {
      controls += `
        <button data-act="open" data-id="${id}" title="${t.open}">▲</button>
        <button data-act="stop" data-id="${id}" title="${t.stop}">■</button>
        <button data-act="close" data-id="${id}" title="${t.close}">▼</button>`;
    }
    const auto = c.entities?.automatic;
    if (cfg.show_automatic && auto) {
      const on = c.automatic && !c.override_until;
      controls += `<button data-act="automatic" data-id="${id}" class="${on ? "on" : ""}"
        title="${on ? t.automatic : t.manual}">${on ? "A" : "✋"}</button>`;
    }
    if (cfg.show_buttons && c.entities?.apply_target && cfg.layout !== "compact") {
      controls += `<button data-act="apply" data-id="${id}" title="${t.apply}">⤓</button>`;
    }
    let confirm = "";
    if (this._confirm === c.entity_id) {
      confirm = `<div class="confirm">${t.lockout}<div class="row">
        <button class="warn" data-act="close_anyway" data-id="${id}">${t.lockout_yes}</button>
        <button data-act="cancel" data-id="${id}">${t.lockout_no}</button></div></div>`;
    }
    return `
      <div class="cover">
        ${shutterSvg(pos, cfg.show_reason ? c.target_position : null, c.awning, moving)}
        <div class="info">
          <span class="name" data-more="${id}">${esc(c.name)}</span>
          <span class="pos">${pct}</span>
          ${lines.join("")}
          ${controls ? `<div class="row">${controls}</div>` : ""}
          ${confirm}
        </div>
      </div>`;
  }

  _click(ev) {
    const more = ev.target.closest("[data-more]");
    if (more) {
      const event = new Event("hass-more-info", { bubbles: true, composed: true });
      event.detail = { entityId: more.dataset.more };
      this.dispatchEvent(event);
      return;
    }
    const button = ev.target.closest("button[data-act]");
    if (!button || !this._hass) return;
    ev.stopPropagation();
    const id = button.dataset.id;
    const c = (this._covers() || []).find((x) => x.entity_id === id);
    if (!c) return;
    const act = button.dataset.act;
    const call = (domain, service, data) => this._hass.callService(domain, service, data);
    if (act === "open") call("cover", "open_cover", { entity_id: id });
    else if (act === "stop") call("cover", "stop_cover", { entity_id: id });
    else if (act === "close" || act === "close_anyway") {
      if (act === "close" && this._config.confirm_lockout && c.lockout_now && !c.awning) {
        this._confirm = id;
        this._render();
        return;
      }
      this._confirm = null;
      call("cover", "close_cover", { entity_id: id });
    } else if (act === "cancel") {
      this._confirm = null;
    } else if (act === "automatic") {
      if (c.override_until && c.entities.clear_override) {
        call("button", "press", { entity_id: c.entities.clear_override });
      } else {
        call("switch", c.automatic ? "turn_off" : "turn_on", { entity_id: c.entities.automatic });
      }
    } else if (act === "apply") {
      call("button", "press", { entity_id: c.entities.apply_target });
    }
    this._render();
    window.setTimeout(() => this._hass && fetchSummary(this._hass, true), 800);
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const t = texts(this._hass);
    let body;
    if (store.error && !store.data) {
      body = `<div class="err">${t.not_loaded} ${esc(store.error)}</div>`;
    } else if (!store.data) {
      body = "";
    } else {
      body = this._body(t);
    }
    const title = this._config.title ? `<div class="title">${esc(this._config.title)}</div>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${title}${body}</ha-card>`;
  }
}

class AscCard extends AscBaseCard {
  static getConfigElement() {
    return document.createElement("autoshutterscontrol-card-editor");
  }

  static getStubConfig() {
    return { layout: "grid" };
  }

  _covers() {
    const all = store.data?.covers;
    if (!all) return null;
    const wanted = this._config?.covers;
    if (!wanted || !wanted.length) return all;
    return wanted.map((id) => all.find((c) => c.entity_id === id)).filter(Boolean);
  }

  _body(t) {
    const covers = this._covers();
    if (!covers.length) return `<div class="line">${t.no_covers}</div>`;
    const layout = ["grid", "list", "compact"].includes(this._config.layout) ? this._config.layout : "grid";
    return `<div class="${layout}">${covers.map((c) => this._coverHtml(c)).join("")}</div>`;
  }
}

class AscCoverCard extends AscBaseCard {
  static getConfigElement() {
    const el = document.createElement("autoshutterscontrol-card-editor");
    el.single = true;
    return el;
  }

  static getStubConfig(hass) {
    const first = store.data?.covers?.[0]?.entity_id;
    if (!first && hass) fetchSummary(hass);
    return { entity: first || "" };
  }

  setConfig(config) {
    super.setConfig({ ...config, layout: "single" });
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return { columns: 6, rows: 4, min_columns: 4, min_rows: 3 };
  }

  _covers() {
    const all = store.data?.covers;
    if (!all) return null;
    return all.filter((c) => c.entity_id === this._config?.entity);
  }

  _body(t) {
    const covers = this._covers();
    if (!covers.length) return `<div class="err">${t.unknown_cover}</div>`;
    return `<div class="single">${this._coverHtml(covers[0])}</div>`;
  }
}

// --- editor ------------------------------------------------------------------

class AscCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      fetchSummary(hass).then(() => this._render());
    }
    if (this._form) this._form.hass = hass;
  }

  _schema() {
    const t = texts(this._hass);
    const options = (store.data?.covers || []).map((c) => ({ value: c.entity_id, label: c.name }));
    const fields = [{ name: "title", selector: { text: {} } }];
    if (this.single) {
      fields.push({ name: "entity", required: true, selector: { select: { options, mode: "dropdown" } } });
    } else {
      fields.push({ name: "covers", selector: { select: { options, multiple: true, mode: "list" } } });
      fields.push({
        name: "layout",
        selector: {
          select: {
            mode: "dropdown",
            options: ["grid", "list", "compact"].map((v) => ({ value: v, label: t[`layout_${v}`] })),
          },
        },
      });
    }
    for (const key of ["show_reason", "show_times", "show_buttons", "show_automatic", "confirm_lockout"]) {
      fields.push({ name: key, selector: { boolean: {} } });
    }
    return fields;
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (field) => texts(this._hass)[field.name] || field.name;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const key of Object.keys(config)) {
          if (config[key] === "" || (Array.isArray(config[key]) && !config[key].length)) delete config[key];
        }
        if (this.single) delete config.layout;
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const defaults = {
      layout: "grid",
      show_times: true,
      show_reason: true,
      show_buttons: true,
      show_automatic: true,
      confirm_lockout: true,
    };
    const data = { ...defaults, ...this._config };
    if (this.single) delete data.layout;
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = data;
  }
}

for (const [tag, cls] of [
  ["autoshutterscontrol-card", AscCard],
  ["autoshutterscontrol-cover-card", AscCoverCard],
  ["autoshutterscontrol-card-editor", AscCardEditor],
]) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
}

window.customCards = window.customCards || [];
{
  const t = texts(null);
  for (const [type, name, description] of [
    ["autoshutterscontrol-card", t.name, t.description],
    ["autoshutterscontrol-cover-card", t.name_cover, t.description_cover],
  ]) {
    if (!window.customCards.some((c) => c.type === type)) {
      window.customCards.push({ type, name, description, preview: true, documentationURL:
        "https://github.com/steigerbalett/ha-autoshutterscontrol" });
    }
  }
}

console.info(`%c AutoShuttersControl card %c ${VERSION} `, "background:#03a9f4;color:#fff", "");
