#!/usr/bin/env python3
"""
credits to mr deepseek v4 flash
"""

import argparse
import json
import os
import struct
import sys
from pathlib import Path
from typing import Optional

ELF_PATH = Path(__file__).resolve().parent.parent / "files" / "isofolder" / "SLPM_657.00"
CRC = "8FA8F9AD"  # SLPM_657.00 CRC for PCSX2 .pnach naming

# Known string cluster boundaries (virtual addresses)
# Source: TetraMCP analysis + manual inspection
STRING_CLUSTERS = [
    (0x002DAE00, 0x002DBA00),  # Main string table (status, stats, technique labels)
    (0x002D0500, 0x002D0A00),  # Match/versus strings
    (0x002D8400, 0x002D9200),  # Menu/status strings
    (0x002D9200, 0x002D9A00),  # Shop/dialog strings
    (0x002CBF00, 0x002CC100),  # General UI strings
    (0x002D4A00, 0x002D4C00),  # Character type strings
]

# ASCII-only format strings cluster (no SJIS, but translatable)
ASCII_CLUSTERS = [
    (0x002DB180, 0x002DB280),  # format strings like %s%s, %-14s
    (0x002DB600, 0x002DB690),  # PassWord %s, %s, %-14s/%s
    (0x002DB900, 0x002DB980),  # dash separators
]

# Technique name records: structured 64-byte entries
# Each record: [name+padding:32B][data:32B]
TECHNIQUE_RECORDS = [
    (0x002A6E00, 0x002A7C00),  # Technique names
    (0x002AA000, 0x002AC600),  # Technique property data
]


# ── Shift-JIS helpers ──────────────────────────────────────────────

def decode_shiftjis(data: bytes) -> str:
    parts = []
    i = 0
    while i < len(data):
        if data[i] == 0x00:
            break
        if i + 1 < len(data):
            try:
                parts.append(data[i:i+2].decode('shift_jis'))
                i += 2
                continue
            except (UnicodeDecodeError, LookupError):
                pass
        try:
            parts.append(chr(data[i]))
        except:
            parts.append(f'\\x{data[i]:02x}')
        i += 1
    return ''.join(parts)


def encode_shiftjis(text: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i:i+2] == '\\x' and i + 3 < len(text):
            h = text[i+2:i+4]
            if all(c in '0123456789abcdefABCDEF' for c in h):
                out.append(int(h, 16))
                i += 4
                continue
        for length in (2, 1):
            if i + length <= len(text):
                try:
                    out.extend(text[i:i+length].encode('shift_jis'))
                    i += length
                    break
                except:
                    if length == 1:
                        out.append(0x3F)
                        i += 1
        else:
            out.append(0x3F)
            i += 1
    return bytes(out)


# ── ELF helpers ────────────────────────────────────────────────────

def is_sjis_lead(b: int) -> bool:
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF)


def is_sjis_trail(b: int) -> bool:
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)


def is_printable_ascii(b: int) -> bool:
    return 0x20 <= b <= 0x7E


