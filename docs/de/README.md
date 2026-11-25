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
   Helligkeit und Sonnenhöhe, Bewohner und Selbstschutz, Positionen, Fenster, Beschattung,
   Lamellen, Sichtschutz,
   Fahrverhalten und manuelle Übersteuerung.
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

### Helligkeit und Sonnenhöhe

Weitere Modi für *Morgens/Abends fahren nach*: **Helligkeit**, **Sonnenhöhe** und **Helligkeit und
Sonnenhöhe**. Gefahren wird, sobald die Bedingung zwischen frühester und spätester Zeit erfüllt ist und
so lange erfüllt bleibt, wie *Bedingung muss gelten für* angibt (Prüfung jede Minute). Die späteste Zeit ist die Frist: Ist die
Bedingung bis dahin nicht erfüllt, wird dann gefahren. Pro Tag gibt es nur eine Morgen- und eine Abendfahrt.

| Einstellung | Bedeutung |
|---|---|
| Öffnen ab / Schließen unter | Lux-Schwellen (Standard 500 / 300) für den Helligkeitssensor (Seite *Sensoren*). |
| Öffnen ab / Schließen unter Sonnenhöhe | Grad über dem Horizont (Standard 3 / 1). |
| Schwelle der Sonnenhöhe aus | *Fest*, *Sensor* (Schwelle aus einem Sensor) oder *Sensor + Versatz*. |
| Helligkeit und Sonnenhöhe verknüpft mit | *Eines davon (ODER)* oder *Beides (UND)*. |

### Kalender

*Früheste und späteste Zeiten aus* = *Kalender* (Kalender auf der Seite *Sensoren*): Ein Termin, dessen Titel *Kalender: Titel für Öffnen* (Standard `open`) enthält,
ersetzt an diesem Tag früheste und späteste Öffnung durch Beginn und Ende des Termins; *Kalender: Titel für
Schließen* (Standard `close`) genauso für den Abend. Groß-/Kleinschreibung zählt nicht, ganztägige Termine werden
ignoriert. Tage ohne passenden Termin und ein nicht lesbarer Kalender nutzen die eingestellten Zeiten.

## Fenster

Je Rollladen auf der Seite *Fenster*: Kontakt *offen*, Kontakt *gekippt* und/oder ein Sensor mit drei
Zuständen (Texte für offen und gekippt einstellbar). Offen gewinnt vor gekippt. Der Sensor *Fenster* zeigt
geschlossen, gekippt oder offen.

- **Lüften**: Wird ein Fenster geöffnet oder gekippt und steht der Rollladen tiefer als *Position Lüften*
  (Standard 50 %), fährt er hoch. Ist es geöffnet, wenn eine Fahrt nach unten ansteht, fährt er nur bis zur
  Lüftungsposition. *Lüften fährt nur nach oben* (Standard an) verhindert, dass ein offenes Fenster einen höher
  stehenden Rollladen herunterfährt.
- **Voll-Lüften (Komfort)**: Ist der globale Schalter *Komfort* an, fährt ein ganz offenes Fenster auf
  *Position Komfort* (Standard 70 %).
- **Fenster zu**: Der Rollladen fährt in den Zielzustand oder, mit *Wenn das Fenster geschlossen wird* =
  *Vorherige Position*, zurück, wo er vor dem Lüften stand. Nur wenn wegen des Fensters gefahren wurde.
- **Verzögerung beim Öffnen / Schließen**: so viele Sekunden muss der Zustand bestehen.
- **Aussperrschutz**: *Weich* oder *hart*: Solange die Tür offen ist (gekippt nur mit *Aussperrschutz auch bei gekippt*), fährt
  der Rollladen nicht nach unten. Eine gesperrte Fahrt wird nachgeholt, sobald die Tür zu ist. *Hart* sperrt
  in dieser Version genauso wie *weich*; der Unterschied (auch Wetterschutz wartet) kommt mit Stufe 4.

## Sichtschutz

- *Abends: Minuten vor dem Schließen*: so lange vor der Abendfahrt auf *Position Sichtschutz (abends)*
  (Standard 50 %).
- *Morgens: Minuten vor dem Öffnen*: so lange vor der Morgenfahrt auf *Position Sichtschutz (morgens)*
  (leer = wie abends).
- *Abends: wenn dunkler als*: abends schon früher, sobald es dunkler als dieser Wert ist.

Der Sensor *Nächster Sichtschutz* zeigt die nächste Sichtschutzfahrt.

## Bewohner

