"""
config/works.yaml에 등록된 작품들의 CSV -> public/data/graph.jsonld 변환 (① 단계).

이 스크립트가 CSV를 직접 아는 유일한 코드다. ②(build-graph-json.py)는 이 스크립트의
산출물(graph.jsonld)만 읽는다.

다중 작품 대응 (CLAUDE.md §4-0): config/works.yaml에 등록된 작품들을 순회하며 엔티티를
하나의 마스터 목록으로 병합한다(reconciliation). 지금은 작품이 dictee 1개뿐이라 병합 경로가
실제로 실행되지는 않지만, 두 번째 작품이 추가돼도 이 스크립트는 수정할 필요가 없다.

data/property_schema_map.csv(공식 predicate 스키마, 모든 작품이 공유)가 아직 없어도 죽지
않게 만들어뒀다 — 없으면 도메인/레인지 검증만 건너뛰고(로그에 1건 기록), predicate는 원본
이름 그대로 dict: 네임스페이스에 싣는다. 파일이 나중에 추가되면 자동으로 검증이 켜진다.

실행: python3 scripts/build-jsonld.py
"""
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "public" / "data"
LOG_DIR = ROOT / "logs"

WORKS_YAML = ROOT / "config" / "works.yaml"
SCHEMA_CSV = ROOT / "data" / "property_schema_map.csv"

CONTEXT = [
    "https://linked.art/ns/v1/linked-art.json",
    {
        "dict": "https://dictee-lod.wikibase.cloud/entity/",
        "dictrel": "https://dictee-lod.wikibase.cloud/prop/direct/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "schema": "https://schema.org/",
        "dct": "http://purl.org/dc/terms/",
    },
]


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


def load_works(logger: IssueLogger) -> list[dict]:
    if not WORKS_YAML.exists():
        print(f"오류: {WORKS_YAML.relative_to(ROOT)}가 없습니다. 작품을 최소 1개 등록해야 합니다.")
        sys.exit(1)
    config = yaml.safe_load(WORKS_YAML.read_text(encoding="utf-8")) or {}
    works = config.get("works") or []
    if not works:
        print(f"오류: {WORKS_YAML.relative_to(ROOT)}에 등록된 작품이 없습니다.")
        sys.exit(1)
    return works


