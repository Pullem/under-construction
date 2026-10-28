# Video-Forensik-Analyzer – OpenCode Project Rules

## 1. Projektziel

Dieses Projekt ist ein modularer Video- und Bild-Forensik-Analyzer.

Ziel ist eine stabile, nachvollziehbare und erweiterbare Anwendung zur Analyse von Bildern und Videos.
Der Schwerpunkt liegt auf der täglichen Praxis eines Bild- und Video-Forensikers.

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

---

## 18. Worker (Bestand)

Alle lang laufenden Aufgaben laufen über `QRunnable`-Worker im `QThreadPool` des Presenters.

Verwendetes Muster:

* Klasse erbt von `QRunnable`
* Signale in einer eigenen `QObject`-Klasse (`...WorkerSignals`)
* Erfolg über `result` / `progress` / `finished` melden
* Fehler als `AppError`-JSON über `error` melden (`err.to_json()`, siehe `src/utils/errors.py`)
* Keine direkten UI-Zugriffe im Worker
* Logging über `logging.getLogger(__name__)`; Kontext über `set_log_context()` / `clear_log_context()`
* Neu hinzugefügte Worker in `src/workers/__init__.py` exportieren

Vorhandene Worker:

| Worker | Datei | Zweck |
|---|---|---|
| `DbWorker` | `src/workers/db_workers.py` | Generische Datenbank-Abfragen ausserhalb des GUI-Threads |
| `ScanWorker` | `src/workers/db_workers.py` | Dateisystem-Scan eines Ordners nach Medien-Endungen |
| `PostProcessWorker` | `src/workers/db_workers.py` | Hash, MediaInfo, ExifTool nach FFmpeg-Lauf |
| `AnalysisWorker` | `src/workers/db_workers.py` | Komplett-Analyse: Hash, MediaInfo, ExifTool, Thumbnail, DB-Speicherung |
| `ElaWorker` | `src/workers/ela_analysis.py` | ELA-Analyse |
| `CopyMoveWorker` | `src/workers/copy_move_analysis.py` | Copy-Move-Erkennung (SIFT), optional CUDA |
| `ResamplingWorker` | `src/workers/resampling_analysis.py` | Resampling-Erkennung (FFT), optional GPU, chunked |
| `JpegGridWorker` | `src/workers/jpeg_grid_analysis.py` | JPEG-Raster-/Blockiness-Analyse |
| `NoiseEstimatorWorker` | `src/workers/noise_estimation.py` | Rauschprofil über Frames (σ, Verteilung) |
| `SharpnessDetectorWorker` | `src/workers/sharpness_analysis.py` | Schärfe-/Unschärfe-Indikatoren pro Frame (Laplacian-Varianz, Tenengrad) |
| `MotionAnalyzerWorker` | `src/workers/motion_analysis.py` | Bewegungsanalyse (Dense Optical Flow, Farneback) |
| `FfprobeWorker` | `src/workers/ffprobe_worker.py` | ffprobe/ffmpeg-Subprozess (modusabhängiges Kommando) |
| `VSMetadataWorker` | `src/workers/vs_metadata_worker.py` | Video-Metadaten via VapourSynth/BestSource |
| `ThumbnailWorker` | `src/workers/thumbnail_worker.py` | Thumbnails via Modell/FFmpeg (Alt-Pfad) |
| `VSThumbnailWorker` | `src/workers/vs_thumbnail_worker.py` | Thumbnails via VapourSynth/BestSource |
| `ImportWorker` | `src/import_dialog.py` | Datei-Import: Kopieren, Lieferant/Lieferung, Fortschritt |

Hinweis: `src/workers/analysis_workers.py.bak` ist eine veraltete Backup-Datei (frühere Zusammenfassung der Analyse-Worker). Sie ist kein Bestandteil des Laufzeitsystems und sendet Fehler als rohen String statt als `AppError`-JSON – beim Dokumentieren oder Refactoring nicht als Referenz verwenden.

---

## 19. VapourSynth

* `VSMetadataWorker` und `VSThumbnailWorker` verwenden VapourSynth mit dem BestSource-Plugin.
* Plugin-Pfad: Umgebungsvariable `VAPOURSYNTH_PLUGIN_PATH`, sonst `vapoursynth_plugins/bestsource.dll` relativ zum Projektroot.
* Das Plugin darf nur einmal geladen werden – vor `LoadPlugin` prüfen, ob `com.vapoursynth.bestsource` bereits im Core registriert ist (sonst Duplikat-Fehler).
* `VSMetadataWorker`-Modi: `streams`, `quickcheck`, `format`. Diese Modi laufen in `src/presenter/ffmpeg_ops.py` über VapourSynth; andere Modi laufen weiter über `FfprobeWorker`.
* Die Ausgabe wird kompatibel zur bisherigen ffprobe-JSON-Struktur aufgebaut. BestSource liefert keine Codec-Bezeichnung – betroffene Felder bleiben `unknown` und dürfen nicht als echte Werte interpretiert werden.
* Fehler wie bei allen Workern als `AppError`-JSON melden.
* Installationsdokumentation: `documentation/vapoursynth_installation_guide.md`, `documentation/vapoursynth_manual_install.md`, `documentation/vapoursynth_integration_final.md`.

