#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a primary GPT from a disk image, including trimmed vendor images."""
import argparse
import json
import struct
import uuid
import zlib
from pathlib import Path


def inspect(path):
    size = path.stat().st_size
    with path.open("rb") as stream:
        for sector in (512, 4096):
            stream.seek(sector)
            header = bytearray(stream.read(sector))
            if header[:8] == b"EFI PART":
                break
        else:
            raise ValueError("No primary GPT signature at sector 1")
        fields = struct.unpack_from("<8sIIIIQQQQ16sQIII", header)
        _, revision, header_size, header_crc, _, current, backup, first, last, guid, table_lba, count, entry_size, table_crc = fields
        if not 92 <= header_size <= sector or entry_size < 128 or count * entry_size > 16 * 1024**2:
            raise ValueError("Invalid GPT geometry")
        struct.pack_into("<I", header, 16, 0)
        header_valid = zlib.crc32(header[:header_size]) == header_crc
        stream.seek(table_lba * sector)
        table = stream.read(count * entry_size)
        table_valid = len(table) == count * entry_size and zlib.crc32(table) == table_crc
        if not header_valid or not table_valid:
            raise ValueError("Primary GPT CRC mismatch")
        parts = []
        for index in range(count):
            entry = table[index * entry_size:(index + 1) * entry_size]
            if entry[:16] == bytes(16):
                continue
            start, end, attrs = struct.unpack_from("<QQQ", entry, 32)
            offset, length = start * sector, (end - start + 1) * sector
            stream.seek(offset)
            probe = stream.read(min(8192, max(0, size - offset)))
            parts.append({"index": index + 1,
                          "name": entry[56:128].decode("utf-16le").split("\0")[0],
                          "type_guid": str(uuid.UUID(bytes_le=entry[:16])),
                          "offset": offset, "bytes": length,
                          "available_bytes": max(0, min(length, size - offset)),
                          "complete_in_file": offset + length <= size,
                          "prefix_hex": probe[:32].hex(),
                          "ext4_magic": probe[1080:1082].hex()})
    return {"image": str(path), "image_bytes": size, "sector_bytes": sector,
            "header_crc_valid": header_valid, "entries_crc_valid": table_valid,
            "disk_guid": str(uuid.UUID(bytes_le=guid)),
            "backup_lba": backup, "backup_header_in_file": (backup + 1) * sector <= size,
            "partitions": parts}
