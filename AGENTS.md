# Video-Forensik-Analyzer – OpenCode Project Rules

## 1. Projektziel

Dieses Projekt ist ein modularer Video- und Bild-Forensik-Analyzer.

Ziel ist eine stabile, nachvollziehbare und erweiterbare Anwendung zur Analyse von Bildern und Videos.

Technologien:

* Python
* PyQt6
* MariaDB
* FFmpeg
* Git / GitHub
* MVP-Architektur

---

## 2. Architektur

Die bestehende Architektur ist grundsätzlich beizubehalten.

Verwendetes Architekturprinzip:

Model
View
Presenter

Zusätzliche technische Bereiche:

* analyzer
* database
* workers
* utilities
* configuration

Keine grundlegende Änderung der Architektur ohne vorherige Begründung.

Vor größeren strukturellen Änderungen:

1. bestehende Architektur analysieren
2. Auswirkungen beschreiben
3. Änderung vorschlagen
4. erst danach implementieren

---

## 3. PyQt6

Die Benutzeroberfläche darf niemals durch lang laufende Operationen blockiert werden.

Insbesondere dürfen folgende Operationen NICHT direkt im GUI-Thread ausgeführt werden:

* FFmpeg-Aufrufe
* Videoanalyse
* Bildanalyse großer Dateien
* Datenbankabfragen über größere Datenmengen
* Dateisystem-Scans
* Hash-Berechnungen großer Dateien
* PRNU-Analyse
* ELA
* Copy-Move-Analyse
* Resampling-Analyse
* FFT/Fourier-Analyse
* Video-Frame-Extraktion

Für solche Aufgaben sind Worker bzw. geeignete Hintergrundmechanismen zu verwenden.

Die GUI muss während einer Analyse responsiv bleiben.

---

## 4. Analyzer

Analyzer sollen möglichst unabhängig voneinander implementiert werden.

Ein Analyzer soll:

* klar definierte Eingaben besitzen
* klar definierte Ergebnisse liefern
* keine GUI-Abhängigkeit besitzen
* keine direkte Manipulation von UI-Elementen durchführen
* testbar sein
* Fehler kontrolliert behandeln

Analyzer sollen nach Möglichkeit über ein gemeinsames Interface eingebunden werden.

Beispiel:

Analyzer
├── ELAAnalyzer
├── CopyMoveAnalyzer
├── ResamplingAnalyzer
├── PRNUAnalyzer
├── JPEGGridAnalyzer
├── IlluminationAnalyzer
└── NoiseAnalyzer

Neue Analyzer sollen dieses Prinzip beibehalten.

---

## 5. Datenbank

MariaDB wird als zentrale Datenbank verwendet.

Datenbankzugriffe dürfen nicht unnötig im GUI-Thread erfolgen.

SQL-Abfragen müssen:

* parametrisiert sein
* SQL-Injection verhindern
* Fehler behandeln
* bei großen Datenmengen effizient sein

Keine unnötigen SELECT * Abfragen.

Indizes sollen bei größeren Tabellen berücksichtigt werden.

Datenbankänderungen dürfen nicht stillschweigend bestehende Daten zerstören.

---

## 6. Dateien und Medien

Das Programm muss mit großen Mengen von Bild- und Videodateien umgehen können.

Dateien sollen nicht unnötig vollständig in den Arbeitsspeicher geladen werden.

Bei großen Dateien bevorzugen:

* Streaming
* Chunk-Verarbeitung
* temporäre Dateien
* Generatoren
* kontrollierte Speicherverwendung

Keine unnötigen Kopien großer Bild- oder Videodaten.

---

## 7. Parallelisierung

Threads und Prozesse nicht ohne Begründung verwenden.

Vor Einführung einer parallelen Verarbeitung prüfen:

* CPU-bound oder I/O-bound?
* Thread oder Process?
* benötigter RAM?
* Anzahl gleichzeitiger Aufgaben?
* Auswirkungen auf PyQt6?
* Datenbankzugriffe?
* Abbruchmöglichkeit?

Keine unkontrollierte Erzeugung von Threads.

Thread-/Process-Pools bevorzugen.

---

## 8. Fehlerbehandlung

Keine Exceptions einfach verschlucken.

Nicht verwenden:

```
except:
    pass
```

Fehler müssen entweder:

* sinnvoll behandelt
* geloggt
* oder kontrolliert weitergegeben werden.

Benutzerfreundliche Fehlermeldungen sollen von technischen Fehlermeldungen getrennt werden.

---

## 9. Logging

