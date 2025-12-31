#!/bin/bash
set -e

TOOLS_DIR="tools"
PYTHON="python3"
SRC_DIR="$TOOLS_DIR/KengoPS2Tools/src"
EXE_PATH="$TOOLS_DIR/kengo_tools"
PYTHON_SCRIPT="$TOOLS_DIR/kengo_menu_text_editor.py"
INPUT_DIR="files/data"
OUTPUT_DIR="files/isofolder/data"
JSON_DIR="files/json"
OUTPUT_FILE="$OUTPUT_DIR/FID.BIN"

mkdir -p "$OUTPUT_DIR"

if [ ! -f "$EXE_PATH" ]; then
    echo "kengo_tools not found. Attempting to compile..."
    g++ "$SRC_DIR/main.cpp" -o "$EXE_PATH"
    if [ $? -ne 0 ]; then
        echo "Failed to compile kengo_tools. Exiting."
        exit 1
    fi
    echo "Successfully compiled kengo_tools."
fi

echo "Importing JSON changes..."
"$PYTHON" "$PYTHON_SCRIPT" import-folder -i "$JSON_DIR" "$INPUT_DIR"
if [ $? -ne 0 ]; then
    echo "Failed to import JSON changes. Exiting."
    exit 1
fi

echo "Building new FID.BIN file..."
"$EXE_PATH" -rfid "$OUTPUT_FILE" "$INPUT_DIR" kengo3
if [ $? -ne 0 ]; then
    echo "Failed to build FID.BIN. Exiting."
    exit 1
fi

echo "Successfully built FID.BIN at $OUTPUT_FILE."
