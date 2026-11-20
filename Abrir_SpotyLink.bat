@echo off
title SpotyLink Launcher
cd /d "%~dp0"

if exist "dist\SpotyLink\SpotyLink.exe" (
    start "" "dist\SpotyLink\SpotyLink.exe"
) else (
    start "" pythonw musica.py
)
exit

