import io
import os
import shutil
import tempfile
import unittest

from hearth.cli import main
from hearth.site import BuildError, build, derive_location, output_path, url_for


def put(root, relative, text):
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read(root, relative):
    with open(os.path.join(root, relative), encoding="utf-8") as handle:
        return handle.read()


class LocationTests(unittest.TestCase):
    def test_pretty_urls(self):
        self.assertEqual(output_path("about"), "about/index.html")
        self.assertEqual(output_path("index"), "index.html")
        self.assertEqual(output_path("blog/index"), "blog/index.html")
        self.assertEqual(output_path("about", pretty=False), "about.html")

    def test_url_for(self):
        self.assertEqual(url_for("about/index.html"), "/about/")
        self.assertEqual(url_for("index.html"), "/")
        self.assertEqual(url_for("a.html"), "/a.html")

    def test_dated_filename(self):
        meta = {}
        self.assertEqual(derive_location("posts/2026-01-02-hello.md", meta), "posts/hello")
        self.assertEqual(str(meta["date"]), "2026-01-02")

    def test_slug_override(self):
        self.assertEqual(derive_location("a.md", {"slug": "b"}), "b")


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.src = os.path.join(self.root, "site")
        self.out = os.path.join(self.root, "out")
        put(self.src, "hearth.json", '{"title": "Test", "base_url": "https://t.example/"}')
        put(self.src, "templates/page.html", "<h1>{{ page.title }}</h1>{{ content | safe }}<i>{{ site.title }}</i>")
        put(self.src, "templates/list.html", "{% for p in site.pages %}{{ p.title }};{% endfor %}")
        put(self.src, "content/index.md", "---\nlayout: list.html\ntitle: Home\n---\n")
        put(self.src, "content/about.md", "---\nlayout: page.html\n---\n# About us\n\nHello *there*.")
        put(self.src, "content/posts/2026-02-01-older.md", "---\nlayout: page.html\ntitle: Older\n---\nx")
        put(self.src, "content/posts/2026-03-01-newer.md", "---\nlayout: page.html\ntitle: Newer\n---\ny")
        put(self.src, "content/posts/2026-04-01-wip.md", "---\nlayout: page.html\ntitle: Wip\ndraft: true\n---\nz")
        put(self.src, "content/photo.txt", "raw")
        put(self.src, "static/css/a.css", "body{}")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_builds_pages_and_assets(self):
        result = build(self.src, self.out)
        self.assertEqual(result, {"pages": 4, "files": 2})
        self.assertIn("<h1>About us</h1><h1", read(self.out, "about/index.html"))
        self.assertIn("<em>there</em>", read(self.out, "about/index.html"))
        self.assertEqual(read(self.out, "photo.txt"), "raw")
        self.assertEqual(read(self.out, "css/a.css"), "body{}")

    def test_pages_sorted_newest_first_and_drafts_hidden(self):
        build(self.src, self.out)
        listing = read(self.out, "index.html")
        self.assertLess(listing.index("Newer"), listing.index("Older"))
        self.assertNotIn("Wip", listing)
        self.assertFalse(os.path.exists(os.path.join(self.out, "posts/wip/index.html")))

    def test_drafts_flag(self):
        build(self.src, self.out, include_drafts=True)
        self.assertIn("Wip", read(self.out, "index.html"))

    def test_title_taken_from_heading(self):
        build(self.src, self.out)
        self.assertIn("About us;", read(self.out, "index.html"))

    def test_sitemap_uses_base_url(self):
        build(self.src, self.out)
        sitemap = read(self.out, "sitemap.xml")
        self.assertIn("<loc>https://t.example/about/</loc>", sitemap)

    def test_rebuild_removes_stale_files(self):
        build(self.src, self.out)
        os.remove(os.path.join(self.src, "content", "about.md"))
        build(self.src, self.out)
        self.assertFalse(os.path.exists(os.path.join(self.out, "about")))

    def test_flat_urls(self):
        build(self.src, self.out, pretty=False)
        self.assertTrue(os.path.exists(os.path.join(self.out, "about.html")))

    def test_missing_content_dir(self):
        with self.assertRaises(BuildError):
            build(self.root, self.out)

    def test_refuses_to_clear_source(self):
        with self.assertRaises(BuildError):
            build(self.src, self.root)

    def test_duplicate_output_paths(self):
        put(self.src, "content/about/index.md", "x")
        put(self.src, "content/about/index.md", "---\nslug: index\n---\nx")
        put(self.src, "content/index2.md", "---\nslug: index\n---\ny")
        with self.assertRaises(BuildError):
            build(self.src, self.out)

    def test_bad_layout_is_reported(self):
        put(self.src, "content/bad.md", "---\nlayout: missing.html\n---\nx")
        with self.assertRaises(BuildError) as caught:
            build(self.src, self.out)
        self.assertIn("bad.md", str(caught.exception))

    def test_default_layout_fallback(self):
        shutil.rmtree(os.path.join(self.src, "templates"))
        put(self.src, "content/index.md", "# Hi")
        for name in ("about.md",):
            put(self.src, "content/" + name, "plain")
        os.remove(os.path.join(self.src, "content", "posts", "2026-02-01-older.md"))
        os.remove(os.path.join(self.src, "content", "posts", "2026-03-01-newer.md"))
        shutil.rmtree(os.path.join(self.src, "content", "posts"))
        build(self.src, self.out)
        self.assertIn("<title>Hi</title>", read(self.out, "index.html"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        put(self.root, "content/index.md", "# Hello")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_build_command(self):
        out = io.StringIO()
        self.assertEqual(main(["build", self.root], out), 0)
        self.assertIn("built 1 pages", out.getvalue())
        self.assertTrue(os.path.exists(os.path.join(self.root, "public", "index.html")))

    def test_error_exit_code(self):
        self.assertEqual(main(["build", os.path.join(self.root, "content")], io.StringIO()), 1)


if __name__ == "__main__":
    unittest.main()

