# Kengo 3 Translation Project

This project focuses on translating the menu text of the PlayStation 2 game "Kengo 3" into English.

## Project Structure
- **tools/**: Contains scripts and utilities
- **files/json/**: JSON files exported from tools for text editing.

## Setup and Usage
1. Clone the repository to your local machine.
2. Unpack your Kengo 3 disc to the `files/isofolder/` directory.
3. Use `unpack_data.bat` to extract game data files.
4. Text changes are made in the JSON files located in `files/json/`.
5. Use `rebuild_data.sh` to repack the modified files back into the game format.
6. Rebuild the ISO.

## Requirements
- Python 3.x
- G++

## Used tools
- [KengoPS2Tools](https://github.com/igorciz777/KengoPS2Tools): Used for extracting and repacking game files.
- Python
- ImHex