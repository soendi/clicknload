# ClickNLoad Bridge

## Release-Workflow

### 1. bump.ps1 (Version erhöhen)
```powershell
.\bump.ps1 patch    # 1.0.16.1 → 1.0.17.0
.\bump.ps1 minor    # 1.0.16.1 → 1.1.0.0
.\bump.ps1 major    # 1.0.16.1 → 2.0.0.0
.\bump.ps1 1.1.0.0  # Bestimmte Version
```

Das Skript bumpert automatisch:
- `version.json`
- `gui.py` (CURRENT_VERSION)
- `main.py` (CURRENT_VERSION)
- `Installer\setup.iss` (MyAppVersion)
- `version_info.txt` (filevers, prodvers, FileVersion, ProductVersion)

Danach: `git commit`, `git tag v...`, `git push --atomic origin HEAD:master v...`

### 2. GitHub Actions (automatisch)
Der Push des Tags `v*` triggert den Workflow:
1. Python + Abhängigkeiten installieren
2. PyInstaller baut `ClickNLoadBridge.exe`
3. Inno Setup baut `ClickNLoadBridge_Setup.exe`
4. `gh release create` erstellt ein GitHub Release mit dem Installer

### 3. Zur Laufzeit: Update-Checker
Die App ruft die GitHub Releases API auf:
```
https://api.github.com/repos/soendi/clicknload/releases?per_page=10
```

Sucht nach:
- Kein `prerelease`
- Kein `draft`
- Tag beginnt mit `v` → Version parsen → größer als aktuelle?

Findet sie einen neueren Release mit .exe-Asset → Update anbieten.

### Warum erscheint das Update erst NACH dem Build?
Die API (`/releases`) listet nur echte GitHub Releases, nicht jeden Tag.
Solange `gh release create` nicht gelaufen ist, existiert kein Release
→ App sieht kein Update.

Schritt | Tag existiert? | Release existiert? | Asset existiert? | App bietet Update?
---|---|---|---|---
Nach `git push` | ✅ | ❌ | ❌ | Nein
Während GH Action läuft | ✅ | ❌ | ❌ | Nein
Nach `gh release create` | ✅ | ✅ | ✅ | Ja
