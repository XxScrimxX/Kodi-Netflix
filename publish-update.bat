@echo off
rem Publish updates for the Unknown add-ons.
rem
rem Default: builds the repository and pushes it to GitHub Pages, so every user's
rem Kodi picks up the update automatically - no IPs, no home network required.
rem Add --lan to build for this PC only (LAN serving, for local testing):
rem   publish-update.bat --lan
rem
rem Before running: raise version="..." in the addon.xml of every add-on you changed
rem (for example skin.unknown\addon.xml 1.0.0 -> 1.0.1). Kodi ignores same-version rebuilds.
setlocal
cd /d "%~dp0"

py -3 tools\build_repo.py %*
if errorlevel 1 (
    echo.
    echo Publishing failed, see the error above.
    pause
    exit /b 1
)

if /i not "%1"=="--lan" (
    echo.
    echo Pushing repository to GitHub Pages...
    git add repo
    if errorlevel 1 goto :pushfailed
    git diff --cached --quiet
    if errorlevel 1 (
        git commit -q -m "Publish repository update"
        if errorlevel 1 goto :pushfailed
    ) else (
        echo Nothing new to commit (versions unchanged?).
    )
    git push -q origin gh-pages
    if errorlevel 1 goto :pushfailed
    echo Live. Users' Kodi will see the update on their next repo refresh.
)
echo.
pause
exit /b 0

:pushfailed
echo.
echo Push failed - check git remote/auth and that the gh-pages branch exists.
pause
exit /b 1