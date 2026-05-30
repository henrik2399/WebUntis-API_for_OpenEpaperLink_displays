# WebUntis API für OpenEPaperLink

Eine Brücke zwischen **WebUntis** und **OpenEPaperLink-Displays**. Das Projekt
liest die Raumbelegung (Stundenplan) aus der öffentlichen WebUntis-Monitoransicht
und stellt sie als fertige Zeichenbefehle bereit, die ein E-Paper-Display direkt
darstellen kann.

## Wie es funktioniert

```
WebUntis (Webseite)  ->  Scraper (Selenium + BeautifulSoup)
                     ->  Flask-Server (Cache + Layout)
                     ->  /display/<raum>  ->  OpenEPaperLink-Display
```

- **[webuntis_api.py](webuntis_api.py)** – startet einen headless Chrome, öffnet die
  WebUntis-Monitorseite der Schule und liest pro Raum die Stunden aus
  (Zeit, Klasse, Fach, Lehrer, Status).
- **[server.py](server.py)** – ein Flask-Webserver, der die Daten alle 5 Minuten im
  Hintergrund aktualisiert und sie als Display-Befehle (Text/Linien) ausliefert.
- **data.json** – Beispiel-/Cache-Datei mit einmal gescrapten Daten.

## Installation

Voraussetzung: Python 3 und ein installierter Google Chrome.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Starten

```powershell
python server.py
```

Der Server läuft dann auf `http://0.0.0.0:5000` (im LAN über die IP des Rechners
erreichbar). Nach dem Start dauert es einige Sekunden, bis die ersten Daten da
sind – solange zeigt das Display „Lade Daten…".

## Endpunkte

| Endpunkt | Beschreibung |
|----------|--------------|
| `/display/<raum>` | **Hauptendpunkt** – Zeichenbefehle für das Display |
| `/api/rooms` | Liste aller verfügbaren Räume |
| `/api/raw/<raum>` | Rohdaten eines Raums (Debug) |
| `/api/refresh` | Erzwingt sofortiges Neu-Laden der Daten |
| `/config` | Display-Konfiguration lesen/setzen |

## Nutzung in OpenEPaperLink

Der Raum wird **nicht** in OpenEPaperLink eingestellt, sondern steckt in der URL –
der letzte Teil ist der Raumname:

| URL | Display zeigt |
|-----|---------------|
| `http://<server-ip>:5000/display/Aul` | Aula |
| `http://<server-ip>:5000/display/034` | Raum 034 |

So richtest du ein Display ein:

1. Im OpenEPaperLink-Access-Point den Tag auswählen.
2. Als Inhaltstyp **„JSON template"** wählen.
3. Im URL-Feld die Adresse mit dem gewünschten Raum eintragen, z. B.
   `http://192.168.178.50:5000/display/Aul`.

Jedes Display bekommt also seine eigene URL mit dem passenden Raumnamen. Welche
Raumnamen gültig sind, zeigt `http://<server-ip>:5000/api/rooms`.

## Layout

Das Display (296×128) zeigt:

```
Aul                         Sa,   15:57     <- Raum links, Tag + Uhrzeit rechts
-------------------------------------------  <- roter Trennstrich
13:15 - 14:00            JOr SUT             <- Stunde 1: Zeit, Fach, Lehrer
5a - 6d                                      <- Klasse(n)
-------------------------------------------
09:45 - 10:30            En SCH              <- Stunde 2
7c
```

- Es werden die **nächsten zwei Stunden** angezeigt.
- **Doppelstunden** (gleiche Klasse/Fach/Lehrer in direkt aufeinanderfolgenden
  Stunden) zählen als **ein** Eintrag mit zusammengefasster Zeit.
- Bei **mehr als zwei Klassen** wird nur die erste und letzte angezeigt (`5a - 6d`).
- Ausgefallene Stunden werden rot durchgestrichen.

## Hinweise

- Die Schule ist über den Parameter `school` in [webuntis_api.py](webuntis_api.py)
  festgelegt (Standard: `katharineum`). Die URL ergibt sich daraus automatisch als
  `https://<school>.webuntis.com/...`.
- Die Schriftarten `fonts/bahnschrift20` und `fonts/bahnschrift30` müssen auf dem
  OpenEPaperLink-Access-Point vorhanden sein.
- Server-Rechner und Access-Point müssen sich im selben Netzwerk befinden.
