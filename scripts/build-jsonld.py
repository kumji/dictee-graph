"""
CSV 3종(엔티티/관계/크로스워크) -> public/data/graph.jsonld 변환 (① 단계).

이 스크립트가 CSV를 직접 아는 유일한 코드다. ②(build-graph-json.py)는 이 스크립트의
산출물(graph.jsonld)만 읽는다.

data/property_schema_map.csv(P1~P18 predicate 도메인/레인지 스키마)는 아직 연구자가
제공하기 전이라 이 파일이 없어도 죽지 않게 만들어뒀다 — 없으면 도메인/레인지 검증만
건너뛰고(로그에 1건 기록), predicate는 원본 이름 그대로 dictv: 네임스페이스에 싣는다.
파일이 나중에 추가되면 자동으로 검증이 켜진다 (코드 수정 불필요).

실행: python3 scripts/build-jsonld.py
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
SCHEMA_CSV = DATA_DIR / "property_schema_map.csv"

CONTEXT = [
    "https://linked.art/ns/v1/linked-art.json",
    {
        "dict": "https://dictee-lod.wikibase.cloud/entity/",
        "dictv": "https://dictee-lod.wikibase.cloud/prop/direct/",
    },
]

# CLAUDE.md §4-1 폐기 목록: 새 JSON-LD에는 만들지 않는 predicate
DEPRECATED_PREDICATES = {"evidenceType", "channels"}


class IssueLogger:
    """매칭 실패·임의 처리·스키마 위반이 발생할 때마다 원본 위치와 상세 내용을 기록."""

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


def clean_label(label: str) -> str:
    return re.sub(r"\s*\(Q\d+\)\s*$", "", label or "").strip()


def extract_slug(uri: str) -> str:
    uri = (uri or "").strip()
    m = re.search(r"/id/(.+)$", uri)
    return m.group(1) if m else uri


def split_chapters(raw: str, source_file: str, row_number: int, logger: IssueLogger) -> list:
    raw = (raw or "").strip()
    if not raw or raw == "—":
        logger.log(source_file, row_number, "Chapter(s)", raw,
                   "Chapter 미기재", "값이 비어있거나 자리표시자(—)만 있음",
                   "빈 배열로 처리")
        return []
    if "→" in raw:
        logger.log(source_file, row_number, "Chapter(s)", raw,
                   "Chapter(s)에 특수 토큰(→) 존재",
                   "쉼표로 구분되는 일반 목록이 아니라 전이를 나타내는 표기로 보임 — 임의로 분리하지 않음",
                   "원문 문자열 그대로 단일 항목으로 보존")
        return [raw]
    return [c.strip() for c in raw.split(",") if c.strip()]


def load_property_schema(logger: IssueLogger) -> dict:
    """property_schema_map.csv -> {predicate: {Domain, Range, 상태, ...}}. 파일 없으면 빈 dict.

    파일 앞뒤에 제목/범례 같은 자유 서식 행이 섞여 있어서(연구자가 직접 정리한 문서),
    'P#'로 시작하는 실제 헤더 행을 찾아서 그 지점부터 'P\\d+' 패턴 행만 데이터로 읽는다.
    """
    if not SCHEMA_CSV.exists():
        logger.log(SCHEMA_CSV.name, 0, "-", "-",
                   "predicate 스키마 파일 없음",
                   "data/property_schema_map.csv가 아직 제공되지 않음 (연구자 작업 대기 중)",
                   "도메인/레인지 검증 및 '스키마 미정의 predicate' 로깅을 이번 실행에서는 생략 — "
                   "모든 predicate를 dictv: 네임스페이스에 원본 이름 그대로 기록. "
                   "파일이 추가되면 다음 실행부터 자동으로 검증됨")
        return {}

    with open(SCHEMA_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    header_idx = next((i for i, r in enumerate(rows) if r and r[0].strip() == "P#"), None)
    if header_idx is None:
        logger.log(SCHEMA_CSV.name, 0, "-", "-",
                   "predicate 스키마 파일 형식 인식 실패",
                   "'P#'로 시작하는 헤더 행을 찾지 못함",
                   "도메인/레인지 검증을 생략하고 스키마 없는 것으로 처리")
        return {}

    header = rows[header_idx]
    schema = {}
    for i, r in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not r or not re.match(r"^P\d+$", (r[0] or "").strip()):
            continue  # P# 패턴이 아니면 범례/빈 줄 등 -> 데이터 종료로 취급하고 스킵
        row = dict(zip(header, r + [""] * (len(header) - len(r))))
        prop = (row.get("Property") or "").strip()
        if prop:
            schema[prop] = row
    return schema


def load_entities(logger: IssueLogger, property_schema: dict):
    """dict:person/xxx -> JSON-LD 노드 dict. 실패한 행은 로그만 남기고 계속 진행."""
    nodes = {}
    entity_types = {}  # id -> 원본 Type 컬럼 값 (person/event/... 도메인 taxonomy, 색상/필터용)
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
                       "이 엔티티는 JSON-LD에서 제외")
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

        la_class = row.get("Linked Art Class", "").strip() or row["Type"]

        identified_by = []
        label_en = clean_label(row["prefLabel (en)"])
        label_ko = clean_label(row["prefLabel (ko)"])
        if label_en:
            identified_by.append({"type": "Name", "content": label_en, "language": "en"})
        if label_ko:
            identified_by.append({"type": "Name", "content": label_ko, "language": "ko"})

        node = {
            "@id": entity_id,
            "@type": la_class,
            "identified_by": identified_by,
            "dictv:entityType": row["Type"],  # 원본 도메인 taxonomy (그래프 뷰어 색상/필터용, @type과 별개)
        }

        primary_uri = row.get("Primary URI", "").strip()
        mapping_status = row.get("Mapping Status", "").strip()
        equivalent = []
        if primary_uri:
            if mapping_status in ("matched", "closeMatch"):
                equivalent.append({"id": primary_uri})
            else:
                logger.log(ENTITIES_CSV.name, i, "Primary URI/Mapping Status", primary_uri,
                           "Primary URI 있으나 Mapping Status 불충분",
                           f"Mapping Status='{mapping_status}' (matched/closeMatch 아님)",
                           "equivalent에 반영하지 않음")

        description = row.get("Definition / Scope Note", "")
        if description:
            node["referred_to_by"] = [{
                "type": "LinguisticObject",
                "content": description,
                "classified_as": "description",
            }]

        node["dictv:isPartIn"] = split_chapters(row.get("Chapter(s)", ""), ENTITIES_CSV.name, i, logger)
        if evidence_type:
            p8 = property_schema.get("evidenceType") if property_schema else None
            if p8 and (p8.get("Domain") or "").strip() not in ("", "Any") and row["Type"] != p8.get("Domain", "").strip():
                logger.log(ENTITIES_CSV.name, i, "Evidence Type", evidence_type,
                           "도메인 스키마 위반 (P8 evidenceType)",
                           f"property_schema_map.csv는 evidenceType(P8)의 Domain을 '{p8.get('Domain')}'로 정의하지만 "
                           f"이 엔티티의 Type='{row['Type']}'",
                           "막지 않고 그대로 반영 (연구자 판단 대기) — dictv:evidenceType 필드는 유지")
            node["dictv:evidenceType"] = evidence_type
        page_refs = row.get("Page References", "")
        if page_refs:
            node["dictv:pageReferences"] = page_refs

        node["_equivalent"] = equivalent  # 크로스워크 QID 병합 후 최종 equivalent로 확정 (merge_crosswalk 참고)
        nodes[entity_id] = node
        entity_types[entity_id] = row["Type"]

    return nodes, entity_types, total_rows


def merge_crosswalk(nodes: dict, logger: IssueLogger) -> int:
    """crosswalk CSV로 Wikibase QID를 equivalent에 병합."""
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
                nodes[entity_id]["_equivalent"].append(
                    {"id": f"https://dictee-lod.wikibase.cloud/wiki/Item:{qid}"}
                )
                n_with_qid += 1
            else:
                logger.log(CROSSWALK_CSV.name, i, "Wikibase QID", entity_id,
                           "QID 미확보", "이 엔티티는 아직 Wikibase에 매핑되지 않음",
                           "equivalent에 추가하지 않음, 프론트엔드에서 '미등록' 배지 표시")

    for node in nodes.values():
        eq = node.pop("_equivalent")
        if eq:
            node["equivalent"] = eq
    return n_with_qid


def load_relationships(nodes: dict, entity_types: dict, property_schema: dict, logger: IssueLogger):
    total_rows = 0
    n_schema_violations = 0
    n_undefined_predicates = 0
    if not RELATIONSHIPS_CSV.exists():
        return 0, 0, 0, 0

    with open(RELATIONSHIPS_CSV, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]

    deprecated = set(DEPRECATED_PREDICATES) | {
        prop for prop, row_ in property_schema.items()
        if (row_.get("상태") or "").strip().upper().startswith("DEPRECATED")
    }

    n_edges = 0
    for i, r in enumerate(rows, start=1):
        if i == 1 or not r or not any(c.strip() for c in r):
            continue
        total_rows += 1
        row = dict(zip(header, r + [""] * (len(header) - len(r))))

        raw_subj = row.get("subject_uri", "")
        raw_obj = row.get("object_uri", "")

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
                           "이 관계(행 전체)를 JSON-LD에서 스킵")
            continue

        predicate = row.get("relationship_property_uri", "").strip().split("/")[-1]
        if not predicate:
            logger.log(RELATIONSHIPS_CSV.name, i, "relationship_property_uri",
                       row.get("relationship_property_uri", ""),
                       "predicate 없음", "관계 유형을 알 수 없음", "이 관계를 JSON-LD에서 스킵")
            continue

        if predicate in deprecated:
            logger.log(RELATIONSHIPS_CSV.name, i, "relationship_property_uri", predicate,
                       "폐기된 predicate",
                       "property_schema_map.csv(또는 CLAUDE.md §4-1 기본 목록)에서 DEPRECATED로 표시됨",
                       "이 관계를 JSON-LD에서 스킵")
            continue

        if property_schema:
            schema_row = property_schema.get(predicate)
            if not schema_row:
                n_undefined_predicates += 1
                logger.log(RELATIONSHIPS_CSV.name, i, "relationship_property_uri", predicate,
                           "스키마 미정의 predicate",
                           "property_schema_map.csv의 공식 P1~P18 목록에 없는 predicate",
                           "버리지 않고 dictv: 네임스페이스에 그대로 기록 (연구자 검토 대기)")
            else:
                domain = (schema_row.get("Domain") or "").strip()
                range_ = (schema_row.get("Range") or "").strip()
                subj_type = entity_types.get(subj_id, "")
                obj_type = entity_types.get(obj_id, "")
                if domain and domain != "Any" and subj_type not in domain:
                    n_schema_violations += 1
                    logger.log(RELATIONSHIPS_CSV.name, i, "subject_uri", raw_subj,
                               "도메인/레인지 스키마 위반",
                               f"predicate '{predicate}'의 정의된 Domain='{domain}'이지만 실제 subject Type='{subj_type}'",
                               "막지 않고 그대로 반영 (연구자 판단 대기)")
                if range_ and range_ != "Any" and obj_type not in range_:
                    n_schema_violations += 1
                    logger.log(RELATIONSHIPS_CSV.name, i, "object_uri", raw_obj,
                               "도메인/레인지 스키마 위반",
                               f"predicate '{predicate}'의 정의된 Range='{range_}'이지만 실제 object Type='{obj_type}'",
                               "막지 않고 그대로 반영 (연구자 판단 대기)")

        key = f"dictv:{predicate}"
        entry = {"id": obj_id}
        if row.get("page_ref"):
            entry["dictv:pageRef"] = row["page_ref"]
        if row.get("note"):
            entry["dictv:note"] = row["note"]
        if row.get("STATUS"):
            entry["dictv:status"] = row["STATUS"]

        nodes[subj_id].setdefault(key, []).append(entry)
        n_edges += 1

    return total_rows, n_edges, n_schema_violations, n_undefined_predicates


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return

    logger = IssueLogger()

    property_schema = load_property_schema(logger)
    nodes, entity_types, n_entity_rows = load_entities(logger, property_schema)
    n_with_qid = merge_crosswalk(nodes, logger)
    n_rel_rows, n_edges, n_schema_violations, n_undefined = load_relationships(
        nodes, entity_types, property_schema, logger
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = {
        "@context": CONTEXT,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "@graph": list(nodes.values()),
    }
    out_path = OUT_DIR / "graph.jsonld"
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"build-jsonld-{timestamp}.log.csv"
    logger.write(log_path)

    n_nodes = len(nodes)
    entity_match_pct = (n_nodes / n_entity_rows * 100) if n_entity_rows else 0
    qid_pct = (n_with_qid / n_nodes * 100) if n_nodes else 0
    edge_match_pct = (n_edges / n_rel_rows * 100) if n_rel_rows else 0
    violation_pct = (n_schema_violations / n_rel_rows * 100) if n_rel_rows else 0
    undefined_pct = (n_undefined / n_rel_rows * 100) if n_rel_rows else 0

    print("=" * 56)
    print("JSON-LD 빌드 결과 요약 (build-jsonld.py)")
    print("=" * 56)
    print(f"엔티티 CSV 원본 행:        {n_entity_rows}건  ->  JSON-LD 노드:  {n_nodes}건  ({entity_match_pct:.1f}%)")
    print(f"Wikibase QID 확보:         {n_with_qid}건  ({qid_pct:.1f}%)")
    print("-" * 56)
    print(f"관계 CSV 원본 행:          {n_rel_rows}건  ->  JSON-LD 관계:  {n_edges}건  ({edge_match_pct:.1f}%)")
    if property_schema:
        print(f"  스키마 위반 (반영은 함):  {n_schema_violations}건  ({violation_pct:.1f}%)")
        print(f"  스키마 미정의 predicate:  {n_undefined}건  ({undefined_pct:.1f}%)")
    else:
        print("  스키마 검증:              건너뜀 (data/property_schema_map.csv 없음)")
    print("-" * 56)
    print(f"발생한 이슈 총 {len(logger.rows)}건 -> 상세 내용: {log_path.relative_to(ROOT)}")
    print("=" * 56)
    print(f"graph.jsonld 저장 완료: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
