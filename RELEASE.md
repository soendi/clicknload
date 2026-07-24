# ClickNLoad Bridge

## Release-Workflow

1. Code-Änderungen committen + pushen (OHNE version.json zu ändern)
2. Tag pushen → triggert GitHub Actions Build
3. Mit `gh run list` prüfen ob Build fertig ist
4. ERST DANACH: version.json + version_info.txt + setup.iss bumpen, committen, pushen

**WICHTIG:** version.json NIE im selben Commit wie Code-Änderungen pushen!
Der Update-Checker liest version.json von master. Wenn die neue Version
da ist, bevor der Build fertig ist, sieht der User ein Update das er
nicht laden kann.
