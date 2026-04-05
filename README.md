<div align="center">

# hearth

A small static site generator in Python. Markdown subset, front matter and a tiny template language in, a folder of plain HTML out.

![License](https://img.shields.io/badge/LICENSE-MIT-blue?style=for-the-badge)  ![Language](https://img.shields.io/badge/PYTHON-3776ab?style=for-the-badge&logo=python&logoColor=white)  ![Tests](https://img.shields.io/badge/TESTS-74-brightgreen?style=for-the-badge)

Refer to [LICENSE](LICENSE) for the legal bits.

</div>

## What's in it

- A front matter reader for `---` blocks: strings, numbers, booleans, dates, inline lists (`[a, b]`) and block lists.
- A markdown renderer written from scratch for the subset I actually use: headings (with anchor ids), paragraphs, emphasis, strong, strikethrough, code spans and fences, links, images, autolinks, nested lists, blockquotes, rules and hard breaks. HTML in the source is escaped.
- A template engine with `{{ var }}` (escaped by default), filters (`safe`, `upper`, `lower`, `title`, `length`, `default`, `join`, `reverse`, `date`, `rfc3339`), `if`/`elif`/`else`, `for` with a `loop` object, `include`, and `extends` with `block` overrides across several levels.
- A site builder: pretty URLs, dated filenames (`2026-03-02-first-light.md` gives a date and a `first-light` slug), drafts, newest-first page lists, tags, copied assets and static files, and a `sitemap.xml` when `base_url` is set.

```
---
title: First light
layout: post.html
tags: [meta, notes]
---

The first post, with a [link](https://example.com).
```

```
{% for p in site.pages %}<a href="{{ p.url }}">{{ p.title }}</a> {{ p.date | date:"%d %b %Y" }}{% endfor %}
```

## 🏗️ Architecture

```
 site/
  ├─ hearth.json      title, description, base_url
  ├─ content/         *.md pages (+ any other file copied as is)
  ├─ templates/       layouts, partials
  └─ static/          copied to the output root

 frontmatter.split ─► meta + body
 markdown.render   ─► html
 site.build        ─► pages[] ─► templates.Environment.render ─► output/
```

- **frontmatter.py** splits the header from the body and parses the small value grammar.
- **markdown.py** is a block parser (`Renderer`) plus an inline pass that stashes code spans and escapes before applying emphasis and links.
- **templates.py** parses to a node tree once per template, then renders it against a context. Layout inheritance collects the child's blocks and renders the parent with them.
- **site.py** reads every page first and renders templates second, so an index page can list all the others. The output directory is cleared on each build, and hearth refuses to clear a directory that contains the source.
- **cli.py** is the `hearth build` command.

## 🚀 Quick start

Python 3.9 or newer, no dependencies.

```
python -m hearth build example -o public
```

```
built 4 pages and copied 1 files to public
```

Options: `-o` for the output directory (default `<source>/public`), `--drafts` to include pages marked `draft: true`, and `--flat` to write `about.html` instead of `about/index.html`. The `example/` folder is a small working site with a base layout, a post layout and an index.

## 🧪 Testing

```
python -m unittest discover -s tests
```

74 tests, all passing:

- Front matter: scalars, quoting, both list forms, comments, unclosed and malformed blocks (9).
- Markdown: inline formatting and escaping, headings and unique ids, lists and nesting, fences, quotes, rules, helpers (22).
- Templates: variables, filters, conditions, loops, scoping, includes, multi-level inheritance, error cases (25).
- Site builder and CLI: URLs and slugs, sorting, drafts, stale file removal, sitemap, duplicate output paths, bad layouts, exit codes (18).
