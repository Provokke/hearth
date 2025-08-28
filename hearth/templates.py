import html
import os
import re
from datetime import date, datetime

TOKEN = re.compile(r"(\{\{.*?\}\}|\{%.*?%\})", re.S)
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


class TemplateError(Exception):
    pass


class Safe(str):
    pass


def to_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def as_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        raise TemplateError(f"cannot read {value!r} as a date")


def f_date(value, pattern="%d %B %Y"):
    return as_date(value).strftime(pattern)


FILTERS = {
    "safe": lambda value, *a: Safe(to_text(value)),
    "upper": lambda value, *a: to_text(value).upper(),
    "lower": lambda value, *a: to_text(value).lower(),
    "title": lambda value, *a: to_text(value).title(),
    "length": lambda value, *a: len(value),
    "default": lambda value, fallback="": value if value not in (None, "", [], False) else fallback,
    "join": lambda value, sep=", ": sep.join(to_text(v) for v in value),
    "reverse": lambda value, *a: list(reversed(list(value))),
    "date": lambda value, pattern="%d %B %Y": f_date(value, pattern),
    "rfc3339": lambda value, *a: as_date(value).strftime("%Y-%m-%dT%H:%M:%SZ"),
}


def split_quoted(text, separator):
    parts = []
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
        elif char == separator:
            parts.append(buffer)
            buffer = ""
        else:
            buffer += char
    parts.append(buffer)
    return parts


def resolve(expression, context):
    expression = expression.strip()
    if not expression:
        raise TemplateError("empty expression")
    if len(expression) >= 2 and expression[0] == expression[-1] and expression[0] in "\"'":
        return expression[1:-1]
    if NUMBER.match(expression):
        return float(expression) if "." in expression else int(expression)
    if expression in ("true", "false"):
        return expression == "true"
    if expression == "none":
        return None
    parts = expression.split(".")
    if parts[0] not in context:
        return None
    value = context[parts[0]]
    for part in parts[1:]:
        value = lookup(value, part)
    return value


def lookup(value, key):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    if isinstance(value, (list, tuple)):
        if key.isdigit() and int(key) < len(value):
            return value[int(key)]
        return None
    return getattr(value, key, None)


def evaluate(expression, context):
    segments = split_quoted(expression, "|")
    value = resolve(segments[0], context)
    safe = isinstance(value, Safe)
    for segment in segments[1:]:
        name, _, argument = segment.strip().partition(":")
        name = name.strip()
        if name not in FILTERS:
            raise TemplateError(f"unknown filter {name!r}")
        args = [resolve(a, context) for a in split_quoted(argument, ":")] if argument.strip() else []
        value = FILTERS[name](value, *args)
        if name == "safe":
            safe = True
    return value, safe


COMPARE = re.compile(r"^(.*?)\s+(==|!=|>=|<=|>|<)\s+(.*)$")


def truthy(condition, context):
    condition = condition.strip()
    if condition.startswith("not "):
        return not truthy(condition[4:], context)
    for word, combine in ((" and ", all), (" or ", any)):
        if word in condition:
            return combine(truthy(part, context) for part in condition.split(word))
    match = COMPARE.match(condition)
    if match:
        left = evaluate(match.group(1), context)[0]
        right = evaluate(match.group(3), context)[0]
        op = match.group(2)
        try:
            return {
                "==": left == right,
                "!=": left != right,
                ">": left > right,
                "<": left < right,
                ">=": left >= right,
                "<=": left <= right,
            }[op]
        except TypeError:
            return False
    return bool(evaluate(condition, context)[0])


