#!/usr/bin/env python3

import argparse
import json
import os
import struct
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional


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


class DialogTextExtractor:
    def __init__(self, filepath: str):
        self.filepath = str(filepath)
        self.filename = os.path.basename(filepath)
        try:
            self.index = int(self.filename.split('.')[0])
        except Exception:
            self.index = 0

    def parse_binary(self) -> Dict[str, Any]:
        with open(self.filepath, 'rb') as f:
            data = f.read()

        file_size = len(data)
        entry_count, magic = struct.unpack_from('<II', data, 0)

        entries = []
        for i in range(entry_count):
            pos = 8 + i * 20
            unk0, unk1, unk2, entry_idx, offset = struct.unpack_from('<IIIII', data, pos)
            entries.append({
                'unk0': unk0, 'unk1': unk1, 'unk2': unk2,
                'entry_idx': entry_idx, 'offset': offset
            })

        parsed_entries = []
        for entry_i, entry in enumerate(entries):
            ehdr_pos = entry['offset']
            unk0, block_count, unk2, unk3, unk4 = struct.unpack_from('<IIIII', data, ehdr_pos)

            blocks = []
            pos = ehdr_pos + 20
            for bi in range(block_count):
                if pos + 4 > file_size:
                    break
                marker, block_size = struct.unpack_from('<HH', data, pos)
                block_data_start = pos + 4
                block_data_end = pos + block_size  # block_size includes the 4-byte header

                if block_data_end > file_size:
                    break

                block_info = {
                    'block_index': bi,
                    'marker': marker,
                    'block_size': block_size,
                    'offset': pos,
                    'texts': []
                }

                if marker == 0x000B and block_size > 4:
                    self._parse_text_block(data, block_data_start, block_data_end, block_info)

                blocks.append(block_info)
                pos = block_data_end

            parsed_entries.append({
                'entry_index': entry_i,
                'entry_idx': entry['entry_idx'],
                'offset': entry['offset'],
                'entry_header': {
                    'unk0': unk0,
                    'block_count': block_count,
                    'unk2': unk2,
                    'unk3': unk3,
                    'unk4': unk4
                },
                'blocks': blocks
            })

        return {
            'file_info': {
                'filename': self.filename,
                'index': self.index,
                'file_size': file_size,
                'entry_count': entry_count,
                'magic': magic
            },
            'entries': parsed_entries
        }

    def _parse_text_block(self, data: bytes, block_data_start: int, block_data_end: int, block_info: dict):
        # Parse sub-header for 0x000B blocks
        if block_data_start + 32 > block_data_end:
            return

        type_val = struct.unpack_from('<I', data, block_data_start)[0]
        padding = struct.unpack_from('<I', data, block_data_start + 4)[0]
        window_style = struct.unpack_from('<H', data, block_data_start + 8)[0]
        padding2 = struct.unpack_from('<H', data, block_data_start + 10)[0]
        text_count = struct.unpack_from('<H', data, block_data_start + 12)[0]
        text_size = struct.unpack_from('<H', data, block_data_start + 14)[0]
        sub_block_idx = struct.unpack_from('<H', data, block_data_start + 16)[0]
        unk5 = struct.unpack_from('<H', data, block_data_start + 18)[0]
        unk6 = struct.unpack_from('<H', data, block_data_start + 20)[0]
        unk7 = struct.unpack_from('<H', data, block_data_start + 22)[0]
        format_flag = struct.unpack_from('<H', data, block_data_start + 24)[0]
        message_id = struct.unpack_from('<H', data, block_data_start + 26)[0]
        data_flag = struct.unpack_from('<H', data, block_data_start + 28)[0]
        data_size = struct.unpack_from('<H', data, block_data_start + 30)[0]

        block_info['sub_header'] = {
            'type': type_val,
            'padding': padding,
            'window_style': window_style,
            'padding2': padding2,
            'text_count': text_count,
            'text_size': text_size,
            'sub_block_idx': sub_block_idx,
            'unk5': unk5,
            'unk6': unk6,
            'unk7': unk7,
            'format_flag': format_flag,
            'message_id': message_id,
            'data_flag': data_flag,
            'data_size': data_size
        }

        # Parse TextEntry headers
        text_entries_pos = block_data_start + 32
        text_entries = []
        for j in range(text_count):
            entry_pos = text_entries_pos + j * 8
            if entry_pos + 8 > block_data_end:
                break
            line_flags, slot_size, rel_offset = struct.unpack_from('<HHI', data, entry_pos)
            text_entries.append({
                'line_flags': line_flags,
                'slot_size': slot_size,
                'rel_offset': rel_offset
            })

        block_info['text_entries'] = text_entries

        # Extract text data - find text between 0x22 delimiters
        text_data_start = text_entries_pos + text_count * 8
        texts = []
        j = text_data_start
        while j < block_data_end:
            if data[j] == 0x22:
                j += 1
                text_start = j
                while j < block_data_end:
                    if data[j] == 0x22:
                        raw = data[text_start:j]
                        decoded = decode_shiftjis_with_escape(raw)
                        texts.append({
                            'start': text_start,
                            'end': j,
                            'raw_hex': raw.hex(),
                            'original': decoded,
                            'modified': decoded
                        })
                        j += 1
                        break
                    j += 1
            else:
                j += 1

        block_info['texts'] = texts

    def export_to_json(self, output_path: Optional[str] = None) -> str:
        out_path = Path(output_path) if output_path else Path(self.filepath).with_suffix('.json')
        data = self.parse_binary()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(out_path)

    def import_from_json(self, json_path: str, output_bin_path: Optional[str] = None) -> str:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_bin_path is None:
            output_bin_path = self.filepath

        with open(self.filepath, 'rb') as f:
            original = bytearray(f.read())

        for entry in data.get('entries', []):
            for block in entry.get('blocks', []):
                if block.get('marker') != 0x000B:
                    continue
                for text_entry in block.get('texts', []):
                    modified_text = text_entry.get('modified', text_entry.get('original', ''))
                    encoded = encode_shiftjis_with_escape(modified_text)
                    start = text_entry.get('start')
                    end = text_entry.get('end')
                    if start is not None and end is not None:
                        original[start:end] = encoded

        with open(output_bin_path, 'wb') as f:
            f.write(original)

        return output_bin_path


def export_command(args):
    extractor = DialogTextExtractor(args.input_file)
    path = extractor.export_to_json(args.output_file)
    print(f"Exported: {path}")


def import_command(args):
    extractor = DialogTextExtractor(args.input_file)
    out = extractor.import_from_json(args.json_file, args.output_file)
    print(f"Imported -> {out}")


def main():
    parser = argparse.ArgumentParser(description='Kengo 3 Dialog Text Extractor')
    sub = parser.add_subparsers(dest='cmd')

    p_export = sub.add_parser('export')
    p_export.add_argument('input_file')
    p_export.add_argument('-o', '--output-file', default=None)
    p_export.set_defaults(func=export_command)

    p_import = sub.add_parser('import')
    p_import.add_argument('input_file', help='Original .bin file')
    p_import.add_argument('json_file', help='JSON file with translations')
    p_import.add_argument('-o', '--output-file', default=None)
    p_import.set_defaults(func=import_command)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
