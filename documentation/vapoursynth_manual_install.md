# Manuelle VapourSynth Installation (ohne Admin-Rechte)

## Problem
Die automatische Installation über Chocolatey schlägt fehl, da Administrator-Rechte für die systemweite Installation erforderlich sind.

## Lösung: Manuelle Installation

### 1. VapourSynth Portable Installation

#### Option A: Portable VapourSynth von GitHub Releases
1. Gehen Sie zu: https://github.com/vapoursynth/vapoursynth/releases
2. Laden Sie die portable Version herunter (z.B. `VapourSynth-R65-Win64-Portable.7z`)
3. Entpacken Sie in einen Ordner Ihrer Wahl, z.B. `D:\Tools\VapourSynth\`
4. Fügen Sie den Ordner zur PATH-Variable hinzu (Benutzer-Ebene reicht):
   - Win+R → `sysdm.cpl` → Erweitert → Umgebungsvariablen
   - Benutzervariablen → Path → Bearbeiten → Neu: `D:\Tools\VapourSynth\`

#### Option B: Über Scoop (Benutzer-Installation, kein Admin nötig)
```powershell
# Scoop installieren (falls nicht vorhanden)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex

# VapourSynth installieren
scoop install vapoursynth

# FFmpeg installieren
scoop install ffmpeg

# FFMS2 über Scoop (falls verfügbar) oder manuell
scoop install ffms2
```

### 2. Python Paket installieren
```powershell
pip install vapoursynth
```

### 3. FFMS2 Plugin manuell installieren

Wenn FFMS2 nicht über Paketmanager verfügbar:

1. Laden Sie FFMS2 von: https://github.com/FFMS/ffms2/releases
2. Extrahieren Sie die `ffms2.dll` (64-bit Version)
3. Kopieren Sie in den VapourSynth Plugin-Ordner:
   - Portable: `D:\Tools\VapourSynth\plugins64\ffms2.dll`
   - Scoop: `~\scoop\apps\vapoursynth\current\plugins64\ffms2.dll`

### 4. Environment Variable für Plugin-Pfad setzen

Fügen Sie zu Ihrer PowerShell-Profil oder System-Umgebungsvariablen hinzu:
```powershell
# Für portable Installation
$env:VAPOURSYNTH_PLUGINS = "D:\Tools\VapourSynth\plugins64"

# Oder dauerhaft in PowerShell Profil:
# notepad $PROFILE
# Fügen Sie hinzu: $env:VAPOURSYNTH_PLUGINS = "D:\Tools\VapourSynth\plugins64"
```

### 5. Test der Installation

```powershell
# VapourSynth Version prüfen
vspipe --version

# Python Import testen
python -c "import vapoursynth as vs; core = vs.core; print('VapourSynth Version:', core.version())"

# Plugins auflisten
python -c "import vapoursynth as vs; core = vs.core; [print('  -', p) for p in core.plugins()]"

# FFMS2 Test mit Projekt-Datei
python -c "
import vapoursynth as vs
import os
core = vs.core
test_files = ['789.mp4', '23-45_5min.mp4', 'ffv1_test.mkv']
test_file = next((f for f in test_files if os.path.exists(f)), None)
if test_file:
    clip = core.ffms2.Source(source=test_file)
    print('FFMS2 OK!')
    print(f'Datei: {test_file}')
    print(f'Auflösung: {clip.width}x{clip.height}')
    print(f'FPS: {float(clip.fps.num)/float(clip.fps.den):.2f}')
    print(f'Frames: {clip.num_frames}')
else:
    print('Keine Testdatei gefunden')
"
```

## Alternative: Systemweite Installation mit Admin-Rechten

Wenn Sie Admin-Rechte haben:

### PowerShell als Administrator öffnen:
1. Win+X → "Windows PowerShell (Administrator)" oder "Terminal (Administrator)"

### Dann Installationsskript ausführen:
```powershell
# ExecutionPolicy temporär setzen
Set-ExecutionPolicy Bypass -Scope Process -Force

# Skript ausführen
.\setup_vapoursynth.ps1
```

### Oder Chocolatey manuell als Admin installieren:
```powershell
# Als Admin in PowerShell:
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Dann Pakete installieren:
choco install vapoursynth ffmpeg ffms2 l-smash-works -y
refreshenv
pip install vapoursynth
```

## Projekt-Integration

Nach erfolgreicher Installation fügen Sie in `main.py` hinzu:

```python
import os
# VapourSynth Plugin-Pfad explizit setzen (falls nicht in PATH)
# Für portable Installation:
os.environ['VAPOURSYNTH_PLUGINS'] = r'D:\Tools\VapourSynth\plugins64'

# Für Scoop Installation:
# os.environ['VAPOURSYNTH_PLUGINS'] = os.path.expanduser(r'~\scoop\apps\vapoursynth\current\plugins64')
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'vapoursynth'"
→ `pip install vapoursynth` ausführen

### "vs.core.ffms2 not found" oder "AttributeError: 'Core' object has no attribute 'ffms2'"
→ FFMS2 Plugin (`ffms2.dll`) fehlt im Plugin-Ordner
→ Prüfen Sie: `python -c "import vapoursynth as vs; print(vs.core.plugins())"`

### "Failed to load libfftw3f-3.dll"
→ FFTW3 Bibliotheken fehlen
→ Meist Teil von FFmpeg Installation
→ Stellen Sie sicher, dass FFmpeg im PATH ist

### Video wird nicht geladen ("FFMS2 Error")
1. Prüfen Sie, ob FFmpeg DLLs verfügbar sind (`ffmpeg.dll`, `avcodec-*.dll`, etc.)
2. Testen Sie mit einer bekannten funktionierenden Videodatei
3. Prüfen Sie Codec-Unterstützung

## Nächste Schritte nach Installation

1. **Integration in Worker**: Siehe `documentation/vapoursynth_implementation_details.md`
2. **FFprobeWorker anpassen**: VapourSynth für Metadaten-Extraktion nutzen
3. **ThumbnailWorker optimieren**: VapourSynth für Frame-Extraktion nutzen
4. **Video-Analyzer erweitern**: Frame-basierte Analysen für Video-Dateien

## Test-Dateien im Projekt

Das Projekt enthält bereits Test-Videos im Root-Ordner:
- `789.mp4`
- `23-45_5min.mp4` 
- `ffv1_test.mkv`

Diese können direkt für Tests verwendet werden.