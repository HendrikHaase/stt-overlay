@echo off
REM Build SttOverlay as a single folder (--onedir) for anti-cheat compatibility.
REM No %TEMP% extraction at runtime — all DLLs sit next to the EXE.
REM
REM Prerequisites:
REM   pip install -r requirements.txt
REM
REM Output: dist\SttOverlay\SttOverlay.exe

pyinstaller ^
    --onedir ^
    --windowed ^
    --name SttOverlay ^
    --collect-all onnx_asr ^
    --collect-all sounddevice ^
    --hidden-import soundfile ^
    --hidden-import numpy ^
    main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo Build failed. See output above.
    exit /b %ERRORLEVEL%
)

echo.
echo Build successful!
echo Run: dist\SttOverlay\SttOverlay.exe
