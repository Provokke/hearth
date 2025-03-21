import argparse
import os
import sys

from . import __version__
from .frontmatter import FrontMatterError
from .site import BuildError, build
from .templates import TemplateError


def build_parser():
    parser = argparse.ArgumentParser(prog="hearth", description="A small static site generator")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build", help="build a site")
    command.add_argument("source", nargs="?", default=".", help="site directory (default: current)")
    command.add_argument("-o", "--output", default=None, help="output directory (default: <source>/public)")
    command.add_argument("--drafts", action="store_true", help="include pages marked draft")
    command.add_argument("--flat", action="store_true", help="write about.html instead of about/index.html")
    return parser


def main(argv=None, out=sys.stdout):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    output = args.output or os.path.join(args.source, "public")
    try:
        result = build(args.source, output, include_drafts=args.drafts, pretty=not args.flat)
    except (BuildError, FrontMatterError, TemplateError) as error:
        print(f"hearth: {error}", file=sys.stderr)
        return 1
    print(f"built {result['pages']} pages and copied {result['files']} files to {output}", file=out)
    return 0
