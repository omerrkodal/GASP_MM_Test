@echo off
setlocal
set "MOVER_REBUILD_PY=C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
if not exist "%MOVER_REBUILD_PY%" (
    echo Unreal's bundled Python was not found: %MOVER_REBUILD_PY%
    echo Run RebuildGlobalMover.py using your Python 3 installation instead.
    pause
    exit /b 1
)
"%MOVER_REBUILD_PY%" "%~dp0RebuildGlobalMover.py" --wait-for-close 600 %*
set "MOVER_REBUILD_EXIT=%ERRORLEVEL%"
echo.
echo Build exit code: %MOVER_REBUILD_EXIT%
pause
exit /b %MOVER_REBUILD_EXIT%
