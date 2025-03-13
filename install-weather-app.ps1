# PowerShell-Script für die Installation und Ausführung der Wetter-Daten-Analyse-App mit Docker
# Erstellt für das Hochschulprojekt von Philipp Ott und Silas Kiehne

# Überprüfen, ob Docker installiert ist
$dockerInstalled = $null
try {
    $dockerInstalled = Get-Command docker -ErrorAction Stop
    Write-Host "Docker ist auf diesem System installiert." -ForegroundColor Green
} 
catch {
    Write-Host "Docker scheint nicht installiert zu sein. Bitte installieren Sie Docker Desktop oder Docker CLI, bevor Sie fortfahren." -ForegroundColor Red
    Write-Host "Download-Link: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# Docker-Image herunterladen
Write-Host "Lade das Docker-Image herunter..." -ForegroundColor Cyan
docker pull ghcr.io/silkiqw/django-wetter-app:latest

# Überprüfen, ob das Image erfolgreich heruntergeladen wurde
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Herunterladen des Docker-Images. Bitte überprüfen Sie Ihre Internetverbindung und Docker-Einstellungen." -ForegroundColor Red
    exit 1
}
Write-Host "Docker-Image wurde erfolgreich heruntergeladen." -ForegroundColor Green

# Überprüfen, ob Port 8000 bereits verwendet wird
$portInUse = $null
try {
    $portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
} catch {}

if ($portInUse) {
    Write-Host "WARNUNG: Port 8000 wird bereits verwendet. Möglicherweise müssen Sie einen anderen Port wählen." -ForegroundColor Yellow
    
    $response = Read-Host "Möchten Sie einen anderen Port verwenden? (j/n)"
    if ($response.ToLower() -eq "j") {
        $newPort = Read-Host "Bitte geben Sie einen alternativen Port ein (z.B. 8080)"
        $portMapping = "$newPort`:8000"
    } else {
        Write-Host "Versuche den Container trotzdem zu starten. Dies könnte fehlschlagen, wenn der Port belegt ist." -ForegroundColor Yellow
        $portMapping = "8000:8000"
    }
} else {
    $portMapping = "8000:8000"
}

# Überprüfen, ob bereits ein Container mit dem Namen 'wetter-app' existiert
$containerExists = docker ps -a --filter "name=wetter-app" --format "{{.Names}}"
if ($containerExists -eq "wetter-app") {
    Write-Host "Ein Container mit dem Namen 'wetter-app' existiert bereits." -ForegroundColor Yellow
    $removeContainer = Read-Host "Möchten Sie den vorhandenen Container entfernen? (j/n)"
    
    if ($removeContainer.ToLower() -eq "j") {
        Write-Host "Entferne vorhandenen Container..." -ForegroundColor Cyan
        docker rm -f wetter-app
    } else {
        Write-Host "Der neue Container wird mit einem automatisch generierten Namen erstellt." -ForegroundColor Yellow
        $containerName = ""
    }
} else {
    $containerName = "--name wetter-app"
}

# Container starten
Write-Host "Starte den Docker-Container..." -ForegroundColor Cyan
if ($containerName) {
    $command = "docker run -d -p $portMapping $containerName ghcr.io/silkiqw/django-wetter-app:latest"
} else {
    $command = "docker run -d -p $portMapping ghcr.io/silkiqw/django-wetter-app:latest"
}

Write-Host "Ausgeführter Befehl: $command" -ForegroundColor DarkGray
Invoke-Expression $command

if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Starten des Docker-Containers. Überprüfen Sie die Docker-Logs für weitere Informationen." -ForegroundColor Red
    exit 1
}

# URL anzeigen
if ($portMapping -eq "8000:8000") {
    $appUrl = "http://localhost:8000/"
} else {
    $appUrl = "http://localhost:$($portMapping.Split(':')[0])/"
}

Write-Host "`nDie Wetter-Daten-Analyse-App wurde erfolgreich gestartet!" -ForegroundColor Green
Write-Host "Sie können die Anwendung im Browser unter folgender URL öffnen:" -ForegroundColor Green
Write-Host $appUrl -ForegroundColor Cyan

# Anleitung zur Verwendung der App anzeigen
Write-Host "`nAnleitung zur Verwendung der App:" -ForegroundColor Yellow
Write-Host "1. Geben Sie die geografischen Koordinaten (Breitengrad und Längengrad) eines Ortes ein"
Write-Host "2. Wählen Sie den gewünschten Zeitraum und den Suchradius"
Write-Host "3. Die Anwendung zeigt eine Liste von Wetterstationen in der Nähe"
Write-Host "4. Wählen Sie eine Station aus, um detaillierte Temperaturanalysen anzuzeigen"
Write-Host "5. Die Ergebnisse enthalten durchschnittliche Minimal- und Maximaltemperaturen, aufgeschlüsselt nach Jahr und Jahreszeit"

# Informationen zum Beenden des Containers
Write-Host "`nUm den Container zu beenden, führen Sie folgenden Befehl aus:" -ForegroundColor Yellow
if ($containerName) {
    Write-Host "docker stop wetter-app" -ForegroundColor DarkGray
} else {
    Write-Host "Führen Sie 'docker ps' aus, um die ID Ihres Containers zu finden, und dann 'docker stop <CONTAINER_ID>'" -ForegroundColor DarkGray
}