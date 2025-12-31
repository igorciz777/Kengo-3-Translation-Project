@echo off
setlocal

set TOOLS_DIR=tools
set SRC_DIR=%TOOLS_DIR%\KengoPS2Tools\src
set EXE_PATH=%TOOLS_DIR%\kengo_tools.exe
set OUTPUT_DIR=files\data
set INPUT_DIR=files\isofolder\data
set INPUT_FILE=%INPUT_DIR%\FID.BIN

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

echo Unpacking FID.BIN file...
"%EXE_PATH%" -ufid "%INPUT_FILE%" "%OUTPUT_DIR%"
if errorlevel 1 (
    echo Failed to unpack FID.BIN. Exiting.
    exit /b 1
)

echo Successfully unpacked FID.BIN to %OUTPUT_DIR%.

endlocal
