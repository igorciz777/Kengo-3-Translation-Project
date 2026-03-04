#!/usr/bin/env python3

"""
CLI tool for Kengo 3 menu text files editing.
"""

import argparse
import json
import os
import struct
import sys
from pathlib import Path
from typing import Dict, Any, Optional

g_file04_text_types = {0, 1, 3, 5, 7, 11, 13, 16, 18, 19, 20, 21, 22, 23, 24, 25, 28, 30, 31, 32, 33, 34, 36, 37}


def decode_shiftjis_with_escape(data: bytes) -> str:
    result = []
    i = 0
    while i < len(data):
        if data[i] == 0x00:
            break
        if i + 1 < len(data):
            try:
                ch = data[i:i + 2].decode('shift_jis')
                result.append(ch)
                i += 2
                continue
            except (UnicodeDecodeError, LookupError):
                pass
        try:
            ch = data[i:i + 1].decode('shift_jis')
            result.append(ch)
        except (UnicodeDecodeError, LookupError):
            result.append(f'\\x{data[i]:02x}')
        i += 1
    return ''.join(result)


def encode_shiftjis_with_escape(text: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i:i + 2] == '\\x' and i + 3 < len(text):
            hex_str = text[i + 2:i + 4]
            if all(c in '0123456789abcdefABCDEF' for c in hex_str):
                out.append(int(hex_str, 16))
                i += 4
                continue
        for length in (2, 1):
            if i + length <= len(text):
                try:
                    out.extend(text[i:i + length].encode('shift_jis'))
                    i += length
                    break
                except (UnicodeEncodeError, LookupError):
                    if length == 1:
                        out.append(0x3F)
                        i += 1
        else:
            out.append(0x3F)
            i += 1
    out.extend(b'\x00\x00')
    return bytes(out)