Seite *Bewohner und Selbstschutz*. *Quellen des Haus-Status* (global, Profil oder Rollladen) und je Rollladen
*Quellen des Raum-Status*. Jede Quelle wird auf einen Zustand abgebildet:

| Quelle | Zustand |
|---|---|
| Person, Device Tracker | `home` = zu Hause, sonst abwesend; länger weg als *Länger weg als (verreist)* = verreist |
| Zone (z. B. `zone.home`) | 0 = abwesend, ab 1 = zu Hause |
| Binärsensor, Input Boolean (Bett, Schlafmodus) | an = schläft, aus = wach |
| Alarmanlage | abwesend/Urlaub = verreist, Nacht = schläft, zu Hause/entschärft = zu Hause |
| Sensor, Auswahl | Zustände `asleep`, `gotosleep`, `awoken`, `home`, `absent`, `gone` |

Mit *Eigene Zuordnung von Quellwerten* lassen sich weitere Werte zuordnen, z. B.
`Schlafen:asleep, Urlaub:gone`. Mehrere Quellen: schläft > geht schlafen > wach > zu Hause > abwesend >
verreist. Ist eine Quelle nicht erreichbar, gilt ihr letzter bekannter Zustand.

Für jeden Rollladen zählt der Raum-Status, falls er Quellen hat, sonst der Haus-Status:

- **Schlafen**: Mit *Schließen, wenn die Bewohner schlafen gehen* (Standard an) fährt der Rollladen auf
  *Position Schlafen* (leer = geschlossen), auch am Tag. Solange geschlafen wird, gibt es keine Morgenfahrt,
  kein Lüften und keine Beschattung, außer es ist erlaubt (*… trotz Schlaf*).
- **Aufwachen**: Mit *Öffnen, wenn die Bewohner aufwachen* (Standard an) fährt der Rollladen am Tag in den
  Zielzustand.
- **Morgenfahrt / Abendfahrt**: *Immer*, *nur wenn jemand zu Hause ist*, *nur wenn niemand zu Hause ist* oder
  *nie* (ASC `ASC_Mode_Up`/`_Down`, gilt für den Haus-Status).
- Neuer Modus *Bewohner* für *Morgens/Abends fahren nach*: morgens öffnen, sobald die Bewohner wach sind,
  abends schließen, sobald sie schlafen, jeweils zwischen frühester und spätester Zeit (späteste Zeit ist die
  Frist).

## Selbstschutz

Ist der Schalter *Selbstschutz* am zentralen Gerät an (Standard aus), schließen Rollläden mit offenem oder
gekipptem Fenster, sobald niemand zu Hause ist: bei *verreist* sofort, bei *abwesend* nach der Verzögerung
(Modus *Wenn niemand zu Hause ist*). Mit *Selbstschutz schließt jeden Rollladen* auch die ohne offenes
Fenster. Der Selbstschutz geht vor Aussperrschutz und Übersteuerung. Kommt jemand heim oder wird das Fenster
geschlossen, fährt der Rollladen wieder in den Zielzustand. Binärsensor *Selbstschutz* je Rollladen.

## Beschattung

Seite *Beschattung*, Standard *aus*. Einschalten mit *Beschattung* = *Immer* (oder nur bei An-/Abwesenheit),
am besten im Profil der Fassade. Der Schalter *Beschattung* am zentralen Gerät schaltet sie für alle ab.

**Bedingungen** (nur, wenn ihr Sensor bzw. Schwellwert eingestellt ist):

| Bedingung | Beginn | Ende (Hysterese) |
|---|---|---|
| Sonnenrichtung | zwischen *von* und *bis* (Standard 105–255°, auch über Nord) | außerhalb |
| Sonnenhöhe | zwischen *ab* und *bis* (Standard 25–90°) | außerhalb |
| Helligkeit | ab *Beginn ab Helligkeit* (35000 lx), optional gemittelt | unter *Ende unter Helligkeit* (20000 lx) |
| Außentemperatur | ab 18 °C | unter 18 °C minus Hysterese (1 K) |
| Innentemperatur | ab Schwelle (leer = aus) | unter Schwelle minus Hysterese |
| Vorhersage-Temperatur | Höchstwert heute ab Schwelle (Sensor oder Tagesvorhersage der Wetter-Entität) | unter Schwelle minus Hysterese |
| Wetterlage | Zustand der Wetter-Entität in der Liste (Standard sonnig, teilweise bewölkt) | nicht in der Liste |
| Eigener Binärsensor | an | aus |

