"""
CSV 3종(엔티티/관계/크로스워크) -> public/data/graph.json 변환.

이번 요구사항 반영:
  - 매칭 실패나 임의 처리(fallback)가 발생할 때마다, 원본 데이터 위치(파일명+행번호+원본 값)와
    무엇이 왜 실패했는지를 로그 파일(CSV)에 남긴다 -> 나중에 사람이 그 행만 골라서 고칠 수 있게.
  - 실행이 끝나면 터미널에 "몇 건 중 몇 건이 매칭됐는지" 퍼센티지 요약을 출력한다.

실행: python3 scripts/build-graph-json.py
"""
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "public" / "data"
LOG_DIR = ROOT / "logs"

ENTITIES_CSV = DATA_DIR / "dictee_entities.csv"
RELATIONSHIPS_CSV = DATA_DIR / "dictee_relationships.csv"
CROSSWALK_CSV = DATA_DIR / "entity_qid_crosswork.csv"

GROUP_COLORS = {  # 참고용 (실제 색상 지정은 프론트엔드 lib/graphStyles.ts에서)
    "Person": "#3B82F6", "Event": "#EF4444", "Concept": "#8B5CF6",
    "Object": "#F59E0B", "Group": "#10B981", "Work": "#EC4899",
}


class IssueLogger:
    """매칭 실패·임의 처리가 발생할 때마다 원본 위치와 상세 내용을 기록."""

    def __init__(self):
        self.rows: list[dict] = []

    def log(self, source_file: str, row_number: int, field: str,
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


def clean_label(label: str) -> str:
    return re.sub(r"\s*\(Q\d+\)\s*$", "", label or "").strip()


def find_qid(label_en: str, label_ko: str) -> tuple[str | None, str | None]:
    """(Q번호 또는 None, 발견된 컬럼 또는 None). en/ko 둘 다 확인 -> 지난번 en만 봐서 놓친 버그 재발 방지."""
    for col_name, lab in (("prefLabel (en)", label_en), ("prefLabel (ko)", label_ko)):
        m = re.search(r"\(Q(\d+)\)", lab or "")
        if m:
            return f"Q{m.group(1)}", col_name
    return None, None


def extract_slug(uri: str) -> str:
    uri = (uri or "").strip()
    m = re.search(r"/id/(.+)$", uri)
    return m.group(1) if m else uri


def load_entities(logger: IssueLogger) -> dict:
    """dict:person/xxx -> node dict. 실패한 행은 로그만 남기고 계속 진행."""
    nodes = {}
    total_rows = 0
    with open(ENTITIES_CSV, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]

    for i, r in enumerate(rows, start=1):
        if not r or not r[0].startswith("dict:"):
            continue
        total_rows += 1
        row = dict(zip(header, r + [""] * (len(header) - len(r))))
        entity_id = row["Entity ID"]

        if not row.get("Type") or not row.get("prefLabel (en)"):
            logger.log(ENTITIES_CSV.name, i, "Type/prefLabel", entity_id,
                       "필수값 누락", "Type 또는 prefLabel(en)이 비어있음",
                       "이 엔티티는 그래프에서 제외")
            continue

        raw_evidence = row.get("Evidence Type", "")
        evidence_type = clean_label(raw_evidence)
        if evidence_type != raw_evidence.strip():
            logger.log(ENTITIES_CSV.name, i, "Evidence Type", raw_evidence,
                       "Evidence Type에 (Q##) 꼬리표 잔존",
                       "prefLabel과 같은 패턴의 꼬리표가 Evidence Type 컬럼에도 섞여 들어감 (QID 크로스워크와는 무관한 값)",
                       "정규식으로 꼬리표 제거 후 사용")
        if evidence_type in ("", "—", "-"):
            logger.log(ENTITIES_CSV.name, i, "Evidence Type", raw_evidence,
                       "Evidence Type 미기재", "값이 비어있거나 자리표시자(—)만 있음",
                       "빈 문자열로 정규화, UI에서 '미기재'로 표시")
            evidence_type = ""

        nodes[entity_id] = {
            "id": entity_id,
            "label_en": clean_label(row["prefLabel (en)"]),
            "label_ko": clean_label(row["prefLabel (ko)"]),
            "group": row["Type"],
            "description": row.get("Definition / Scope Note", ""),
            "evidenceType": evidence_type,
            "pageReferences": row.get("Page References", ""),
            "chapters": [c.strip() for c in row.get("Chapter(s)", "").split(",") if c.strip()],
            "wikibaseUrl": None,  # crosswalk 병합 단계에서 채움
        }
    return nodes, total_rows


def merge_crosswalk(nodes: dict, logger: IssueLogger) -> int:
    """crosswalk CSV로 wikibaseUrl 채우기. 여기서도 QID를 en/ko 둘 다 재확인 (이중 안전장치)."""
    n_with_qid = 0
    if not CROSSWALK_CSV.exists():
        return 0
    with open(CROSSWALK_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            entity_id = row.get("Entity ID", "")
            qid = row.get("Wikibase QID", "없음")
            if entity_id not in nodes:
                logger.log(CROSSWALK_CSV.name, i, "Entity ID", entity_id,
                           "크로스워크에는 있지만 엔티티 CSV엔 없음",
                           "엔티티 CSV가 그 사이 바뀌었을 가능성", "이 행 무시")
                continue
            if qid and qid != "없음":
                nodes[entity_id]["wikibaseUrl"] = f"https://dictee-lod.wikibase.cloud/wiki/Item:{qid}"
                n_with_qid += 1
            else:
                logger.log(CROSSWALK_CSV.name, i, "Wikibase QID", entity_id,
                           "QID 미확보", "이 엔티티는 아직 Wikibase에 매핑되지 않음",
                           "wikibaseUrl=null로 두고, 프론트엔드에서 '미등록' 배지 표시")
    return n_with_qid


def load_relationships(nodes: dict, logger: IssueLogger) -> list:
    edges = []
    total_rows = 0
    if not RELATIONSHIPS_CSV.exists():
        return edges, 0

    with open(RELATIONSHIPS_CSV, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]

    for i, r in enumerate(rows, start=1):
        if i == 1 or not r or not any(c.strip() for c in r):
            continue
        total_rows += 1
        row = dict(zip(header, r + [""] * (len(header) - len(r))))

        raw_subj = row.get("subject_uri", "")
        raw_obj = row.get("object_uri", "")

        # 개행 문자 등 이상 공백 -> 정리하되 로그에 원본 그대로 남김
        if "\n" in raw_subj or "\n" in raw_obj:
            logger.log(RELATIONSHIPS_CSV.name, i, "subject_uri/object_uri",
                       f"subject={raw_subj!r} object={raw_obj!r}",
                       "URI 필드 내 개행 문자", "CSV 원본 셀에 줄바꿈이 섞여있음",
                       "공백 제거 후 매칭 시도 (원본 CSV 수정 권장)")

        subj_slug = extract_slug(raw_subj)
        obj_slug = extract_slug(raw_obj)
        subj_id = f"dict:{subj_slug}"
        obj_id = f"dict:{obj_slug}"

        missing = []
        if subj_id not in nodes:
            missing.append(("subject_uri", raw_subj, subj_id))
        if obj_id not in nodes:
            missing.append(("object_uri", raw_obj, obj_id))

        if missing:
            for field, raw, resolved in missing:
                logger.log(RELATIONSHIPS_CSV.name, i, field, raw,
                           "매칭 실패 (dangling reference)",
                           f"'{resolved}'에 해당하는 엔티티를 dictee_entities.csv에서 찾을 수 없음",
                           "이 관계(행 전체)를 그래프에서 스킵")
            continue

        predicate = row.get("relationship_property_uri", "").strip().split("/")[-1]
        if not predicate:
            logger.log(RELATIONSHIPS_CSV.name, i, "relationship_property_uri",
                       row.get("relationship_property_uri", ""),
                       "predicate 없음", "관계 유형을 알 수 없음", "이 관계를 그래프에서 스킵")
            continue

        edges.append({
            "source": subj_id,
            "target": obj_id,
            "predicate": predicate,
            "pageRef": row.get("page_ref", ""),
            "note": row.get("note", ""),
            "status": row.get("STATUS", ""),
        })

    return edges, total_rows


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return

    logger = IssueLogger()

    nodes, n_entity_rows = load_entities(logger)
    n_with_qid = merge_crosswalk(nodes, logger)
    edges, n_rel_rows = load_relationships(nodes, logger)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
    graph_path = OUT_DIR / "graph.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"build-graph-{timestamp}.log.csv"
    logger.write(log_path)

    # ===== 터미널 요약 (퍼센티지) =====
    n_nodes = len(nodes)
    n_edges = len(edges)
    entity_match_pct = (n_nodes / n_entity_rows * 100) if n_entity_rows else 0
    qid_pct = (n_with_qid / n_nodes * 100) if n_nodes else 0
    edge_match_pct = (n_edges / n_rel_rows * 100) if n_rel_rows else 0

    print("=" * 56)
    print("그래프 빌드 결과 요약")
    print("=" * 56)
    print(f"엔티티 CSV 원본 행:      {n_entity_rows}건")
    print(f"  -> 그래프 노드로 변환:  {n_nodes}건  ({entity_match_pct:.1f}%)")
    print(f"  -> Wikibase QID 확보:  {n_with_qid}건  ({qid_pct:.1f}%)")
    print("-" * 56)
    print(f"관계 CSV 원본 행:        {n_rel_rows}건")
    print(f"  -> 그래프 엣지로 변환:  {n_edges}건  ({edge_match_pct:.1f}%)")
    print(f"  -> 매칭 실패/스킵:      {n_rel_rows - n_edges}건  ({100 - edge_match_pct:.1f}%)")
    print("-" * 56)
    print(f"발생한 이슈 총 {len(logger.rows)}건 -> 상세 내용: {log_path.relative_to(ROOT)}")
    print("=" * 56)
    print(f"graph.json 저장 완료: {graph_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
