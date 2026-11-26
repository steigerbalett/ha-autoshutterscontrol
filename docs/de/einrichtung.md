# Einrichtung Schritt für Schritt

Diese Anleitung führt dich vom Installieren bis zum ersten Rollladen, der morgens von selbst öffnet und
abends schließt. Für die ersten Schritte brauchst du etwa 15 Minuten. Alles Weitere kannst du später nach
und nach einschalten. Die vollständige Beschreibung aller Einstellungen steht in der
[Dokumentation](README.md).

**Inhalt**

1. [Bevor du anfängst](#1-bevor-du-anfängst)
2. [Installieren](#2-installieren)
3. [Integration hinzufügen](#3-integration-hinzufügen)
4. [Globale Einstellungen prüfen](#4-globale-einstellungen-prüfen)
5. [Rollläden hinzufügen](#5-rollläden-hinzufügen)
6. [Erst einmal testen: Simulation](#6-erst-einmal-testen-simulation)
7. [Profile für Gruppen von Rollläden](#7-profile-für-gruppen-von-rollläden)
8. [Einen Rollladen anpassen](#8-einen-rollladen-anpassen)
9. [Rezepte für typische Räume](#9-rezepte-für-typische-räume)
10. [Umstieg von FHEM](#10-umstieg-von-fhem)
11. [Die Übersicht](#11-die-übersicht)
12. [Wenn etwas nicht klappt](#12-wenn-etwas-nicht-klappt)

## So funktioniert es in einem Satz

Jede Einstellung gibt es auf drei Ebenen: **global** (für das ganze Haus), im **Profil** (für eine Gruppe,
z. B. „Südseite“) und am **Rollladen**. Der Rollladen nimmt immer den nächsten gesetzten Wert:
Rollladen → Profil → global → Standard. Du stellst also das meiste einmal global ein und trägst am Rollladen
nur ein, was dort anders ist. Ein leeres Feld heißt „erben“, und die Zeile `↳` unter dem Feld zeigt dir, was
geerbt wird.

## 1. Bevor du anfängst

Nötig ist nur ein Rollladen in Home Assistant, der seine Position kennt (eine `cover`-Entität mit Position
0–100 %). Alles andere ist optional und lässt sich später ergänzen:

| Was | Wofür | Ohne |
|---|---|---|
| Integration **Workday** (Arbeitstag) | andere Zeiten an Wochenende und Feiertagen | Montag bis Freitag sind Arbeitstage |
| **Helligkeitssensor** (lx) | Öffnen und Schließen nach Helligkeit, Beschattung | Sonnenstand wird genutzt |
| **Fensterkontakte** | Lüften, Aussperrschutz an der Terrassentür | keine Fensterfunktionen |
| **Personen** oder ein Schlafmodus | nur öffnen, wenn jemand wach ist | Fahrten nach Zeit und Sonne |
| **Außentemperatur**, Wetter | Beschattung bei Hitze, Frostschutz | Beschattung nur nach Sonne und Helligkeit |
| Regen- und Windsensor | Regen- und Windschutz | kein Wetterschutz |

Tipp: Lege die Workday-Integration zweimal an, einmal für heute und einmal mit einem Tag Versatz für morgen.
Dann weiß AutoShuttersControl abends schon, ob morgen ausgeschlafen wird.

## 2. Installieren

1. Öffne *Einstellungen → Marketplace* (ab Home Assistant 2026.11, vorher heißt es HACS).
2. Oben rechts die drei Punkte → *Benutzerdefinierte Repositories*.
3. Trage `https://github.com/steigerbalett/ha-autoshutterscontrol` ein, Typ *Integration*.
4. Versionen 0.x sind Vorabversionen: schalte beim Repository *Beta-Versionen anzeigen* ein.
5. *AutoShuttersControl for HA* installieren und Home Assistant neu starten.

Schneller geht es mit dem Knopf in der [README](../../README.md#deutsch).

## 3. Integration hinzufügen

1. *Einstellungen → Geräte & Dienste → Integration hinzufügen* → **AutoShuttersControl for HA**.
2. Es erscheint ein Formular mit den **Sensoren für das ganze Haus**. Wähle, was du hast. Leer lassen ist in
   Ordnung:
   - *Arbeitstag-Sensor (heute)* und *(morgen)*: die Workday-Binärsensoren.
   - *Helligkeitssensor*: ein Außensensor in lx.
   - *Außentemperatur*, *Wetter*, *Regensensor*, *Windgeschwindigkeit*: für Beschattung und Wetterschutz.
3. *Absenden*. Jetzt gibt es den Eintrag **AutoShuttersControl** mit einem zentralen Gerät. Dort liegen die
   Schalter für das ganze Haus, z. B. *Automatik*, *Pause*, *Beschattung*, *Urlaub* und *Simulation*.

Es gibt immer nur **einen** Eintrag für das ganze Haus. Rollläden und Profile hängen darunter.

## 4. Globale Einstellungen prüfen

Am Eintrag auf **Konfigurieren** klicken. Du siehst ein Menü mit Seiten. Für den Anfang reichen zwei:

**Zeitplan**

- *Morgens fahren nach* und *Abends fahren nach*: Standard ist **Sonne**. Der Rollladen öffnet bei
  Sonnenaufgang und schließt bei Sonnenuntergang, aber nie früher als *Früheste* und nie später als
  *Späteste* Zeit.
- Standard an Arbeitstagen: öffnen zwischen 05:00 und 08:30, schließen zwischen 16:00 und 22:00. Für freie
  Tage gibt es eigene Zeiten.
- Lieber feste Zeiten? Stelle den Modus auf **Zeit**. Dann fährt der Rollladen zur frühesten Zeit.
- Mit Helligkeitssensor: Modus **Helligkeit**, dazu auf der Seite *Helligkeit und Sonnenhöhe* die
  Schwellen *Öffnen ab* und *Schließen unter*.

**Positionen**

- *Position offen* (Standard 100 %) und *Position geschlossen* (Standard 0 %). Viele Rollläden lassen
  geschlossen gern einen kleinen Spalt, z. B. 10 %.

Wichtig: Änderungen auf den Seiten werden erst übernommen, wenn du am Ende im Menü auf
**💾 Speichern und schließen** klickst. Schließt du den Dialog vorher mit dem X, sind sie weg.

## 5. Rollläden hinzufügen

1. Am Eintrag auf **Rollläden hinzufügen** klicken.
2. Wähle einen oder gleich mehrere Rollläden aus. Ein Profil brauchst du jetzt noch nicht.
3. *Absenden*. Jeder Rollladen bekommt eigene Entitäten, z. B. *Nächste Öffnung*, *Nächstes Schließen*,
   *Zielzustand*, die Schalter *Automatik* und *Pause* und den Knopf *Zielzustand anfahren*.

Hat der Rollladen in Home Assistant ein eigenes Gerät, erscheinen diese Entitäten direkt auf diesem Gerät.

Ab jetzt fährt der Rollladen nach dem globalen Zeitplan.

## 6. Erst einmal testen: Simulation

Willst du erst sehen, was passieren würde, ohne dass sich etwas bewegt?

1. Am zentralen Gerät den Schalter **Simulation** einschalten (oder am Rollladen für nur diesen einen).
2. AutoShuttersControl entscheidet wie sonst, fährt aber nicht. Im Logbuch steht dann z. B. „würde auf 0 %
   fahren (Abend), Simulation“, und der Sensor *Simulierte Fahrt* zeigt die letzte Entscheidung.
3. Passt alles, Simulation wieder ausschalten.

Den aktuellen Plan siehst du jederzeit an den Sensoren *Nächste Öffnung* und *Nächstes Schließen*.

## 7. Profile für Gruppen von Rollläden

Ein Profil lohnt sich, sobald mehrere Rollläden dieselbe Abweichung haben, z. B. alle Fenster nach Süden mit
Beschattung oder alle Schlafzimmer mit späterer Öffnung.

1. Am Eintrag auf **Profil hinzufügen**, Namen eingeben, z. B. „Südseite“.
2. Im Menü die Seiten öffnen und nur das eintragen, was für diese Gruppe anders ist. Leere Felder erben von
   global.
3. **💾 Speichern und schließen**.
4. Am Rollladen (drei Punkte → *Neu konfigurieren*) → *Name und Profil* → Profil „Südseite“ wählen und
   speichern.

## 8. Einen Rollladen anpassen

Beim Rollladen auf die drei Punkte → **Neu konfigurieren**. Du siehst dasselbe Menü wie global. Trag nur ein,
was bei diesem einen Rollladen anders ist, und klicke dann auf **💾 Speichern und schließen**.

Felder, die es nur am Rollladen gibt:

- Seite *Fensterkontakte*: *Kontakt „offen“*, *Kontakt „gekippt“* oder ein *Fenstersensor mit drei
  Zuständen*.
- Seite *Bewohner und Selbstschutz*: *Quellen des Raum-Status* (z. B. die Personen, die hier schlafen) und *Gäste in diesem
  Raum*.
- Seite *Beschattung*: *Horizont des Fensters*, *Brüstung über dem Boden* und *Fensterhöhe*.
- Menüpunkt *Aus FHEM übernehmen*: die Einstellungen eines FHEM-Rollladens, siehe
  [Umstieg von FHEM](#10-umstieg-von-fhem).

Mit *Auf geerbten Wert zurücksetzen* leerst du Felder wieder.

## 9. Rezepte für typische Räume

### Schlafzimmer: erst öffnen, wenn alle wach sind

1. Global auf der Seite *Bewohner und Selbstschutz*: *Quellen des Haus-Status* = deine Personen.
2. Am Schlafzimmer-Rollladen, Seite *Bewohner und Selbstschutz*: *Quellen des Raum-Status* = z. B. ein Input Boolean
   „Schlafmodus“ oder ein Bettsensor (an = schläft).
3. Seite *Zeitplan*: *Morgens fahren nach* = **Bewohner (wenn wach)**. Der Rollladen öffnet, sobald der
   Schlafmodus ausgeht, aber spätestens zur spätesten Zeit.

### Südseite: Beschattung bei Sonne und Wärme

1. Profil „Südseite“ anlegen und den Rollläden zuweisen.
2. Im Profil, Seite *Beschattung*: *Beschattung* = **Immer**. *Sonnenrichtung von/bis* passt du an die
   Fassade an, z. B. 135° bis 225° für Süd.
3. Global gibt es schon sinnvolle Schwellen: ab 35000 lx und ab 18 °C außen. Ohne Helligkeitssensor zählen
   nur Sonnenstand und Temperatur.
4. Seite *Positionen*: *Position Beschattung*, z. B. 30 %.

Am Rollladen hilft der Knopf **Sonne hat das Fenster verlassen**: drück ihn, wenn die Sonne hinter dem
Nachbarhaus verschwindet. Dann weiß AutoShuttersControl, wo der Horizont dieses Fensters liegt.

### Terrassentür: nicht aussperren

1. Am Rollladen, Seite *Fensterkontakte*: den Türkontakt eintragen.
2. *Aussperrschutz* = **Weich**: Solange die Tür offen ist, fährt der Rollladen nicht nach unten. Die Fahrt
   wird nachgeholt, sobald die Tür zu ist. **Hart** lässt zusätzlich Regen- und Windschutz warten.

### Winter: andere Zeiten, sobald es kalt ist

1. Profil „Winter“ anlegen, z. B. mit früherem Schließen.
2. Am Rollladen, *Name und Profil*: *Alternatives Profil* = „Winter“ und *Entität für das alternative
   Profil* = der Binärsensor **Winter** des zentralen Geräts. Er geht an, wenn das 24-Stunden-Mittel der
   Außentemperatur unter 12 °C liegt.
3. Statt des Sensors geht auch ein fester Zeitraum, z. B. *ab* `1.11.` *bis* `31.3.`.

### Urlaub: bewohnt aussehen

Am zentralen Gerät den Schalter **Urlaub** einschalten. Morgen- und Abendfahrt verschieben sich dann jeden
Tag zufällig um bis zu 30 Minuten, je Rollladen anders.

### Schulferien: in den Ferien später öffnen

Zwei Wege, je nachdem, was du schon hast:

1. **Arbeitstag-Sensor im Profil**: Leg einen Template-Binärsensor an, der in den Ferien aus ist, z. B. aus
   einem Ferienkalender: `{{ is_state('binary_sensor.workday_sensor', 'on') and is_state('calendar.schulferien', 'off') }}`.
   Leg ein Profil „Kinderzimmer“ an und trag ihn dort auf der Seite *Sensoren* als *Arbeitstag-Sensor (heute)*
   ein. Dann gelten in den Ferien für diese Rollläden die Zeiten der freien Tage, für alle anderen nicht.
2. **Alternatives Profil mit Kalender**: Leg ein Profil „Ferien“ mit späterer frühester und spätester Öffnung an.
   Am Rollladen, *Name und Profil*: *Alternatives Profil* = „Ferien“, *Entität für das alternative Profil* =
   der Kalender mit den Ferien (z. B. `calendar.schulferien`, er ist an, solange ein Termin läuft). Für feste
   Ferien geht auch der Zeitraum *ab*/*bis*.

### Rauchmelder: im Notfall alles auf

1. *Konfigurieren* → *Sonderfunktionen*: *Notfall-Eingang* = deine Rauchmelder (Binärsensoren).
2. Geht einer an, fahren alle Rollläden auf (*Notfall-Position*, Standard 100 %), Markisen fahren ein, auch bei
   Automatik aus oder Pause.
3. Danach am zentralen Gerät **Notfall zurücksetzen** drücken. Erst dann fahren die Rollläden wieder normal.

## 10. Umstieg von FHEM

Deine Einstellungen aus ASC in FHEM lassen sich übernehmen. Die Namen in FHEM und in Home Assistant dürfen
verschieden sein, weil du die Zuordnung selbst wählst. Übernommen werden nur Einstellungen, also die
`attr`-Zeilen. Perl-Code und ein paar FHEM-eigene Attribute lassen sich nicht übertragen. Sie werden am Ende
aufgelistet.

### Alles auf einmal

1. In FHEM oben in die Befehlszeile eingeben:
   - `list -r TYPE=AutoShuttersControl` (das ASC-Gerät mit den globalen Einstellungen)
   - `list -r ASC=[12]` (alle Rollläden mit dem Attribut ASC 1 oder 2)
2. Die Ausgaben beider Befehle markieren und kopieren. Statt dessen geht auch die ganze `fhem.cfg`.
3. In Home Assistant: AutoShuttersControl → **Konfigurieren** → **Aus FHEM übernehmen** → Text einfügen.
4. Jedem FHEM-Rollladen den Rollladen in Home Assistant zuordnen. Vorschläge kommen aus ähnlichen Namen. Leer
   lassen heißt „nicht übernehmen“.
5. Den FHEM-Geräten (Sensoren, Fensterkontakte, Bewohner) Entitäten zuordnen.
6. Die Zusammenfassung zeigt, was passiert. Sind Rollläden schon eingerichtet, kannst du wählen, ob sie mit
   den FHEM-Werten aktualisiert werden. *Absenden* legt die übrigen Rollläden an und speichert die globalen
   Einstellungen.

Werte, die alle Rollläden gleich haben, landen in den globalen Einstellungen. Werte, die nur den Standard
wiederholen, entfallen. So bleibt am Rollladen nur, was wirklich anders ist.

### Einen einzelnen Rollladen

So übernimmst du die Einstellungen eines FHEM-Rollladens für einen Rollladen, den es in Home Assistant schon
gibt:

1. In FHEM: `list -r` und den Namen des Rollladens in FHEM, z. B. `list -r EG_Wohnzimmer_Rollo`. Die ganze
   Ausgabe kopieren.
2. In Home Assistant beim Rollladen die drei Punkte → *Neu konfigurieren* → **Aus FHEM übernehmen** → Text
   einfügen.
3. Stehen mehrere Rollläden im Text, wählst du den richtigen aus.
4. Geräte zuordnen (z. B. den Fensterkontakt).
5. Die Liste zeigt jede Einstellung, die übernommen wird. Optional *Bisherige eigene Werte dieses Rollladens
   vorher löschen*.
6. *Absenden* und danach **💾 Speichern und schließen**.

Tipp: Lass FHEM und Home Assistant nicht beide denselben Rollladen steuern. Sonst hält jede Seite die Fahrten
der anderen für eine Handfahrt. Schalte in FHEM das Attribut `ASC` des Rollladens auf 0, sobald er in Home
Assistant läuft.

## 11. Die Übersicht

**Konfigurieren** → **Übersicht** zeigt alle Rollläden mit Position, Ziel, nächsten Fahrten, letzter Fahrt,
Beschattung und Fenster, darunter alle verknüpften Sensoren mit ihrem aktuellen Wert. Ein ❗ zeigt eine Entität,
die es nicht gibt.

Der Dialog von Home Assistant ist schmal. Mehr Platz hat die Seite in der Seitenleiste: *Konfigurieren* →
*Fahrverhalten* → **Übersicht in der Seitenleiste** einschalten und speichern. Dann gibt es links den Eintrag
*AutoShuttersControl* mit einer großen Tabelle, die sich alle 10 Sekunden aktualisiert.

Auf derselben Seite gibt es den Reiter **Rollläden bearbeiten**. Dort siehst du alle Rollläden in einer Tabelle,
kannst sie hinzufügen, duplizieren und entfernen und mehrere auf einmal ändern: ankreuzen, *Auswahl bearbeiten*,
nur die Felder ändern, die für alle gelten sollen, und speichern.

Für das Dashboard gibt es die Karte **AutoShuttersControl**: *Dashboard bearbeiten* → *Karte hinzufügen* →
*Benutzerdefiniert*. Sie zeigt jeden Rollladen mit Position, Ziel und Grund, den nächsten Fahrten und Knöpfen.
Lade die Seite nach dem Installieren einmal neu, damit die Karte in der Auswahl erscheint.

## 12. Wenn etwas nicht klappt

**Der Rollladen fährt nicht.** Schau am Rollladen auf den Sensor *Nicht gefahren wegen*. Dort steht der Grund,
z. B. „Fenster offen“, „Manuelle Übersteuerung“ oder „Pause“. Das Logbuch des Rollladens zeigt jede
Entscheidung.

**Er fährt nach einer Handfahrt nicht mehr.** Das ist gewollt: Nach einer Fahrt von Hand pausiert die
Automatik (Standard 20 Minuten). Der Knopf *Übersteuerung beenden* hebt das sofort auf.

**Die Zeiten passen nicht.** Prüfe auf der Seite *Zeitplan* den Modus und die früheste und späteste Zeit. Der
Knopf *Zeiten neu berechnen* am zentralen Gerät rechnet sofort neu.

**Der Diagnose-Sensor *Hängt* ist an.** Der Rollladen ist nach einer Fahrt nicht an seiner Position
angekommen. Meldet er seine Position nicht zuverlässig, schalte auf der Seite *Fahrverhalten* *Jede Fahrt
prüfen* für diesen Rollladen aus.

**Woher kommt ein Wert?** Der Sensor *Zielzustand* zeigt im Attribut `effective_config` jeden wirksamen Wert
und ob er vom Rollladen, vom Profil, global oder vom Standard kommt.

**Ich will kurz alles anhalten.** Schalter *Pause* (danach fährt der Rollladen in seinen Zielzustand) oder
*Automatik* aus (es passiert gar nichts), global oder je Rollladen.

Weitere Fragen beantwortet die [Dokumentation](README.md#häufige-fragen).
