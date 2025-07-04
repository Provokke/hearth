import html
import re

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
BULLET = re.compile(r"^(\s*)([-*+])\s+(.*)$")
NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
FENCE = re.compile(r"^```\s*([\w+-]*)\s*$")
ESCAPABLE = "\\`*_{}[]()#+-.!>"


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def escape(text):
    return html.escape(text, quote=False)


def render_inline(text):
    stash = []

    def hold(markup):
        stash.append(markup)
        return f"\x00{len(stash) - 1}\x00"

    def code(match):
        return hold(f"<code>{escape(match.group(2).strip())}</code>")

    text = re.sub(r"(`+)(.+?)\1", code, text)

    def escaped(match):
        return hold(escape(match.group(1)))

    text = re.sub(r"\\([" + re.escape(ESCAPABLE) + r"])", escaped, text)
    text = escape(text)

    def image(match):
        alt, url = match.group(1), match.group(2)
        return hold(f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}">')

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, text)

    def link(match):
        label, url = match.group(1), match.group(2)
        return hold(f'<a href="{html.escape(html.unescape(url), quote=True)}">') + label + hold("</a>")

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)

    def autolink(match):
        url = match.group(1)
        return hold(f'<a href="{url}">{url}</a>')

    text = re.sub(r"&lt;(https?://[^\s&]+)&gt;", autolink, text)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(?=\S)(.+?)(?<=\S)\*", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text)
    text = re.sub(r" {2,}\n", "<br>\n", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def starts_block(line):
    return bool(
        HEADING.match(line)
        or FENCE.match(line)
        or RULE.match(line)
        or line.startswith(">")
        or BULLET.match(line)
        or NUMBERED.match(line)
    )


class Renderer:
    def __init__(self):
        self.used_ids = {}

    def unique_id(self, text):
        base = slugify(text) or "section"
        count = self.used_ids.get(base, 0)
        self.used_ids[base] = count + 1
        return base if count == 0 else f"{base}-{count}"

    def blocks(self, lines):
        out = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            fence = FENCE.match(line)
            if fence:
                index = self.fenced(lines, index, fence.group(1), out)
                continue
            heading = HEADING.match(line)
            if heading:
                level = len(heading.group(1))
                inner = render_inline(heading.group(2))
                out.append(f'<h{level} id="{self.unique_id(inner)}">{inner}</h{level}>')
                index += 1
                continue
            if RULE.match(line):
                out.append("<hr>")
                index += 1
                continue
            if line.startswith(">"):
                index = self.quote(lines, index, out)
                continue
            if BULLET.match(line) or NUMBERED.match(line):
                index = self.list(lines, index, out)
                continue
            index = self.paragraph(lines, index, out)
        return "\n".join(out)

    def fenced(self, lines, index, language, out):
        body = []
        index += 1
        while index < len(lines) and not lines[index].startswith("```"):
            body.append(lines[index])
            index += 1
        attribute = f' class="language-{language}"' if language else ""
        out.append(f"<pre><code{attribute}>{escape(chr(10).join(body))}\n</code></pre>")
        return index + 1

    def quote(self, lines, index, out):
        inner = []
        while index < len(lines) and lines[index].startswith(">"):
            inner.append(re.sub(r"^>\s?", "", lines[index]))
            index += 1
        out.append(f"<blockquote>\n{self.blocks(inner)}\n</blockquote>")
        return index

    def paragraph(self, lines, index, out):
        chunk = [lines[index]]
        index += 1
        while index < len(lines) and lines[index].strip() and not starts_block(lines[index]):
            chunk.append(lines[index])
            index += 1
        joined = "\n".join(line.lstrip() if line.endswith("  ") else line.strip() for line in chunk)
        out.append(f"<p>{render_inline(joined.strip())}</p>")
        return index

    def list(self, lines, index, out):
        first = BULLET.match(lines[index]) or NUMBERED.match(lines[index])
        ordered = bool(NUMBERED.match(lines[index]) and not BULLET.match(lines[index]))
        base = len(first.group(1))
        items = []
        while index < len(lines):
            line = lines[index]
            match = (NUMBERED if ordered else BULLET).match(line)
            if match and len(match.group(1)) == base:
                items.append([match.group(3)])
                index += 1
                continue
            if not line.strip():
                lookahead = index + 1
                if lookahead < len(lines) and lines[lookahead].startswith(" " * (base + 2)) and items:
                    items[-1].append("")
                    index += 1
                    continue
                break
            if items and len(line) - len(line.lstrip()) > base:
                items[-1].append(line[base + 2 :] if line.startswith(" " * (base + 2)) else line.lstrip())
                index += 1
                continue
            break
        tag = "ol" if ordered else "ul"
        rendered = []
        for item in items:
            inner = self.blocks(item)
            single = re.fullmatch(r"<p>(.*)</p>", inner, re.S)
            if single and "</p>" not in single.group(1):
                inner = single.group(1)
            else:
                inner = re.sub(r"^<p>([^\n]*?)</p>\n(?=<[uo]l>)", r"\1\n", inner)
            rendered.append(f"<li>{inner}</li>")
        out.append(f"<{tag}>\n" + "\n".join(rendered) + f"\n</{tag}>")
        return index


def render(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return Renderer().blocks(lines)


def first_paragraph(text, limit=200):
    for chunk in re.split(r"\n\s*\n", text.strip()):
        chunk = chunk.strip()
        if chunk and not starts_block(chunk.split("\n")[0]):
            plain = re.sub(r"<[^>]+>", "", render_inline(" ".join(chunk.split())))
            plain = html.unescape(plain)
            if len(plain) > limit:
                plain = plain[: limit - 1].rsplit(" ", 1)[0] + "…"
            return plain
    return ""
