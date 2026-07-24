# bump.ps1 - Version erhöhen, committen, taggen und pushen
# Usage: .\bump.ps1 patch
#        .\bump.ps1 minor
#        .\bump.ps1 major
#        .\bump.ps1 1.0.17.0

param(
    [Parameter(Mandatory=$true)]
    [string]$BumpType
)

$ErrorActionPreference = "Stop"

# UTF-8 ohne BOM schreiben (PowerShell 5.1 schreibt sonst mit BOM)
function Write-Utf8NoBom($Path, $Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

# ANSI (Windows-1252) schreiben — fuer Inno Setup .iss Dateien
function Write-Ansi($Path, $Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.Encoding]::GetEncoding(1252))
}

# Aktuelle Version aus version.json lesen
$current = (Get-Content "version.json" | ConvertFrom-Json).version
Write-Host "Aktuelle Version: $current"

# Version aufteilen: Major.Minor.Patch.Build
$parts = $current -split '\.'
$major = [int]$parts[0]
$minor = [int]$parts[1]
$patch = [int]$parts[2]
$build = [int]$parts[3]

switch ($BumpType) {
    "major" { $major++; $minor = 0; $patch = 0; $build = 0 }
    "minor" { $minor++; $patch = 0; $build = 0 }
    "patch" { $patch++; $build = 0 }
    "build" { $build++ }
    default {
        # Prüfe ob es eine vollständige Versionsnummer ist
        if ($BumpType -match '^\d+\.\d+\.\d+\.\d+$') {
            $parts = $BumpType -split '\.'
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            $patch = [int]$parts[2]
            $build = [int]$parts[3]
        } else {
            Write-Error "Ungültiger Bump-Typ: $BumpType (nutze major, minor, patch, build oder x.y.z.w)"
            exit 1
        }
    }
}

$newVersion = "$major.$minor.$patch.$build"
Write-Host "Neue Version: $newVersion"

# dateien updaten
# 1. version.json
Write-Utf8NoBom "version.json" "{`"version`": `"$newVersion`"}`n"

# 2. gui.py
$content = Get-Content "gui.py" -Raw
$content = $content -replace 'CURRENT_VERSION = "[^"]*"', "CURRENT_VERSION = `"$newVersion`""
Write-Utf8NoBom "gui.py" $content

# 3. main.py
$content = Get-Content "main.py" -Raw
$content = $content -replace 'CURRENT_VERSION = "[^"]*"', "CURRENT_VERSION = `"$newVersion`""
Write-Utf8NoBom "main.py" $content

# 4. setup.iss (ANSI encoding fuer Inno Setup)
$content = Get-Content "Installer\setup.iss" -Raw
$content = $content -replace '#define MyAppVersion "[^"]*"', "#define MyAppVersion `"$newVersion`""
Write-Ansi "Installer\setup.iss" $content

# 5. version_info.txt
$content = Get-Content "version_info.txt" -Raw
$versionDot = "$major.$minor.$patch.$build"
$content = $content -replace 'filevers=\([\d, ]+\)', "filevers=($major, $minor, $patch, $build)"
$content = $content -replace 'prodvers=\([\d, ]+\)', "prodvers=($major, $minor, $patch, $build)"
$content = $content -replace "StringStruct\(u'FileVersion', u'[^']*'\)", "StringStruct(u'FileVersion', u'$versionDot')"
$content = $content -replace "StringStruct\(u'ProductVersion', u'[^']*'\)", "StringStruct(u'ProductVersion', u'$versionDot')"
Write-Utf8NoBom "version_info.txt" $content

Write-Host "Dateien aktualisiert."

# Git — nur committen und pushen, KEIN Tag
# Der Tag wird erst vom GitHub Actions Workflow erstellt,
# nachdem der Build erfolgreich abgeschlossen ist.
# So bietet die App das Update erst an, wenn der Installer fertig ist.
git add version.json gui.py main.py Installer\setup.iss version_info.txt
git commit -m "v$newVersion"
git push origin master

Write-Host "Push abgeschlossen. Version: v$newVersion"
Write-Host "GitHub Actions baut den Installer und erstellt den Release..."
