"""Save a trimmed live response as a test fixture. Usage: grab_fixture.py NAME URL [--post JSON] [--keep N] [--path a.b]

Fixtures hold at most a few rows and no description text, so tests stay small and offline.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobalfred_index.polite import Client

DROP = {"description", "descriptionPlain", "descriptionHtml", "content", "job_description", "basic_qualifications",
        "preferred_qualifications", "additional", "additionalPlain", "lists", "contents", "jobDescriptions", "excerpt",
        "description_html", "descriptionBody", "requirements", "benefits", "responsibilities", "jobPostingDescription"}

def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in DROP}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o

def main():
    name, url = sys.argv[1], sys.argv[2]
    post = None; keep = 3; path = None
    a = sys.argv[3:]
    while a:
        f = a.pop(0)
        if f == "--post": post = json.loads(a.pop(0))
        elif f == "--keep": keep = int(a.pop(0))
        elif f == "--path": path = a.pop(0)
    c = Client(default_gap=0.2)
    r = c.post(url, json=post) if post is not None else c.get(url)
    print(name, r.status, len(r.content), r.reason)
    if not r.ok:
        return
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / name
    ct = r.headers.get("content-type", "")
    txt = r.text
    if txt.lstrip()[:1] in "[{" :
        d = json.loads(txt)
        def trim(x):
            if isinstance(x, list):
                return [trim(v) for v in x[:keep]]
            if isinstance(x, dict):
                return {k: trim(v) for k, v in x.items()}
            return x
        d = strip(d)
        d = trim(d)
        out.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    else:
        # XML / RSS: keep the first N repeated item blocks, drop long text nodes
        for tag in ("item", "position", "job"):
            blocks = re.findall(rf"<{tag}[ >].*?</{tag}>", txt, re.S)
            if blocks:
                head = txt[: txt.index(blocks[0])]
                tail = txt[txt.rindex(blocks[-1]) + len(blocks[-1]):]
                body = "\n".join(blocks[:keep])
                txt = head + body + tail
                break
        txt = re.sub(r"<(description|jobDescriptions|content:encoded)[^>]*>.*?</\1>", r"<\1></\1>", txt, flags=re.S)
        out.write_text(txt)
    print("saved", out, out.stat().st_size)

main()
