# VapourSynth Installationsanleitung für Windows

## Übersicht

Diese Anleitung beschreibt die Installation von VapourSynth und den notwendigen Komponenten für das Video-Forensik-Analyzer Projekt unter Windows.

## 1. VapourSynth Core Installation

### Option A: Offizieller Installer (Empfohlen)
1. Besuchen Sie: https://www.vapoursynth.com/doc/installation.html
2. Laden Sie den aktuellen Windows Installer herunter (z.B. `VapourSynth-R65.exe` oder neuer)
3. Führen Sie den Installer als Administrator aus
4. Wählen Sie "Add to PATH" während der Installation

### Option B: Über Chocolatey
```powershell
choco install vapoursynth
```

### Option C: Über Scoop
```powershell
scoop install vapoursynth
```

## 2. Python Paket Installation

Nach der Core-Installation muss das Python-Paket installiert werden:

```powershell
# In der Projekt-Virtual-Environment oder global
pip install vapoursynth
```

**Wichtig**: Das Python-Paket `vapoursynth` ist nur ein Wrapper. Die eigentliche VapourSynth-Installation muss separat vorhanden sein.

## 3. Erforderliche Plugins für Video-Analyse

Für die Video-Forensik werden folgende Plugins benötigt:

### FFMS2 (Essentiell für Video-Loading)
```powershell
# Über Chocolatey
choco install ffms2

# Oder manuell: https://github.com/FFMS/ffms2/releases
# DLL in VapourSynth plugins Ordner kopieren (typischerweise: C:\Program Files\VapourSynth\plugins64\)
```

### L-SMASH-Works (Alternative zu FFMS2)
```powershell
# Über Chocolatey
choco install l-smash-works

# Oder manuell von: https://github.com/HolyWu/L-SMASH-Works/releases
```

### Weitere nützliche Plugins
```powershell
# Für erweiterte Filter
choco install vapoursynth-plugin-*

# Oder einzeln:
# - vs-placebo (hochwertige Skalierung)
# - vs-znedi3 (Deinterlacing)
# - vs-fftw3 (FFT Operationen)
# - vs-dfttest (Rauschreduzierung)
```

## 4. FFmpeg Installation (für FFMS2)

FFMS2 benötigt FFmpeg. Stellen Sie sicher, dass FFmpeg im PATH ist:

```powershell
# Über Chocolatey
choco install ffmpeg

# Oder von https://ffmpeg.org/download.html
```

**Wichtig**: Das Projekt hat bereits `ffmpeg.exe` und `ffprobe.exe` im Root-Ordner. Diese können verwendet werden, 
aber FFMS2 benötigt die FFmpeg-Bibliotheken (DLLs), nicht nur die Executables.

## 5. Verifizierung der Installation

### VapourSynth Core testen:
```powershell
vspipe --version
```

### Python Paket testen:
```powershell
python -c "import vapoursynth as vs; core = vs.core; print('VapourSynth Version:', core.version())"
```

### Plugin-Verfügbarkeit testen:
```powershell
python -c "
import vapoursynth as vs
core = vs.core
print('Verfügbare Plugins:')
for plugin in core.plugins():
    print(f'  - {plugin}')
"
```

### FFMS2 testen:
```powershell
python -c "
import vapoursynth as vs
core = vs.core
try:
    clip = core.ffms2.Source(source='test.mp4')
    print('FFMS2 funktioniert! Video Info:', clip.width, 'x', clip.height, '@', clip.fps)
except Exception as e:
    print('FFMS2 Fehler:', e)
"
```

## 6. Projekt-spezifische Konfiguration

### Environment Variable für Plugin-Pfad (falls nötig)
```powershell
# Falls Plugins nicht automatisch gefunden werden
$env:VAPOURSYNTH_PLUGINS = "C:\Program Files\VapourSynth\plugins64"
```

### Python Path für VS-Scripts
Fügen Sie zum Projekt-Startup in `main.py` hinzu:
```python
import os
# Plugin-Pfad explizit setzen falls nötig
os.environ['VAPOURSYNTH_PLUGINS'] = r'C:\Program Files\VapourSynth\plugins64'
```

## 7. Häufige Probleme und Lösungen

### Problem: "ModuleNotFoundError: No module named 'vapoursynth'"
**Lösung**: Python-Paket installieren: `pip install vapoursynth`

### Problem: "vs.core.ffms2 not found"
**Lösung**: FFMS2 Plugin fehlt. Installieren Sie FFMS2 und stellen Sie sicher, dass die DLL im VapourSynth plugins Ordner liegt.

### Problem: "Failed to load libfftw3f-3.dll"
**Lösung**: FFTW3 Bibliotheken installieren (oft Teil von FFmpeg Installation)

### Problem: Video wird nicht geladen
**Lösung**: 
1. Prüfen Sie, ob FFmpeg DLLs verfügbar sind
2. Testen Sie mit einer bekannten funktionierenden Videodatei
3. Überprüfen Sie Codec-Unterstützung

## 8. Automatisiertes Setup Script

Erstellen Sie `setup_vapoursynth.ps1` für einfache Installation:

```powershell
# setup_vapoursynth.ps1
Write-Host "Installiere VapourSynth und Abhängigkeiten..." -ForegroundColor Green

# VapourSynth Core
if (!(Get-Command vspipe -ErrorAction SilentlyContinue)) {
    Write-Host "Installiere VapourSynth Core..." -ForegroundColor Yellow
    choco install vapoursynth -y
} else {
    Write-Host "VapourSynth Core bereits installiert" -ForegroundColor Green
}

# FFmpeg
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Installiere FFmpeg..." -ForegroundColor Yellow
    choco install ffmpeg -y
} else {
    Write-Host "FFmpeg bereits installiert" -ForegroundColor Green
}

# FFMS2
Write-Host "Installiere FFMS2..." -ForegroundColor Yellow
choco install ffms2 -y

# Python Paket
Write-Host "Installiere Python vapoursynth Paket..." -ForegroundColor Yellow
pip install vapoursynth

Write-Host "Installation abgeschlossen!" -ForegroundColor Green
Write-Host "Testen Sie mit: python -c \"import vapoursynth as vs; print(vs.core.version())\"" -ForegroundColor Cyan
```

## 9. Integration in CI/CD (Optional)

Für GitHub Actions oder ähnliche:
```yaml
- name: Install VapourSynth
  run: |
    choco install vapoursynth ffms2 ffmpeg -y
    pip install vapoursynth
```

## 10. Nächste Schritte

Nach erfolgreicher Installation:
1. Testen Sie die Integration mit den vorhandenen Test-Videos im Projekt-Root
2. Passen Sie die Worker-Komponenten an (wie in `vapoursynth_implementation_details.md` beschrieben)
3. Führen Sie die forensischen Analysen auf Video-Dateien aus

---

**Hinweis**: Diese Installation erfordert Administrator-Rechte für die systemweite Installation von VapourSynth Core und Plugins.