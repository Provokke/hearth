import unittest
from datetime import date

from hearth import frontmatter


class FrontMatterTests(unittest.TestCase):
    def test_no_front_matter(self):
        meta, body = frontmatter.split("# Title\n\ntext")
        self.assertEqual(meta, {})
        self.assertEqual(body, "# Title\n\ntext")

    def test_scalars(self):
        meta, body = frontmatter.split(
            "---\ntitle: Hello there\ncount: 3\nratio: 1.5\ndraft: true\nwhen: 2026-05-01\n---\nbody"
        )
        self.assertEqual(meta["title"], "Hello there")
        self.assertEqual(meta["count"], 3)
        self.assertEqual(meta["ratio"], 1.5)
        self.assertIs(meta["draft"], True)
        self.assertEqual(meta["when"], date(2026, 5, 1))
        self.assertEqual(body, "body")

    def test_quoted_strings_keep_text(self):
        meta, _ = frontmatter.split('---\ntitle: "Yes: no"\nother: \'true\'\n---\n')
        self.assertEqual(meta["title"], "Yes: no")
        self.assertEqual(meta["other"], "true")

    def test_inline_list(self):
        meta, _ = frontmatter.split('---\ntags: [a, "b, c", 3]\nnone: []\n---\n')
        self.assertEqual(meta["tags"], ["a", "b, c", 3])
        self.assertEqual(meta["none"], [])

    def test_block_list(self):
        meta, _ = frontmatter.split("---\ntags:\n  - one\n  - two\nafter: x\n---\n")
        self.assertEqual(meta["tags"], ["one", "two"])
        self.assertEqual(meta["after"], "x")

    def test_empty_value_becomes_empty_string(self):
        meta, _ = frontmatter.split("---\nsubtitle:\ntitle: x\n---\n")
        self.assertEqual(meta["subtitle"], "")

    def test_comments_and_blank_lines(self):
        meta, _ = frontmatter.split("---\n# note\n\ntitle: x\n---\n")
        self.assertEqual(meta, {"title": "x"})

    def test_unclosed(self):
        with self.assertRaises(frontmatter.FrontMatterError):
            frontmatter.split("---\ntitle: x\nbody")

    def test_bad_line(self):
        with self.assertRaises(frontmatter.FrontMatterError):
            frontmatter.split("---\njust words\n---\n")


if __name__ == "__main__":
    unittest.main()
