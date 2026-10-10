"""
public/data/graph.jsonld + vocab.jsonld -> 엔티티·predicate URI 페이지 생성 (③ 단계).

모든 엔티티 @id(dict:person/cha-theresa)와 연구용 predicate(dictrel:prefigures)가 실제로 열리는
주소가 되도록, GitHub Pages가 그대로 서빙할 정적 페이지를 public/ 아래에 만든다:

  public/entity/{type}/{slug}/index.html   사람용 페이지 (같은 내용의 JSON-LD를 <script>로 내장)
  public/entity/{type}/{slug}/index.jsonld 기계용 JSON-LD
  public/prop/{name}/index.html|.jsonld    predicate 정의 + 실제 사용 사례
  public/entity/index.html, public/prop/index.html  목록

이 스크립트도 CSV를 읽지 않는다 — ①의 산출물만 읽는다. 실행할 때마다 entity/, prop/를 지우고
다시 만들므로, CSV에서 삭제된 엔티티의 페이지는 자동으로 사라진다.

실행: build-jsonld.py -> build-graph-json.py -> python3 scripts/build-pages.py
"""
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
DATA_DIR = PUBLIC / "data"
GRAPH_PATH = DATA_DIR / "graph.jsonld"
VOCAB_PATH = DATA_DIR / "vocab.jsonld"

# 노드 속성으로 표시하는 키 — 나머지 list 필드는 관계(엣지)로 본다 (build-graph-json.py와 같은 규칙)
NON_EDGE_KEYS = {
    "@id", "@type", "identified_by", "referred_to_by",
    "dictrel:entityType", "dictrel:documentedIn",
    "equivalent", "skos:closeMatch", "dictrel:evidenceType", "classified_as",
}

STYLE = """
:root { --bg:#ffffff; --fg:#111827; --muted:#6b7280; --line:#e5e7eb; --link:#2563eb; --chip:#f3f4f6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111827; --fg:#f3f4f6; --muted:#9ca3af; --line:#374151; --link:#93c5fd; --chip:#1f2937; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 32px 16px 64px; }
nav { font-size: 13px; color: var(--muted); margin-bottom: 24px; }
nav a { margin-right: 12px; }
a { color: var(--link); text-decoration: none; word-break: break-all; }
a:hover { text-decoration: underline; }
h1 { font-size: 26px; margin: 0; line-height: 1.3; }
.sub { color: var(--muted); font-size: 17px; margin: 2px 0 12px; }
.chip { display:inline-block; background:var(--chip); border-radius:999px; padding:1px 10px; font-size:12px; margin-right:6px; }
code { font-size: 13px; word-break: break-all; }
h2 { font-size: 15px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1px solid var(--line); }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
td, th { text-align: left; vertical-align: top; padding: 6px 8px 6px 0; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 500; width: 34%; }
ul { padding-left: 18px; margin: 4px 0; }
.muted { color: var(--muted); }
"""


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def label_for(node: dict, lang: str) -> str:
    for entry in node.get("identified_by") or []:
        if entry.get("language") == lang:
            return entry.get("content", "")
    return ""


class Site:
    def __init__(self, context: list, nodes: list[dict], vocab: list[dict]):
        self.context = context
        self.prefixes = next((c for c in context if isinstance(c, dict)), {})
        self.nodes = {n["@id"]: n for n in nodes}
        self.vocab = {v["@id"]: v for v in vocab}

    def expand(self, curie: str) -> str:
        prefix, _, local = curie.partition(":")
        if prefix in self.prefixes and not local.startswith("//"):
            return self.prefixes[prefix] + local
        return curie

    @staticmethod
    def local_path(curie: str) -> str:
        """dict:person/cha-theresa -> person/cha-theresa, dictrel:prefigures -> prefigures"""
        return curie.split(":", 1)[1]

    def entity_href(self, eid: str, root: str) -> str:
        return f"{root}entity/{self.local_path(eid)}/"

    def prop_href(self, key: str, root: str) -> str:
        """연구용 predicate는 우리 prop 페이지로, 표준 어휘는 원 기관의 정의 URI로."""
        if key.startswith("dictrel:"):
            return f"{root}prop/{self.local_path(key)}/"
        return self.expand(key)

    def node_label(self, eid: str) -> str:
        n = self.nodes.get(eid)
        if not n:
            return eid
        en, ko = label_for(n, "en"), label_for(n, "ko")
        return f"{en} · {ko}" if en and ko else (en or ko or eid)

    def entity_link(self, eid: str, root: str) -> str:
        if eid in self.nodes:
            return f'<a href="{self.entity_href(eid, root)}">{esc(self.node_label(eid))}</a>'
        return f'<a href="{esc(eid)}">{esc(eid)}</a>'

    def prop_link(self, key: str, root: str) -> str:
        return f'<a href="{esc(self.prop_href(key, root))}"><code>{esc(key)}</code></a>'

    def relations(self):
        """(subject_id, key, object_id) — 내부 엔티티를 가리키는 관계만."""
        for sid, n in self.nodes.items():
            for key, value in n.items():
                if key in NON_EDGE_KEYS or not isinstance(value, list):
                    continue
                for entry in value:
                    if isinstance(entry, dict) and entry.get("id") in self.nodes:
                        yield sid, key, entry["id"]