---

## 20. GPU-Beschleunigung

* Konfiguration: `config/gpu.ini`, ausgewertet von `src/utils/gpu_config.py` (`GPUConfig`: `enabled`, `device`, `device_index`, `decode_hwaccel`, `thumbnail_hwaccel`, `max_vram`, Chunk-Größe).
* Gültige `decode_hwaccel`-Werte: unter anderem `nvdec` und `cuda` (Validierung in `GPUConfig`).
* Verfügbarkeit über `check_cuda_available()` prüfen; Initialisierung in einer `_init_gpu()`-Methode abfangen.
* Eingesetzt für:
  * FFmpeg-Decode: `-hwaccel nvdec`/`cuda` (`src/model/media.py`, `src/presenter/ffmpeg_ops.py`)
  * Thumbnail-Skalierung: `scale_cuda=120:-2`
  * CopyMove: CUDA-SIFT (`cv2.cuda_SIFT_create`, `GpuMat`)
  * Resampling: GPU-FFT chunked (`_gpu_fft2_chunked`, `_gpu_rfft_chunked`)
* GPU ist immer optional: Ohne CUDA, bei `enabled = false` oder bei Fehlern muss der CPU-Pfad laufen. Keine GPU-Annahmen ohne Prüfung, keine verschluckten Fehler (loggen).
* Diagnose im Root: `check_gpu.py`, `FFmpeg-NVIDIA-Diagnose.py`; `opencv-python-cuda-build/` liefert die CUDA-fähige OpenCV-Variante.

---

## 21. Roadmap: Geplante Video-Analyzer-Worker

**Status: geplant – derzeit nicht implementiert.** Diese Klassen existieren im Code noch nicht (Stand: 26.10.2026) und dürfen weder importiert noch als vorhanden referenziert werden.

Geplante Worker, umgesetzt nach dem Muster aus Abschnitt 18 (`QRunnable` + `...WorkerSignals`, keine GUI-Abhängigkeit, `AppError`-Fehler, testbar):

| Worker | Geplanter Zweck |
|---|---|
| ~~`NoiseEstimatorWorker`~~ | ~~Rauschprofil über Frames schätzen (σ, Verteilung)~~ → **umgesetzt** (26.10.2026), siehe Abschnitt 18 (`src/workers/noise_estimation.py`, Tests in `src/tests/test_noise_estimation.py`) |
| ~~`SharpnessDetectorWorker`~~ | ~~Schärfe-/Unschärfe-Indikatoren pro Frame (z. B. Laplacian-Variance)~~ → **umgesetzt** (26.10.2026), siehe Abschnitt 18 (`src/workers/sharpness_analysis.py`, Tests in `src/tests/test_sharpness_analysis.py`) |
| ~~`MotionAnalyzerWorker`~~ | ~~Bewegungsanalyse (optical flow, Kamerabewegung)~~ → **umgesetzt** (26.10.2026), siehe Abschnitt 18 (`src/workers/motion_analysis.py`, Tests in `src/tests/test_motion_analysis.py` - Arbeitspaket) |
| `VideoStabilizerWorker` | Stabilitäts-/Wackelbewegungs-Indikatoren |
| `NightVisionEnhancerWorker` | Indikatoren für Nachtsicht-/IR-Material |
| `BrightnessStabilityWorker` | Helligkeitsstabilität über Frames (Belichtungs-/Schnittwechsel) |
| `FrameRateEstimatorWorker` | Effektive Bildrate schätzen (Anomalien der Framerate) |

Bei Umsetzung gilt Abschnitt 18 vollständig. Ergebnisse sind nach Abschnitt 13 als Indikator/Score darzustellen, nicht als Aussage „Bild/Video ist gefälscht".

---

## 22. Tool Calling – Ollama / Qwen3 Coder

- Wenn du ein Tool benötigst, rufe es unmittelbar auf, bevor du erklärenden Text oder einen Arbeitsplan ausgibst.
- Gib vor einem Tool-Aufruf keine Statusmeldung, Zusammenfassung oder Ankündigung aus.
- Gib Tool-Aufrufe niemals als JSON, XML oder sonstigen Text aus. Verwende ausschließlich echte, vom Agenten-Framework unterstützte Tool-Aufrufe.
- Warte nach einem Tool-Aufruf auf dessen Ergebnis und setze die Aufgabe danach selbstständig fort.
- Arbeite die angeforderte Aufgabe vollständig ab. Beende den Lauf nicht lediglich mit einer Liste noch ausstehender Schritte.
- Wenn weitere Dateioperationen erforderlich sind, führe sie direkt aus, statt nur anzukündigen, dass du die Dateien untersuchen wirst.
- Berichte erst dann über den Arbeitsfortschritt, wenn ein sinnvoller Arbeitsschritt abgeschlossen ist.


