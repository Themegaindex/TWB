# Tribal Wars Bot (TWB)

Ein Open-Source-Bot für das Browsergame "Die Stämme".

TWB ist ein hochentwickelter Bot, der darauf ausgelegt ist, eine Vielzahl von Aufgaben im Spiel zu automatisieren. Von der Ressourcenverwaltung bis hin zur komplexen Angriffs- und Verteidigungsstrategie nimmt Ihnen TWB die repetitiven Aufgaben ab und ermöglicht es Ihnen, sich auf die strategische Planung zu konzentrieren.

## Discord-Community
Für Hilfe, Diskussionen und den Austausch mit anderen Nutzern gibt es einen [offiziellen Discord-Server](https://discord.gg/8PuzHjttMy).

## Wichtiger Hinweis (Disclaimer)
**Die Nutzung dieses Bots verstößt gegen die Spielregeln von "Die Stämme" und kann zur dauerhaften Sperrung deines Accounts führen.** Die Entwickler und Mitwirkenden dieses Projekts übernehmen keine Haftung für eventuelle Konsequenzen. Du nutzt diese Software auf eigenes Risiko. Wir empfehlen dringend, den Bot so zu konfigurieren, dass sein Verhalten menschlichem Spiel möglichst nahekommt (z. B. durch realistische Pausenzeiten), um das Entdeckungsrisiko zu minimieren.

## Features

TWB bietet eine breite Palette an Funktionen, die eine umfassende Automatisierung des Spielgeschehens ermöglichen:

*   **Kooperativer Modus:** Du kannst weiterhin über den Browser spielen, während der Bot im Hintergrund Aufgaben verwaltet, ohne dass es zu Konflikten kommt.
*   **Gebäudemanager:** Automatisiert den Ausbau von Gebäuden basierend auf anpassbaren Vorlagen (`templates`).
*   **Truppenmanager:** Rekrutiert automatisch Einheiten basierend auf Vorlagen und passt die Produktion an die verfügbaren Ressourcen an.
*   **Verteidigungsmanager:** Reagiert auf eingehende Angriffe, evakuiert Truppen und kann automatisch Unterstützung von anderen eigenen Dörfern anfordern.
*   **Flaggen-Management:** Weist Flaggen automatisch zu, um Boni (z.B. Ressourcenproduktion, Verteidigungsstärke) zu maximieren.
*   **Farm-Manager:**
    *   Sucht und farmt automatisch Barbarendörfer in der Umgebung.
    *   **Intelligente Optimierung:** Analysiert Berichte, um die Effizienz zu bewerten. Passt die Farmziele und Angriffspausen dynamisch an (z.B. längere Pausen für Dörfer mit wenig Beute oder hohen Verlusten).
*   **Marktplatz-Manager:** Gleicht Ressourcen zwischen den Dörfern automatisch aus, um Engpässe zu vermeiden und den Bau zu beschleunigen.
*   **Forschungs-Manager:** Führt automatisch Forschungen in der Schmiede durch, sobald die Voraussetzungen erfüllt sind.
*   **Automatische Adelung:** Prägt Münzen und adelt vollautomatisch neue Dörfer.
*   **Berichts-Manager:** Verarbeitet und analysiert eingehende Berichte.
*   **ReCaptcha-Umgang:** Umgeht das Login-Captcha durch die Verwendung eines gültigen Browser-Cookies, was einen ununterbrochenen Betrieb ermöglicht, solange die Browser-Sitzung gültig ist.
*   **Web-Interface:** Ein lokales Web-Dashboard zur Überwachung und Steuerung des Bots.
*   **Benachrichtigungen:** Unterstützt Benachrichtigungen über [Telegram](https://telegram.org/), um dich über wichtige Ereignisse (z.B. Angriffe) zu informieren.
*   **Dynamische Konfiguration:**
    *   Neu eroberte Dörfer werden automatisch zur Konfiguration hinzugefügt.
    *   Die Konfiguration wird bei Updates automatisch mit neuen Optionen zusammengeführt, ohne deine Einstellungen zu überschreiben.

## Installation

Folge dieser Anleitung, um den Bot auf deinem System einzurichten.

### 1. Voraussetzungen

*   **Python 3.x:** Du benötigst eine installierte Version von Python 3. Eine Anleitung zur Installation findest du auf der [offiziellen Python-Website](https://www.python.org/downloads/). Stelle sicher, dass du bei der Installation die Option "Add Python to PATH" aktivierst.
*   **Bot-Dateien:** Lade das Projekt von GitHub herunter. Du kannst dies entweder über `git clone` tun oder indem du das Projekt als ZIP-Datei herunterlädst und entpackst.

### 2. Abhängigkeiten installieren

Öffne eine Kommandozeile (Terminal, PowerShell, CMD) im Hauptverzeichnis des Bots (dort, wo sich die `requirements.txt`-Datei befindet) und führe den folgenden Befehl aus, um alle notwendigen Python-Pakete zu installieren:

```bash
pip install -r requirements.txt
```

Oder, falls du mehrere Python-Versionen hast, stelle sicher, dass du die `pip`-Version von Python 3 verwendest:

```bash
python -m pip install -r requirements.txt
```

### 3. Bot starten

Nachdem die Installation der Abhängigkeiten abgeschlossen ist, kannst du den Bot mit diesem Befehl starten:

```bash
python twb.py
```

Beim ersten Start wird der Bot feststellen, dass noch keine Konfigurationsdatei (`config.json`) vorhanden ist und dich durch einen interaktiven Einrichtungs-Wizard führen.

## Erster Start & Konfiguration

Die gesamte Steuerung des Bots erfolgt über die zentrale Konfigurationsdatei `config.json`. Wenn du den Bot zum ersten Mal startest, wird eine solche Datei für dich erstellt.

### Der Konfigurations-Wizard

Wenn du `python twb.py` ohne eine vorhandene `config.json` ausführst, startet ein interaktiver Wizard, der dich nach den grundlegendsten Informationen fragt:
1.  **Spiel-URL:** Die vollständige URL, die du in deinem Browser siehst, wenn du im Spiel angemeldet bist (z.B. `https://de123.die-staemme.de/game.php?village=12345&screen=overview`).
2.  **User-Agent:** Dein Browser-User-Agent, um die Bot-Anfragen zu tarnen. Suche einfach in Google nach "what is my user agent" und kopiere die Zeichenkette.

Nachdem du diese Schritte befolgt hast, wird eine `config.json` erstellt und der Bot ist bereit für die weitere Konfiguration.

### Die `config.json` im Detail

Du kannst die `config.json` mit einem beliebigen Texteditor öffnen und bearbeiten. Der Bot lädt Änderungen an der Datei automatisch bei jedem neuen Durchlauf neu.

Hier ist eine detaillierte Erklärung aller Sektionen und Parameter:

---

### `server`
Diese Sektion enthält die grundlegenden Informationen zu deinem Spielserver.

*   `"server"`: Der Kurzname deines Servers (z.B. `"de123"`).
*   `"endpoint"`: Die URL zum Spiel-Endpunkt. Endet normalerweise auf `game.php`. Wird vom Wizard automatisch gesetzt.
*   `"server_on_twstats"`: Setze dies auf `false`, wenn deine Welt nicht auf [twstats.com](http://twstats.com/) gelistet ist. Dies beeinflusst, wie der Bot Weltdaten (z.B. für Gebäude) abruft.

---

### `bot`
Allgemeine Einstellungen zum Verhalten des Bots.

*   `"active_hours"`: Die Stunden, in denen der Bot aktiv sein soll (z.B. `"6-23"` für 06:00 bis 23:00 Uhr). Außerhalb dieser Zeit läuft der Bot im inaktiven Modus.
*   `"active_delay"`: Die minimale Wartezeit (in Sekunden) zwischen den Aktionen während der aktiven Stunden.
*   `"inactive_delay"`: Die minimale Wartezeit im inaktiven Modus.
*   `"inactive_still_active"`: Wenn `true`, führt der Bot auch im inaktiven Modus weiterhin Aktionen aus, nur eben langsamer. Wenn `false`, stoppt der Bot komplett und deine Sitzung läuft wahrscheinlich ab.
*   `"add_new_villages"`: Wenn `true`, werden neu eroberte Dörfer automatisch zur Konfiguration hinzugefügt, wobei die Einstellungen aus `village_template` übernommen werden.
*   `"user_agent"`: Dein Browser-User-Agent. **Sehr wichtig, um das Entdeckungsrisiko zu senken.**

---

### `building`
Einstellungen für den Gebäudemanager.

*   `"manage_buildings"`: Globaler Schalter. Wenn `false`, wird der Bau in allen Dörfern deaktiviert.
*   `"default"`: Die Standard-Bauvorlage aus dem `templates/builder/` Ordner (z.B. `"purple_predator"`).
*   `"max_lookahead"`: Wie viele Gebäude in der Bauschleife der Bot überspringen darf, wenn die Voraussetzungen (z.B. Rohstoffe) nicht erfüllt sind. Ein Wert unter 5 wird empfohlen.
*   `"max_queued_items"`: Die maximale Anzahl an Gebäuden, die gleichzeitig in der Bauschleife sein können.

---

### `units`
Einstellungen für die Truppenrekrutierung.

*   `"recruit"`: Globaler Schalter. Wenn `true`, rekrutiert der Bot Einheiten.
*   `"upgrade"`: Wenn `true`, forscht der Bot automatisch Einheiten, die in der aktuellen Truppenvorlage des Dorfes definiert sind.
*   `"default"`: Die Standard-Truppenvorlage aus dem `templates/troops/` Ordner (z.B. `"basic"`).
*   `"batch_size"`: Die Anzahl der Einheiten, die der Bot auf einmal zu rekrutieren versucht. Im Lategame sind Werte von 500-1500 sinnvoll.
*   `"manage_defence"`: Globaler Schalter für das Verteidigungsmanagement.

---

### `village_template` & Dorf-spezifische Konfiguration
Dies ist eine Vorlage für alle neu hinzugefügten Dörfer. Jedes Dorf in der `"villages"` Sektion kann diese Einstellungen individuell überschreiben.

*   `"building"`: Überschreibt die globale Bauvorlage für dieses Dorf.
*   `"units"`: Überschreibt die globale Truppenvorlage für dieses Dorf.
*   `"managed"`: Wenn `false`, wird dieses Dorf vom Bot komplett ignoriert.
*   `"prioritize_building"`: Wenn `true`, wird die Rekrutierung pausiert, bis die Bauschleife voll ist.
*   `"prioritize_snob"`: Wenn `true`, reserviert der Bot Ressourcen für die Münzprägung und den Bau von Adelsgeschlechtern.
*   `"snobs"`: Die maximale Anzahl an AGs, die in diesem Dorf gebaut werden sollen.
*   `"additional_farms"`: Eine Liste von Dorf-IDs (als Strings), die zusätzlich zu den automatisch gefundenen Barbarendörfern gefarmt werden sollen. **Vorsicht:** Der Bot prüft nicht, wem diese Dörfer gehören!
*   `"gather_enabled"`: Wenn `true`, schickt der Bot Truppen zum Sammeln, wenn sie nicht für Angriffe oder Farmen gebraucht werden.

---

### `farms`
Einstellungen für den Farm-Manager.

*   `"farm"`: Globaler Schalter. Wenn `true`, ist das Farmen aktiviert.
*   `"search_radius"`: Der Radius (in Feldern) um deine Dörfer, in dem nach Barbarendörfern gesucht wird.
*   `"default_away_time"`: Standard-Wartezeit (in Sekunden) bis zum nächsten Angriff auf eine Farm.
*   `"full_loot_away_time"`: Kürzere Wartezeit für Farmen, die beim letzten Angriff volle Beute gebracht haben.
*   `"low_loot_away_time"`: Längere Wartezeit für Farmen mit geringer Beute (wird vom Bot automatisch verwaltet).
*   `"max_farms"`: Die maximale Anzahl an Farmen, die ein Dorf gleichzeitig verwalten soll.
*   `"forced_peace_times"`: Eine Liste von Zeiträumen, in denen nicht angegriffen wird (z.B. an Feiertagen).

---

### `market`
Einstellungen für den Marktplatz.

*   `"auto_trade"`: Wenn `true`, erstellt der Bot automatisch Angebote auf dem Marktplatz, um Ressourcen auszugleichen.
*   `"max_trade_duration"`: Maximale Laufzeit für Angebote in Stunden.
*   `"trade_multiplier"`: Wenn `true`, versucht der Bot, ungleiche Tauschgeschäfte zu einem besseren Kurs zu erstellen (z.B. 900 Lehm für 1000 Holz anbieten).

---

### `world`
Diese Optionen werden vom Bot normalerweise automatisch erkannt und gesetzt.

*   `"knight_enabled"`, `"flags_enabled"`, `"quests_enabled"`, etc.: `true` oder `false`, je nachdem, welche Features die Spielwelt hat.

---

### `reporting` & `notifications`
Einstellungen für Logging und Benachrichtigungen.

*   `"reporting"`:
    *   `"enabled"`: Wenn `true`, wird ein detailliertes Log geschrieben.
    *   `"connection_string"`: Der Speicherort. Standardmäßig `file://cache/logs/twb_{ts}.log`.
*   `"notifications"`:
    *   `"enabled"`: Wenn `true`, werden Benachrichtigungen via Telegram gesendet.
    *   `"channel_id"`: Deine Telegram Chat-ID.
    *   `"token"`: Der Token deines Telegram-Bots.

## Funktionsweise (Wie es funktioniert)

Dieser Abschnitt gibt einen Einblick in die internen Abläufe des Bots.

### Login und Anti-Captcha

"Die Stämme" schützt den normalen Login-Vorgang mit einem ReCaptcha, was eine Automatisierung erschwert. TWB umgeht dieses Problem auf elegante Weise: Anstatt sich mit Benutzername und Passwort anzumelden, verwendet der Bot eine **gültige Sitzungs-Cookie**.

**Wie funktioniert das?**
1.  Du loggst dich normal im Browser in deinen Account ein.
2.  Dein Browser erhält vom Spieleserver ein Cookie, das deine Sitzung identifiziert.
3.  Du kopierst den Wert dieses Cookies und fügst ihn beim ersten Start des Bots ein.
4.  Der Bot sendet dieses Cookie bei jeder Anfrage an den Server und erscheint so, als wäre er ein ganz normaler, eingeloggter Browser.

**Wichtig:** Diese Cookies haben eine begrenzte Lebensdauer. Um zu vermeiden, dass der Bot plötzlich ausgeloggt wird, solltest du dich **mindestens 1-2 Mal pro Tag im Browser neu einloggen** und dem Bot bei Aufforderung ein frisches Cookie zur Verfügung stellen. Ein 24/7-Betrieb mit einem einzigen Cookie ist ein hohes Risiko für eine Sperre.

### Der Hauptprozess (`twb.py`)

Der Bot operiert in einer Endlosschleife, die bei jedem Durchlauf folgende Schritte ausführt:
1.  **Prüfung der aktiven Stunden:** Der Bot prüft, ob er sich in den in der Konfiguration definierten `"active_hours"` befindet.
2.  **Internet-Check:** Eine kurze Prüfung, ob eine Internetverbindung besteht.
3.  **Konfiguration laden:** Die `config.json` wird neu eingelesen, um Änderungen zu übernehmen.
4.  **Übersicht abrufen:** Der Bot lädt die Dorf-Übersichtsseite. Dadurch erkennt er die aktuell verfügbaren Dörfer und die Welteinstellungen (z.B. ob Ritter oder Flaggen aktiv sind).
5.  **Dörfer durchlaufen:** Der Bot iteriert durch jedes in der `config.json` als `"managed": true` markierte Dorf und führt die entsprechenden Aktionen aus (Bauen, Rekrutieren, Farmen etc.).
6.  **Farm-Manager ausführen:** Nach dem Durchlauf aller Dörfer wird der globale Farm-Manager (`farm_manager`) aufgerufen, um die Farm-Statistiken zu analysieren und zu optimieren.
7.  **Pause:** Der Bot pausiert für die in `"active_delay"` oder `"inactive_delay"` definierte Zeit, plus eine zufällige Spanne, um menschliches Verhalten zu simulieren.

### Automatisches Farm-Management (`manager.py`)

Eine der stärksten Funktionen des Bots ist die selbstständige Optimierung der Farm-Effizienz. Dies geschieht durch die Analyse der im `cache/reports/` Ordner gespeicherten Berichte.

*   **Analyse:** Der `farm_manager` berechnet für jede Farm die durchschnittliche Beute und die prozentualen Truppenverluste.
*   **Profil-Anpassung:**
    *   Farmen mit konstant hoher Beute werden als `"high_profile"` markiert und häufiger angegriffen.
    *   Farmen mit geringer Beute oder leichten Verlusten werden als `"low_profile"` markiert, und die Pause bis zum nächsten Angriff wird erhöht.
*   **Sicherheits-Check:** Wenn eine Farm konstant hohe Verluste (>50%) verursacht, wird sie als unsicher (`"safe": false`) markiert und nicht mehr automatisch angegriffen.

### Das Web-Interface

TWB enthält ein optionales Web-Interface, das eine visuelle Übersicht über den Bot-Status bietet.
1.  Navigiere in deiner Kommandozeile in das `webmanager` Verzeichnis: `cd webmanager`
2.  Starte den Server: `python server.py`
3.  Öffne deinen Browser und gehe zu `http://127.0.0.1:5000/`, um das Dashboard zu sehen.

### Automatische Konfigurations-Aktualisierung

Wenn der Bot aktualisiert wird und neue Konfigurations-Optionen in der `config.example.json` hinzukommen, erkennt TWB dies automatisch. Deine bestehende `config.json` wird gesichert (`config.bak`) und die neuen Optionen werden intelligent hinzugefügt, **ohne deine bisherigen Einstellungen zu überschreiben**. Dies stellt sicher, dass deine Konfiguration immer auf dem neuesten Stand ist, ohne dass du sie manuell anpassen musst.

## FAQ (Häufig gestellte Fragen)

**F: Wie bekomme ich das Browser-Cookie?**

A: Das Cookie findest du in den Entwicklertools deines Browsers (Taste F12).
1.  Gehe zum "Netzwerk" (oder "Network") Tab.
2.  Lade die Spielseite neu (F5).
3.  Suche nach einer Anfrage, die `game.php` heißt.
4.  Klicke darauf und suche in den "Anfrage-Headern" (Request Headers) nach dem `cookie:` Eintrag. Kopiere den gesamten Wert.

![Screenshot, der den Cookie-Header in den Chrome-Entwicklertools zeigt](readme/network.JPG)

**F: Was soll ich tun, wenn der Bot abstürzt?**

A: Der Bot ist so konzipiert, dass er sich nach einem Absturz bis zu dreimal selbst neu startet. Wenn er dauerhaft abstürzt, überprüfe die Log-Dateien im `cache/logs/` Ordner. Dort findest du detaillierte Fehlermeldungen, die dir (oder der Community im Discord) helfen können, das Problem zu diagnostizieren.

**F: Wie hoch ist das Risiko, gesperrt zu werden?**

A: Das Risiko ist real und sollte nicht unterschätzt werden. Um es zu minimieren:
*   Verwende realistische Pausenzeiten (`active_delay`).
*   Nutze die `"active_hours"`, um eine "Schlafenszeit" für den Bot zu simulieren.
*   Aktualisiere dein Cookie regelmäßig.
*   Vermeide es, den Bot auf brandneuen Welten oder mit einem neuen Account zu aggressiv zu nutzen.

**F: Wie aktualisiere ich den Bot auf eine neue Version?**

A: Wenn du `git` verwendest, führe einfach `git pull` im Bot-Verzeichnis aus. Wenn du die ZIP-Datei heruntergeladen hast, lade die neue Version herunter, entpacke sie und kopiere deine `config.json` in den neuen Ordner. Dank der automatischen Konfigurations-Aktualisierung bleiben deine Einstellungen erhalten.

## Verbesserungsvorschläge

Dieses Projekt hat eine solide Basis, aber es gibt immer Raum für Weiterentwicklungen. Hier sind einige Ideen:

*   **Erweiterte Anti-Bot-Erkennungsmuster:** Implementierung von zufälligeren Klickpfaden, variableren Timings und Mausbewegungs-Simulation (z.B. über eine Browser-Automatisierungs-Bibliothek wie Selenium oder Playwright), um die Erkennung weiter zu erschweren.
*   **Ausbau des Web-Interface:** Das Web-UI könnte um interaktive Elemente erweitert werden, z.B. das Ändern von Konfigurationen, das manuelle Starten von Bauaufträgen oder das Einsehen von detaillierten Dorf-Statistiken direkt im Browser.
*   **Multi-Account-Unterstützung:** Die Architektur könnte erweitert werden, um mehrere Accounts (z.B. auf unterschiedlichen Welten) gleichzeitig von einer einzigen Bot-Instanz aus zu verwalten.
*   **Vorlagen-Editor:** Ein Tool oder ein Bereich im Web-UI, der das Erstellen und Anpassen von Bau- und Truppenvorlagen vereinfacht, anstatt Textdateien manuell bearbeiten zu müssen.

## Lizenz

Dieses Projekt steht unter der GNU General Public License v3.0. Details findest du in der `LICENSE.md` Datei.