class BinaryTextEditor:
    def __init__(self, filepath: str):
        self.filepath = str(filepath)
        self.filename = os.path.basename(filepath)
        try:
            self.index = int(self.filename.split('.')[0])
        except Exception:
            self.index = 0
        self.data = None

    def parse_binary(self, ignore_type: bool = False) -> Dict[str, Any]:
        with open(self.filepath, 'rb') as f:
            file_size, = struct.unpack('<I', f.read(4))
            block_count, = struct.unpack('<I', f.read(4))

            entries = []
            blocks = []

            for _ in range(block_count):
                start, size = struct.unpack('<II', f.read(8))
                entries.append({'start': start, 'size': size})

            for entry_idx, entry in enumerate(entries):
                f.seek(entry['start'])
                header = f.read(16)
                if len(header) < 16:
                    raise ValueError(f"Block {entry_idx} header truncated")
                block_type, size_field, count, padding = struct.unpack('<IIII', header)

                if (self.index == 4 and block_type in g_file04_text_types) or block_type == 1 or ignore_type:
                    block_data = {
                        'block_index': entry_idx,
                        'type': block_type,
                        'size': size_field,
                        'count': count,
                        'padding': padding,
                        'texts': []
                    }
                    text_size = size_field
                    for i in range(count):
                        text_start = f.tell()
                        text_bytes = f.read(text_size)
                        if len(text_bytes) < text_size:
                            text_bytes = text_bytes + b'\x00' * (text_size - len(text_bytes))
                        stripped = text_bytes.rstrip(b'\x00')
                        original_text = decode_shiftjis_with_escape(stripped)
                        block_data['texts'].append({
                            'index': i,
                            'start': text_start,
                            'original': original_text,
                            'modified': original_text
                        })

                    blocks.append(block_data)

            return {
                'file_info': {
                    'filename': self.filename,
                    'index': self.index,
                    'file_size': file_size,
                    'block_count': block_count
                },
                'blocks': blocks
            }

    def export_to_json(self, output_path: Optional[str] = None, ignore_type: bool = False) -> str:
        def _strip_trailing_nulls(s: str) -> str | None | Any:
            if s is None:
                return s
            s = s.rstrip('\x00')
            while s.endswith('\\x00'):
                s = s[:-4]
            return s

        out_path = Path(output_path) if output_path else Path(self.filepath).with_suffix('.json')

        try:
            data = self.parse_binary(ignore_type=ignore_type)
        except Exception:
            data = None

        if data is None and out_path.exists():
            try:
                with out_path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = None

        if data is None:
            data = {
                "file_info": {"filename": Path(self.filepath).name, "index": 0,
                              "file_size": Path(self.filepath).stat().st_size if Path(self.filepath).exists() else 0,
                              "block_count": 0},
                "blocks": []
            }

        for block in data.get('blocks', []):
            for text in block.get('texts', []):
                if 'original' in text and isinstance(text['original'], str):
                    text['original'] = _strip_trailing_nulls(text['original'])
                if 'modified' in text and isinstance(text['modified'], str):
                    text['modified'] = _strip_trailing_nulls(text['modified'])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(out_path)

    def import_from_json(self, json_path: str, output_bin_path: Optional[str] = None) -> str:
        """
        Import changes from JSON into an existing .bin file.
        This method modifies the .bin file in place, overlaying new text on top of the original text blocks.
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_bin_path is None:
            output_bin_path = self.filepath

        with open(output_bin_path, 'r+b') as bin_file:
            for block in data['blocks']:
                if self.index == 4:
                    if block['type'] not in g_file04_text_types:
                        continue
                elif block['type'] != 1:
                    continue

                for text_entry in block['texts']:
                    modified_text = text_entry.get('modified', text_entry.get('original', ''))
                    encoded_text = encode_shiftjis_with_escape(modified_text)

                    entry_start = text_entry['start']
                    text_size = block['size']

                    if len(encoded_text) > text_size:
                        raise ValueError(f"Modified text at index {text_entry['index']} is too large.")

                    bin_file.seek(entry_start)
                    bin_file.write(encoded_text)

        print(f"Modified binary file: {output_bin_path}")
        return output_bin_path

    def validate_json(self, json_path: str) -> bool:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'file_info' not in data or 'blocks' not in data:
            print("Error: Missing keys")
            return False

        for block in data['blocks']:
            if block['type'] == 1:
                if 'size' not in block:
                    print(f"Error: text block missing 'size'")
                    return False
                if len(block.get('texts', [])) != block.get('count', 0):
                    print(f"Error: block texts/count mismatch")
                    return False
                for text in block['texts']:
                    if 'original' not in text or 'modified' not in text:
                        print(f"Error: text entry missing fields")
                        return False
        print("JSON validation passed")
        return True

    def validate_menu_text_file(self) -> bool:
        """
        Validates if the file matches the menu text file structure.
        Returns True if valid, False otherwise.
        """
        try:
            with open(self.filepath, 'rb') as f:
                # Validate file size and block count
                file_size, = struct.unpack('<I', f.read(4))
                block_count, = struct.unpack('<I', f.read(4))

                if file_size != os.path.getsize(self.filepath):
                    # print(f"Validation failed: File size mismatch for {self.filepath}")
                    return False

                if block_count <= 0:
                    # print(f"Validation failed: Invalid block count for {self.filepath}")
                    return False

            return True
        except Exception as e:
            # print(f"Validation failed: {e} for {self.filepath}")
            return False


def export_command(args):
    editor = BinaryTextEditor(args.input_file)
    path = editor.export_to_json(args.output_file, ignore_type=args.ignore_type)
    if args.validate:
        ok = editor.validate_json(path)
        print(f"Validated: {ok}")
    else:
        print(f"Exported: {path}")


def import_command(args):
    src_bin = args.json_file.replace('.json', '.bin')
    editor = BinaryTextEditor(src_bin)
    if args.validate:
        ok = editor.validate_json(args.json_file)
        print(f"Validated: {ok}")
    out = editor.import_from_json(args.json_file, args.output_file)
    print(f"Imported -> {out}")

def export_from_folder(folder_path: str, output_folder: Optional[str] = None):
    folder = Path(folder_path)
    out_folder = Path(output_folder) if output_folder else folder / 'exported_json'
    out_folder.mkdir(parents=True, exist_ok=True)

    for bin_file in folder.glob('*.bin'):
        editor = BinaryTextEditor(str(bin_file))
        if editor.validate_menu_text_file():
            out_path = out_folder / (bin_file.stem + '.json')
            if editor.export_to_json(str(out_path)):
                print(f"Exported: {out_path}")

def import_to_folder(folder_path: str, input_folder: Optional[str] = None):
    folder = Path(folder_path)
    in_folder = Path(input_folder) if input_folder else folder / 'exported_json'

    for json_file in in_folder.glob('*.json'):
        src_bin = folder / (json_file.stem + '.bin')
        editor = BinaryTextEditor(str(src_bin))
        editor.import_from_json(str(json_file), str(src_bin))
        print(f"Imported: {src_bin}")


def convert_to_hex_command(args):
    """
    Converts a Shift-JIS string to its hexadecimal representation.
    """
    try:
        encoded = encode_shiftjis_with_escape(args.text)
        hex_output = ' '.join(f'{byte:02X}' for byte in encoded)
        print(f"Hexadecimal representation: {hex_output}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description='Kengo 3 Menu Shift-JIS Text Editor CLI')
    sub = parser.add_subparsers(dest='cmd')

    # Export single file
    p_export = sub.add_parser('export')
    p_export.add_argument('input_file')
    p_export.add_argument('-o', '--output-file', default=None)
    p_export.add_argument('--validate', action='store_true')
    p_export.add_argument('--ignore-type', action='store_true')
    p_export.set_defaults(func=export_command)

    # Import single file
    p_import = sub.add_parser('import')
    p_import.add_argument('json_file')
    p_import.add_argument('-o', '--output-file', default=None)
    p_import.add_argument('--validate', action='store_true')
    p_import.set_defaults(func=import_command)

    # Export entire folder
    p_export_folder = sub.add_parser('export-folder')
    p_export_folder.add_argument('folder_path', help='Path to the folder containing .bin files')
    p_export_folder.add_argument('-o', '--output-folder', default=None, help='Path to save exported JSON files')
    p_export_folder.set_defaults(func=lambda args: export_from_folder(args.folder_path, args.output_folder))

    # Import entire folder
    p_import_folder = sub.add_parser('import-folder')
    p_import_folder.add_argument('folder_path', help='Path to the folder containing .bin files')
    p_import_folder.add_argument('-i', '--input-folder', default=None, help='Path to the folder containing JSON files')
    p_import_folder.set_defaults(func=lambda args: import_to_folder(args.folder_path, args.input_folder))

    # Convert Shift-JIS text to hex
    p_convert_to_hex = sub.add_parser('hex', help='Convert Shift-JIS text to hexadecimal representation')
    p_convert_to_hex.add_argument('text', help='The Shift-JIS text to convert')
    p_convert_to_hex.set_defaults(func=convert_to_hex_command)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