def page(title: str, root: str, body: str, jsonld: dict | None) -> str:
    script = ""
    alt = ""
    if jsonld is not None:
        data = json.dumps(jsonld, ensure_ascii=False, indent=2).replace("</", "<\\/")
        script = f'<script type="application/ld+json">\n{data}\n</script>'
        alt = '<link rel="alternate" type="application/ld+json" href="index.jsonld">'
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{alt}
<style>{STYLE}</style>
{script}
</head>
<body><main>
<nav><a href="{root}">그래프 뷰어</a><a href="{root}entity/">전체 엔티티</a><a href="{root}prop/">전체 predicate</a></nav>
{body}
</main></body>
</html>
"""


def link_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_entity_page(site: Site, eid: str, incoming: list, root: str) -> str:
    n = site.nodes[eid]
    en, ko = label_for(n, "en"), label_for(n, "ko")
    rows = []
    if n.get("dictrel:evidenceType"):
        rows.append(("Evidence Type", esc(n["dictrel:evidenceType"])))
    if n.get("dictrel:documentedIn"):
        rows.append(("Documented in", esc(", ".join(n["dictrel:documentedIn"]))))
    for e in n.get("equivalent") or []:
        rows.append(("Equivalent", f'<a href="{esc(e["id"])}">{esc(e["id"])}</a>'))
    broader = [site.entity_link(e["id"], root) for e in n.get("skos:broader") or []]
    if broader:
        rows.append(("Broader", link_list(broader)))
    classified = [f'<a href="{esc(e["id"])}">{esc(e["id"])}</a>' for e in n.get("classified_as") or []]
    if classified:
        rows.append(("Classified as", link_list(classified)))
    close = [f'<a href="{esc(e["id"])}">{esc(e["id"])}</a>' for e in n.get("skos:closeMatch") or []]
    if close:
        rows.append(("Close match", link_list(close)))
    table = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)

    desc = (n.get("referred_to_by") or [{}])[0].get("content", "")
    outgoing = [f"{site.prop_link(k, root)} → {site.entity_link(o, root)}"
                for _, k, o in site.relations_by_subject.get(eid, [])]
    incoming_items = [f"{site.entity_link(s, root)} → {site.prop_link(k, root)}" for s, k, _ in incoming]

    body = f"""
<h1>{esc(en or ko or eid)}</h1>
{f'<p class="sub">{esc(ko)}</p>' if en and ko else ''}
<p><span class="chip">{esc(n.get("dictrel:entityType", ""))}</span><span class="chip">{esc(n.get("@type", ""))}</span></p>
<p class="muted">URI <code>{esc(site.expand(eid))}</code> · <a href="index.jsonld">JSON-LD</a></p>
{f'<p>{esc(desc)}</p>' if desc else ''}
{f'<table>{table}</table>' if table else ''}
{f'<h2>이 엔티티에서 나가는 관계 ({len(outgoing)})</h2>' + link_list(outgoing) if outgoing else ''}
{f'<h2>이 엔티티로 들어오는 관계 ({len(incoming_items)})</h2>' + link_list(incoming_items) if incoming_items else ''}
"""
    return page(f"{en or ko or eid} — Dictée LOD", root, body, {"@context": site.context, **n})


def build_prop_page(site: Site, key: str, uses: list, root: str) -> str:
    v = site.vocab[key]
    items = [f"{site.entity_link(s, root)} → {site.entity_link(o, root)}" for s, _, o in uses]
    body = f"""
