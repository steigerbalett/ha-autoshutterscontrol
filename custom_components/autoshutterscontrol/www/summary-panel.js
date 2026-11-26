// AutoShuttersControl for HA: overview page (as the ASC Configuration and
// Information Summary in FHEM). Plain web component, no build step.

const TEXTS = {
  en: {
    title: "AutoShuttersControl",
    summary: "Configuration and information summary",
    linked: "Linked sensors and values",
    refresh: "Refresh",
    updated: "Updated",
    covers: "Cover",
    profile: "Profile",
    next_up: "Next opening",
    next_down: "Next closing",
    up_mode: "Morning by",
    down_mode: "Evening by",
    presence: "Residents up / down",
    shading_mode: "Shading",
    party: "Party mode",
    lockout: "Lock-out",
    last: "Last drive",
    position: "Position",
    target: "Target",
    blocked: "Not driven because",
    shading: "Shading info",
    window: "Window",
    residents: "Residents",
    state: "State",
    entity: "Entity",
    value: "Value",
    setting: "Setting",
    used_by: "Used by",
    changed: "Changed",
    global: "Global",
    on: "on",
    off: "off",
    sun: "Sun",
    azimuth: "azimuth",
    elevation: "elevation",
    forecast: "Forecast today",
    house: "House status",
    switches: "Switches",
    protections: "Protection",
    none: "–",
    missing: "missing",
    override: "manual until",
    paused: "pause",
    automatic_off: "automatic off",
    simulation: "simulation",
    hot_day: "hot day",
    quiet: "quiet hours",
    error: "AutoShuttersControl is not loaded.",
    tab_overview: "Overview",
    tab_edit: "Edit covers",
    sw: {
      automatic: "Automatic",
      weekend_times: "Weekend times",
      morning: "Morning drive",
      evening: "Evening drive",
      pause: "Pause",
      comfort: "Comfort",
      shading: "Shading",
      self_defense: "Self defense",
      party: "Party",
      advent: "Advent",
      hardware_lock: "Hardware lock",
      simulation: "Simulation",
      holiday: "Holiday",
    },
    prot: { rain: "rain", wind: "wind", frost: "frost", rain_window: "water" },
  },
  de: {
    title: "AutoShuttersControl",
    summary: "Übersicht der Einstellungen und Zustände",
    linked: "Verknüpfte Sensoren und Werte",
    refresh: "Aktualisieren",
    updated: "Stand",
    covers: "Rollladen",
    profile: "Profil",
    next_up: "Nächste Öffnung",
    next_down: "Nächstes Schließen",
    up_mode: "Morgens nach",
    down_mode: "Abends nach",
    presence: "Bewohner auf / zu",
    shading_mode: "Beschattung",
    party: "Partymodus",
    lockout: "Aussperrschutz",
    last: "Letzte Fahrt",
    position: "Position",
    target: "Ziel",
    blocked: "Nicht gefahren wegen",
    shading: "Beschattung Info",
    window: "Fenster",
    residents: "Bewohner",
    state: "Zustand",
    entity: "Entität",
    value: "Wert",
    setting: "Einstellung",
    used_by: "Verwendet von",
    changed: "Geändert",
    global: "Global",
    on: "an",
    off: "aus",
    sun: "Sonne",
    azimuth: "Richtung",
    elevation: "Höhe",
    forecast: "Vorhersage heute",
    house: "Haus-Status",
    switches: "Schalter",
    protections: "Schutz",
    none: "–",
    missing: "fehlt",
    override: "Hand bis",
    paused: "Pause",
    automatic_off: "Automatik aus",
    simulation: "Simulation",
    hot_day: "heißer Tag",
    quiet: "Ruhezeit",
    error: "AutoShuttersControl ist nicht geladen.",
    tab_overview: "Übersicht",
    tab_edit: "Rollläden bearbeiten",
    sw: {
      automatic: "Automatik",
      weekend_times: "Wochenendzeiten",
      morning: "Morgenfahrt",
      evening: "Abendfahrt",
      pause: "Pause",
      comfort: "Komfort",
      shading: "Beschattung",
      self_defense: "Selbstschutz",
      party: "Party",
      advent: "Advent",
      hardware_lock: "Hardware-Sperre",
      simulation: "Simulation",
      holiday: "Urlaub",
    },
    prot: { rain: "Regen", wind: "Wind", frost: "Frost", rain_window: "Wasser" },
  },
};

// The editor tab lives in its own file (same version as this one)
let editorLoaded = null;
function loadEditor() {
  if (!editorLoaded) {
    editorLoaded = import(new URL(`./editor.js${new URL(import.meta.url).search}`, import.meta.url).href);
  }
  return editorLoaded;
}

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

class AscSummaryPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._timer = null;
    this.shadowRoot.addEventListener("click", (ev) => this._click(ev));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._editor) this._editor.hass = hass;
    if (first) this._load();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
    this._render();
  }

  connectedCallback() {
    this._timer = window.setInterval(() => this._tab !== "edit" && this._load(), 10000);
    if (this._hass) this._load();
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
    this._timer = null;
  }

  get _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return TEXTS[lang] || TEXTS.en;
  }

  async _load() {
    if (!this._hass) return;
    try {
      this._data = await this._hass.callWS({ type: "autoshutterscontrol/summary" });
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._render();
  }

  _click(ev) {
    const target = ev.target.closest("[data-entity]");
    if (target) {
      const event = new Event("hass-more-info", { bubbles: true, composed: true });
      event.detail = { entityId: target.dataset.entity };
      this.dispatchEvent(event);
      return;
    }
    const tab = ev.target.closest("[data-tab]");
    if (tab) {
      this._tab = tab.dataset.tab;
      if (this._tab === "edit") {
        loadEditor().then(() => this._render());
      } else {
        this._load();
      }
      this._render();
      return;
    }
    if (ev.target.closest("#refresh")) {
      if (this._tab === "edit" && this._editor) this._editor.reload();
      else this._load();
    }
    if (ev.target.closest("#menu")) {
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    }
  }

  _time(iso, withDate = true) {
    if (!iso) return this._t.none;
    const date = new Date(iso);
    const lang = this._hass?.locale?.language || this._hass?.language || "en";
    const opts = withDate
      ? { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }
      : { hour: "2-digit", minute: "2-digit" };
    return date.toLocaleString(lang, opts);
  }

  _bool(value) {
    return value ? this._t.on : this._t.off;
  }

  _num(value, unit = "") {
    if (value === null || value === undefined) return this._t.none;
    return `${Math.round(value * 10) / 10}${unit}`;
  }

  _entity(id, name) {
    return `<a class="entity" data-entity="${esc(id)}">${esc(name || id)}</a>`;
  }

  _coverRows() {
    const t = this._t;
    return this._data.covers
      .map((c) => {
        const flags = [];
        if (!c.automatic) flags.push(t.automatic_off);
        if (c.paused) flags.push(t.paused);
        if (c.simulation) flags.push(t.simulation);
        if (c.override_until) flags.push(`${t.override} ${this._time(c.override_until, false)}`);
        if (c.hot_day) flags.push(t.hot_day);
        if (c.quiet) flags.push(t.quiet);
        for (const p of c.protections) flags.push(t.prot[p] || p);
        const shading = c.shading_since
          ? `${esc(c.shading)} – ${this._time(c.shading_since, false)}`
          : esc(c.shading);
        const last = c.last_reason
          ? `${esc(c.last_reason)} → ${this._num(c.last_position, " %")}<br><small>${this._time(
              c.last_time
            )}</small>`
          : t.none;
        const target = `${esc(c.target ?? t.none)} ${this._num(c.target_position, " %")}<br><small>${esc(
          c.target_reason ?? ""
        )}</small>`;
        return `<tr>
          <td class="name">${this._entity(c.entity_id, c.name)}${
          c.profile ? `<br><small>${esc(c.profile)}</small>` : ""
        }${flags.length ? `<br><span class="flags">${esc(flags.join(", "))}</span>` : ""}</td>
          <td>${this._time(c.next_up)}</td>
          <td>${this._time(c.next_down)}</td>
          <td>${esc(c.up_mode)}</td>
          <td>${esc(c.down_mode)}</td>
          <td>${esc(c.presence_up)} / ${esc(c.presence_down)}</td>
          <td>${esc(c.shading_mode)}</td>
          <td>${this._bool(c.party)}</td>
          <td>${esc(c.lockout)}</td>
          <td>${last}</td>
          <td>${this._num(c.position, " %")}${
          c.tilt !== null && c.tilt !== undefined ? `<br><small>${this._num(c.tilt, " %")}</small>` : ""
        }</td>
          <td>${target}</td>
          <td>${esc(c.blocked_by ?? t.none)}</td>
          <td>${shading}</td>
          <td>${esc(c.window ?? t.none)}</td>
          <td>${esc(c.residents ?? t.none)}</td>
        </tr>`;
      })
      .join("");
  }

  _entityRows() {
    const t = this._t;
    return this._data.entities
      .map((e) => {
        const value =
          e.state === null
            ? `<span class="missing">${t.missing}</span>`
            : `${esc(e.state)}${e.unit ? " " + esc(e.unit) : ""}`;
        const users = e.used_by.map((u) => (u === "" ? t.global : u)).join(", ");
        return `<tr>
          <td>${this._entity(e.entity_id, e.name)}<br><small>${esc(e.entity_id)}</small></td>
          <td class="value">${value}</td>
          <td>${esc(e.setting_name)}</td>
          <td>${esc(users)}</td>
          <td>${this._time(e.changed)}</td>
        </tr>`;
      })
      .join("");
  }

  _globalInfo() {
    const t = this._t;
    const g = this._data.global;
    const switches = Object.entries(g.switches)
      .map(
        ([k, v]) => `<span class="chip ${v ? "on" : ""}">${esc(t.sw[k] || k)}: ${this._bool(v)}</span>`
      )
      .join("");
    const prot = Object.entries(g.protections)
      .filter(([, v]) => v)
      .map(([k]) => t.prot[k] || k)
      .join(", ");
    return `<div class="info">
        <span><b>${t.sun}</b> ${t.azimuth} ${this._num(g.sun_azimuth, "°")}, ${t.elevation} ${this._num(
      g.sun_elevation,
      "°"
    )}</span>
        <span><b>${t.forecast}</b> ${this._num(g.forecast, " °C")}${
      g.forecast_condition ? " " + esc(g.forecast_condition) : ""
    }</span>
        <span><b>${t.house}</b> ${esc(g.house_status ?? t.none)}</span>
        <span><b>${t.protections}</b> ${esc(prot || t.none)}</span>
      </div>
      <div class="chips">${switches}</div>`;
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = this._t;
    // Keep the horizontal scroll position of the tables
    const scroll = [...this.shadowRoot.querySelectorAll(".scroll")].map((el) => el.scrollLeft);
    let body;
    if (this._error) {
      body = `<div class="card"><p class="missing">${esc(t.error)} ${esc(this._error)}</p></div>`;
    } else if (!this._data) {
      body = "";
    } else {
      body = `
        <div class="card">
          <h2>${t.summary}</h2>
          ${this._globalInfo()}
          <div class="scroll"><table>
            <thead><tr>
              <th>${t.covers}</th><th>${t.next_up}</th><th>${t.next_down}</th>
              <th>${t.up_mode}</th><th>${t.down_mode}</th><th>${t.presence}</th>
              <th>${t.shading_mode}</th><th>${t.party}</th><th>${t.lockout}</th>
              <th>${t.last}</th><th>${t.position}</th><th>${t.target}</th><th>${t.blocked}</th>
              <th>${t.shading}</th><th>${t.window}</th><th>${t.residents}</th>
            </tr></thead>
            <tbody>${this._coverRows()}</tbody>
          </table></div>
        </div>
        <div class="card">
          <h2>${t.linked}</h2>
          <div class="scroll"><table>
            <thead><tr>
              <th>${t.entity}</th><th>${t.value}</th><th>${t.setting}</th><th>${t.used_by}</th>
              <th>${t.changed}</th>
            </tr></thead>
            <tbody>${this._entityRows()}</tbody>
          </table></div>
          <p class="updated">${t.updated}: ${this._time(this._data.time)}</p>
        </div>`;
    }
    const editing = this._tab === "edit";
    if (editing) body = "";
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; min-height: 100vh; background: var(--primary-background-color);
          color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        header { display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px;
          background: var(--app-header-background-color, var(--primary-color));
          color: var(--app-header-text-color, #fff); font-size: 20px; }
        header .grow { flex: 1; }
        button { background: none; border: 0; color: inherit; cursor: pointer; font: inherit;
          font-size: 14px; padding: 8px; border-radius: 4px; }
        button:hover { background: rgba(255,255,255,.15); }
        #menu { display: ${this._narrow ? "inline-block" : "none"}; font-size: 22px; }
        main { padding: 16px; display: grid; gap: 16px; }
        .card { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none); border: 1px solid var(--divider-color);
          padding: 16px; overflow: hidden; }
        h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
        .scroll { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; font-size: 13px; }
        th, td { text-align: left; vertical-align: top; padding: 6px 8px;
          border-bottom: 1px solid var(--divider-color); white-space: nowrap; }
        th { font-weight: 500; color: var(--secondary-text-color); }
        tbody tr:nth-child(odd) { background: var(--table-row-alternative-background-color, rgba(127,127,127,.06)); }
        small, .updated { color: var(--secondary-text-color); }
        .entity { color: var(--primary-color); cursor: pointer; }
        .flags { color: var(--warning-color, #db7c00); font-size: 12px; }
        .missing { color: var(--error-color, #db4437); }
        .value { font-weight: 500; }
        .info { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-bottom: 8px; font-size: 14px; }
        .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        .chip { font-size: 12px; padding: 2px 8px; border-radius: 10px; border: 1px solid var(--divider-color);
          color: var(--secondary-text-color); }
        .chip.on { color: var(--primary-text-color); border-color: var(--primary-color); }
        .tab { opacity: .75; border-bottom: 2px solid transparent; border-radius: 0; }
        .tab.active { opacity: 1; border-bottom-color: currentColor; }
      </style>
      <header>
        <button id="menu" title="Menu">☰</button>
        <span class="grow">${t.title}</span>
        <button class="tab ${editing ? "" : "active"}" data-tab="overview">${t.tab_overview}</button>
        <button class="tab ${editing ? "active" : ""}" data-tab="edit">${t.tab_edit}</button>
        <button id="refresh">${t.refresh}</button>
      </header>
      <main>${body}</main>`;
    if (editing && customElements.get("asc-editor")) {
      if (!this._editor) this._editor = document.createElement("asc-editor");
      this._editor.hass = this._hass;
      this.shadowRoot.querySelector("main").appendChild(this._editor);
    }
    this.shadowRoot.querySelectorAll(".scroll").forEach((el, i) => {
      el.scrollLeft = scroll[i] || 0;
    });
  }
}

if (!customElements.get("asc-summary-panel")) {
  customElements.define("asc-summary-panel", AscSummaryPanel);
}
