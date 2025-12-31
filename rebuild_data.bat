@echo off
setlocal

set TOOLS_DIR=tools
set PYTHON=python
set SRC_DIR=%TOOLS_DIR%\KengoPS2Tools\src
set EXE_PATH=%TOOLS_DIR%\kengo_tools.exe
set PYTHON_SCRIPT=%TOOLS_DIR%\kengo_menu_text_editor.py
set INPUT_DIR=files\data
set OUTPUT_DIR=files\isofolder\data
set JSON_DIR=files\json
set OUTPUT_FILE=%OUTPUT_DIR%\FID.BIN

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if not exist "%EXE_PATH%" (
    echo kengo_tools.exe not found. Attempting to compile...
    g++ "%SRC_DIR%\main.cpp" -o "%EXE_PATH%"
    if errorlevel 1 (
        echo Failed to compile kengo_tools.exe. Exiting.
        exit /b 1
    )
    echo Successfully compiled kengo_tools.exe.
)

echo Importing JSON changes...
"%PYTHON%" "%PYTHON_SCRIPT%" import-folder -i "%JSON_DIR%" "%INPUT_DIR%"
if errorlevel 1 (
    echo Failed to import JSON changes. Exiting.
    exit /b 1
)

echo Building new FID.BIN file...
"%EXE_PATH%" -rfid "%OUTPUT_FILE%" "%INPUT_DIR%" kengo3
if errorlevel 1 (
    echo Failed to build FID.BIN. Exiting.
    exit /b 1
)

echo Successfully built FID.BIN at %OUTPUT_FILE%.
endlocal