<h1>{esc(v.get("rdfs:label", key))}</h1>
<p><span class="chip">rdf:Property</span></p>
<p class="muted">URI <code>{esc(site.expand(key))}</code> · <a href="index.jsonld">JSON-LD</a></p>
<p>{esc(v.get("rdfs:comment", ""))}</p>
{f'<h2>사용 사례 ({len(items)})</h2>' + link_list(items) if items else '<p class="muted">그래프의 엔티티 간 관계로는 아직 쓰이지 않음 (엔티티 속성으로만 쓰이거나 미사용).</p>'}
"""
    return page(f"{v.get('rdfs:label', key)} — Dictée LOD predicate", root, body, {"@context": site.context, **v})


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return
    for p in (GRAPH_PATH, VOCAB_PATH):
        if not p.exists():
            print(f"오류: {p.relative_to(ROOT)}가 없습니다. 먼저 실행하세요: python3 scripts/build-jsonld.py")
            sys.exit(1)

    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    site = Site(graph["@context"], graph.get("@graph", []), vocab.get("@graph", []))

    rels = list(site.relations())
    site.relations_by_subject = {}
    incoming: dict[str, list] = {}
    uses: dict[str, list] = {}
    for s, k, o in rels:
        site.relations_by_subject.setdefault(s, []).append((s, k, o))
        incoming.setdefault(o, []).append((s, k, o))
        uses.setdefault(k, []).append((s, k, o))

    for d in ("entity", "prop"):
        shutil.rmtree(PUBLIC / d, ignore_errors=True)

    # 엔티티 페이지: public/entity/{type}/{slug}/ — 깊이 3이라 사이트 루트는 ../../../
    for eid, n in site.nodes.items():
        local = site.local_path(eid)
        out = PUBLIC / "entity" / local
        root = "../" * (local.count("/") + 2)
        write(out / "index.html", build_entity_page(site, eid, incoming.get(eid, []), root))
        write(out / "index.jsonld", json.dumps({"@context": site.context, **n}, ensure_ascii=False, indent=2))

    for key, v in site.vocab.items():
        local = site.local_path(key)
        out = PUBLIC / "prop" / local
        root = "../" * (local.count("/") + 2)
        write(out / "index.html", build_prop_page(site, key, uses.get(key, []), root))
        write(out / "index.jsonld", json.dumps({"@context": site.context, **v}, ensure_ascii=False, indent=2))

    # 목록 페이지
    by_type: dict[str, list] = {}
    for eid, n in sorted(site.nodes.items(), key=lambda kv: site.node_label(kv[0]).lower()):
        by_type.setdefault(n.get("dictrel:entityType", "기타"), []).append(eid)
    body = "<h1>전체 엔티티</h1>" + "".join(
        f"<h2>{esc(t)} ({len(ids)})</h2>" + link_list([site.entity_link(i, '../') for i in ids])
        for t, ids in sorted(by_type.items())
    )
    write(PUBLIC / "entity" / "index.html", page("전체 엔티티 — Dictée LOD", "../", body, None))

    prop_items = [f'{site.prop_link(k, "../")} <span class="muted">— 사용 {len(uses.get(k, []))}건</span>'
                  for k in sorted(site.vocab)]
    body = "<h1>전체 predicate</h1><p class=\"muted\">이 프로젝트가 정의한 연구용 predicate. " \
           "표준 어휘(SKOS, Schema.org, Dublin Core)는 각 기관의 정의를 따른다.</p>" + link_list(prop_items)
    write(PUBLIC / "prop" / "index.html", page("전체 predicate — Dictée LOD", "../", body, None))

    print("=" * 56)
    print("URI 페이지 생성 결과 (build-pages.py)")
    print("=" * 56)
    print(f"엔티티 페이지:   {len(site.nodes)}건  -> public/entity/")
    print(f"predicate 페이지: {len(site.vocab)}건  -> public/prop/")
    print(f"기준 URI:        {site.prefixes.get('dict', '?')} , {site.prefixes.get('dictrel', '?')}")
    print("=" * 56)


if __name__ == "__main__":
    main()
