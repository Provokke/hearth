import re
from datetime import date, datetime

DELIMITER = "---"
INTEGER = re.compile(r"^-?\d+$")
FLOAT = re.compile(r"^-?\d+\.\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")


class FrontMatterError(ValueError):
    pass


def split(text):
    text = text.lstrip("﻿")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != DELIMITER:
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].rstrip() == DELIMITER:
            meta = parse_block(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return meta, body
    raise FrontMatterError("front matter is not closed with ---")


def parse_block(lines):
    meta = {}
    pending = set()
    current_list = None
    for number, raw in enumerate(lines, start=2):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list is not None:
            meta[current_list].append(parse_scalar(stripped[2:].strip()))
            continue
        if ":" not in line:
            raise FrontMatterError(f"line {number}: expected 'key: value'")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            raise FrontMatterError(f"line {number}: missing key")
        if value == "":
            meta[key] = []
            pending.add(key)
            current_list = key
        else:
            meta[key] = parse_value(value)
            current_list = None
    for key in pending:
        if meta[key] == []:
            meta[key] = ""
    return meta


def parse_value(value):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in split_items(inner)]
    return parse_scalar(value)


def split_items(text):
    items = []
    buffer = ""
    quote = None
    for char in text:
        if quote:
            buffer += char
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            buffer += char
        elif char == ",":
            items.append(buffer)
            buffer = ""
        else:
            buffer += char
    items.append(buffer)
    return items


def parse_scalar(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if INTEGER.match(value):
        return int(value)
    if FLOAT.match(value):
        return float(value)
    if ISO_DATE.match(value):
        return date.fromisoformat(value)
    if ISO_DATETIME.match(value):
        return datetime.fromisoformat(value.replace(" ", "T"))
    return value
