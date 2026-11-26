# Translating AutoShuttersControl for HA

Every language is one file. A new language needs no code change.

1. Copy `custom_components/autoshutterscontrol/translations/en.json` to `<language>.json`
   (e.g. `fr.json`, `nl.json`).
2. Translate the values, never the keys. Keep placeholders like `{name}`, `{position}` or `{inh_pos_open}`
   and the line `↳ {inh_...}` exactly as they are.
3. Field texts of the settings are written **once** in `options.step.<section>` (and fields that exist
   only on covers in `config_subentries.cover.step.<section>`). Run

   ```
   python script/expand_translations.py
   ```

   It copies them into the profile and cover pages, the reset lists and the config entities.
4. Run the tests (`python -m pytest tests/test_translations.py`): they check that every language has all
   keys of `strings.json` and that the expansion is up to date.
5. Open a pull request.

The reasons of drives (`night_close`, `shading` …) are stored as keys and translated only for display, so
automations do not depend on the language. Logbook texts are in `exceptions.logbook_*`.

The sidebar page and the dashboard cards are web components with their own texts: the object `TEXTS` at the
top of `www/summary-panel.js`, `www/editor.js` and `www/asc-card.js`. Add a block for your language there (two
letter code, e.g. `fr`). The labels of the settings on the page *Edit covers* come from the translation files.
