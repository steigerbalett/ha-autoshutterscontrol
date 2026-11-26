# AutoShuttersControl for HA

## Installation

1. *Einstellungen → Marketplace* (ab Home Assistant 2026.11, vorher HACS) → drei Punkte → *Benutzerdefinierte
   Repositories* → `https://github.com/steigerbalett/ha-autoshutterscontrol`, Typ *Integration*. Oder den Button
   in der [README](../../README.md#installation-1) drücken.
2. Versionen 0.x sind Pre-Releases: beim Repository *Beta-Versionen anzeigen* einschalten.
3. *AutoShuttersControl for HA* installieren und Home Assistant neu starten.
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → AutoShuttersControl for HA*.

Nötig ist Home Assistant 2026.10 oder neuer.

## Einrichtung

Es gibt **einen** Eintrag für das ganze Haus.

1. **Haupteintrag**: Arbeitstag-Sensoren wählen (optional). Ohne Sensor gelten Montag bis Freitag als Arbeitstage.
2. **Optionen** (Zahnrad am Eintrag): globale Einstellungen, je eine Seite für Zeitplan, Sensoren,
   Helligkeit und Sonnenhöhe, Bewohner und Selbstschutz, Positionen, Fenster, Beschattung,
   Lamellen, Sichtschutz, Regen/Wind/Frost, Sonderfunktionen, Fahrverhalten, manuelle Übersteuerung,
   Zusatzbedingungen und -aktionen sowie *Aus FHEM übernehmen*.
3. **Profile** (optional, *Profil hinzufügen*): Einstellungen für eine Gruppe von Rollläden, z. B. „Südseite“.
4. **Rollläden** (*Rollläden hinzufügen*): einen oder mehrere Rollläden und ein Profil wählen. Abweichungen
   trägst du über *Neu konfigurieren* am Rollladen ein.

### Erben

Jeder Wert wird so aufgelöst: **Rollladen → Profil → global → Standard**. Auf den Seiten von Profil und
Rollladen erbt ein leeres Feld; die Zeile `↳` unter dem Feld zeigt den geerbten Wert. *Auf geerbten Wert
zurücksetzen* leert Felder. Der Sensor *Zielzustand* jedes Rollladens zeigt im Attribut `effective_config`
alle wirksamen Werte und ihre Herkunft.

### Alternatives Profil (z. B. Sommer/Winter)

Am Rollladen auf der Seite *Rollladen*: *Alternatives Profil*, eine *Entität für das alternative Profil* und
ihr *Wert* (Standard `on`). Solange die Entität den Wert zeigt, erbt der Rollladen vom alternativen Profil statt
vom normalen, z. B. mit einem Input Boolean „Winter“ oder einer Auswahl „Jahreszeit“. Beim Umschalten fährt der
Rollladen in den neuen Zielzustand, in jede Richtung. Ist die Entität kurz nicht verfügbar, gilt ihr letzter
Zustand. Der Sensor *Zielzustand* zeigt das aktive Profil im Attribut `profile`.

Statt oder zusätzlich zur Entität geht ein Zeitraum im Jahr: *Alternatives Profil ab* und *bis* als TT.MM.,
z. B. `1.11.` bis `31.3.` für den Winter (über den Jahreswechsel, beide Tage eingeschlossen). Um Mitternacht
wird geprüft, ob der Zeitraum beginnt oder endet. Mit Entität und Zeitraum gilt das alternative Profil, sobald
eins von beiden zutrifft.

## Zeitplan

| Einstellung | Bedeutung |
|---|---|
| Morgens/Abends fahren nach | *Sonne*: Sonnenereignis plus Versatz, begrenzt auf früheste und späteste Zeit. *Zeit*: zur frühesten Zeit (wie ASC). *Entität*: zur Zeit einer Entität plus Versatz, begrenzt auf früheste und späteste Zeit. |
| Morgen-/Abendzeit aus Entität | Für *Entität*: ein `input_datetime`, eine Zeit-Entität oder ein Zeitstempel-Sensor, z. B. *Nächster Wecker* der Home-Assistant-App, `sensor.sun_next_rising`/`_setting` oder eine eigene Template-Berechnung. Ein Zeitstempel zählt nur an seinem Tag; ohne brauchbaren Wert gilt morgens die späteste, abends die früheste Zeit. Ist die Fahrt gelaufen, ist der Tag erledigt, auch wenn der Wecker schon den nächsten Tag zeigt. |
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
  der Rollladen nicht nach unten. Eine gesperrte Fahrt wird nachgeholt, sobald die Tür zu ist. *Hart* lässt
  zusätzlich Regen- und Windschutz warten und kann den Aktor sperren (siehe *Hardware-Sperre*).

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

### Gäste

Am Rollladen (Seite *Bewohner*): *Gäste in diesem Raum* nimmt Personen, Device-Tracker oder einen
Schalter/Input Boolean (`home` bzw. an = Gast da). Alternativ schaltet der Schalter **Gast anwesend** am
Rollladen den Gast hart an. *Bei Gast* (Standard *Keine Morgenfahrt*):

- *Keine Morgenfahrt*: der Rollladen öffnet morgens nicht (auch nicht für Beschattung oder Sichtschutz);
  Schließen, Lüften und Schutzfunktionen bleiben.
- *Keine Morgen- und Abendfahrt*: der Zeitplan fährt gar nicht.
- *Nur manuelle Fahrten*: keine automatischen Fahrten außer Zwang und Schutz (Regen, Wind, Wasser, Frost,
  Selbstschutz); *Nicht gefahren wegen* zeigt *Gast*.

Ist der Gast weg bzw. der Schalter aus, fährt der Rollladen sofort in seinen Zielzustand (die Morgenfahrt
wird nachgeholt). Binärsensor *Gast* je Rollladen.

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

**Heißer Tag** (*Heißer Tag: morgens Beschattungsposition*, Standard aus): Sagt die Vorhersage für heute
mindestens *Heißer Tag ab* (Standard 26 °C, Vorhersage-Sensor oder Tagesvorhersage der Wetter-Entität) und,
mit *nur bei sonniger Vorhersage*, eine der Wetterlagen der Beschattung voraus, fährt die Morgenfahrt nicht
ganz auf, sondern direkt auf die Beschattungsposition, sofern die Sonne das Fenster heute noch trifft
(Sonnenrichtung und Sonnenhöhe der Beschattung). Nachts fährt nichts in die Beschattung, die Wohnung kann
maximal auskühlen. Der Rollladen bleibt auf der Beschattungsposition, bis die Sonne am Fenster vorbei ist
oder die normale Beschattung des Tages endet; dann fährt er wie nach der Beschattung zurück. Der Binärsensor
*Heißer Tag* je Rollladen zeigt, ob das gerade gilt.

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

**Lamellenwinkel nach der Sonne** (Standard aus): beim Beschatten berechnet AutoShuttersControl aus
Sonnenstand und Lamellengeometrie den Winkel, bei dem die direkte Sonne gerade draußen bleibt und möglichst
viel Licht hereinkommt, und stellt die Lamellen jede Minute in 5-%-Schritten nach. Dazu gehören
*Lamellenabstand / Lamellenbreite* (Standard 0,9), die Lamellenpositionen für *waagerecht* (100 %) und
*senkrecht* (0 %) und auf der Seite *Beschattung* die *Fensterrichtung* (leer = Mitte von *Sonnenrichtung
von/bis*). Steht die Sonne hoch oder seitlich, öffnen die Lamellen weiter, steht sie tief vor dem Fenster,
schließen sie fast. Die Stufen nach Sonnenhöhe gelten dann nicht.

## Regen, Wind und Frost

Sensoren auf der Seite *Sensoren*: *Regensensor* (Binärsensor, an = Regen, oder Regenmenge), *Windgeschwindigkeit*
und *Außentemperatur*. Die Einstellungen stehen auf der Seite *Regen, Wind und Frost*. Alle Schutzfunktionen
haben eine Hysterese und Wartezeiten in beide Richtungen; ein nicht verfügbarer Sensor behält den letzten Zustand.

- **Wasserschutz** (Standard an): Regnet es und ist das Fenster gekippt oder offen (einstellbar), fährt der
  Rollladen auf *Position Wasserschutz* (Standard 0 %). Mit Aussperrschutz höchstens bis zur Lüftungsposition,
  außer *Wasserschutz schließt trotz Aussperrschutz ganz* ist an. Einmal je Regen kommt das Ereignis
  `autoshutterscontrol_rain_window` (und die Zusatzaktion *Aktion beim Wasserschutz*), z. B. für eine
  Benachrichtigung.
  - *Zurück nach dem Regen* (Standard *Vorherige Position*): Ist es wieder trocken (nach *Wartezeit nach dem
    Regen*) oder das Fenster zu, fährt der Rollladen auf die Position von vor dem Wasserschutz, z. B. auf die
    40 %, die du vorher von Hand eingestellt hattest.
  - Gilt inzwischen etwas anderes, fährt er stattdessen in den neuen Zielzustand. Das ist der Fall, wenn
    seitdem die Abend- oder Morgenfahrt fällig war, die Beschattung begonnen oder geendet hat, eine Übersteuerung
    begonnen oder geendet hat (auch durch eine Handfahrt während des Regens) oder sich die Positionen geändert
    haben.
  - Mit *Zielzustand* geht es immer in den aktuellen Zielzustand (Verhalten bis 0.6.0).
- **Regenschutz** (Standard aus, für Markisen): fährt bei Regen auf *Position Regen*, nach *Wartezeit nach dem
  Regen* (Standard 15 min) zurück.
- **Windschutz** (Standard aus, für Jalousien und Markisen): ab *Wind ab* (Standard 50 km/h) auf *Position Wind*;
  endet unter Schwelle minus Hysterese (Standard 20) und nach der Wartezeit (Standard 10 min).
- **Frostschutz** (Standard aus) unter *Frost unter* (Standard 2 °C): *Sanft* schließt nur bis *Position Frost*,
  *Vormittags* bzw. *Nachmittags* sperrt Fahrten bis bzw. ab 12 Uhr, *Gar nicht fahren* sperrt alles außer
  Regen, Wind und Zwang.

Regen- und Windschutz gehen vor Übersteuerung, Selbstschutz und allen Fahrplänen. *Aussperrschutz hart*
lässt auch Regen- und Windschutz warten, bis die Tür zu ist.

Am zentralen Gerät zeigen die Binärsensoren *Regen*, *Wind* und *Frost* die globalen Sensoren, je Rollladen
*Regenschutz*, *Wasserschutz*, *Windschutz* und *Frostschutz*, was gerade wirkt.

## Sonderfunktionen

Seite *Sonderfunktionen*; Felder mit Entitäten gibt es nur am Rollladen.

- **Zwangsfunktionen**: *Zwangsweise schließen / öffnen / lüften / beschatten*, je eine Entität (Input Boolean,
  Schalter, Binärsensor). Solange an, hält der Rollladen die Position, vor allen anderen Regeln (auch bei
  Automatik aus oder Pause). Aus: zurück in den Zielzustand (*Nach einer Zwangsfunktion zurückfahren*).
- **Pause-Entität**: solange an, fährt dieser Rollladen nicht automatisch; aus: Zielzustand.
- **Party**: Schalter *Party* am zentralen Gerät (Standard aus). Solange an, fahren alle teilnehmenden
  Rollläden nicht automatisch (Schutzfunktionen schon); aus: Zielzustand.
- **Advent**: Schalter *Advent* am zentralen Gerät (Standard aus). Vom 1. Advent bis 6. Januar (oder 2. Februar)
  wartet das abendliche Schließen, bis die Taste *Aufgeschobene Fahrten freigeben* oder die Aktion
  `autoshutterscontrol.release_deferred` es freigibt; die Freigabe gilt bis zum Ende des Tages.
  - Zeitraum: *Adventsmodus ab* = 1. Advent (Standard) oder *Eigener Tag* mit *Eigener Beginn*, z. B. `1.12.`.
    *Adventsmodus bis* = 6. Januar (Standard), 2. Februar oder *Eigener Tag* mit *Eigenes Ende*, z. B. `24.12.`
    oder `15.1.`. Tage als TT.MM., der Zeitraum darf über den Jahreswechsel gehen.
  - Fehlt ein eigener Tag oder ist er ungültig, gilt der Standard, und unter *Reparaturen* erscheint ein Hinweis.
- **Externer Trigger**: eine beliebige Entität mit bis zu zwei Werten und je einer Position, z. B. eine
  Auswahl *Kino* → 0 %. Endet der Wert, fährt der Rollladen in den Zielzustand.
- **Wackeln**: Taste *Wackeln* je Rollladen, *Alle wackeln* am zentralen Gerät, oder Aktion
  `autoshutterscontrol.wiggle`: fährt um *Wackeln um* (Standard 5 %) und nach *Wartezeit beim Wackeln* zurück.
  Zählt nicht als Handfahrt.
- **Hardware-Sperre**: Mit *Aussperrschutz hart* und einer Entität unter *Hardware-Sperre* (Schalter,
  Schloss, Input Boolean) wird der Aktor gesperrt, solange die Tür offen ist, und danach entsperrt. Schalter
  *Hardware-Sperre* am zentralen Gerät (Standard an) schaltet das ab.

## Zusatzbedingungen und -aktionen

Seite *Zusatzbedingungen und -aktionen*, mit den Editoren von Home Assistant:

- Bedingungen für alle Fahrten, fürs Öffnen, Schließen, Lüften und die Beschattung. Ist sie zur Fahrzeit
  nicht erfüllt, entfällt die Fahrt; *Zielzustand anfahren* holt sie nach. Zwang und Schutzfunktionen sind nicht
  betroffen. Eine ungültige Bedingung gilt als nicht erfüllt (Warnung im Log).
- Aktionen bei jeder Fahrt (Variablen `cover`, `position`, `reason`, `trigger`), bei einer Handfahrt
  (`position`), am Ende der Übersteuerung und beim Wasserschutz.

## Nachholen nach Neustart oder Ausfall

*Verpasste Fahrten nachholen* (Seite *Fahrverhalten*):

- *Nach einem Ausfall* (Standard): War Home Assistant aus, als eine Morgen- oder Abendfahrt fällig war, fährt
  jeder Rollladen 45 Sekunden nach dem Start in seinen Zielzustand. War der Rollladen selbst nicht erreichbar,
  wird die verpasste Fahrt nachgeholt, sobald er wieder da ist.
- *Immer nach einem Neustart*: nach jedem Start in den Zielzustand.
- *Nie*.

Nachgeholt wird mit allen Regeln (Übersteuerung, Aussperrschutz, Fenster …). Der Zustand (Übersteuerung,
erledigte Fahrten, Schutzfunktionen) liegt im Speicher von Home Assistant und überlebt jeden Neustart.

## Prüfung, Logbuch und Diagnose

- **Plausibilitätsprüfung**: Beim Start und nach jeder Änderung prüft AutoShuttersControl die wirksamen
  Einstellungen jedes Rollladens und meldet Fehler unter *Einstellungen → Reparaturen*, z. B. früheste Zeit nach
  der spätesten, 0:00 als späteste Schließzeit, vertauschte Schwellen, Regenschutz ohne Regensensor oder
  eingetragene Entitäten, die es nicht gibt. Ist der Fehler behoben, verschwindet der Hinweis.
- **Logbuch** (*Logbuch-Einträge*, Standard an): je Fahrt ein Eintrag am Rollladen mit Grund, ebenso für
  jede bewusst unterlassene Fahrt (z. B. „fuhr nicht (Abendfahrt): Pause“) und für Handfahrten.
- Der Diagnose-Sensor **Nicht gefahren wegen** zeigt, warum die letzte Entscheidung nicht gefahren ist.
- **Diagnose** (Eintrag → drei Punkte → *Diagnose herunterladen*): je Rollladen die wirksamen Einstellungen
  und die letzten 50 Entscheidungen mit allen Eingangswerten (Lage, Wünsche, Bewohner, Fenster, Beschattung,
  Schutzfunktionen).

## Übersicht

Die Übersicht entspricht der *ASC Configuration and Information Summary* von FHEM. Es gibt sie an zwei
Stellen:

- direkt in der Integration: *Konfigurieren* → **Übersicht** (Stand beim Öffnen, zum Aktualisieren neu
  öffnen);
- optional als Seite **AutoShuttersControl** in der Seitenleiste (*Übersicht in der Seitenleiste*, Seite
  *Fahrverhalten*, Standard aus), mit allen Spalten, aktualisiert alle 10 Sekunden.

Gezeigt werden:

- oben Sonnenrichtung und Sonnenhöhe, Vorhersage heute, Haus-Status, aktive Schutzfunktionen und alle
  globalen Schalter;
- je Rollladen: nächste Öffnung und nächstes Schließen, Morgens/Abends fahren nach, Bewohner auf/zu,
  Beschattung, Partymodus, Aussperrschutz, letzte Fahrt (Grund, Position, Zeit), Position und Lamellen, Ziel
  mit Grund, Nicht gefahren wegen, Beschattungszustand seit, Fenster, Bewohner sowie Hinweise wie Pause,
  Simulation, Übersteuerung bis, Ruhezeit, heißer Tag, Regen/Wind/Wasser/Frost;
- **Verknüpfte Sensoren und Werte** (wie die überwachten Geräte, NOTIFYDEV, in FHEM): jede Entität aus den
  Einstellungen mit aktuellem Wert und Einheit (z. B. Helligkeitssensor 23000 lx, Regen, Wind,
  Temperaturen, Fensterkontakte, Bewohner), der Einstellung, wer sie nutzt (Global und/oder Rollläden) und
  wann sie sich zuletzt geändert hat. Fehlt eine Entität, steht dort *fehlt*.

Auf der Seite in der Seitenleiste öffnet ein Klick auf einen Rollladen oder eine Entität ihren Dialog.

## Aus FHEM übernehmen

Optionen → *Aus FHEM übernehmen*:

1. `fhem.cfg` einfügen (oder nur die Zeilen des AutoShuttersControl-Geräts und der Rollläden mit `ASC 1/2`).
   Gelesen werden nur `define`- und `attr`-Zeilen.
2. Jedem FHEM-Rollladen einen Rollladen in Home Assistant zuordnen. Vorschläge kommen aus ähnlichen Namen.
3. Den FHEM-Geräten in den Attributen (Sensoren, Fensterkontakte, Bewohner) Entitäten zuordnen.
4. Die Übersicht zeigt, was übernommen wird und was nicht übertragbar ist (Perl-Code, unbekannte Attribute).
   Absenden legt die Rollläden an und speichert die globalen Einstellungen.

Übernommen werden die Attribute des ASC-Geräts als globale Einstellungen und die der Rollläden je Rollladen.
Werte, die alle Rollläden gleich haben, wandern in die globalen Einstellungen; Werte, die nur den Standard
wiederholen, entfallen. Schon eingerichtete Rollläden bleiben unverändert.

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
- *Gestaffelt fahren* (nur global, Standard 0): Rollläden, die zur gleichen Zeit fahren sollen, starten
  nacheinander im eingestellten Abstand in Sekunden (Funk, Strom). Zwang, Regen-, Wind- und Wasserschutz
  fahren immer sofort. Aus FHEM wird `ASC_shuttersDriveDelay` übernommen.
- *Ruhezeit von/bis* (Seite *Fahrverhalten*, feste Zeit oder aus einem `input_datetime`/einer Zeit-Entität,
  auch über Mitternacht): keine automatischen Fahrten, außer Zwang, Regen-, Wind-, Wasser-, Frostschutz und
  Selbstschutz. *Lüften in der Ruhezeit* (Standard an) lässt ein geöffnetes Fenster weiter auf die
  Lüftungsposition fahren. Am Ende der Ruhezeit fährt der Rollladen in seinen Zielzustand. Binärsensor
  *Ruhezeit* je Rollladen.
- *Simulation* (Schalter am zentralen Gerät für alle, am Rollladen für einen): AutoShuttersControl
  entscheidet und protokolliert alles wie sonst, fährt aber nicht („würde auf 30 % fahren (Beschattung),
  Simulation“ im Logbuch, Ereignis `autoshutterscontrol_drive` mit `simulation: true`). Der Diagnose-Sensor
  *Simulierte Fahrt* zeigt die letzte. Aktionen von Hand (`autoshutterscontrol.drive`) fahren weiter.

## Entitäten

**Zentrales Gerät**: Schalter Automatik, Wochenend- und Feiertagszeiten, Morgenfahrt, Abendfahrt, Pause,
Komfort, Beschattung, Selbstschutz, Party, Advent, Hardware-Sperre, Simulation; Sensor Haus-Status; Binärsensoren Regen,
Wind, Frost; Diagnose: Sensoren Sonnenrichtung, Sonnenhöhe (aus dem Standort von Home Assistant berechnet),
Höchstwert Vorhersage heute (globaler Vorhersage-Sensor oder Tagesvorhersage der globalen Wetter-Entität),
Binärsensoren Sonnig (Wetterlage jetzt in der Liste der Beschattung) und Heißer Tag (Vorhersage ab *Heißer Tag
ab*); Knöpfe Zeiten neu berechnen, Alle Rollläden in den Zielzustand, Alle wackeln, Aufgeschobene
Fahrten freigeben.

Die Entitäten eines Rollladens stehen auf dem Gerät des echten Rollladens (z. B. dem Shelly- oder
Homematic-Aktor), so wie bei den Helfern von Home Assistant. Hat der Rollladen kein Gerät (z. B. ein
Template-Cover), bekommt er ein eigenes Gerät „ASC ‹Name›“ unter dem zentralen Gerät.

**Je Rollladen**: Schalter Automatik, Pause, Simulation und Gast anwesend; Binärsensoren Tag, Manuelle Übersteuerung, Selbstschutz,
Regenschutz, Wasserschutz, Windschutz, Frostschutz, Zwangsfunktion, Heißer Tag, Ruhezeit und Gast; Sensoren
Nächste Öffnung, Nächstes Schließen, Nächster Sichtschutz, Letzter Fahrgrund, Zielzustand, Nicht gefahren wegen, Fenster, Bewohner, Beschattung, Simulierte Fahrt; Knöpfe Zielzustand anfahren,
Übersteuerung beenden und Wackeln; Auswahl Morgens/Abends fahren nach (mit *Erben*); ausgeblendete
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
| `autoshutterscontrol.wiggle` | Rollläden ein Stück und zurück fahren (Funktionsprüfung). |
| `autoshutterscontrol.release_deferred` | Advent: das heute aufgeschobene Schließen jetzt fahren. |

Alle Aktionen nehmen `entity_id` (die gesteuerten Rollläden) und/oder `profile` (Name); leer heißt alle.

Ereignisse: `autoshutterscontrol_drive` (jede Fahrt, mit `reason` und `trigger`) und
`autoshutterscontrol_manual` (Handfahrt erkannt) und `autoshutterscontrol_rain_window` (Regen bei offenem
Fenster, mit `window`, `position`, `driven`, `blocked_by`).

## Häufige Fragen

**Warum fährt ein Rollladen nicht?** Sensor *Nicht gefahren wegen* und das Logbuch am Rollladen zeigen den
Grund. Der Sensor *Zielzustand* zeigt, was gerade gelten würde, und in `effective_config`, woher jeder Wert kommt.

**Der Rollladen fährt nach einer Handfahrt nicht mehr automatisch.** Das ist die manuelle Übersteuerung. Sie
endet nach der eingestellten Zeit oder mit der Taste *Übersteuerung beenden*.

**Kann ich AutoShuttersControl kurz abschalten?** Schalter *Pause* (Zielzustand läuft mit und wird danach
angefahren) oder *Automatik* (nichts passiert, auch nicht beim Einschalten), global oder je Rollladen.

**Brauche ich Profile?** Nein. Sie sparen Arbeit, wenn mehrere Rollläden dieselben Abweichungen haben,
z. B. eine Fassade für die Beschattung.

**Laufen FHEM und Home Assistant parallel?** Ja, aber steuere einen Rollladen nur von einer Seite. Sonst
erkennt jede Seite die Fahrten der anderen als Handfahrt.

## Übersetzen

Jede Sprache ist eine Datei in `custom_components/autoshutterscontrol/translations/`. Feldtexte stehen einmal
in `options.step.<Bereich>`; `python script/expand_translations.py` kopiert sie in die Seiten von Profil und
Rollladen. Pull Requests mit neuen Sprachen sind willkommen; Anleitung: [translating.md](../en/translating.md).

## Dank

AutoShuttersControl for HA baut die Funktionen des FHEM-Moduls AutoShuttersControl nach. Großer Dank an seinen Autor **CoolTux**:

> AutoShuttersControl für FHEM
>
> (c) 2018-2026 Copyright: Marko Oldenburg (fhemdevelopment at cooltux dot net)

Aus dem FHEM-Modul übernommen, besonderer Dank geht an:

- Bernd (Cluni): this module is based on the logic of his script "Rollladensteuerung für HM/ROLLO inkl. Abschattung und Komfortfunktionen in Perl" ([FHEM forum](https://forum.fhem.de/index.php/topic,73964.0.html))
- Beta-User for many tests, many suggestions and good discussions
- pc1246 write english commandref
- FunkOdyssey commandref style
- sledge fix many typo in commandref
- many User that use with modul and report bugs
- Christoph (christoph.kaiser.in) Patch that expand RegEx for Window Events
- Julian (Loredo) expand Residents Events for new Residents functions
- Christoph (Christoph Morrison) for fix Commandref, many suggestions and good discussions
