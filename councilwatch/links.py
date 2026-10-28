"""Check that every internal link and asset reference in the built site resolves to a file."""
import html.parser
import os
import urllib.parse


class _Refs(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.refs.append(a[k])


def check(site_dir):
    pages, problems = {}, []
    for root, _, files in os.walk(site_dir):
        for n in files:
            if n.endswith(".html"):
                p = os.path.join(root, n)
                parser = _Refs()
                with open(p, encoding="utf-8") as f:
                    parser.feed(f.read())
                pages[os.path.normpath(p)] = parser
    for path, parser in pages.items():
        for ref in parser.refs:
            u = urllib.parse.urlsplit(ref)
            if u.scheme or u.netloc or ref.startswith("mailto:"):
                continue
            if ref.startswith("/"):
                problems.append(f"{path}: root-relative link {ref} breaks under a Pages base path")
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(path), urllib.parse.unquote(u.path))) if u.path else path
            if not os.path.exists(target):
                problems.append(f"{path}: {ref} -> missing {target}")
            elif u.fragment and target in pages and u.fragment not in pages[target].ids:
                problems.append(f"{path}: {ref} -> no #{u.fragment} in {target}")
    return len(pages), problems
