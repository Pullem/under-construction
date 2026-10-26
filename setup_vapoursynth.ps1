# VapourSynth Setup Script für Windows PowerShell
# Ausführen als Administrator: .\setup_vapoursynth.ps1

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "VapourSynth Installation für Video-Forensik-Analyzer" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Prüfen auf Administrator-Rechte
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "WARNUNG: Dieses Skript sollte als Administrator ausgeführt werden!" -ForegroundColor Red
    Write-Host "Einige Installationen (VapourSynth Core, Chocolatey Pakete) benötigen Admin-Rechte." -ForegroundColor Yellow
    Write-Host ""
}

# Funktion: Prüfen ob Kommando existiert
function Test-CommandExists($command) {
    return (Get-Command $command -ErrorAction SilentlyContinue) -ne $null
}

# Funktion: Chocolatey installieren falls nicht vorhanden
function Install-ChocolateyIfNeeded {
    if (-not (Test-CommandExists choco)) {
        Write-Host "Chocolatey nicht gefunden. Installiere Chocolatey..." -ForegroundColor Yellow
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        refreshenv
        Write-Host "Chocolatey installiert!" -ForegroundColor Green
    } else {
        Write-Host "Chocolatey bereits vorhanden: $(choco --version)" -ForegroundColor Green
    }
}

# 1. Chocolatey sicherstellen
Install-ChocolateyIfNeeded

# 2. VapourSynth Core installieren
Write-Host ""
Write-Host "--- VapourSynth Core ---" -ForegroundColor Cyan
if (Test-CommandExists vspipe) {
    Write-Host "VapourSynth bereits installiert: $(vspipe --version)" -ForegroundColor Green
} else {
    Write-Host "Installiere VapourSynth Core..." -ForegroundColor Yellow
    choco install vapoursynth -y --params "'/AddToPath'"
    refreshenv
    if (Test-CommandExists vspipe) {
        Write-Host "VapourSynth erfolgreich installiert: $(vspipe --version)" -ForegroundColor Green
    } else {
        Write-Host "FEHLER: VapourSynth Installation fehlgeschlagen!" -ForegroundColor Red
    }
}

# 3. FFmpeg installieren
Write-Host ""
Write-Host "--- FFmpeg ---" -ForegroundColor Cyan
if (Test-CommandExists ffmpeg) {
    Write-Host "FFmpeg bereits installiert: $(ffmpeg -version | Select-Object -First 1)" -ForegroundColor Green
} else {
    Write-Host "Installiere FFmpeg..." -ForegroundColor Yellow
    choco install ffmpeg -y
    refreshenv
    if (Test-CommandExists ffmpeg) {
        Write-Host "FFmpeg erfolgreich installiert" -ForegroundColor Green
    } else {
        Write-Host "FEHLER: FFmpeg Installation fehlgeschlagen!" -ForegroundColor Red
    }
}

# 4. FFMS2 installieren (wichtig für Video-Loading in VapourSynth)
Write-Host ""
Write-Host "--- FFMS2 Plugin ---" -ForegroundColor Cyan
Write-Host "Installiere FFMS2 (für Video-Source in VapourSynth)..." -ForegroundColor Yellow
choco install ffms2 -y
refreshenv
Write-Host "FFMS2 Installation versucht" -ForegroundColor Green

# 5. L-SMASH-Works als Alternative (optional)
Write-Host ""
Write-Host "--- L-SMASH-Works (Optional) ---" -ForegroundColor Cyan
Write-Host "Installiere L-SMASH-Works als Alternative zu FFMS2..." -ForegroundColor Yellow
choco install l-smash-works -y
refreshenv
Write-Host "L-SMASH-Works Installation versucht" -ForegroundColor Green

# 6. Python Paket installieren
Write-Host ""
Write-Host "--- Python vapoursynth Paket ---" -ForegroundColor Cyan
Write-Host "Installiere Python Wrapper..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install vapoursynth
Write-Host "Python vapoursynth Paket installiert" -ForegroundColor Green

# 7. Verifikation
Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "VERIFIKATION" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# VapourSynth Version
Write-Host ""
Write-Host "VapourSynth Version:" -ForegroundColor Yellow
vspipe --version

# Python Import Test
Write-Host ""
Write-Host "Python Import Test:" -ForegroundColor Yellow
python -c "import vapoursynth as vs; core = vs.core; print('VapourSynth Core Version:', core.version()); print('Python Wrapper OK')"

# Plugin Test
Write-Host ""
Write-Host "Verfügbare VapourSynth Plugins:" -ForegroundColor Yellow
python -c "import vapoursynth as vs; core = vs.core; plugins = list(core.plugins()); [print('  -', p) for p in plugins] if plugins else print('  Keine Plugins gefunden (Plugin-Pfad prüfen!)')"

# FFMS2 Test
Write-Host ""
Write-Host "FFMS2 Funktions-Test:" -ForegroundColor Yellow
python -c "import vapoursynth as vs; import os; core = vs.core; test_files = ['789.mp4', '23-45_5min.mp4', 'ffv1_test.mkv']; test_file = next((f for f in test_files if os.path.exists(f)), None); print('FFMS2 OK - Testdatei:', test_file, '| Auflösung:', clip.width, 'x', clip.height, '| FPS:', float(clip.fps.num)/float(clip.fps.den), '| Frames:', clip.num_frames, '| Format:', clip.format) if test_file and (clip := core.ffms2.Source(source=test_file)) else print('Keine Testdatei gefunden oder FFMS2 nicht verfügbar')"

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "INSTALLATION ABGESCHLOSSEN" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Yellow
Write-Host "1. Starten Sie Ihre PowerShell/Terminal neu (für PATH Aktualisierung)"
Write-Host "2. Testen Sie: python -c 'import vapoursynth as vs; print(vs.core.version())'"
Write-Host "3. Integrieren Sie VapourSynth in die Worker (siehe documentation/vapoursynth_implementation_details.md)"
Write-Host ""
Read-Host "Drücken Sie Enter zum Beenden"