*Muss (alle)* (Standard: alle) und *Oder (mindestens eine)*: Beginn, wenn alle Muss-Bedingungen und, falls
die Oder-Liste eingestellte Bedingungen hat, eine davon erfüllt sind. Ein nicht erreichbarer Sensor startet
keine Beschattung, beendet aber auch keine.

**Ablauf** wie ASC: keine → *beginnt gleich* (*Wartezeit vor der Beschattung*, Standard 10 min) →
Beschattung → *endet gleich* (*Wartezeit vor dem Ende*, Standard 20 min) → keine. Verlässt die Sonne den
Bereich, endet sie sofort (abschaltbar). Geprüft wird jede Minute, nur am Tag und im Zeitfenster
*Beschattung ab/bis*.

**Fahren**: auf *Position Beschattung* (30 %), solange *Entität für die alternative Position* an ist auf die
alternative Position. *Beschattung fährt nur nach unten* (Standard an). Am Ende fährt der Rollladen zurück in
den Zielzustand, aber nur, wenn er noch auf der Beschattungsposition steht (nicht nach einer Handfahrt oder
wenn er geschlossen ist); *Nach der Beschattung wieder öffnen* aus lässt ihn bis zum Abend stehen. Ein offenes
Fenster geht vor (Lüftungsposition).

**Hitzeschutz**: ab *Hitzeschutz ab* (Außentemperatur) wird beschattet, auch ohne Sonne, und bis zum Abend
gehalten.

Der Sensor *Beschattung* je Rollladen zeigt den Zustand und in den Attributen alle Eingangswerte
(Sonnenrichtung, Sonnenhöhe, Helligkeit, Temperaturen, Vorhersage, Wetterlage).

## Lamellen

Seite *Lamellen*, für Rollläden mit Lamellenposition (oder eine eigene Lamellen-Entität je Rollladen).
Je Fahrt eine Lamellenstellung (offen, geschlossen, Schlafen, Lüften, Komfort, Beschattung, Sichtschutz);
leer = Lamellen bleiben. *Beschattungsstufen nach Sonnenhöhe*: bis zu 4 Stufen `Sonnenhöhe:Lamelle`, z. B.
`20:70, 35:50, 50:30`; ändert sich die Stufe während der Beschattung, werden nur die Lamellen nachgestellt.

*Reihenfolge*: Position, dann Lamellen bei Stillstand (Standard, mit Zeitlimit) oder nach der Wartezeit,
oder erst Lamellen, dann Position (Z-Wave). *Lamellen vor neuer Einstellung erst schließen* und eine eigene
*Toleranz der Lamellen* gibt es ebenfalls. Lamellen von Hand verstellen zählt als Handfahrt (nicht bei einer eigenen Lamellen-Entität).

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

**Zentrales Gerät**: Schalter Automatik, Wochenend- und Feiertagszeiten, Morgenfahrt, Abendfahrt, Pause,
Komfort, Beschattung, Selbstschutz; Sensor Haus-Status;
Knöpfe Zeiten neu berechnen, Alle Rollläden in den Zielzustand.

**Je Rollladen**: Schalter Automatik und Pause; Binärsensoren Tag, Manuelle Übersteuerung und Selbstschutz; Sensoren
Nächste Öffnung, Nächstes Schließen, Nächster Sichtschutz, Letzter Fahrgrund, Zielzustand, Fenster, Bewohner, Beschattung; Knöpfe Zielzustand anfahren und
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
| 1 | Grundgerüst, Erben, Entscheider, Zeitplan (Zeit/Sonne/Arbeitstag), Positionen, Übersteuerung, Verzögerung, EN/DE |
| 2 | Fensterkontakte (Lüften, Komfort, Aussperrschutz), Helligkeit, Sonnenhöhe, Sichtschutz, Kalender |
| 3 (diese Version) | Bewohner, Selbstschutz, Beschattung mit allen Bedingungen, Lamellen |
| 4 | Regen (auch bei offenem Fenster), Wind, Frost, Force, Party, Advent, Trigger, Wackeln |
| 5 | Nachholen nach Neustart, Plausibilitätsprüfung, Logbuch, FHEM-Import, HACS-Standard |

## Übersetzen

Jede Sprache ist eine Datei in `custom_components/autoshutterscontrol/translations/`. Feldtexte stehen einmal
in `options.step.<Bereich>`; `python script/expand_translations.py` kopiert sie in die Seiten von Profil und
Rollladen. Pull Requests mit neuen Sprachen sind willkommen.
