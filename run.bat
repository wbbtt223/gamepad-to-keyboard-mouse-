@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Gamepad Mapper

set "VENV=%~dp0.venv"
set "PYEXE="

rem --- 1) prefer the local .venv, but only if it actually runs ---
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -c "import sys" >nul 2>nul && set "PYEXE=%VENV%\Scripts\python.exe"
)

rem --- 2) fall back to system python ---
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    where py >nul 2>nul && set "PYEXE=py"
)
if not defined PYEXE (
    echo [ERROR] Python not found.
    echo         Install Python 3.9+ from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

rem --- 3) already has pygame -> start right away ---
"%PYEXE%" -c "import pygame" >nul 2>nul
if not errorlevel 1 goto start

rem --- 4) need pygame: make sure a working local .venv exists first ---
if not exist "%VENV%\Scripts\python.exe" (
    echo [1/3] Creating local virtual env .venv ...
    "%PYEXE%" -m venv "%VENV%" >nul 2>nul
)
if exist "%VENV%\Scripts\python.exe" set "PYEXE=%VENV%\Scripts\python.exe"

echo [2/3] Installing pygame, this only happens once ...
"%PYEXE%" -m pip install --quiet --upgrade pip
"%PYEXE%" -m pip install --quiet pygame

"%PYEXE%" -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pygame install failed.
    echo         Please run manually:  pip install pygame
    pause
    exit /b 1
)

:start
echo [3/3] Starting Gamepad Mapper ...
echo.
"%PYEXE%" "%~dp0gamepad_mapper.py" %*
echo.
echo Program exited.
pause
