import unittest

from hearth import markdown
from hearth.markdown import render, render_inline, slugify, first_paragraph


class InlineTests(unittest.TestCase):
    def test_emphasis_and_strong(self):
        self.assertEqual(render_inline("a *b* and **c**"), "a <em>b</em> and <strong>c</strong>")

    def test_underscores_inside_words_are_left(self):
        self.assertEqual(render_inline("snake_case_name"), "snake_case_name")

    def test_code_span_is_escaped_and_protected(self):
        self.assertEqual(render_inline("`a <b> *c*`"), "<code>a &lt;b&gt; *c*</code>")

    def test_link_and_image(self):
        self.assertEqual(render_inline("[x](http://a.b/?q=1&r=2)"), '<a href="http://a.b/?q=1&amp;r=2">x</a>')
        self.assertEqual(render_inline("![alt](pic.png)"), '<img src="pic.png" alt="alt">')

    def test_html_is_escaped(self):
        self.assertEqual(render_inline("<script>x</script>"), "&lt;script&gt;x&lt;/script&gt;")

    def test_backslash_escape(self):
        self.assertEqual(render_inline(r"\*not em\*"), "*not em*")

    def test_strikethrough_and_autolink(self):
        self.assertEqual(render_inline("~~gone~~"), "<del>gone</del>")
        self.assertEqual(render_inline("<https://x.org>"), '<a href="https://x.org">https://x.org</a>')

    def test_hard_break(self):
        self.assertIn("<br>", render_inline("one  \ntwo"))


class BlockTests(unittest.TestCase):
    def test_headings_get_ids(self):
        self.assertEqual(render("## Hello World"), '<h2 id="hello-world">Hello World</h2>')

    def test_duplicate_heading_ids_are_unique(self):
        out = render("# Same\n\n# Same")
        self.assertIn('id="same"', out)
        self.assertIn('id="same-1"', out)

    def test_paragraphs(self):
        self.assertEqual(render("one\ntwo\n\nthree"), "<p>one\ntwo</p>\n<p>three</p>")

    def test_unordered_list(self):
        self.assertEqual(render("- a\n- b"), "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")

    def test_ordered_list(self):
        self.assertEqual(render("1. a\n2. b"), "<ol>\n<li>a</li>\n<li>b</li>\n</ol>")

    def test_nested_list(self):
        out = render("- a\n  - b\n- c")
        self.assertIn("<li>a\n<ul>\n<li>b</li>\n</ul></li>", out)
        self.assertIn("<li>c</li>", out)

    def test_code_fence_keeps_markup_literal(self):
        out = render("```html\n<b>*x*</b>\n```")
        self.assertEqual(out, '<pre><code class="language-html">&lt;b&gt;*x*&lt;/b&gt;\n</code></pre>')

    def test_blockquote(self):
        out = render("> quoted *text*\n> more")
        self.assertTrue(out.startswith("<blockquote>"))
        self.assertIn("<em>text</em>", out)

    def test_rule(self):
        self.assertEqual(render("above\n\n---\n\nbelow"), "<p>above</p>\n<hr>\n<p>below</p>")

    def test_paragraph_stops_at_list(self):
        out = render("intro\n- item")
        self.assertIn("<p>intro</p>", out)
        self.assertIn("<ul>", out)

    def test_windows_newlines(self):
        self.assertEqual(render("a\r\n\r\nb"), "<p>a</p>\n<p>b</p>")


class HelperTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Hello, World! It's 5pm"), "hello-world-its-5pm")

    def test_first_paragraph_skips_headings_and_strips_markup(self):
        self.assertEqual(first_paragraph("# Title\n\nSome *bold* words."), "Some bold words.")

    def test_first_paragraph_truncates(self):
        out = first_paragraph("word " * 100, limit=20)
        self.assertLessEqual(len(out), 20)
        self.assertTrue(out.endswith("…"))


if __name__ == "__main__":
    unittest.main()
