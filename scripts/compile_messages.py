"""Compile Django .po files into .mo without external gettext binaries.

Usage:
    python scripts/compile_messages.py
"""

from __future__ import annotations

import ast
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "locale"


def _encode_mo(messages: dict[str, str]) -> bytes:
    keys = sorted(messages)
    ids = [key.encode("utf-8") for key in keys]
    strs = [messages[key].encode("utf-8") for key in keys]

    n = len(keys)
    keystart = 7 * 4
    orig_table = keystart
    trans_table = orig_table + n * 8
    ids_offset = trans_table + n * 8

    offsets_ids: list[tuple[int, int]] = []
    offsets_strs: list[tuple[int, int]] = []

    current = ids_offset
    for value in ids:
        offsets_ids.append((len(value), current))
        current += len(value) + 1

    for value in strs:
        offsets_strs.append((len(value), current))
        current += len(value) + 1

    out = bytearray()
    out.extend(struct.pack("Iiiiiii", 0x950412DE, 0, n, orig_table, trans_table, 0, 0))

    for length, offset in offsets_ids:
        out.extend(struct.pack("ii", length, offset))
    for length, offset in offsets_strs:
        out.extend(struct.pack("ii", length, offset))

    for value in ids:
        out.extend(value + b"\0")
    for value in strs:
        out.extend(value + b"\0")

    return bytes(out)


def _unquote(value: str) -> str:
    return ast.literal_eval(value)


def parse_po(po_path: Path) -> dict[str, str]:
    messages: dict[str, str] = {}
    entry: dict[str, object] = {}
    state: str | None = None

    def commit() -> None:
        nonlocal entry, state
        if not entry:
            return

        if entry.get("fuzzy"):
            entry = {}
            state = None
            return

        msgid = str(entry.get("msgid", ""))
        if msgid == "":
            messages[msgid] = str(entry.get("msgstr", ""))
            entry = {}
            state = None
            return

        msgctxt = str(entry.get("msgctxt", ""))
        msgid_plural = entry.get("msgid_plural")
        msgstr_plural = entry.get("msgstr_plural", {})
        msgstr = str(entry.get("msgstr", ""))

        key = msgid
        if msgctxt:
            key = f"{msgctxt}\x04{msgid}"

        if msgid_plural is not None:
            key = f"{key}\x00{msgid_plural}"
            plural_values = [
                str(value)
                for _, value in sorted(
                    dict(msgstr_plural).items(), key=lambda item: item[0]
                )
            ]
            messages[key] = "\x00".join(plural_values)
        else:
            messages[key] = msgstr

        entry = {}
        state = None

    with po_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                commit()
                continue
            if line.startswith("#,") and "fuzzy" in line:
                entry["fuzzy"] = True
                continue
            if line.startswith("#"):
                continue
            if line.startswith("msgctxt "):
                state = "msgctxt"
                entry[state] = _unquote(line[7:].strip())
                continue
            if line.startswith("msgid_plural "):
                state = "msgid_plural"
                entry[state] = _unquote(line[12:].strip())
                continue
            if line.startswith("msgid "):
                state = "msgid"
                entry[state] = _unquote(line[5:].strip())
                continue
            if line.startswith("msgstr["):
                end = line.find("]")
                index = int(line[7:end])
                value = _unquote(line[end + 1 :].strip())
                plural_map = dict(entry.get("msgstr_plural", {}))
                plural_map[index] = value
                entry["msgstr_plural"] = plural_map
                state = f"msgstr[{index}]"
                continue
            if line.startswith("msgstr "):
                state = "msgstr"
                entry[state] = _unquote(line[6:].strip())
                continue
            if line.startswith('"'):
                fragment = _unquote(line)
                if state == "msgctxt":
                    entry["msgctxt"] = str(entry.get("msgctxt", "")) + fragment
                elif state == "msgid":
                    entry["msgid"] = str(entry.get("msgid", "")) + fragment
                elif state == "msgid_plural":
                    entry["msgid_plural"] = (
                        str(entry.get("msgid_plural", "")) + fragment
                    )
                elif state == "msgstr":
                    entry["msgstr"] = str(entry.get("msgstr", "")) + fragment
                elif state and state.startswith("msgstr["):
                    index = int(state[7:-1])
                    plural_map = dict(entry.get("msgstr_plural", {}))
                    plural_map[index] = str(plural_map.get(index, "")) + fragment
                    entry["msgstr_plural"] = plural_map

    commit()
    return messages


def compile_file(po_path: Path) -> None:
    messages = parse_po(po_path)
    mo_path = po_path.with_suffix(".mo")
    mo_path.write_bytes(_encode_mo(messages))
    print(f"compiled: {po_path.relative_to(ROOT)} -> {mo_path.relative_to(ROOT)}")


def main() -> int:
    po_files = sorted(LOCALE_DIR.rglob("*.po"))
    if not po_files:
        print("no .po files found")
        return 0

    for po_path in po_files:
        compile_file(po_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
