# AutoShuttersControl for HA

## Installation

1. HACS → drei Punkte → *Benutzerdefinierte Repositories* → `https://github.com/steigerbalett/ha-autoshutterscontrol`, Typ *Integration*.
2. *AutoShuttersControl for HA* installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → AutoShuttersControl for HA*.

Nötig ist Home Assistant 2026.10 oder neuer.

## Einrichtung

Es gibt **einen** Eintrag für das ganze Haus.

1. **Haupteintrag**: Arbeitstag-Sensoren wählen (optional). Ohne Sensor gelten Montag bis Freitag als Arbeitstage.
2. **Optionen** (Zahnrad am Eintrag): globale Einstellungen, je eine Seite für Zeitplan, Sensoren,
   Positionen, Fahrverhalten und manuelle Übersteuerung.
3. **Profile** (optional, *Profil hinzufügen*): Einstellungen für eine Gruppe von Rollläden, z. B. „Südseite“.
4. **Rollläden** (*Rollläden hinzufügen*): einen oder mehrere Rollläden und ein Profil wählen. Abweichungen
   trägst du über *Neu konfigurieren* am Rollladen ein.

### Erben

Jeder Wert wird so aufgelöst: **Rollladen → Profil → global → Standard**. Auf den Seiten von Profil und
Rollladen erbt ein leeres Feld; die Zeile `↳` unter dem Feld zeigt den geerbten Wert. *Auf geerbten Wert
zurücksetzen* leert Felder. Der Sensor *Zielzustand* jedes Rollladens zeigt im Attribut `effective_config`
alle wirksamen Werte und ihre Herkunft.

## Zeitplan

| Einstellung | Bedeutung |
|---|---|
| Morgens/Abends fahren nach | *Sonne*: Sonnenereignis plus Versatz, begrenzt auf früheste und späteste Zeit. *Zeit*: zur frühesten Zeit (wie ASC). |
| Sonnenereignis | Sonnenauf-/-untergang, bürgerliche, nautische, astronomische Dämmerung oder eigene Sonnenhöhe. |
| Früheste/späteste Öffnung und Schließen | Getrennt für Arbeitstage und freie Tage. |
| Abends nach dem morgigen Tag richten | Freitagabend gelten schon die Zeiten des freien Tages. |

Der globale Schalter *Wochenend- und Feiertagszeiten* aus nimmt jeden Tag die Arbeitstag-Zeiten.
Die Schalter *Morgenfahrt* und *Abendfahrt* schalten diese Fahrten für alle Rollläden ab.

## Manuelle Übersteuerung

Eine Fahrt, die nicht von AutoShuttersControl kommt (App, Taster, Wandschalter, andere Automation), startet
eine manuelle Übersteuerung. Eigene Fahrten erkennt AutoShuttersControl am Context von Home Assistant;
Positionsmeldungen während der *Fahrzeit* nach dem eigenen Befehl zählen ebenfalls als eigene Fahrt.

- *Gesperrt während der Übersteuerung*: welche Fahrten warten (Standard: Lüften und Beschattung, wie ASC).
- *Die Übersteuerung endet*: nach einer Dauer (Standard 20 min), zu einer festen Uhrzeit, bei der nächsten
  geplanten Fahrt oder nur von Hand (Knopf *Übersteuerung beenden*).
- *Öffnen von Hand zählt als Morgenfahrt*: zwischen frühester Öffnung und geplanter Zeit von Hand geöffnet,
  dann an diesem Tag keine zweite Morgenfahrt. Abends genauso.

## Regeln

- *Öffnen fährt nie nach unten*, *Schließen fährt nie nach oben* (Richtungsregel von ASC).
- Toleranz: so nah an einer Position gilt sie als erreicht; es wird nicht gefahren.
- Verzögerung: feste plus zufällige Sekunden vor einer geplanten Fahrt.

## Entitäten

**Zentrales Gerät**: Schalter Automatik, Wochenend- und Feiertagszeiten, Morgenfahrt, Abendfahrt, Pause;
Knöpfe Zeiten neu berechnen, Alle Rollläden in den Zielzustand.

**Je Rollladen**: Schalter Automatik und Pause; Binärsensoren Tag und Manuelle Übersteuerung; Sensoren
Nächste Öffnung, Nächstes Schließen, Letzter Fahrgrund, Zielzustand; Knöpfe Zielzustand anfahren und
Übersteuerung beenden; Auswahl Morgens/Abends fahren nach (mit *Erben*); ausgeblendete
Konfigurations-Entitäten für Positionen und Zeiten.

Pause: es wird nicht gefahren, der Zielzustand läuft mit; endet die Pause, fährt der Rollladen ihn an.
Automatik aus: es wird nicht gefahren, und beim Einschalten passiert nichts.

## Aktionen

| Aktion | Zweck |
|---|---|
| `autoshutterscontrol.drive` | Auf eine Position oder eine benannte Position (`open`, `closed`, …) fahren. |
| `autoshutterscontrol.apply_target` | Mit allen Regeln in den aktuellen Zielzustand fahren. |
| `autoshutterscontrol.recalculate` | Fahrzeiten neu berechnen. |
| `autoshutterscontrol.clear_override` | Manuelle Übersteuerung beenden. |
| `autoshutterscontrol.set_option` | Eine Einstellung von Rollläden oder einem Profil setzen; ohne Wert erbt sie wieder. |

Alle Aktionen nehmen `entity_id` (die gesteuerten Rollläden) und/oder `profile` (Name); leer heißt alle.

Ereignisse: `autoshutterscontrol_drive` (jede Fahrt, mit `reason` und `trigger`) und
`autoshutterscontrol_manual` (Handfahrt erkannt).

## Fahrplan

| Stufe | Inhalt |
|---|---|
| 1 (diese Version) | Grundgerüst, Erben, Entscheider, Zeitplan (Zeit/Sonne/Arbeitstag), Positionen, Übersteuerung, Verzögerung, EN/DE |
| 2 | Fensterkontakte (Lüften, Komfort, Aussperrschutz), Helligkeit, Sonnenhöhe, Sichtschutz, Kalender |
| 3 | Bewohner, Selbstschutz, Beschattung mit allen Bedingungen, Lamellen |
| 4 | Regen (auch bei offenem Fenster), Wind, Frost, Force, Party, Advent, Trigger, Wackeln |
| 5 | Nachholen nach Neustart, Plausibilitätsprüfung, Logbuch, FHEM-Import, HACS-Standard |

## Übersetzen

Jede Sprache ist eine Datei in `custom_components/autoshutterscontrol/translations/`. Feldtexte stehen einmal
in `options.step.<Bereich>`; `python script/expand_translations.py` kopiert sie in die Seiten von Profil und
Rollladen. Pull Requests mit neuen Sprachen sind willkommen.
