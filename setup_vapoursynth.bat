@echo off
REM VapourSynth Setup Script für Windows Batch
REM Ausführen als Administrator: setup_vapoursynth.bat

echo ===========================================
echo VapourSynth Installation für Video-Forensik-Analyzer
echo ===========================================
echo.

REM Prüfen auf Administrator-Rechte
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrator-Rechte: VORHANDEN
) else (
    echo WARNUNG: Keine Administrator-Rechte!
    echo Einige Installationen benötigen Admin-Rechte.
    echo Bitte als Administrator ausfuehren.
    echo.
)

REM Chocolatey prüfen
where choco >nul 2>&1
if %errorLevel% == 0 (
    echo Chocolatey: VORHANDEN
    choco --version
) else (
    echo Chocolatey nicht gefunden. Installiere Chocolatey...
    @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"
    refreshenv
)

echo.
echo ===========================================
echo 1. VapourSynth Core installieren
echo ===========================================
where vspipe >nul 2>&1
if %errorLevel% == 0 (
    echo VapourSynth bereits installiert
    vspipe --version
) else (
    echo Installiere VapourSynth Core...
    choco install vapoursynth -y --params "/AddToPath"
    refreshenv
)

echo.
echo ===========================================
echo 2. FFmpeg installieren
echo ===========================================
where ffmpeg >nul 2>&1
if %errorLevel% == 0 (
    echo FFmpeg bereits installiert
    ffmpeg -version | head -1
) else (
    echo Installiere FFmpeg...
    choco install ffmpeg -y
    refreshenv
)

echo.
echo ===========================================
echo 3. FFMS2 Plugin installieren
echo ===========================================
echo Installiere FFMS2 (für Video-Source in VapourSynth)...
choco install ffms2 -y
refreshenv

echo.
echo ===========================================
echo 4. L-SMASH-Works installieren (Optional)
echo ===========================================
choco install l-smash-works -y
refreshenv

echo.
echo ===========================================
echo 5. Python vapoursynth Paket installieren
echo ===========================================
python -m pip install --upgrade pip
python -m pip install vapoursynth

echo.
echo ===========================================
echo VERIFIKATION
echo ===========================================
echo.

echo VapourSynth Version:
vspipe --version

echo.
echo Python Import Test:
python -c "import vapoursynth as vs; core = vs.core; print(f'VapourSynth Core Version: {core.version()}'); print('Python Wrapper OK')"

echo.
echo Verfuegbare VapourSynth Plugins:
python -c "import vapoursynth as vs; core = vs.core; plugins = list(core.plugins()); [print(f'  - {p}') for p in plugins] if plugins else print('  Keine Plugins gefunden')"

echo.
echo FFMS2 Test:
python -c "
import vapoursynth as vs
import os
core = vs.core
test_files = ['789.mp4', '23-45_5min.mp4', 'ffv1_test.mkv']
test_file = None
for f in test_files:
    if os.path.exists(f):
        test_file = f
        break
if test_file:
    clip = core.ffms2.Source(source=test_file)
    print(f'FFMS2 OK - Testdatei: {test_file}')
    print(f'  Aufloesung: {clip.width}x{clip.height}')
    print(f'  FPS: {float(clip.fps.num)/float(clip.fps.den):.2f}')
    print(f'  Frames: {clip.num_frames}')
    print(f'  Format: {clip.format}')
else:
    print('Keine Testdatei gefunden')
"

echo.
echo ===========================================
echo INSTALLATION ABGESCHLOSSEN
echo ===========================================
echo.
echo Naechste Schritte:
echo 1. Terminal neu starten (für PATH Aktualisierung)
echo 2. Testen: python -c "import vapoursynth as vs; print(vs.core.version())"
echo 3. Integration in Worker (siehe documentation/vapoursynth_implementation_details.md)
echo.
pause