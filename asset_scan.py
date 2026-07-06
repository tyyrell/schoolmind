import glob
import os
import re
roots = [
    "schoolmind/templates",
    "schoolmind/static/css",
    "schoolmind/static/js",
]
scan_exts = (".html", ".css", ".js", ".jinja", ".j2")
asset_exts = ("png", "jpg", "jpeg", "webp", "avif", "svg")
pattern = re.compile(
    r"""(?:
        (?:src|href)\s*=\s*[\"'][^\"']+\.(?:%s)[^\"']*[\"']
        |
        url\([\"']?[^\"')]+\.(?:%s)[^\"')]*[\"']?\)
        |
        [\"'][^\"']+\.(?:%s)[^\"']*[\"']
    )""" % ("|".join(asset_exts), "|".join(asset_exts), "|".join(asset_exts)),
    re.IGNORECASE | re.VERBOSE)
refs = set()
for root in roots:
    if not os.path.exists(root):
        continue
    for path in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if not os.path.isfile(path):
            continue
        if not path.lower().endswith(scan_exts):
            continue
        try:
            text = open(path, "r", encoding="utf-8").read()
        except UnicodeDecodeError:
            try:
                text = open(path, "r", encoding="latin-1").read()
            except Exception:
                continue
        except Exception:
            continue
        matches = pattern.findall(text)
        for match in pattern.finditer(text):
            refs.add(f"{path} :: {match.group(0)}")
print("FOUND_REFS", len(refs))
for ref in sorted(refs):
    print(ref)
