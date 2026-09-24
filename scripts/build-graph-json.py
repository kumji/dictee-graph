"""
public/data/graph.jsonld -> public/data/graph.json 변환 (② 단계, Cytoscape 전용 평면 뷰).

이 스크립트는 CSV를 직접 읽지 않는다 — CSV를 아는 코드는 build-jsonld.py(①)에만 있다.
graph.jsonld의 @graph 노드를 평평한 nodes/edges 배열로 펼치기만 한다.

실행: python3 scripts/build-jsonld.py 를 먼저 실행한 뒤 -> python3 scripts/build-graph-json.py
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "public" / "data"
LOG_DIR = ROOT / "logs"

JSONLD_PATH = OUT_DIR / "graph.jsonld"

# 노드 속성으로 이미 처리되는 키들 — dict:{predicate} 등 나머지 list 필드는 전부 엣지로 취급한다
# (①이 predicate를 property_schema_map.csv의 실제 네임스페이스(dict:/skos:/schema:/dct:)로
#  기록하므로, "dict:"로 시작하는 키만 보는 게 아니라 알려진 속성 키를 제외한 나머지를 엣지로 본다)
NON_EDGE_KEYS = {
    "@id", "@type", "identified_by", "referred_to_by",
    "dictrel:entityType", "dictrel:documentedIn",
    "equivalent", "skos:closeMatch", "dict:evidenceType",
}


class IssueLogger:
    def __init__(self):
        self.rows: list[dict] = []

    def log(self, source_file: str, row_number, field: str,
            raw_value: str, issue_type: str, detail: str, action_taken: str):
        self.rows.append({
            "source_file": source_file,
            "row_number": row_number,
            "field": field,
            "raw_value": raw_value,
            "issue_type": issue_type,
            "detail": detail,
            "action_taken": action_taken,
        })

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["source_file", "row_number", "field", "raw_value",
                      "issue_type", "detail", "action_taken"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)


def label_for(identified_by: list, lang: str) -> str:
    for entry in identified_by or []:
        if entry.get("language") == lang:
            return entry.get("content", "")
    return ""


def equivalent_uri(equivalent: list) -> str | None:
    for entry in equivalent or []:
        eid = entry.get("id", "")
        if eid:
            return eid
    return None


def uri_list(field: list, node_ids: set) -> list:
    """skos:broader/closeMatch 값 중 내부 엔티티가 아니라 진짜 외부 어휘 URI만 남긴다.

    skos:broader는 엔티티 CSV의 broader URI 컬럼(항상 외부 URI)뿐 아니라 관계 CSV의
    predicate로도 쓰일 수 있어(Concept -> Concept), 내부 엔티티를 가리키는 경우가 섞여 있다.
    내부를 가리키는 값은 extract_edges에서 그래프 엣지로 처리하므로 여기서는 제외한다.
    """
    return [e.get("id") for e in (field or []) if e.get("id") and e["id"] not in node_ids]


def flatten_node(node: dict, node_ids: set) -> dict:
    return {
        "id": node["@id"],
        "label_en": label_for(node.get("identified_by"), "en"),
        "label_ko": label_for(node.get("identified_by"), "ko"),
        "group": node.get("dictrel:entityType", node.get("@type", "")),
        "description": (node.get("referred_to_by") or [{}])[0].get("content", ""),
        "evidenceType": node.get("dict:evidenceType", ""),
        "equivalentUri": equivalent_uri(node.get("equivalent")),
        "broader": uri_list(node.get("skos:broader"), node_ids),
        "closeMatch": uri_list(node.get("skos:closeMatch"), node_ids),
        "documentedIn": node.get("dictrel:documentedIn", []),
    }


def extract_edges(node: dict, node_ids: set, logger: IssueLogger) -> list:
    """엔티티 노드의 predicate-키 list 필드들을 엣지로 펼친다.

    skos:broader는 특별 취급: 내부 엔티티(Concept -> Concept)를 가리키면 엣지로 만들고,
    외부 어휘 URI를 가리키면 flatten_node의 'broader' 표시 필드 몫이므로 조용히 건너뛴다
    (외부 URI를 dangling reference로 잘못 로깅하지 않도록 dangling 체크 이전에 분리).
    """
    edges = []
    subj_id = node["@id"]
    for key, value in node.items():
        if key in NON_EDGE_KEYS or not isinstance(value, list):
            continue
        predicate = key.split(":", 1)[-1]
        for entry in value:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            obj_id = entry["id"]
            if key == "skos:broader" and obj_id not in node_ids:
                continue  # 외부 어휘 URI — flatten_node의 broader 필드에서 이미 표시됨
            if obj_id not in node_ids:
                logger.log(JSONLD_PATH.name, "-", key, f"{subj_id} -> {obj_id}",
                           "매칭 실패 (dangling reference)",
                           f"'{obj_id}'에 해당하는 노드를 graph.jsonld의 @graph에서 찾을 수 없음",
                           "이 엣지를 그래프에서 스킵")
                continue
            edges.append({
                "source": subj_id,
                "target": obj_id,
                "predicate": predicate,
                "documentedIn": entry.get("dictrel:documentedIn", []),
                "schemaViolation": bool(entry.get("dictrel:schemaViolation", False)),
            })
    return edges


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return

    if not JSONLD_PATH.exists():
        print(f"오류: {JSONLD_PATH.relative_to(ROOT)}가 없습니다. 먼저 실행하세요: python3 scripts/build-jsonld.py")
        sys.exit(1)

    logger = IssueLogger()
    jsonld = json.loads(JSONLD_PATH.read_text(encoding="utf-8"))
    graph_nodes = jsonld.get("@graph", [])
    node_ids = {n["@id"] for n in graph_nodes}

    nodes = [flatten_node(n, node_ids) for n in graph_nodes]
    edges = []
    for n in graph_nodes:
        edges.extend(extract_edges(n, node_ids, logger))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
    }
    graph_path = OUT_DIR / "graph.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"build-graph-{timestamp}.log.csv"
    logger.write(log_path)

    n_with_equivalent = sum(1 for n in nodes if n["equivalentUri"])

    print("=" * 56)
    print("그래프 빌드 결과 요약 (build-graph-json.py, graph.jsonld 기반)")
    print("=" * 56)
    print(f"graph.jsonld 노드:       {len(graph_nodes)}건  ->  그래프 노드:  {len(nodes)}건  (100.0%)")
    print(f"  -> 외부 URI 매핑:      {n_with_equivalent}건  ({(n_with_equivalent / len(nodes) * 100) if nodes else 0:.1f}%)")
    print("-" * 56)
    print(f"  -> 그래프 엣지:        {len(edges)}건")
    if logger.rows:
        print(f"  -> 매칭 실패/스킵:      {len(logger.rows)}건")
    print("-" * 56)
    if logger.rows:
        print(f"발생한 이슈 총 {len(logger.rows)}건 -> 상세 내용: {log_path.relative_to(ROOT)}")
    else:
        print("발생한 이슈 없음")
    print("=" * 56)
    print(f"graph.json 저장 완료: {graph_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
