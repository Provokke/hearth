import json
import os
import re
import shutil
from datetime import date, datetime
from xml.sax.saxutils import escape as xml_escape

from . import frontmatter, markdown
from .templates import Environment, Safe, TemplateError

DEFAULT_LAYOUT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{ page.title }}</title>
</head>
<body>
{{ content | safe }}
</body>
</html>
"""

DATED_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


class BuildError(Exception):
    pass


class Page:
    def __init__(self, source, relative, meta, body):
        self.source = source
        self.relative = relative
        self.meta = dict(meta)
        self.body = body
        self.html = ""
        self.url = ""
        self.output = ""

    def as_dict(self):
        data = dict(self.meta)
        data.update(url=self.url, content=Safe(self.html), source=self.relative)
        return data


def sort_key(page):
    stamp = page.meta.get("date")
    if isinstance(stamp, datetime):
        stamp = stamp.date()
    return (stamp or date.min, str(page.meta.get("title", "")))


def load_config(root):
    config = {"title": "Untitled site", "description": "", "base_url": ""}
    path = os.path.join(root, "hearth.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                config.update(json.load(handle))
        except json.JSONDecodeError as error:
            raise BuildError(f"hearth.json is not valid JSON: {error}")
    config["base_url"] = str(config["base_url"]).rstrip("/")
    return config


def derive_location(relative, meta):
    stem = os.path.splitext(relative)[0].replace(os.sep, "/")
    directory, _, name = stem.rpartition("/")
    match = DATED_NAME.match(name)
    if match:
        meta.setdefault("date", date.fromisoformat(match.group(1)))
        name = match.group(2)
    slug = str(meta.get("slug") or name)
    return f"{directory}/{slug}" if directory else slug


def output_path(location, pretty=True):
    if location == "index" or location.endswith("/index"):
        return location + ".html"
    return f"{location}/index.html" if pretty else location + ".html"


def url_for(output):
    url = "/" + output.replace(os.sep, "/")
    if url.endswith("/index.html"):
        url = url[: -len("index.html")]
    return url


def read_pages(content_dir, include_drafts):
    pages = []
    assets = []
    for folder, directories, files in os.walk(content_dir):
        directories.sort()
        for name in sorted(files):
            full = os.path.join(folder, name)
            relative = os.path.relpath(full, content_dir)
            if not name.lower().endswith(".md"):
                assets.append((full, relative))
                continue
            with open(full, encoding="utf-8") as handle:
                text = handle.read().replace("\r\n", "\n")
            try:
                meta, body = frontmatter.split(text)
            except frontmatter.FrontMatterError as error:
                raise BuildError(f"{relative}: {error}")
            if meta.get("draft") and not include_drafts:
                continue
            pages.append(Page(full, relative, meta, body))
    return pages, assets


def prepare(page, pretty):
    location = derive_location(page.relative, page.meta)
    page.output = output_path(location, pretty)
    page.url = url_for(page.output)
    page.html = markdown.render(page.body)
    if not page.meta.get("title"):
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", page.html, re.S)
        if heading:
            page.meta["title"] = re.sub(r"<[^>]+>", "", heading.group(1))
        else:
            page.meta["title"] = os.path.splitext(os.path.basename(page.relative))[0].replace("-", " ").title()
    if not page.meta.get("summary"):
        page.meta["summary"] = markdown.first_paragraph(page.body)


def copy_tree(source, target):
    if not os.path.isdir(source):
        return 0
    count = 0
    for folder, _, files in os.walk(source):
        for name in files:
            full = os.path.join(folder, name)
            destination = os.path.join(target, os.path.relpath(full, source))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(full, destination)
            count += 1
    return count


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def sitemap(config, pages):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        lines.append(f"  <url><loc>{xml_escape(config['base_url'] + page.url)}</loc></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def safe_to_clear(source, output):
    source = os.path.abspath(source)
    output = os.path.abspath(output)
    return output != source and not source.startswith(output + os.sep)


def build(source, output, include_drafts=False, pretty=True):
    source = os.path.abspath(source)
    content_dir = os.path.join(source, "content")
    if not os.path.isdir(content_dir):
        raise BuildError(f"no content directory in {source}")
    if not safe_to_clear(source, output):
        raise BuildError("output directory would overwrite the source")
    config = load_config(source)
    pages, assets = read_pages(content_dir, include_drafts)
    seen = {}
    for page in pages:
        prepare(page, pretty)
        if page.output in seen:
            raise BuildError(f"{page.relative} and {seen[page.output]} both build to {page.output}")
        seen[page.output] = page.relative
    pages.sort(key=sort_key, reverse=True)
    templates_dir = os.path.join(source, "templates")
    environment = Environment(templates_dir if os.path.isdir(templates_dir) else None, {"default.html": DEFAULT_LAYOUT})
    tags = {}
    for page in pages:
        for tag in page.meta.get("tags") or []:
            tags.setdefault(str(tag), []).append(page.as_dict())
    site = dict(config)
    site["pages"] = [p.as_dict() for p in pages]
    site["tags"] = tags
    site["built"] = date.today().isoformat()
    if os.path.isdir(output):
        shutil.rmtree(output)
    os.makedirs(output)
    for page in pages:
        layout = page.meta.get("layout") or "default.html"
        context = {"site": site, "page": page.as_dict(), "content": Safe(page.html)}
        try:
            text = environment.render(layout, context)
        except TemplateError as error:
            raise BuildError(f"{page.relative}: {error}")
        write(os.path.join(output, page.output), text)
    copied = 0
    for full, relative in assets:
        destination = os.path.join(output, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(full, destination)
        copied += 1
    copied += copy_tree(os.path.join(source, "static"), output)
    if config["base_url"]:
        write(os.path.join(output, "sitemap.xml"), sitemap(config, pages))
    return {"pages": len(pages), "files": copied}
