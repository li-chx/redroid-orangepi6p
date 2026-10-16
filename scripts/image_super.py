#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a raw, single-device Android super partition; optionally extract one FS.

Format reference: AOSP android-14.0.0_r1 liblp/metadata_format.h.
Only slot 0, primary metadata, raw disk images and LINEAR/ZERO extents supported.
No mounts, device-mapper mappings or input writes.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


def read_at(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Unexpected EOF")
    return data


def checked_digest(data, start, end):
    expected = data[start:end]
    cleared = bytearray(data)
    cleared[start:end] = bytes(end - start)
    if hashlib.sha256(cleared).digest() != expected:
        raise ValueError("Metadata SHA256 mismatch")


def parse(stream, offset, length):
    geo = read_at(stream, offset + 4096, 4096)
    magic, size = struct.unpack_from("<II", geo)
    if magic != 0x616C4467 or size != 52:
        raise ValueError("Unsupported LP geometry")
    checked_digest(geo[:size], 8, 40)
    maximum, slots, block = struct.unpack_from("<III", geo, 40)
    if not 128 <= maximum <= 16 * 1024**2 or not 1 <= slots <= 8:
        raise ValueError("Invalid metadata bounds")
    pos = offset + 12288
    prefix = read_at(stream, pos, 128)
    magic, major, minor, header_size = struct.unpack_from("<IHHI", prefix)
    if magic != 0x414C5030 or major != 10 or minor > 2 or header_size not in (128, 256):
        raise ValueError("Unsupported LP metadata header")
    header = read_at(stream, pos, header_size)
    checked_digest(header, 12, 44)
    tables_size = struct.unpack_from("<I", header, 44)[0]
    if header_size + tables_size > maximum:
        raise ValueError("Tables exceed metadata slot")
    tables = read_at(stream, pos + header_size, tables_size)
    if hashlib.sha256(tables).digest() != header[48:80]:
        raise ValueError("Tables SHA256 mismatch")

    def table(at, expected_size):
        begin, count, entry_size = struct.unpack_from("<III", header, at)
        if entry_size != expected_size or begin + count * entry_size > len(tables):
            raise ValueError("Invalid table descriptor")
        return [tables[begin + i * entry_size:begin + (i + 1) * entry_size]
                for i in range(count)]

    devices = []
    for entry in table(116, 64):
        first, align, align_offset, size, name, flags = struct.unpack("<QIIQ36sI", entry)
        devices.append({"name": name.split(b"\0")[0].decode(), "bytes": size,
                        "first_sector": first})
    if len(devices) != 1 or devices[0]["name"] != "super" or devices[0]["bytes"] != length:
        raise ValueError("Only matching, single-device super images supported")
    extents = []
    for entry in table(92, 24):
        sectors, kind, target, source = struct.unpack("<QIQI", entry)
        if kind not in (0, 1) or source != 0:
            raise ValueError("Unsupported extent")
        if kind == 0 and (target < devices[0]["first_sector"] or (target + sectors) * 512 > length):
            raise ValueError("Linear extent outside super data")
        if kind == 1 and target != 0:
            raise ValueError("Invalid zero extent")
        extents.append({"bytes": sectors * 512, "kind": kind, "super_offset": target * 512})
    groups = table(104, 48)
    partitions = []
    for entry in table(80, 52):
        name, attrs, first, count, group = struct.unpack("<36sIIII", entry)
        name = name.split(b"\0")[0].decode()
        if not re.fullmatch(r"[A-Za-z0-9_]+", name) or first + count > len(extents) or group >= len(groups):
            raise ValueError("Invalid partition record")
        owned = extents[first:first + count]
        partitions.append({"name": name, "attributes": attrs, "bytes": sum(x["bytes"] for x in owned),
                           "extents": owned})
    return {"version": [major, minor], "geometry_sha256_valid": True,
            "header_sha256_valid": True, "tables_sha256_valid": True,
            "metadata_max_bytes": maximum, "slots": slots, "devices": devices,
            "partitions": partitions}
