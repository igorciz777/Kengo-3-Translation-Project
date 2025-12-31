#!/bin/bash
set -e

TOOLS_DIR="tools"
SRC_DIR="$TOOLS_DIR/KengoPS2Tools/src"
EXE_PATH="$TOOLS_DIR/kengo_tools"
OUTPUT_DIR="files/data"
INPUT_DIR="files/isofolder/data"
INPUT_FILE="$INPUT_DIR/FID.BIN"

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

echo "Unpacking FID.BIN file..."
"$EXE_PATH" -ufid "$INPUT_FILE" "$OUTPUT_DIR"
if [ $? -ne 0 ]; then
    echo "Failed to unpack FID.BIN. Exiting."
    exit 1
fi

echo "Successfully unpacked FID.BIN to $OUTPUT_DIR."