Für technische Fehler und Analyseabläufe soll das Python-Logging-System verwendet werden.

Debug-Ausgaben mit print() nicht als dauerhafte Lösung verwenden.

Logging soll möglichst Informationen enthalten über:

* Zeitpunkt
* Analyzer
* Datei
* Operation
* Dauer
* Fehler
* relevante Parameter

Keine sensiblen Daten unnötig loggen.

---

## 10. Git

Vor Änderungen zuerst den aktuellen Git-Status prüfen.

Keine automatischen Änderungen an Git-History durchführen.

Insbesondere niemals ohne ausdrückliche Zustimmung:

* git reset --hard
* git push --force
* git rebase mit potenziell zerstörerischen Auswirkungen
* Löschen von Dateien

Vor einem Commit:

1. Änderungen prüfen
2. Tests ausführen
3. relevante Fehler korrigieren
4. Diff kontrollieren

---

## 11. Änderungen

Bei einer kleinen Aufgabe nur die notwendigen Dateien ändern.

Keine großflächigen Refactorings durchführen, wenn diese nicht erforderlich sind.

Bestehende funktionierende Logik nicht ohne Grund ersetzen.

Vor dem Ändern einer Funktion zuerst ihre Verwendung im Projekt prüfen.

---

## 12. Tests

Neue Funktionalität soll nach Möglichkeit mit Tests versehen werden.

Besonders wichtig:

* Analyzer
* Datenbankzugriffe
* Dateiverarbeitung
* Parser
* Berechnungen
* Bildverarbeitung
* Videoverarbeitung

Bei mathematischen/forensischen Verfahren sind reproduzierbare Testdaten zu verwenden.

---

## 13. Forensische Ergebnisse

Forensische Analyseergebnisse müssen nachvollziehbar sein.

Keine Aussage wie:

"Bild ist gefälscht"

wenn der verwendete Algorithmus lediglich Indikatoren liefert.

Stattdessen Ergebnisse beispielsweise als:

* unauffällig
* auffällig
* Indikator vorhanden
* Wahrscheinlichkeit
* Score
* technische Auffälligkeit

darstellen.

Methoden und Parameter sollen möglichst dokumentiert werden.

---

## 14. Sicherheit

Dateipfade, externe Programme und Benutzereingaben müssen validiert werden.

Keine Shell-Befehle mit ungeprüften Benutzereingaben zusammensetzen.

FFmpeg-Aufrufe möglichst über strukturierte Argumentlisten ausführen.

Keine Zugangsdaten oder Passwörter in den Quellcode schreiben.

---

## 15. OpenCode Arbeitsweise

Vor einer Änderung:

1. relevante Dateien untersuchen
2. bestehende Architektur verstehen
3. Abhängigkeiten prüfen
4. kleinste sinnvolle Änderung bestimmen

Bei komplexen Aufgaben zuerst einen Plan erstellen.

Nach einer Änderung:

1. Code prüfen
2. Tests ausführen
3. Fehler korrigieren
4. Änderung zusammenfassen

Keine Architekturänderung ohne Begründung.

Wenn Anforderungen unklar sind, nicht einfach eine große Änderung durchführen.

---

## 16. Prioritäten

Bei Zielkonflikten gilt:

1. Korrektheit
2. Stabilität
3. Datenintegrität
4. Nachvollziehbarkeit
5. Wartbarkeit
6. Performance
7. Komfort

Performance darf nicht auf Kosten der Datenintegrität gehen.

Forensische Nachvollziehbarkeit ist wichtiger als maximale Geschwindigkeit.

---

## 17. Dateien im Root-Ordner

Im Projekt-Root liegen Diagnose-, Test- und Beispieldateien, die kein Bestandteil des Anwendungs-Codes sind:

* `check_gpu.py`, `FFmpeg‑NVIDIA‑Diagnose.py` – GPU-/FFmpeg-Diagnoseskripte
* `789.mp4`, `23-45_5min.mp4`, `ffv1_test.mkv` – Beispiel-/Testvideos
* `ffmpeg.exe`, `ffprobe.exe`, `MediaInfo.exe`, `exiftool.exe` – gebündelte Binärdateien
* `text.txt`, `*.pyproj`, `*.slnx`, `*.pyproj.user` – Sonstiges/IDE

Diese Dateien bei Code-Analysen, Refactoring und Architekturaufgaben nicht berücksichtigen, sofern nicht ausdrücklich danach gefragt wird. Relevanter Projektcode liegt in `src/`, `main.py`, `setup_db.py` und `config/`.