class ElfStringExtractor:
    def __init__(self, elf_path: str):
        self.elf_path = elf_path
        self.elf_data = Path(elf_path).read_bytes()
        self.file_size = len(self.elf_data)
        self.load_offset = 0
        self.load_vaddr = 0
        self.load_filesz = 0
        self.load_memsz = 0
        self._parse_elf()

    def _parse_elf(self):
        d = self.elf_data
        if d[:4] != b'\x7fELF':
            raise ValueError("Not a valid ELF file")
        ei_class = d[4]
        ei_data = d[5]
        if ei_class != 1 or ei_data != 1:
            raise ValueError("Only 32-bit LE ELF supported")
        e_phoff = struct.unpack_from('<I', d, 0x1C)[0]
        e_phentsize = struct.unpack_from('<H', d, 0x2A)[0]
        e_phnum = struct.unpack_from('<H', d, 0x2C)[0]
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from('<I', d, off)[0]
            if p_type == 1:
                p_offset = struct.unpack_from('<I', d, off + 0x04)[0]
                p_vaddr = struct.unpack_from('<I', d, off + 0x08)[0]
                p_filesz = struct.unpack_from('<I', d, off + 0x10)[0]
                p_memsz = struct.unpack_from('<I', d, off + 0x14)[0]
                if p_filesz > 0 and p_offset < self.file_size:
                    self.load_offset = p_offset
                    self.load_vaddr = p_vaddr
                    self.load_filesz = p_filesz
                    self.load_memsz = p_memsz
                    break
        if self.load_filesz == 0:
            raise ValueError("No LOAD segment with file data")

    def vaddr_to_file(self, vaddr: int) -> int:
        return vaddr - self.load_vaddr + self.load_offset

    def file_to_vaddr(self, foff: int) -> int:
        return foff - self.load_offset + self.load_vaddr

    def _is_in_known_cluster(self, vaddr: int, cluster_list=None) -> bool:
        if cluster_list is None:
            cluster_list = STRING_CLUSTERS
        for start, end in cluster_list:
            if start <= vaddr < end:
                return True
        return False

    def _extract_technique_names(self, data, end, min_length):
        """Extract names from structured 64-byte technique record arrays."""
        strings = []
        for start_vaddr, end_vaddr in TECHNIQUE_RECORDS:
            start = self.vaddr_to_file(start_vaddr)
            rec_end = min(self.vaddr_to_file(end_vaddr), end)
            step = 0x40  # 64 bytes per record
            for rec_start in range(start, rec_end, step):
                j = rec_start
                raw = bytearray()
                sjis_count = 0
                valid = True
                while j < min(rec_start + step, end):
                    bj = data[j]
                    if bj == 0x00:
                        break
                    if is_printable_ascii(bj):
                        raw.append(bj)
                        j += 1
                    elif is_sjis_lead(bj) and j + 1 < end and is_sjis_trail(data[j+1]):
                        raw.append(bj)
                        raw.append(data[j+1])
                        sjis_count += 1
                        j += 2
                    else:
                        valid = False
                        break

                original_length = j - rec_start
                if valid and original_length >= min_length and sjis_count >= 1:
                    k = j
                    while k < rec_start + 0x20 and k < end and data[k] == 0x00:
                        k += 1
                    max_allowed = k - rec_start
                    original_text = decode_shiftjis(raw)
                    vaddr = self.file_to_vaddr(rec_start)
                    strings.append({
                        "index": len(strings) + 10000,  # placeholder, reindexed later
                        "vaddr": f"0x{vaddr:08X}",
                        "file_offset": rec_start,
                        "original_bytes": original_length,
                        "max_allowed_bytes": max_allowed,
                        "original": original_text,
                        "modified": original_text,
                    })
        return strings

    def extract_strings(self, min_length=6, min_sjis=1, cluster_only=True):
        """
        Extract Shift-JIS strings from the ELF.

        If *cluster_only* is True, only scan known string cluster regions.
        Otherwise scan the entire data section with strict filtering.
        """
        start = self.load_offset
        end = self.load_offset + self.load_filesz
        data = self.elf_data
        strings = []

        # Phase 1: scan known clusters byte-by-byte
        i = start
        while i < end:
            vaddr = self.file_to_vaddr(i)
            if cluster_only and not self._is_in_known_cluster(vaddr):
                i += 1
                continue

            b = data[i]
            if not (is_sjis_lead(b) or is_printable_ascii(b)):
                i += 1
                continue

            str_start = i
            raw = bytearray()
            j = i
            sjis_count = 0
            valid = True

            while j < end:
                bj = data[j]
                if bj == 0x00:
                    break
                if is_printable_ascii(bj):
                    raw.append(bj)
                    j += 1
                elif is_sjis_lead(bj) and j + 1 < end and is_sjis_trail(data[j+1]):
                    raw.append(bj)
                    raw.append(data[j+1])
                    sjis_count += 1
                    j += 2
                else:
                    valid = False
                    break

            original_length = j - str_start

            if valid and original_length >= min_length and sjis_count >= 1:
                k = j
                while k < end and data[k] == 0x00:
                    k += 1
                max_allowed = k - str_start
                original_text = decode_shiftjis(raw)

                if len(original_text) > 0:
                    strings.append({
                        "index": len(strings),
                        "vaddr": f"0x{vaddr:08X}",
                        "file_offset": str_start,
                        "original_bytes": original_length,
                        "max_allowed_bytes": max_allowed,
                        "original": original_text,
                        "modified": original_text,
                    })
                i = j
            else:
                i += 1

        # Phase 2: extract technique names from structured records
        if cluster_only:
            tech_strings = self._extract_technique_names(data, end, min_length)
            strings.extend(tech_strings)

        # Phase 3: ASCII-only format strings
        if cluster_only:
            i = start
            while i < end:
                vaddr = self.file_to_vaddr(i)
                if not self._is_in_known_cluster(vaddr, ASCII_CLUSTERS):
                    i += 1
                    continue

                b = data[i]
                if not is_printable_ascii(b):
                    i += 1
                    continue

                j = i
                ascii_only = True
                while j < end:
                    bj = data[j]
                    if bj == 0x00:
                        break
                    if is_printable_ascii(bj):
                        j += 1
                    elif is_sjis_lead(bj) and j + 1 < end and is_sjis_trail(data[j+1]):
                        ascii_only = False
                        break
                    else:
                        ascii_only = False
                        break

                if ascii_only and j - i >= 4:
                    k = j
                    while k < end and data[k] == 0x00:
                        k += 1
                    max_allowed = k - i
                    original_text = data[i:j].decode('ascii', errors='replace')
                    strings.append({
                        "index": 99999,
                        "vaddr": f"0x{vaddr:08X}",
                        "file_offset": i,
                        "original_bytes": j - i,
                        "max_allowed_bytes": max_allowed,
                        "original": original_text,
                        "modified": original_text,
                    })
                i = j if ascii_only else i + 1

        # Post-filter: remove garbage strings
        def _is_garbage(text: str) -> bool:
            for ch in text:
                if ch in '$' or ('\u0370' <= ch <= '\u03ff'):  # Greek letters
                    return True
            return False

        strings = [s for s in strings if not _is_garbage(s["original"])]

        # Reindex
        for idx, s in enumerate(strings):
            s["index"] = idx

        return strings

    def export_to_json(self, strings, output_path):
        data = {
            "file_info": {
                "filename": Path(self.elf_path).name,
                "file_size": self.file_size,
                "load_vaddr": f"0x{self.load_vaddr:08X}",
                "load_filesz": self.load_filesz,
                "crc": CRC,
            },
            "strings": strings,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path

    def generate_pnach(self, json_path, output_path=None, group_name="Translation"):
        """Generate a .pnach file from a completed translation JSON."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_path is None:
            output_path = Path(json_path).with_suffix('.pnach')

        lines = []
        lines.append(f"gametitle=Kengo 3 (SLPM_657.00) {CRC}")
        lines.append("")
        lines.append(f"[{group_name}]")
        lines.append(f"description=Text translation patch")

        patched_count = 0
        skipped_count = 0

        for entry in data.get("strings", []):
            modified = entry.get("modified", entry.get("original", ""))
            original = entry.get("original", "")
            vaddr = entry["vaddr"]
            max_allowed = entry["max_allowed_bytes"]

            if modified == original:
                continue

            encoded = encode_shiftjis(modified)
            if len(encoded) > max_allowed:
                print(f"  SKIP  [{vaddr}] '{modified}' ({len(encoded)}B) > max {max_allowed}B")
                skipped_count += 1
                continue

            # Pad with nulls up to max_allowed_bytes
            padded = encoded + b'\x00' * (max_allowed - len(encoded))
            hex_data = padded.hex().upper()

            address = int(vaddr, 16)
            lines.append(f"patch=1,EE,{address:08X},bytes,{hex_data}")
            patched_count += 1

        lines.append("")
        lines.append(f"// Patched {patched_count} strings, skipped {skipped_count}")

        output = '\n'.join(lines) + '\n'
        Path(output_path).write_text(output, encoding='utf-8')
        print(f"Generated .pnach: {output_path}")
        print(f"  Patched: {patched_count}, Skipped (too long): {skipped_count}")
        return output_path


# ── CLI ────────────────────────────────────────────────────────────

def export_command(args):
    extractor = ElfStringExtractor(args.elf)
    cluster_mode = not args.full_scan
    print(f"Scanning {Path(args.elf).name}...")
    print(f"  Mode: {'known clusters only' if cluster_mode else 'full scan (strict)'}")
    strings = extractor.extract_strings(
        min_length=args.min_length,
        min_sjis=args.min_sjis,
        cluster_only=cluster_mode,
    )
    print(f"  Found {len(strings)} strings.")
    out = extractor.export_to_json(strings, args.output)
    print(f"  Exported -> {out}")


def pnach_command(args):
    extractor = ElfStringExtractor(args.elf)
    out = args.output
    if out is None:
        out = f"SLPM-65700_CB56E6FB.pnach"
    extractor.generate_pnach(args.json, out, group_name=args.group)


def info_command(args):
    extractor = ElfStringExtractor(args.elf)
    print(f"ELF:      {Path(args.elf).name}")
    print(f"Size:     {extractor.file_size} bytes")
    print(f"LOAD vaddr: 0x{extractor.load_vaddr:08X}")
    print(f"LOAD foff:  0x{extractor.load_offset:X}")
    print(f"LOAD filesz: {extractor.load_filesz} bytes")
    print(f"LOAD memsz:  {extractor.load_memsz} bytes")
    print(f"CRC:      {CRC}")
    print(f"\nString clusters:")
    for s, e in STRING_CLUSTERS:
        sz = e - s
        foff = extractor.vaddr_to_file(s)
        print(f"  0x{s:08X}-0x{e:08X} ({sz:>6} bytes)  file:0x{foff:X}")


def main():
    parser = argparse.ArgumentParser(
        description="Kengo 3 ELF → JSON → .pnach translation tool"
    )
    sub = parser.add_subparsers(dest="cmd")

    # export
    p = sub.add_parser("export", help="Extract Shift-JIS strings → JSON")
    p.add_argument("elf", nargs="?", default=str(ELF_PATH))
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--full-scan", action="store_true",
                   help="Scan entire binary (slow, many false positives)")
    p.add_argument("--min-length", type=int, default=6)
    p.add_argument("--min-sjis", type=int, default=3)
    p.set_defaults(func=export_command)

    # pnach
    p = sub.add_parser("pnach", help="Generate .pnach from translated JSON")
    p.add_argument("json", help="Translated JSON file")
    p.add_argument("elf", nargs="?", default=str(ELF_PATH))
    p.add_argument("-o", "--output", default=None, help="Output .pnach path")
    p.add_argument("--group", default="Translation", help="Patch group name")
    p.set_defaults(func=pnach_command)

    # info
    p = sub.add_parser("info", help="Show ELF info + cluster map")
    p.add_argument("elf", nargs="?", default=str(ELF_PATH))
    p.set_defaults(func=info_command)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    if args.output is None and hasattr(args, "elf") and args.cmd == "export":
        base = Path(args.elf).with_suffix("")
        args.output = str(base) + "_strings.json"

    args.func(args)


if __name__ == "__main__":
    main()
