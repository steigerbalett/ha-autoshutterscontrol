// AutoShuttersControl for HA: tab "Edit covers" of the sidebar page.
// Lists the covers, changes several at once (only the changed fields), adds,
// duplicates and removes covers. The values stay in the subentries.

const DOMAIN = "autoshutterscontrol";
const P = `component.${DOMAIN}.`;

const TEXTS = {
  en: {
    add: "Add covers",
    edit_selected: "Edit selected",
    delete_selected: "Remove selected",
    edit: "Edit",
    duplicate: "Duplicate",
    remove: "Remove",
    name: "Name",
    entity: "Cover",
    profile: "Profile",
    own: "Own values",
    no_profile: "–",
    keep: "unchanged",
    mixed: "different values",
    inherit: "Inherit",
    undo: "Undo",
    inherited: "inherited",
    from: { global: "global", profile: "profile", default: "default", preset: "preset" },
    save: "Save",
    saving: "Saving …",
    cancel: "Cancel",
    back: "Back",
    editing: "Edit",
    editing_n: "Edit {covers}",
    bulk_hint: "Only the fields you change are saved, for every selected cover. Everything else stays as it is.",
    condition_hint: "Conditions and actions are changed in the dialog (Reconfigure on the cover).",
    changes: "{n} changes",
    change1: "1 change",
    cover1: "1 cover",
    coverN: "{n} covers",
    saved: "Saved for {covers}.",
    nothing: "Nothing changed.",
    admin_only: "Only administrators can change covers.",
    add_title: "Add covers",
    add_hint: "Choose the covers. They drive by the global schedule from now on.",
    add_button: "Add",
    added: "{covers} added.",
    dup_title: "Duplicate “{name}”",
    dup_hint:
      "The new covers get the profile and the own values of this cover. Window contacts and room sensors are not copied.",
    dup_button: "Duplicate",
    filter: "Filter",
    none_left: "No other covers in Home Assistant.",
    confirm_remove: "Remove {covers} from AutoShuttersControl? The covers themselves stay in Home Assistant.",
    removed: "{covers} removed.",
    empty: "No covers yet.",
    error: "Error",
    loading: "Loading …",
    on: "on",
    off: "off",
  },
  de: {
    add: "Rollläden hinzufügen",
    edit_selected: "Auswahl bearbeiten",
    delete_selected: "Auswahl entfernen",
    edit: "Bearbeiten",
    duplicate: "Duplizieren",
    remove: "Entfernen",
    name: "Name",
    entity: "Rollladen",
    profile: "Profil",
    own: "Eigene Werte",
    no_profile: "–",
    keep: "unverändert",
    mixed: "verschiedene Werte",
    inherit: "Erben",
    undo: "Zurück",
    inherited: "geerbt",
    from: { global: "global", profile: "Profil", default: "Standard", preset: "Vorlage" },
    save: "Speichern",
    saving: "Speichere …",
    cancel: "Abbrechen",
    back: "Zurück",
    editing: "Bearbeiten",
    editing_n: "{covers} bearbeiten",
    bulk_hint:
      "Gespeichert werden nur die Felder, die du änderst, und zwar bei jedem ausgewählten Rollladen. Alles andere bleibt, wie es ist.",
    condition_hint: "Bedingungen und Aktionen änderst du im Dialog (Neu konfigurieren am Rollladen).",
    changes: "{n} Änderungen",
    change1: "1 Änderung",
    cover1: "1 Rollladen",
    coverN: "{n} Rollläden",
    saved: "Für {covers} gespeichert.",
    nothing: "Nichts geändert.",
    admin_only: "Nur Administratoren können Rollläden ändern.",
    add_title: "Rollläden hinzufügen",
    add_hint: "Wähle die Rollläden. Sie fahren ab jetzt nach dem globalen Zeitplan.",
    add_button: "Hinzufügen",
    added: "{covers} hinzugefügt.",
    dup_title: "„{name}“ duplizieren",
    dup_hint:
      "Die neuen Rollläden bekommen das Profil und die eigenen Werte dieses Rollladens. Fensterkontakte und Raumsensoren werden nicht kopiert.",
    dup_button: "Duplizieren",
    filter: "Filter",
    none_left: "Keine weiteren Rollläden in Home Assistant.",
    confirm_remove:
      "{covers} aus AutoShuttersControl entfernen? Die Rollläden selbst bleiben in Home Assistant.",
    removed: "{covers} entfernt.",
    empty: "Noch keine Rollläden.",
    error: "Fehler",
    loading: "Lade …",
    on: "an",
    off: "aus",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const fmt = (text, values) => text.replace(/\{(\w+)\}/g, (_m, k) => values[k] ?? "");

// "1 cover" / "3 covers"
const count = (t, n) => (n === 1 ? t.cover1 : fmt(t.coverN, { n }));

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

const MIXED = Symbol("mixed");

class AscEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._tr = {};
    this._selected = new Set();
    this._view = "list";
    this._message = null;
    this.shadowRoot.addEventListener("click", (ev) => this._click(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._change(ev));
    this.shadowRoot.addEventListener("input", (ev) => this._input(ev));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this.reload();
  }

  get _lang() {
    return (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
  }

  get _t() {
    return TEXTS[this._lang] || TEXTS.en;
  }

  async reload(tries = 6) {
    if (!this._hass) return;
    try {
      if (!Object.keys(this._tr).length) await this._loadTexts();
      this._data = await this._hass.callWS({ type: `${DOMAIN}/editor/data` });
      this._error = null;
    } catch (err) {
      // While the entry reloads after adding or removing covers
      if (tries > 0) {
        window.setTimeout(() => this.reload(tries - 1), 1500);
        return;
      }
      this._error = err?.message || String(err);
    }
    const known = new Set((this._data?.covers || []).map((c) => c.subentry_id));
    this._selected = new Set([...this._selected].filter((id) => known.has(id)));
    this._render();
  }

  async _loadTexts() {
    const language = this._hass.locale?.language || this._hass.language || "en";
    for (const category of ["config_subentries", "options", "selector"]) {
      try {
        const res = await this._hass.callWS({
          type: "frontend/get_translations",
          language,
          category,
          integration: [DOMAIN],
        });
        Object.assign(this._tr, res.resources || {});
      } catch (_err) {
        // Labels fall back to the keys
      }
    }
  }

  // --- texts of the integration -------------------------------------------

  _section(sec) {
    return (
      this._tr[`${P}config_subentries.cover.step.${sec}.title`] ||
      this._tr[`${P}options.step.init.menu_options.${sec}`] ||
      sec
    );
  }

  _label(field) {
    return (
      this._tr[`${P}config_subentries.cover.step.${field.section}.data.${field.key}`] ||
      this._tr[`${P}options.step.${field.section}.data.${field.key}`] ||
      field.key
    );
  }

  _help(field) {
    const text =
      this._tr[`${P}config_subentries.cover.step.${field.section}.data_description.${field.key}`] ||
      this._tr[`${P}options.step.${field.section}.data_description.${field.key}`] ||
      "";
    return text
      .split("\n")
      .filter((line) => !line.trim().startsWith("↳"))
      .join(" ")
      .replace(/\{[^}]*\}/g, "")
      .trim();
  }

  _option(key, value) {
    return this._tr[`${P}selector.${key}.options.${value}`] || value;
  }

  _show(field, value) {
    const t = this._t;
    if (value === null || value === undefined) return "–";
    switch (field.kind) {
      case "bool":
        return value ? t.on : t.off;
      case "time":
        return String(value).slice(0, 5);
      case "select":
        return this._option(field.key, value);
      case "multi":
        return value.length ? value.map((v) => this._option(field.key, v)).join(", ") : "–";
      case "entities":
        return value.length ? value.join(", ") : "–";
      default:
        return field.unit ? `${value} ${field.unit}` : String(value);
    }
  }

  // --- data helpers --------------------------------------------------------

  _cover(id) {
    return this._data.covers.find((c) => c.subentry_id === id);
  }

  _field(key) {
    return this._data.fields.find((f) => f.key === key);
  }

  _editCovers() {
    return this._edit.ids.map((id) => this._cover(id)).filter(Boolean);
  }

  // Own value of the selected covers: the value, undefined (all inherit) or MIXED
  _own(key) {
    const values = this._editCovers().map((c) => c.settings[key]);
    return values.every((v) => same(v, values[0])) ? values[0] : MIXED;
  }

  _inherited(key) {
    const values = this._editCovers().map((c) => c.inherited[key]);
    return values.every((v) => same(v, values[0])) ? values[0] : MIXED;
  }

  // Value shown in the field: a change, the common own value, or MIXED
  _value(key) {
    if (key in this._edit.changes) return this._edit.changes[key];
    const own = this._own(key);
    return own === undefined ? null : own;
  }

  _newCovers() {
    const taken = new Set(this._data.covers.map((c) => c.cover_entity));
    return Object.keys(this._hass.states)
      .filter((id) => id.startsWith("cover."))
      .filter((id) => !taken.has(id) && this._hass.entities?.[id]?.platform !== DOMAIN)
      .sort((a, b) => this._name(a).localeCompare(this._name(b)));
  }

  _name(entityId) {
    return this._hass.states[entityId]?.attributes?.friendly_name || entityId;
  }

  _profileName(id) {
    return this._data.profiles.find((p) => p.id === id)?.title || this._t.no_profile;
  }

  // --- events --------------------------------------------------------------

  _click(ev) {
    const el = ev.target.closest("[data-act]");
    if (!el) return;
    const act = el.dataset.act;
    const id = el.dataset.id;
    const t = this._t;
    this._message = act === "dismiss" ? null : this._message;
    switch (act) {
      case "edit":
        this._startEdit(id ? [id] : [...this._selected]);
        break;
      case "add":
        this._view = "add";
        this._pick = new Set();
        this._filter = "";
        this._addProfile = null;
        this._render();
        break;
      case "duplicate":
        this._view = "duplicate";
        this._source = id;
        this._pick = new Set();
        this._filter = "";
        this._render();
        break;
      case "remove":
        this._removeIds = id ? [id] : [...this._selected];
        this._render();
        break;
      case "remove_yes":
        this._run({ type: `${DOMAIN}/editor/delete`, subentry_ids: this._removeIds }, (res) =>
          fmt(t.removed, { covers: count(t, res.removed) })
        );
        this._removeIds = null;
        break;
      case "remove_no":
        this._removeIds = null;
        this._render();
        break;
      case "back":
        this._view = "list";
        this._render();
        break;
      case "section":
        this._edit.section = el.dataset.section;
        this._render();
        break;
      case "inherit":
        this._edit.changes[el.dataset.key] = null;
        this._renderField(el.dataset.key);
        break;
      case "undo":
        delete this._edit.changes[el.dataset.key];
        this._renderField(el.dataset.key);
        break;
      case "drop": {
        const key = el.dataset.key;
        const list = [...(this._value(key) === MIXED ? [] : this._value(key) || [])];
        list.splice(Number(el.dataset.index), 1);
        this._edit.changes[key] = list;
        this._renderField(key);
        break;
      }
      case "save":
        this._save();
        break;
      case "add_yes":
        this._run(
          {
            type: `${DOMAIN}/editor/add`,
            cover_entities: [...this._pick],
            ...(this._addProfile ? { profile: this._addProfile } : {}),
          },
          (res) => fmt(t.added, { covers: count(t, res.subentry_ids.length) })
        );
        break;
      case "dup_yes":
        this._run(
          { type: `${DOMAIN}/editor/duplicate`, subentry_id: this._source, cover_entities: [...this._pick] },
          (res) => fmt(t.added, { covers: count(t, res.subentry_ids.length) })
        );
        break;
      case "dismiss":
        this._render();
        break;
      default:
        break;
    }
  }

  _change(ev) {
    const el = ev.target;
    if (el.dataset.select !== undefined) {
      const id = el.dataset.select;
      if (id === "__all") {
        this._selected = el.checked ? new Set(this._data.covers.map((c) => c.subentry_id)) : new Set();
      } else if (el.checked) this._selected.add(id);
      else this._selected.delete(id);
      this._render();
      return;
    }
    if (el.dataset.pick !== undefined) {
      if (el.checked) this._pick.add(el.dataset.pick);
      else this._pick.delete(el.dataset.pick);
      this._updateButtons();
      return;
    }
    if (el.id === "add_profile") {
      this._addProfile = el.value || null;
      return;
    }
    if (el.id === "edit_profile") {
      if (el.value === "__keep") delete this._edit.profile;
      else this._edit.profile = el.value === "__none" ? null : el.value;
      this._updateButtons();
      return;
    }
    if (el.id === "edit_title") {
      this._edit.title = el.value;
      this._updateButtons();
      return;
    }
    const key = el.dataset.key;
    if (!key) return;
    const field = this._field(key);
    const changes = this._edit.changes;
    switch (field.kind) {
      case "bool":
      case "select":
        if (el.value === "__keep") delete changes[key];
        else if (el.value === "__inherit") changes[key] = null;
        else changes[key] = field.kind === "bool" ? el.value === "true" : el.value;
        break;
      case "int":
      case "float":
        changes[key] = el.value === "" ? null : Number(el.value);
        break;
      case "multi": {
        const boxes = this.shadowRoot.querySelectorAll(`input[data-key="${key}"]`);
        changes[key] = [...boxes].filter((b) => b.checked).map((b) => b.value);
        break;
      }
      case "entities": {
        const value = el.value.trim();
        if (!value) return;
        const current = this._value(key);
        const list = current === MIXED || !current ? [] : [...current];
        if (!list.includes(value)) list.push(value);
        changes[key] = list;
        break;
      }
      default:
        changes[key] = el.value.trim() === "" ? null : el.value.trim();
    }
    this._renderField(key);
  }

  _input(ev) {
    if (ev.target.id === "filter") {
      this._filter = ev.target.value.toLowerCase();
      this.shadowRoot.querySelectorAll("[data-row]").forEach((row) => {
        row.hidden = this._filter && !row.dataset.row.includes(this._filter);
      });
    }
  }

  async _run(msg, done) {
    try {
      const res = await this._hass.callWS(msg);
      this._message = { ok: true, text: done(res) };
      this._view = "list";
    } catch (err) {
      this._message = { ok: false, text: `${this._t.error}: ${err?.message || err}` };
    }
    this._render();
    window.setTimeout(() => this.reload(), 1200);
  }

  _startEdit(ids) {
    if (!ids.length) return;
    this._edit = { ids, changes: {}, section: this._data.sections[0] };
    this._view = "edit";
    this._render();
  }

  _changeCount() {
    const e = this._edit;
    let n = Object.keys(e.changes).length;
    if ("profile" in e) n += 1;
    if (e.title !== undefined && e.ids.length === 1 && e.title !== this._cover(e.ids[0])?.title) n += 1;
    return n;
  }

  async _save() {
    const t = this._t;
    const e = this._edit;
    const msg = { type: `${DOMAIN}/editor/update`, subentry_ids: e.ids, set: {}, clear: [] };
    for (const [key, value] of Object.entries(e.changes)) {
      if (value === null) msg.clear.push(key);
      else msg.set[key] = value;
    }
    if ("profile" in e) msg.profile = e.profile;
    if (e.title !== undefined && e.ids.length === 1 && e.title.trim()) msg.title = e.title.trim();
    if (!this._changeCount()) {
      this._message = { ok: true, text: t.nothing };
      this._view = "list";
      this._render();
      return;
    }
    this._saving = true;
    this._updateButtons();
    try {
      await this._hass.callWS(msg);
      this._message = { ok: true, text: fmt(t.saved, { covers: count(t, e.ids.length) }) };
      this._view = "list";
    } catch (err) {
      this._message = { ok: false, text: `${t.error}: ${err?.message || err}` };
    }
    this._saving = false;
    this._render();
    window.setTimeout(() => this.reload(), 600);
  }

  _updateButtons() {
    const t = this._t;
    const save = this.shadowRoot.querySelector('[data-act="save"]');
    if (save) {
      const n = this._changeCount();
      save.textContent = this._saving ? t.saving : `${t.save}${n ? ` (${n === 1 ? t.change1 : fmt(t.changes, { n })})` : ""}`;
      save.disabled = this._saving || !this._data.admin;
    }
    for (const act of ["add_yes", "dup_yes"]) {
      const button = this.shadowRoot.querySelector(`[data-act="${act}"]`);
      if (button) button.disabled = !this._pick.size || !this._data.admin;
    }
  }

  // --- rendering -----------------------------------------------------------

  _fieldHtml(field) {
    const t = this._t;
    const key = field.key;
    const value = this._value(key);
    const changed = key in this._edit.changes;
    const mixed = value === MIXED;
    const inh = this._inherited(key);
    const inhText =
      inh === MIXED
        ? t.mixed
        : `${this._show(field, inh[0])} (${t.from[inh[1]] || inh[1]})`;
    const isSet = !mixed && value !== null && value !== undefined;
    const ro = this._data.admin ? "" : "disabled";
    let input;
    const selectOptions = (options, current) => {
      const out = [];
      if (mixed && !changed) out.push(`<option value="__keep" selected>${t.mixed}</option>`);
      out.push(
        `<option value="__inherit" ${!mixed && (current === null || current === undefined) ? "selected" : ""}>${t.inherit} (${esc(inhText)})</option>`
      );
      for (const [v, label] of options) {
        out.push(`<option value="${esc(v)}" ${!mixed && same(current, v) ? "selected" : ""}>${esc(label)}</option>`);
      }
      return `<select data-key="${key}" ${ro}>${out.join("")}</select>`;
    };
    const placeholder = "";
    const inherited = mixed
      ? `<span class="unit">${t.mixed}</span>`
      : isSet
        ? ""
        : `<span class="unit">↳ ${esc(inhText)}</span>`;
    switch (field.kind) {
      case "bool":
        input = selectOptions(
          [
            [true, t.on],
            [false, t.off],
          ].map(([v, l]) => [String(v), l]),
          isSet ? String(value) : value
        );
        break;
      case "select":
        input = selectOptions(
          field.options.map((o) => [o, this._option(key, o)]),
          value
        );
        break;
      case "int":
      case "float":
        input = `<input type="number" data-key="${key}" ${ro}
          ${field.min !== null ? `min="${field.min}"` : ""} ${field.max !== null ? `max="${field.max}"` : ""}
          step="${field.kind === "int" ? Math.max(1, field.step || 1) : field.step || "any"}"
          value="${isSet ? esc(value) : ""}" placeholder="${esc(placeholder)}">
          ${field.unit ? `<span class="unit">${esc(field.unit)}</span>` : ""}${inherited}`;
        break;
      case "time":
        input = `<input type="time" data-key="${key}" ${ro} value="${isSet ? esc(String(value).slice(0, 5)) : ""}">
          ${inherited}`;
        break;
      case "multi": {
        const list = isSet ? value : [];
        input = `<div class="boxes">${field.options
          .map(
            (o) => `<label><input type="checkbox" data-key="${key}" value="${esc(o)}" ${ro}
              ${list.includes(o) ? "checked" : ""}> ${esc(this._option(key, o))}</label>`
          )
          .join("")}</div>${inherited}`;
        break;
      }
      case "entity":
        input = `<input type="text" data-key="${key}" list="dl_${key}" ${ro}
          value="${isSet ? esc(value) : ""}" placeholder="${esc(placeholder)}">${inherited}${this._datalist(field)}`;
        break;
      case "entities": {
        const list = isSet ? value : [];
        input = `<div class="chips">${list
          .map(
            (e, i) => `<span class="chip">${esc(this._name(e))}
              <button data-act="drop" data-key="${key}" data-index="${i}" ${ro} title="${esc(e)}">×</button></span>`
          )
          .join("")}</div>
          <input type="text" data-key="${key}" list="dl_${key}" ${ro} value=""
            placeholder="${esc(list.length ? "+" : placeholder)}">${inherited}${this._datalist(field)}`;
        break;
      }
      default:
        input = `<input type="text" data-key="${key}" ${ro} value="${isSet ? esc(value) : ""}"
          placeholder="${esc(placeholder)}">${inherited}`;
    }
    const help = this._help(field);
    const actions = [];
    if (changed) actions.push(`<button class="link" data-act="undo" data-key="${key}">${t.undo}</button>`);
    if (this._data.admin && (isSet || mixed) && !(changed && value === null)) {
      actions.push(`<button class="link" data-act="inherit" data-key="${key}">${t.inherit}</button>`);
    }
    return `
      <div class="field ${changed ? "changed" : ""}" data-field="${key}">
        <div class="label">${esc(this._label(field))}</div>
        <div class="input">${input}</div>
        <div class="actions">${actions.join("")}</div>
        ${help ? `<div class="help">${esc(help)}</div>` : ""}
      </div>`;
  }

  _datalist(field) {
    const domains = field.domains || [];
    const ids = Object.keys(this._hass.states)
      .filter((id) => !domains.length || domains.includes(id.split(".")[0]))
      .sort();
    return `<datalist id="dl_${field.key}">${ids
      .map((id) => `<option value="${esc(id)}">${esc(this._name(id))}</option>`)
      .join("")}</datalist>`;
  }

  _renderField(key) {
    // Replacing the field can fire blur and change again: only once at a time
    if (this._busy) return;
    this._busy = true;
    try {
      const old = this.shadowRoot.querySelector(`[data-field="${key}"]`);
      if (old?.isConnected) {
        const template = document.createElement("template");
        template.innerHTML = this._fieldHtml(this._field(key));
        old.replaceWith(template.content);
      }
    } finally {
      this._busy = false;
    }
    this._updateButtons();
  }

  _listHtml() {
    const t = this._t;
    const covers = this._data.covers;
    const admin = this._data.admin;
    const n = this._selected.size;
    const rows = covers
      .map((c) => {
        const own = Object.keys(c.settings).length;
        return `<tr>
          <td><input type="checkbox" data-select="${c.subentry_id}" ${this._selected.has(c.subentry_id) ? "checked" : ""}></td>
          <td><a class="link" data-act="edit" data-id="${c.subentry_id}">${esc(c.title)}</a></td>
          <td class="dim">${esc(c.cover_entity)}</td>
          <td>${esc(this._profileName(c.profile))}</td>
          <td>${own || "–"}</td>
          <td class="row-actions">
            <button data-act="edit" data-id="${c.subentry_id}">${t.edit}</button>
            <button data-act="duplicate" data-id="${c.subentry_id}" ${admin ? "" : "disabled"}>${t.duplicate}</button>
            <button data-act="remove" data-id="${c.subentry_id}" ${admin ? "" : "disabled"}>${t.remove}</button>
          </td>
        </tr>`;
      })
      .join("");
    const all = covers.length && n === covers.length ? "checked" : "";
    let confirm = "";
    if (this._removeIds) {
      confirm = `<div class="confirm">${esc(fmt(t.confirm_remove, { covers: count(t, this._removeIds.length) }))}
        <div class="bar"><button class="warn" data-act="remove_yes">${t.remove}</button>
        <button data-act="remove_no">${t.cancel}</button></div></div>`;
    }
    return `
      <div class="card">
        <div class="bar">
          <button class="primary" data-act="add" ${admin ? "" : "disabled"}>+ ${t.add}</button>
          <button data-act="edit" ${n ? "" : "disabled"}>${t.edit_selected}${n ? ` (${n})` : ""}</button>
          <button data-act="remove" ${n && admin ? "" : "disabled"}>${t.delete_selected}</button>
        </div>
        ${admin ? "" : `<p class="dim">${t.admin_only}</p>`}
        ${confirm}
        ${
          covers.length
            ? `<div class="scroll"><table>
          <thead><tr><th><input type="checkbox" data-select="__all" ${all}></th><th>${t.name}</th>
          <th>${t.entity}</th><th>${t.profile}</th><th>${t.own}</th><th></th></tr></thead>
          <tbody>${rows}</tbody></table></div>`
            : `<p class="dim">${t.empty}</p>`
        }
      </div>`;
  }

  _editHtml() {
    const t = this._t;
    const e = this._edit;
    const covers = this._editCovers();
    const single = covers.length === 1;
    const head = single
      ? `${t.editing}: ${esc(covers[0].title)}`
      : esc(fmt(t.editing_n, { covers: count(t, covers.length) }));
    const profiles = this._data.profiles;
    const ownProfile = covers.every((c) => c.profile === covers[0].profile) ? covers[0].profile : MIXED;
    const current = "profile" in e ? e.profile : ownProfile;
    const ro = this._data.admin ? "" : "disabled";
    const profileSelect = `<select id="edit_profile" ${ro}>
      ${!("profile" in e) && ownProfile === MIXED ? `<option value="__keep" selected>${t.mixed}</option>` : ""}
      <option value="__none" ${current === null || current === undefined ? "selected" : ""}>${t.no_profile}</option>
      ${profiles.map((p) => `<option value="${esc(p.id)}" ${current === p.id ? "selected" : ""}>${esc(p.title)}</option>`).join("")}
    </select>`;
    const tabs = this._data.sections
      .map(
        (sec) =>
          `<button class="sec ${sec === e.section ? "active" : ""}" data-act="section" data-section="${sec}">${esc(this._section(sec))}${
            this._data.fields.some((f) => f.section === sec && f.key in e.changes) ? " •" : ""
          }</button>`
      )
      .join("");
    const fields = this._data.fields.filter((f) => f.section === e.section).map((f) => this._fieldHtml(f));
    return `
      <div class="card">
        <div class="bar"><button data-act="back">← ${t.back}</button><h2>${head}</h2></div>
        ${single ? "" : `<p class="dim">${esc(covers.map((c) => c.title).join(", "))}</p><p class="hint">${t.bulk_hint}</p>`}
        ${single ? `<div class="field"><div class="label">${t.name}</div><div class="input"><input type="text" id="edit_title" ${ro} value="${esc(e.title ?? covers[0].title)}"></div><div></div></div>` : ""}
        <div class="field"><div class="label">${t.profile}</div><div class="input">${profileSelect}</div><div></div></div>
        <div class="tabs">${tabs}</div>
        <div class="fields">${fields.join("")}</div>
        <p class="dim">${t.condition_hint}</p>
        <div class="bar sticky">
          <button class="primary" data-act="save" ${this._data.admin ? "" : "disabled"}>${t.save}</button>
          <button data-act="back">${t.cancel}</button>
        </div>
        ${this._data.admin ? "" : `<p class="dim">${t.admin_only}</p>`}
      </div>`;
  }

  _pickHtml(title, hint, button) {
    const t = this._t;
    const covers = this._newCovers();
    const rows = covers
      .map(
        (id) => `<label class="pick" data-row="${esc(`${id} ${this._name(id)}`.toLowerCase())}">
          <input type="checkbox" data-pick="${esc(id)}" ${this._pick.has(id) ? "checked" : ""}>
          ${esc(this._name(id))} <span class="dim">${esc(id)}</span></label>`
      )
      .join("");
    const profile =
      this._view === "add"
        ? `<div class="field"><div class="label">${t.profile}</div><div class="input"><select id="add_profile">
          <option value="">${t.no_profile}</option>
          ${this._data.profiles.map((p) => `<option value="${esc(p.id)}">${esc(p.title)}</option>`).join("")}
          </select></div><div></div></div>`
        : "";
    return `
      <div class="card">
        <div class="bar"><button data-act="back">← ${t.back}</button><h2>${esc(title)}</h2></div>
        <p class="hint">${esc(hint)}</p>
        ${profile}
        ${
          covers.length
            ? `<input type="search" id="filter" placeholder="${t.filter}" value="${esc(this._filter)}">
               <div class="picks">${rows}</div>`
            : `<p class="dim">${t.none_left}</p>`
        }
        <div class="bar"><button class="primary" data-act="${button}" disabled>${
          button === "add_yes" ? t.add_button : t.dup_button
        }</button><button data-act="back">${t.cancel}</button></div>
      </div>`;
  }

  _render() {
    const t = this._t;
    let body;
    if (this._error) body = `<div class="card"><p class="err">${t.error}: ${esc(this._error)}</p></div>`;
    else if (!this._data) body = `<div class="card"><p class="dim">${t.loading}</p></div>`;
    else if (this._view === "edit" && this._edit) body = this._editHtml();
    else if (this._view === "add") body = this._pickHtml(t.add_title, t.add_hint, "add_yes");
    else if (this._view === "duplicate") {
      const source = this._cover(this._source);
      body = this._pickHtml(fmt(t.dup_title, { name: source?.title || "" }), t.dup_hint, "dup_yes");
    } else body = this._listHtml();
    const message = this._message
      ? `<div class="msg ${this._message.ok ? "ok" : "err"}" data-act="dismiss">${esc(this._message.text)}</div>`
      : "";
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px);
          border: 1px solid var(--divider-color); padding: 16px; display: grid; gap: 12px; }
        h2 { margin: 0; font-size: 18px; font-weight: 500; }
        .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        .sticky { position: sticky; bottom: 0; background: var(--card-background-color, #fff); padding: 8px 0; }
        button, select, input { font: inherit; font-size: 14px; color: var(--primary-text-color); }
        button { cursor: pointer; border-radius: 8px; padding: 6px 12px; border: 1px solid var(--divider-color);
          background: var(--card-background-color, #fff); }
        button:hover:not([disabled]) { border-color: var(--primary-color); }
        button[disabled] { opacity: .45; cursor: default; }
        button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
        button.warn { background: var(--error-color, #db4437); color: #fff; border-color: transparent; }
        button.link, a.link { border: 0; background: none; padding: 0 4px; color: var(--primary-color); cursor: pointer; }
        select, input[type=text], input[type=number], input[type=time], input[type=search] {
          background: var(--secondary-background-color, #f5f5f5); border: 1px solid var(--divider-color);
          border-radius: 6px; padding: 6px 8px; max-width: 100%; box-sizing: border-box; }
        input[type=text], input[type=search], select { min-width: 220px; }
        input[type=number] { width: 110px; }
        .scroll { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; font-size: 14px; }
        th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--divider-color); white-space: nowrap; }
        th { font-weight: 500; color: var(--secondary-text-color); }
        .row-actions button { padding: 2px 8px; font-size: 13px; }
        .dim, .unit, .help { color: var(--secondary-text-color); font-size: 13px; }
        .hint { margin: 0; font-size: 14px; }
        .tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid var(--divider-color); padding-bottom: 8px; }
        .sec { font-size: 13px; padding: 4px 10px; border-radius: 14px; }
        .sec.active { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
        .fields { display: grid; gap: 4px; }
        .field { display: grid; grid-template-columns: minmax(160px, 260px) 1fr auto; gap: 4px 12px;
          align-items: center; padding: 6px 4px; border-radius: 6px; }
        .field.changed { background: rgba(3, 169, 244, .1); }
        .field .help { grid-column: 2 / 4; }
        .label { font-size: 14px; }
        .input { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; }
        .boxes { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 14px; }
        .chips { display: flex; flex-wrap: wrap; gap: 4px; }
        .chip { font-size: 13px; padding: 2px 4px 2px 10px; border-radius: 12px; border: 1px solid var(--divider-color); }
        .chip button { border: 0; padding: 0 6px; background: none; }
        .picks { display: grid; gap: 2px; max-height: 50vh; overflow: auto; }
        .pick { display: flex; gap: 8px; align-items: center; padding: 4px; font-size: 14px; }
        .confirm { padding: 10px; border-radius: 8px; background: rgba(219, 68, 55, .12); display: grid; gap: 8px; }
        .msg { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; cursor: pointer; }
        .msg.ok { background: rgba(67, 160, 71, .15); }
        .msg.err, .err { color: var(--error-color, #db4437); }
        .msg.err { background: rgba(219, 68, 55, .12); }
        @media (max-width: 700px) {
          .field { grid-template-columns: 1fr; }
          .field .help { grid-column: 1; }
          input[type=text], input[type=search], select { min-width: 0; width: 100%; }
        }
      </style>
      ${message}${body}`;
    this._updateButtons();
  }
}

if (!customElements.get("asc-editor")) customElements.define("asc-editor", AscEditor);
