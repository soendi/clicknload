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
@{ version = $newVersion } | ConvertTo-Json | Set-Content "version.json" -Encoding UTF8

# 2. gui.py
(Get-Content "gui.py") -replace 'CURRENT_VERSION = "[^"]*"', "CURRENT_VERSION = `"$newVersion`"" | Set-Content "gui.py" -Encoding UTF8

# 3. main.py
(Get-Content "main.py") -replace 'CURRENT_VERSION = "[^"]*"', "CURRENT_VERSION = `"$newVersion`"" | Set-Content "main.py" -Encoding UTF8

# 4. setup.iss
(Get-Content "Installer\setup.iss") -replace '#define MyAppVersion "[^"]*"', "#define MyAppVersion `"$newVersion`"" | Set-Content "Installer\setup.iss" -Encoding UTF8

# 5. version_info.txt
$content = Get-Content "version_info.txt" -Raw
$versionDot = "$major.$minor.$patch.$build"
$content = $content -replace 'filevers=\([\d, ]+\)', "filevers=($major, $minor, $patch, $build),"
$content = $content -replace 'prodvers=\([\d, ]+\)', "prodvers=($major, $minor, $patch, $build),"
$content = $content -replace "StringStruct\(u'FileVersion', u'[^']*'\)", "StringStruct(u'FileVersion', u'$versionDot')"
$content = $content -replace "StringStruct\(u'ProductVersion', u'[^']*'\)", "StringStruct(u'ProductVersion', u'$versionDot')"
Set-Content "version_info.txt" $content -Encoding UTF8

Write-Host "Dateien aktualisiert."

# Git
git add version.json gui.py main.py Installer\setup.iss version_info.txt
git commit -m "v$newVersion"
git tag "v$newVersion"
git push origin master --tags

Write-Host "Push abgeschlossen. Tag: v$newVersion"
Write-Host "GitHub Actions baut jetzt den Installer..."