class Template:
    def __init__(self, source, name="<string>"):
        self.name = name
        self.nodes, self.parent = self.parse(source)

    def parse(self, source):
        tokens = [t for t in TOKEN.split(source) if t != ""]
        parent = None
        position = 0
        if tokens and tokens[0].startswith("{%"):
            match = re.match(r'\{%\s*extends\s+["\'](.+?)["\']\s*%\}', tokens[0])
            if match:
                parent = match.group(1)
                position = 1
        nodes, position, closer = self.parse_nodes(tokens, position, ())
        if closer:
            raise TemplateError(f"{self.name}: unexpected {closer!r}")
        return nodes, parent

    def parse_nodes(self, tokens, position, stops):
        nodes = []
        while position < len(tokens):
            token = tokens[position]
            position += 1
            if token.startswith("{{"):
                nodes.append(("var", token[2:-2].strip()))
            elif token.startswith("{%"):
                tag = token[2:-2].strip()
                word = tag.split(None, 1)[0] if tag else ""
                if word in stops:
                    return nodes, position, tag
                if word == "if":
                    node, position = self.parse_if(tokens, position, tag[2:].strip())
                    nodes.append(node)
                elif word == "for":
                    match = re.match(r"^for\s+(\w+)\s+in\s+(.+)$", tag)
                    if not match:
                        raise TemplateError(f"{self.name}: bad for tag {tag!r}")
                    body, position, closer = self.parse_nodes(tokens, position, ("endfor",))
                    if not closer:
                        raise TemplateError(f"{self.name}: for without endfor")
                    nodes.append(("for", match.group(1), match.group(2), body))
                elif word == "block":
                    name = tag[5:].strip()
                    body, position, closer = self.parse_nodes(tokens, position, ("endblock",))
                    if not closer:
                        raise TemplateError(f"{self.name}: block without endblock")
                    nodes.append(("block", name, body))
                elif word == "include":
                    match = re.match(r'^include\s+["\'](.+?)["\']$', tag)
                    if not match:
                        raise TemplateError(f"{self.name}: bad include tag {tag!r}")
                    nodes.append(("include", match.group(1)))
                else:
                    raise TemplateError(f"{self.name}: unknown tag {tag!r}")
            else:
                nodes.append(("text", token))
        return nodes, position, None

    def parse_if(self, tokens, position, condition):
        branches = []
        otherwise = []
        body, position, closer = self.parse_nodes(tokens, position, ("elif", "else", "endif"))
        branches.append((condition, body))
        while closer and not closer.startswith("endif"):
            if closer.startswith("elif"):
                condition = closer[4:].strip()
                body, position, closer = self.parse_nodes(tokens, position, ("elif", "else", "endif"))
                branches.append((condition, body))
            else:
                otherwise, position, closer = self.parse_nodes(tokens, position, ("endif",))
        if not closer:
            raise TemplateError(f"{self.name}: if without endif")
        return ("if", branches, otherwise), position

    def render(self, context, environment, overrides=None):
        overrides = dict(overrides or {})
        if self.parent:
            for node in self.nodes:
                if node[0] == "block":
                    overrides.setdefault(node[1], node[2])
            return environment.get(self.parent).render(context, environment, overrides)
        return "".join(self.run(self.nodes, context, environment, overrides))

    def run(self, nodes, context, environment, overrides):
        for node in nodes:
            kind = node[0]
            if kind == "text":
                yield node[1]
            elif kind == "var":
                value, safe = evaluate(node[1], context)
                text = to_text(value)
                yield text if safe else html.escape(text, quote=True)
            elif kind == "if":
                chosen = node[2]
                for condition, body in node[1]:
                    if truthy(condition, context):
                        chosen = body
                        break
                yield from self.run(chosen, context, environment, overrides)
            elif kind == "for":
                items = evaluate(node[2], context)[0] or []
                items = list(items)
                for index, item in enumerate(items):
                    inner = dict(context)
                    inner[node[1]] = item
                    inner["loop"] = {
                        "index": index + 1,
                        "index0": index,
                        "first": index == 0,
                        "last": index == len(items) - 1,
                        "length": len(items),
                    }
                    yield from self.run(node[3], inner, environment, overrides)
            elif kind == "block":
                body = overrides.get(node[1], node[2])
                yield from self.run(body, context, environment, overrides)
            elif kind == "include":
                yield environment.get(node[1]).render(context, environment)


class Environment:
    def __init__(self, directory=None, sources=None):
        self.directory = directory
        self.sources = dict(sources or {})
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            if name in self.sources:
                source = self.sources[name]
            elif self.directory:
                path = os.path.join(self.directory, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        source = handle.read()
                except OSError:
                    raise TemplateError(f"template {name!r} not found")
            else:
                raise TemplateError(f"template {name!r} not found")
            self.cache[name] = Template(source, name)
        return self.cache[name]

    def render(self, name, context):
        return self.get(name).render(context, self)

    def render_string(self, source, context):
        return Template(source).render(context, self)
