"""
public/data/graph.jsonld -> public/data/graph.json 변환 (② 단계, Cytoscape 전용 평면 뷰).

이 스크립트는 CSV를 직접 읽지 않는다 — CSV를 아는 코드는 build-jsonld.py(①)에만 있다.
graph.jsonld의 @graph 노드를 평평한 nodes/edges 배열로 펼치기만 한다.
graph.json의 형태(§4 예시)는 구버전과 동일하게 유지해서 프론트엔드(GraphCanvas.tsx 등) 코드는
수정할 필요가 없다.

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

WIKIBASE_HOST = "dictee-lod.wikibase.cloud"


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


def wikibase_url(equivalent: list) -> str | None:
    for entry in equivalent or []:
        eid = entry.get("id", "")
        if WIKIBASE_HOST in eid:
            return eid
    return None


def flatten_node(node: dict) -> dict:
    return {
        "id": node["@id"],
        "label_en": label_for(node.get("identified_by"), "en"),
        "label_ko": label_for(node.get("identified_by"), "ko"),
        "group": node.get("dictv:entityType", node.get("@type", "")),
        "description": (node.get("referred_to_by") or [{}])[0].get("content", ""),
        "evidenceType": node.get("dictv:evidenceType", ""),
        "pageReferences": node.get("dictv:pageReferences", ""),
        "chapters": node.get("dictv:isPartIn", []),
        "wikibaseUrl": wikibase_url(node.get("equivalent")),
    }


def extract_edges(node: dict, node_ids: set, logger: IssueLogger) -> list:
    edges = []
    subj_id = node["@id"]
    for key, value in node.items():
        if not key.startswith("dictv:") or not isinstance(value, list):
            continue
        predicate = key[len("dictv:"):]
        for entry in value:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            obj_id = entry["id"]
            if obj_id not in node_ids:
                logger.log(JSONLD_PATH.name, "-", "dictv:" + predicate, f"{subj_id} -> {obj_id}",
                           "매칭 실패 (dangling reference)",
                           f"'{obj_id}'에 해당하는 노드를 graph.jsonld의 @graph에서 찾을 수 없음",
                           "이 엣지를 그래프에서 스킵")
                continue
            edges.append({
                "source": subj_id,
                "target": obj_id,
                "predicate": predicate,
                "pageRef": entry.get("dictv:pageRef", ""),
                "note": entry.get("dictv:note", ""),
                "status": entry.get("dictv:status", ""),
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

    nodes = [flatten_node(n) for n in graph_nodes]
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

    n_with_qid = sum(1 for n in nodes if n["wikibaseUrl"])

    print("=" * 56)
    print("그래프 빌드 결과 요약 (build-graph-json.py, graph.jsonld 기반)")
    print("=" * 56)
    print(f"graph.jsonld 노드:       {len(graph_nodes)}건  ->  그래프 노드:  {len(nodes)}건  (100.0%)")
    print(f"  -> Wikibase QID 확보:  {n_with_qid}건  ({(n_with_qid / len(nodes) * 100) if nodes else 0:.1f}%)")
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