def load_property_schema(logger: IssueLogger) -> dict:
    """property_schema_map.csv -> {predicate: {"Property (with namespace)", "Domain", "Range", ...}}.

    작품별 파일이 아니라 프로젝트 전체가 공유하는 단일 스키마 (CLAUDE.md §4-0).
    앞뒤에 제목/범례 같은 자유 서식 행이 섞여 있어서(연구자가 직접 정리한 문서),
    'Property'로 시작하는 실제 헤더 행을 찾아서 그 지점부터 데이터로 읽는다.
    """
    if not SCHEMA_CSV.exists():
        logger.log(SCHEMA_CSV.name, 0, "-", "-",
                   "predicate 스키마 파일 없음",
                   "data/property_schema_map.csv가 아직 제공되지 않음",
                   "도메인/레인지 검증 및 '스키마 미정의 predicate' 로깅을 이번 실행에서는 생략 — "
                   "모든 predicate를 dict: 네임스페이스에 원본 이름 그대로 기록. "
                   "파일이 추가되면 다음 실행부터 자동으로 검증됨")
        return {}

    with open(SCHEMA_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    header_idx = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Property"), None)
    if header_idx is None:
        logger.log(SCHEMA_CSV.name, 0, "-", "-",
                   "predicate 스키마 파일 형식 인식 실패",
                   "'Property'로 시작하는 헤더 행을 찾지 못함",
                   "도메인/레인지 검증을 생략하고 스키마 없는 것으로 처리")
        return {}

    header = rows[header_idx]
    schema = {}
    for r in rows[header_idx + 1:]:
        if not r or not (r[0] or "").strip():
            continue
        row = dict(zip(header, r + [""] * (len(header) - len(r))))
        prop = (row.get("Property") or "").strip()
        if prop:
            schema[prop] = row
    return schema


def build_entity_node(row: dict, i: int, csv_name: str, work_id: str,
                       property_schema: dict, logger: IssueLogger):
    """CSV 한 행 -> JSON-LD 노드 dict. 실패한 행은 로그만 남기고 None 반환.

    제외 컬럼(CLAUDE.md §4): internal_Definition / Scope Note, Chapter(s), Page References는
    이 함수가 읽지 않는다 — 존재 자체를 무시한다.
    """
    entity_id = row["Entity ID"]

    if not row.get("Type") or not row.get("prefLabel (en)"):
        logger.log(csv_name, i, "Type/prefLabel", entity_id,
                   "필수값 누락", "Type 또는 prefLabel(en)이 비어있음",
                   "이 엔티티는 JSON-LD에서 제외")
        return None

    raw_evidence = row.get("Evidence Type", "")
    evidence_type = clean_label(raw_evidence)
    if evidence_type != raw_evidence.strip():
        logger.log(csv_name, i, "Evidence Type", raw_evidence,
                   "Evidence Type에 (Q##) 꼬리표 잔존",
                   "prefLabel과 같은 패턴의 꼬리표가 Evidence Type 컬럼에도 섞여 들어감",
                   "정규식으로 꼬리표 제거 후 사용")
    if evidence_type in ("", "—", "-"):
        logger.log(csv_name, i, "Evidence Type", raw_evidence,
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
        "dictrel:entityType": row["Type"],
        "dictrel:documentedIn": [work_id],
    }

    primary_uri = row.get("Primary URI", "").strip()
    mapping_status = row.get("Mapping Status", "").strip()
    if primary_uri:
        if mapping_status in ("matched", "closeMatch"):
            node["equivalent"] = [{"id": primary_uri}]
        else:
            logger.log(csv_name, i, "Primary URI/Mapping Status", primary_uri,
                       "Primary URI 있으나 Mapping Status 불충분",
                       f"Mapping Status='{mapping_status}' (matched/closeMatch 아님)",
                       "equivalent에 반영하지 않음")

    broader_uri = row.get("broader URI", "").strip()
    if broader_uri:
        node["skos:broader"] = [{"id": broader_uri}]

    close_match_raw = row.get("closeMatch URI", "").strip()
    if close_match_raw:
        uris = [u.strip() for u in close_match_raw.split(";") if u.strip()]
        node["skos:closeMatch"] = [{"id": u} for u in uris]

    description = row.get("Definition / Scope Note", "")
    if description:
        node["referred_to_by"] = [{
            "type": "LinguisticObject",
            "content": description,
            "classified_as": "description",
        }]

    if evidence_type:
        schema_row = property_schema.get("evidenceType")
        if schema_row:
            domain = (schema_row.get("Domain") or "").strip()
            if domain and domain != "Any" and row["Type"] not in domain:
                logger.log(csv_name, i, "Evidence Type", evidence_type,
                           "도메인 스키마 위반 (evidenceType)",
                           f"property_schema_map.csv는 evidenceType의 Domain을 '{domain}'로 정의하지만 "
                           f"이 엔티티의 Type='{row['Type']}'",
                           "막지 않고 그대로 반영 (연구자 판단 대기)")
        node["dict:evidenceType"] = evidence_type

    return node


def ingest_work_entities(work: dict, property_schema: dict, logger: IssueLogger,
                          master_entities: dict, master_by_uri: dict, master_by_label_type: dict):
    """작품 하나의 entities_csv를 읽어 reconciliation 규칙(§4-0)에 따라 master_entities에 병합.

    우선순위: ① Primary URI 완전 일치 -> ② Entity ID 완전 일치 -> ③ prefLabel(en)+Type 일치(fallback).
    반환: (원본 CSV 행 수, id_remap) — id_remap은 이 작품의 CSV상 Entity ID가 기존 마스터 엔티티로
    병합됐을 때 {이 작품의 Entity ID: 최종 마스터 @id} 를 담는다. 관계 처리 시 참조 해석에 쓰인다.
    """
    work_id = work["work_id"]
    entities_csv = ROOT / work["entities_csv"]
    if not entities_csv.exists():
        logger.log(str(work["entities_csv"]), 0, "-", "-",
                   "엔티티 CSV 없음",
                   f"config/works.yaml의 '{work_id}' 항목이 가리키는 entities_csv가 존재하지 않음",
                   "이 작품의 엔티티 처리를 스킵")
        return 0, {}

    with open(entities_csv, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    csv_name = entities_csv.name

    total_rows = 0
    id_remap: dict[str, str] = {}

    for i, r in enumerate(rows, start=1):
        if not r or not r[0].startswith("dict:"):
            continue
        total_rows += 1
        row = dict(zip(header, r + [""] * (len(header) - len(r))))
        entity_id = row["Entity ID"]
        primary_uri = row.get("Primary URI", "").strip()

        node = build_entity_node(row, i, csv_name, work_id, property_schema, logger)
        if node is None:
            continue

        existing_id = None
        match_rule = None
        if primary_uri and primary_uri in master_by_uri:
            existing_id = master_by_uri[primary_uri]
            match_rule = "Primary URI 일치"
        elif entity_id in master_entities:
            existing_id = entity_id
            match_rule = "Entity ID 일치"
        else:
            label = node["identified_by"][0]["content"] if node["identified_by"] else ""
            label_type_key = (label, row["Type"])
            if label_type_key in master_by_label_type:
                existing_id = master_by_label_type[label_type_key]
                match_rule = "label+Type fallback"

        if existing_id:
            existing = master_entities[existing_id]
            if match_rule == "label+Type fallback":
                logger.log(csv_name, i, "Entity ID", entity_id,
                           "엔티티 병합 (label+Type fallback)",
                           f"Primary URI/Entity ID로는 매칭 안 됐지만 prefLabel(en)+Type이 "
                           f"기존 엔티티 '{existing_id}'와 동일",
                           f"두 엔티티를 병합, documentedIn에 '{work_id}' 추가 "
                           "(오탐 가능성 있음 — 연구자 검토 필요)")
            elif match_rule == "Entity ID 일치" and existing.get("dictrel:entityType") != row["Type"]:
                logger.log(csv_name, i, "Type", row["Type"],
                           "동일 ID, 다른 정의",
                           f"'{entity_id}'가 이미 다른 작품에서 Type='{existing.get('dictrel:entityType')}'로 "
                           f"등록됨, 이번 작품에서는 Type='{row['Type']}'",
                           "충돌 자동 해결하지 않음 — 먼저 등록된 작품의 정의를 유지")
            if work_id not in existing["dictrel:documentedIn"]:
                existing["dictrel:documentedIn"].append(work_id)
            if entity_id != existing_id:
                id_remap[entity_id] = existing_id
            continue

        master_entities[entity_id] = node
        if primary_uri:
            master_by_uri[primary_uri] = entity_id
        label = node["identified_by"][0]["content"] if node["identified_by"] else ""
        master_by_label_type[(label, row["Type"])] = entity_id

    return total_rows, id_remap


def ingest_work_relationships(work: dict, id_remap: dict, master_entities: dict,
                               property_schema: dict, logger: IssueLogger):
    """작품 하나의 relationships_csv를 읽어 (subject_id, namespaced_key, entry) 리스트를 만든다.

    실제로 master_entities에 붙이는 건 main()의 몫 — 이 함수는 CSV 한 편을 해석하기만 한다.
    제외 컬럼(§4): page_ref, note는 읽지 않는다.

    주의: 관계 CSV의 첫 컬럼(subject URI)은 헤더 셀이 빈칸(' ')이라 이름으로 조회할 수 없어
    위치(r[0])로 읽는다. subject_uri/object_uri는 이미 'dict:person/...' CURIE 형태라
    별도 슬러그 추출 없이 엔티티 @id와 바로 문자열 비교한다.
    """
    work_id = work["work_id"]
    relationships_csv = ROOT / work["relationships_csv"]
    if not relationships_csv.exists():
        logger.log(str(work["relationships_csv"]), 0, "-", "-",
                   "관계 CSV 없음",
                   f"config/works.yaml의 '{work_id}' 항목이 가리키는 relationships_csv가 존재하지 않음",
                   "이 작품의 관계 처리를 스킵")
        return 0, [], 0, 0, 0

    with open(relationships_csv, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    csv_name = relationships_csv.name

    total_rows = 0
    n_dangling = 0
    n_schema_violations = 0
    n_undefined_predicates = 0
    edges: list[tuple[str, str, dict]] = []

    for i, r in enumerate(rows, start=1):
        if i == 1 or not r or not any(c.strip() for c in r):
            continue
        total_rows += 1
        row = dict(zip(header, r + [""] * (len(header) - len(r))))

        raw_subj = (r[0] or "").strip()
        raw_obj = row.get("object_uri", "").strip()

        if "\n" in raw_subj or "\n" in raw_obj:
            logger.log(csv_name, i, "subject/object_uri",
                       f"subject={raw_subj!r} object={raw_obj!r}",
                       "URI 필드 내 개행 문자", "CSV 원본 셀에 줄바꿈이 섞여있음",
                       "개행 제거 후 매칭 시도 (원본 CSV 수정 권장)")
            raw_subj = raw_subj.replace("\n", "").strip()
            raw_obj = raw_obj.replace("\n", "").strip()

        subj_id = id_remap.get(raw_subj, raw_subj)
        obj_id = id_remap.get(raw_obj, raw_obj)

        missing = []
        if subj_id not in master_entities:
            missing.append(("subject", raw_subj, subj_id))
        if obj_id not in master_entities:
            missing.append(("object_uri", raw_obj, obj_id))
        if missing:
            n_dangling += 1
            for field, raw, resolved in missing:
                logger.log(csv_name, i, field, raw,
                           "매칭 실패 (dangling reference)",
                           f"'{resolved}'에 해당하는 엔티티를 어떤 작품의 엔티티 CSV에서도 찾을 수 없음",
                           "이 관계(행 전체)를 JSON-LD에서 스킵")
            continue

        predicate = row.get("relationship_property_uri", "").strip().split("/")[-1]
        if not predicate:
            logger.log(csv_name, i, "relationship_property_uri",
                       row.get("relationship_property_uri", ""),
                       "predicate 없음", "관계 유형을 알 수 없음", "이 관계를 JSON-LD에서 스킵")
            continue

        violation = False
        if property_schema:
            schema_row = property_schema.get(predicate)
            namespaced = (schema_row.get("Property (with namespace)") if schema_row else "") \
                or f"dict:{predicate}"
            if not schema_row:
                n_undefined_predicates += 1
                logger.log(csv_name, i, "relationship_property_uri", predicate,
                           "스키마 미정의 predicate",
                           "property_schema_map.csv의 공식 목록에 없는 predicate",
                           f"버리지 않고 '{namespaced}'로 그대로 기록 (연구자 검토 대기)")
            else:
                domain = (schema_row.get("Domain") or "").strip()
                range_ = (schema_row.get("Range") or "").strip()
                subj_type = master_entities[subj_id].get("dictrel:entityType", "")
                obj_type = master_entities[obj_id].get("dictrel:entityType", "")
                if domain and domain != "Any" and subj_type and subj_type not in domain:
                    violation = True
                    n_schema_violations += 1
                    logger.log(csv_name, i, "subject", raw_subj,
                               "도메인/레인지 스키마 위반",
                               f"predicate '{predicate}'의 정의된 Domain='{domain}'이지만 "
                               f"실제 subject Type='{subj_type}'",
                               "막지 않고 그대로 반영 (연구자 판단 대기)")
                if range_ and range_ != "Any" and obj_type and obj_type not in range_:
                    violation = True
                    n_schema_violations += 1
                    logger.log(csv_name, i, "object_uri", raw_obj,
                               "도메인/레인지 스키마 위반",
                               f"predicate '{predicate}'의 정의된 Range='{range_}'이지만 "
                               f"실제 object Type='{obj_type}'",
                               "막지 않고 그대로 반영 (연구자 판단 대기)")
        else:
            namespaced = f"dict:{predicate}"

        entry = {"id": obj_id, "dictrel:documentedIn": [work_id]}
        if violation:
            entry["dictrel:schemaViolation"] = True
        edges.append((subj_id, namespaced, entry))

    return total_rows, edges, n_schema_violations, n_undefined_predicates, n_dangling


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return

    logger = IssueLogger()
    works = load_works(logger)
    property_schema = load_property_schema(logger)

    master_entities: dict = {}
    master_by_uri: dict = {}
    master_by_label_type: dict = {}

    n_entity_rows = 0
    n_rel_rows = 0
    n_edges = 0
    n_dangling = 0
    n_schema_violations = 0
    n_undefined = 0

    for work in works:
        rows, id_remap = ingest_work_entities(
            work, property_schema, logger, master_entities, master_by_uri, master_by_label_type
        )
        n_entity_rows += rows

        rel_rows, edges, n_v, n_u, n_d = ingest_work_relationships(
            work, id_remap, master_entities, property_schema, logger
        )
        n_rel_rows += rel_rows
        n_schema_violations += n_v
        n_undefined += n_u
        n_dangling += n_d
        for subj_id, key, entry in edges:
            master_entities[subj_id].setdefault(key, []).append(entry)
        n_edges += len(edges)

    n_with_equivalent = sum(1 for n in master_entities.values() if n.get("equivalent"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = {
        "@context": CONTEXT,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "@graph": list(master_entities.values()),
    }
    out_path = OUT_DIR / "graph.jsonld"
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"build-jsonld-{timestamp}.log.csv"
    logger.write(log_path)

    n_nodes = len(master_entities)
    entity_match_pct = (n_nodes / n_entity_rows * 100) if n_entity_rows else 0
    equivalent_pct = (n_with_equivalent / n_nodes * 100) if n_nodes else 0
    edge_match_pct = (n_edges / n_rel_rows * 100) if n_rel_rows else 0
    dangling_pct = (n_dangling / n_rel_rows * 100) if n_rel_rows else 0
    violation_pct = (n_schema_violations / n_rel_rows * 100) if n_rel_rows else 0
    undefined_pct = (n_undefined / n_rel_rows * 100) if n_rel_rows else 0

    print("=" * 56)
    print("JSON-LD 빌드 결과 요약 (build-jsonld.py)")
    print("=" * 56)
    print(f"엔티티 CSV 원본 행:        {n_entity_rows}건  ->  JSON-LD 노드:  {n_nodes}건  ({entity_match_pct:.1f}%)")
    print(f"외부 URI 매핑(equivalent): {n_with_equivalent}건  ({equivalent_pct:.1f}%)")
    print("-" * 56)
    print(f"관계 CSV 원본 행:          {n_rel_rows}건  ->  JSON-LD 관계:  {n_edges}건  ({edge_match_pct:.1f}%)")
    if property_schema:
        print(f"  매칭 실패(dangling):      {n_dangling}건  ({dangling_pct:.1f}%)")
        print(f"  스키마 위반 (반영은 함):  {n_schema_violations}건  ({violation_pct:.1f}%)")
        print(f"  스키마 미정의 predicate:  {n_undefined}건  ({undefined_pct:.1f}%)")
    else:
        print(f"  매칭 실패(dangling):      {n_dangling}건  ({dangling_pct:.1f}%)")
        print("  스키마 검증:              건너뜀 (data/property_schema_map.csv 없음)")
    print("-" * 56)
    print(f"발생한 이슈 총 {len(logger.rows)}건 -> 상세 내용: {log_path.relative_to(ROOT)}")
    print("=" * 56)
    print(f"graph.jsonld 저장 완료: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
