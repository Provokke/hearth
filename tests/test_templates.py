import unittest
from datetime import date

from hearth.templates import Environment, Safe, TemplateError


def render(source, **context):
    return Environment().render_string(source, context)


class VariableTests(unittest.TestCase):
    def test_plain_and_dotted(self):
        self.assertEqual(render("{{ a.b.c }}", a={"b": {"c": 5}}), "5")

    def test_list_index(self):
        self.assertEqual(render("{{ xs.1 }}", xs=["a", "b"]), "b")

    def test_missing_is_empty(self):
        self.assertEqual(render("[{{ nope }}][{{ a.b }}]", a={}), "[][]")

    def test_autoescape(self):
        self.assertEqual(render("{{ x }}", x="<b>&</b>"), "&lt;b&gt;&amp;&lt;/b&gt;")

    def test_safe_filter_and_safe_value(self):
        self.assertEqual(render("{{ x | safe }}", x="<b>"), "<b>")
        self.assertEqual(render("{{ x }}", x=Safe("<i>")), "<i>")

    def test_literals(self):
        self.assertEqual(render('{{ "hi" }} {{ 3 }} {{ true }}'), "hi 3 true")


class FilterTests(unittest.TestCase):
    def test_case_and_length(self):
        self.assertEqual(render("{{ x | upper }}{{ x | length }}", x="ab"), "AB2")

    def test_default(self):
        self.assertEqual(render('{{ x | default:"none" }}', x=""), "none")
        self.assertEqual(render('{{ x | default:"none" }}', x="set"), "set")

    def test_join(self):
        self.assertEqual(render('{{ xs | join:" / " }}', xs=["a", "b"]), "a / b")

    def test_date(self):
        self.assertEqual(render('{{ d | date:"%d/%m/%Y" }}', d=date(2026, 7, 4)), "04/07/2026")
        self.assertEqual(render("{{ d | date }}", d="2026-07-04"), "04 July 2026")

    def test_chained(self):
        self.assertEqual(render("{{ x | upper | length }}", x="abc"), "3")

    def test_unknown_filter(self):
        with self.assertRaises(TemplateError):
            render("{{ x | bogus }}", x=1)


class ControlTests(unittest.TestCase):
    def test_if_else(self):
        source = "{% if a %}yes{% else %}no{% endif %}"
        self.assertEqual(render(source, a=1), "yes")
        self.assertEqual(render(source, a=0), "no")

    def test_elif(self):
        source = "{% if n == 1 %}one{% elif n == 2 %}two{% else %}many{% endif %}"
        self.assertEqual([render(source, n=n) for n in (1, 2, 3)], ["one", "two", "many"])

    def test_not_and_or(self):
        self.assertEqual(render("{% if not a %}x{% endif %}", a=False), "x")
        self.assertEqual(render("{% if a and b %}x{% endif %}", a=1, b=0), "")
        self.assertEqual(render("{% if a or b %}x{% endif %}", a=0, b=1), "x")

    def test_comparison_with_strings(self):
        self.assertEqual(render('{% if s != "a" %}x{% endif %}', s="b"), "x")

    def test_for_with_loop(self):
        source = "{% for i in xs %}{{ loop.index }}{{ i }}{% if not loop.last %},{% endif %}{% endfor %}"
        self.assertEqual(render(source, xs=["a", "b", "c"]), "1a,2b,3c")

    def test_for_over_nothing(self):
        self.assertEqual(render("{% for i in xs %}x{% endfor %}", xs=None), "")

    def test_nested_for_does_not_leak(self):
        source = "{% for a in xs %}{% for b in ys %}{{ a }}{{ b }} {% endfor %}{% endfor %}{{ a }}"
        self.assertEqual(render(source, xs=[1, 2], ys=["x"]), "1x 2x ")

    def test_unclosed_if(self):
        with self.assertRaises(TemplateError):
            render("{% if a %}x")

    def test_unknown_tag(self):
        with self.assertRaises(TemplateError):
            render("{% wibble %}")


class InheritanceTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(sources={
            "base.html": "<{% block head %}base{% endblock %}|{% block body %}default{% endblock %}>",
            "child.html": '{% extends "base.html" %}{% block body %}child {{ name }}{% endblock %}',
            "grand.html": '{% extends "child.html" %}{% block head %}grand{% endblock %}',
            "part.html": "[{{ name }}]",
            "uses.html": '{% include "part.html" %}!',
        })

    def test_block_override(self):
        self.assertEqual(self.env.render("child.html", {"name": "x"}), "<base|child x>")

    def test_multi_level(self):
        self.assertEqual(self.env.render("grand.html", {"name": "y"}), "<grand|child y>")

    def test_include_shares_context(self):
        self.assertEqual(self.env.render("uses.html", {"name": "z"}), "[z]!")

    def test_missing_template(self):
        with self.assertRaises(TemplateError):
            self.env.render("absent.html", {})


if __name__ == "__main__":
    unittest.main()
