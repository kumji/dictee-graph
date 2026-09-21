# CLAUDE.md — Dictée LOD 인터랙티브 그래프 (GitHub Pages 테스트 프로토타입)

## 0. 이 문서의 목적

Dictée 엔티티(57개)·관계(27건, 그중 1건은 참조 오류로 스킵)·공식 Property 스키마(20종) 데이터를
**GitHub Pages에 띄우는 최소 기능 인터랙티브 그래프**로 시각화하는 테스트 프로젝트의 스펙이다.
이 문서를 CLAUDE.md로 두고 바이브 코딩(Claude Code)으로 구현한다.

**연구자의 최종 목표는 Dictée 하나가 아니다.** 앞으로 두세 작품을 더 추가해서 **하나의 그래프**로 합쳐야 한다.
그래서 이번 프로토타입부터 "Dictée 전용 스크립트"가 아니라 **설정 파일(`config/works.yaml`)에 작품을 등록하면
코드 수정 없이 확장되는 구조**로 짠다. 지금은 실제 데이터가 Dictée 하나뿐이라 결과물은 동일하지만, 파이프라인
코드 자체는 처음부터 다중 작품을 전제로 작성한다.

**이건 프로토타입이다.** Wikibase에 쓰기, 실시간 동기화는 이번 스코프에 없다.

**⚠️ 2026-09-08 데이터 갱신으로 스펙이 크게 바뀌었다.** 엔티티 수(67→57), predicate 스키마(18→20종,
전부 공식 확정), 식별자 체계(단일 `dict:` 네임스페이스로 통일), 외부 권위 연결 방식(Wikibase 로컬 QID → 정식
Wikidata URI)이 전부 변경됐다. 이전 버전 문서를 참고하고 있다면 전부 무시하고 이 문서를 기준으로 할 것.

---

## 1. 목표 / 비목표

### 목표
- CSV를 진짜 JSON-LD(`graph.jsonld`)로 변환하는 것 — 이게 프로젝트 본래 목표이자 핵심 산출물
- **설정 파일(`config/works.yaml`)에 작품을 등록하는 방식으로 재사용 가능한 파이프라인** — 두 번째·세 번째
  작품 추가 시 스크립트 수정 없이 CSV 파일 + 설정 항목만 추가
- 57개 엔티티를 노드로, 26개 관계(27건 중 dangling reference 1건 제외)를 엣지로 그리는 인터랙티브 그래프
- 노드 클릭 시 상세 정보(설명, Evidence Type, 외부 권위 링크) 패널 표시
- 타입별 색상 구분 (Person/Event/Concept/Object/Group/Work)
- Evidence Type 필터 (Textual/Biographical/Scholarly/Direct Term/Synthesis/Modeling 등으로 관계 신뢰도 시각적 구분)
- GitHub Pages에 정적 배포

### 비목표 (이번 스코프 아님)
- Wikibase에 쓰기(write-back)
- 실시간 SPARQL 연동 — 정적 스냅샷 JSON만 사용
- **다중 작품 UI 지원** — 파이프라인 코드는 다중 작품을 전제로 짜지만, 그래프 뷰어 UI에 "작품별 필터" 같은
  기능을 넣는 건 이번 스코프 밖 (실제 두 번째 작품 데이터가 들어올 때 추가)
- 사용자 인증, 편집 기능
- **Chapter 필터** — `Chapter(s)` 컬럼은 연구자 참고용으로 분류되어 이 프로그램이 다루지 않음
- **관계의 근거(`page_ref`, `note`) 표시** — 연구자 참고용 컬럼으로 분류되어 프로그램이 다루지 않음. 엣지 클릭 시 predicate만 표시

---

## 2. 그래프 라이브러리 선택: Cytoscape.js

### 비교했던 대안들

| 라이브러리 | 장점 | 이 프로젝트에 안 맞는 이유 |
|---|---|---|
| **Cytoscape.js** ✅ | 속성 기반 스타일링(`node[type="Person"]`)이 강력함. 레이아웃 다양. React 래퍼 존재 | 없음 — 채택 |
| react-force-graph | 설정 없이도 물리 시뮬레이션이 예쁘게 나옴, WebGL이라 빠름 | 노드/엣지 메타데이터를 세밀하게 스타일링하기엔 API가 덜 유연함 |
| D3.js (직접 force-directed) | 완전한 커스터마이징 | 이번 스코프엔 과함 |
| vis.js Network | 배우기 쉬움 | 유지보수·커스텀 스타일링 한계 |

JSON-LD 자체를 이해하는 그래프 라이브러리는 존재하지 않는다 — `@context` 해석과 노드/엣지 분리는 항상 별도
변환 코드가 필요하다 (4번 섹션의 파이프라인이 그 역할).

### 채택 이유
- 데이터가 "타입 있는 노드 + predicate 라벨 붙은 방향성 엣지" 구조라 Cytoscape의 스타일시트 문법과 정확히 맞음
- `cose`(물리 기반) 레이아웃으로 바로 실험 가능
- `react-cytoscapejs`로 기존 React+TS 스택에 그대로 통합

---

## 3. 기술 스택

- **React 18 + TypeScript + Vite**
- **Tailwind CSS**
- **cytoscape** + **react-cytoscapejs**
- **cytoscape-cose-bilkent** (더 나은 force-directed 레이아웃)
- 상태관리: React 기본 `useState`/`useMemo`로 충분 (57 노드/26 엣지)
- 배포: **GitHub Pages** (Vite `base` 설정 + GitHub Actions)

---

## 4. 데이터 파이프라인 (2단계: CSV → 진짜 JSON-LD → Cytoscape용 평면 JSON)

```
data/*.csv (작품별로 여러 쌍)
   ↓ ① scripts/build-jsonld.py  ← config/works.yaml을 읽어 등록된 모든 작품을 순회
public/data/graph.jsonld     ← 진짜 JSON-LD (모든 작품이 합쳐진 하나의 그래프)
   ↓ ② scripts/build-graph-json.py
public/data/graph.json       ← Cytoscape 전용 파생 뷰
```

②는 ①의 파생물일 뿐이므로 CSV를 직접 읽지 않는다. CSV를 아는 코드는 ①에만 존재한다.

### 4-0. 다중 작품 확장 설계 원칙 (반드시 먼저 읽을 것)

**작품 레지스트리 — `config/works.yaml`**. 새 작품을 추가할 때 수정하는 건 이 파일과 `data/` 폴더뿐이고,
`scripts/*.py`는 절대 건드리지 않는다:
```yaml
works:
  - work_id: dictee
    title: "Dictée"
    entities_csv: "data/dictee_entities.csv"
    relationships_csv: "data/dictee_relationships.csv"
  # - work_id: exilee                              # 예시 — 실제 파일 확보되면 추가
  #   title: "Exilée and Temps Morts"
  #   entities_csv: "data/exilee_entities.csv"
  #   relationships_csv: "data/exilee_relationships.csv"
```

**`property_schema_map.csv`는 작품별로 만들지 않는다 — 전체 프로젝트가 공유하는 단일 파일이다.**
`creator`, `hasPostcolonialParallel`, `mythologicalParallelOf` 같은 predicate는 Dictée만의 개념이 아니라
연구자의 이론적 프레임워크 전체에 적용되는 것이므로, 작품이 몇 개로 늘어나든 이 스키마 파일 하나만 계속 쓴다.

**엔티티 중복 판정(reconciliation)** — 같은 실존 인물/개념(예: Spivak, Postcolonial Feminism)이 여러 작품의
`entities_csv`에 각각 등장할 수 있다. `build-jsonld.py`는 모든 작품의 엔티티를 하나의 마스터 목록으로 합칠 때
다음 우선순위로 "이미 존재하는 엔티티인지" 판단한다:
1. **`Primary URI` 완전 일치** — 둘 다 같은 Wikidata URI를 가리키면 같은 엔티티 (가장 신뢰도 높음)
2. **`Entity ID` 완전 일치** — 연구자가 두 작품에서 똑같은 ID(`dict:person/spivak`)를 재사용했다면 그대로 병합
3. **`prefLabel (en)` + `Type` 완전 일치** — 위 둘 다 없을 때의 fallback (오탐 가능성 있으므로 로그에 남김)

병합된 엔티티는 `documentedIn: ["dictee", "exilee"]`처럼 **어느 작품(들)에 등장하는지 배열로 기록**한다.
관계(edge)에도 동일하게 `documentedIn`을 기록해서, 나중에 "이 관계가 어느 작품 분석에서 나온 것인지" 추적 가능.

**⚠️ 알려진 위험 — 지금은 작품이 1개라 검증 불가**: 연구자가 새 작품 CSV에서 Spivak에게 실수로 다른 ID
(`dict:person/spivak-2`)를 새로 부여하면, 3번 fallback(라벨+Type 일치)이 잡아주긴 하지만 **다른 실존 인물이
우연히 같은 이름이면 잘못 병합될 수 있다.** 이건 코드로 100% 막을 수 없고, 두 번째 작품 CSV가 실제로 들어오면
merge 로그를 사람이 한 번 검토하는 단계가 필요하다 (8번 섹션에 이슈로 등록).

**`dict:` 네임스페이스는 이미 작품별이 아니라 프로젝트 전체용이다** — 별도 변경 불필요. 새 엔티티를 새로
만들어야 할 때만 `dict:{type}/{slug}` 형태로 발급.

### 입력 파일
```
config/
└── works.yaml                   ← 작품 레지스트리 (위 4-0 참고)
data/
├── dictee_entities.csv          ← 57개 엔티티
├── dictee_relationships.csv     ← 27건 관계
└── property_schema_map.csv      ← 공식 predicate 스키마 20종 (모든 작품 공유, 작품별 파일 아님)
```
**이전 버전에 있던 `entity_qid_crosswalk.csv`는 이번 데이터에서 필요 없어졌다.** `Primary URI` 컬럼이 이제
로컬 Wikibase 번호가 아니라 정식 Wikidata URI라서, 크로스워크 없이 `Mapping Status`(matched/closeMatch)와
`Primary URI`만으로 외부 권위 연결이 가능하다.

### 이 프로그램이 다루지 않는 컬럼 (연구자 참고용, 반드시 파싱/매핑 대상에서 제외)
| 파일 | 제외 컬럼 |
|---|---|
| 엔티티 CSV | `internal_Definition / Scope Note`, `Chapter(s)`, `Page References` |
| 관계 CSV | `page_ref`, `note` |
| Property 스키마 CSV | `출처 어휘`, `표준 대응/변경사항` |

이 컬럼들은 CSV에는 남아있지만 `build-jsonld.py`가 읽지 않는다 — 존재 자체를 무시하면 됨 (에러 처리 대상도 아님).

---

### 4-1. ① `scripts/build-jsonld.py` — CSV → 진짜 JSON-LD

**실행 흐름 (다중 작품 대응)**:
```python
config = yaml.safe_load(open("config/works.yaml"))
master_entities = {}   # key: 최종 @id, value: 엔티티 dict (4-0의 reconciliation 규칙 적용)
master_edges = []      # 각 edge에도 documentedIn 기록

for work in config["works"]:
    ingest_entities(work, master_entities)      # reconciliation 수행하며 병합
    ingest_relationships(work, master_edges, master_entities)

write_jsonld(master_entities, master_edges)     # 작품 수와 무관하게 항상 이 한 번만 호출
```
지금은 `config["works"]`에 항목이 1개(dictee)뿐이라 결과가 이전과 동일하지만, 항목이 늘어도 이 함수들은
수정할 필요가 없다 — 이게 "재사용 가능한 프로그램"의 핵심이다.

**컨텍스트**:
```json
"@context": [
  "https://linked.art/ns/v1/linked-art.json",
  { "dict": "https://dictee-lod.wikibase.cloud/entity/",
    "dictrel": "https://dictee-lod.wikibase.cloud/prop/direct/" }
]
```

**클래스 매핑** (`Type` 컬럼 → `@type`, 이전과 동일):
| Type | @type |
|---|---|
| Person | `Person` |
| Event | `Period` |
| Concept | `Type` |
| Group | `Group` |
| Object | `HumanMadeObject` (`Linked Art Class`가 `LinguisticObject`인 행은 그대로 유지) |
| Work | CSV의 `Linked Art Class` 값을 그대로 사용 (이제 `dict:work/dictee` 1건뿐) |

**Predicate 스키마 — 20종 전부 공식 확정, `property_schema_map.csv` 하나를 모든 작품이 공유** (27건 관계에
쓰인 12종 predicate 전부 아래 표에 있음):

| Property | 네임스페이스 | Domain | Range | 비고 |
|---|---|---|---|---|
| `broader` | `skos:broader` | Concept | Concept 또는 외부 URI(AAT/LCSH/Homosaurus) | 엔티티 CSV의 `broader URI` 컬럼에서 생성 |
| `subverts` | `dict:subverts` | Object/Any | Concept or Type | |
| `isPartOf` | `dict:isPartIn` | Person | Chapter | (표시명 `isPartOf`, 네임스페이스는 `isPartIn` 그대로) |
| `mentions` | `schema:mentions` | Any | Any | 범용 약한 연결자 (이전 `refersTo` 대체) |
| `critiques` | `dict:critiques` | Person(Scholarly) | Concept | |
| `evidenceType` | `dict:evidenceType` | Concept\|Person\|Event\|Object\|Group\|Work | Evidence Type(Q1-3) | 전 타입으로 확장 확정 |
| `composedOf` | `dict:composedOf` | Work | Chapter | |
| `creator` | `dct:creator` | **Work → Person** | | ⚠️ 방향 확정: Work가 주어 |
| `hasNarrator` | `dict:hasNarrator` | Work | Person(Diseuse) | |
| `narrates` | `dict:narrates` | Person(Diseuse) | Chapter | 구 `channels` 완전 폐기, 이 predicate로 통일 |
| `hasExchangeableIdentity` | `dict:hasExchangeableIdentity` | Person | Person | symmetric |
| `hasPostcolonialParallel` | `dict:hasPostcolonialParallel` | **Any** | **Any** | ⚠️ 이번에 Event→Event에서 Any→Any로 확장 확정 (Person-Person, Object-Person 실사용 반영) |
| `performsMediation` | `dict:performsMediation` | Person(Diseuse) | Person | ⚠️ 실제 데이터에 Object가 주어인 2건 있음 — 아직 스키마 위반, 4-1-1 로그 필수 |
| `prefigures` | `dict:prefigures` | Any(Object/Concept) | Any(Concept) | |
| `silences` | `dict:silences` | Event/Concept | Person | |
| `isRecurrenceOf` | `dict:isRecurrenceOf` | Event | Event | |
| `hasFamilyRelation` | `dict:hasFamilyRelation` | Person | Person | |
| `closeMatch` | `skos:closeMatch` | Any | 외부 URI | 엔티티 CSV의 `closeMatch URI` 컬럼(세미콜론 구분 다중값)에서 생성 |
| `mythologicalParallelOf` | `dict:mythologicalParallelOf` | Person | Person | 신규 확정 |
| `sharesNameWith` | `dict:sharesNameWith` | Person | Person | 신규 확정 |
| `performsAs` | `dict:performsAs` | Person | Person | 신규 확정 |
| `requiresExcavationBy` | `dict:requiresExcavationBy` | Concept | Person or Concept | 신규 확정 |
| `embodiesPunctuation` | `dict:embodiesPunctuation` | Person | Concept or Type | 신규 확정 |

**속성 매핑 (엔티티)**:
| CSV 컬럼 | JSON-LD 속성 |
|---|---|
| `Entity ID` | `@id` — reconciliation으로 기존 엔티티와 병합되면 **최초 등장한 작품의 ID를 그대로 유지** |
| `prefLabel (en)`/`(ko)` | `identified_by: [{type:"Name", content, language}]` (이번 데이터엔 `(Q##)` 꼬리표 없음 — 확인됨, 그래도 방어적으로 정규식 제거는 유지) |
| `Primary URI` | `equivalent: [{id: ...}]` — `Mapping Status`가 `matched`/`closeMatch`일 때만. 정식 Wikidata URI (`http(s)://www.wikidata.org/entity|wiki/Q...`) |
| `broader URI` | `skos:broader: [{id: ...}]` |
| `closeMatch URI` | `skos:closeMatch: [{id: ...}, ...]` — 세미콜론(`;`)으로 분리해서 배열로 |
| `Definition / Scope Note` | `referred_to_by: [{type:"LinguisticObject", content, classified_as:"description"}]` |
| *(신규)* | `dictrel:documentedIn: ["dictee"]` — 이 엔티티가 등장하는 작품 `work_id` 배열, reconciliation 시 append |

**관계(Relationship)에도 동일하게 `documentedIn: ["dictee"]` 필드를 붙인다** (어느 작품 분석에서 나온
관계인지 추적용). `relationship_property_uri`가 `dict:rel/{predicateName}` 형태로 통일되어 있어 `/` 마지막
세그먼트만 뽑으면 바로 predicate 이름. `subject_uri`/`object_uri`도 이미 `dict:person/cha-theresa` 형태의
CURIE라서 별도 슬러그 추출 없이 바로 엔티티 `@id`와 문자열 비교 가능.

**도메인/레인지 검증**: 관계 하나를 쓰기 전에 subject/object의 실제 `Type`이 위 표의 Domain/Range와 맞는지
검사. 안 맞아도 막지 않고 반영하되 반드시 로그에 남긴다.

**출력**: `public/data/graph.jsonld` — 등록된 모든 작품의 엔티티·관계가 하나로 합쳐진 단일 그래프.

---

### 4-1-1. 로깅 + 매칭률 리포트 (①·② 공통 요구사항)

**① 로그 파일** — `logs/build-jsonld-{timestamp}.log.csv` / `logs/build-graph-{timestamp}.log.csv`
| 컬럼 | 내용 |
|---|---|
| `source_file` | 어느 CSV에서 발생했는지 |
| `row_number` | 몇 번째 행인지 |
| `field` | 어느 컬럼 |
| `raw_value` | 원본 값 |
| `issue_type` | "매칭 실패 (dangling reference)" / "도메인·레인지 스키마 위반" 등 |
| `detail` | 왜 문제인지 |
| `action_taken` | 실제 처리 방식 (스킵/반영 등, 침묵 처리 금지) |

**이번 데이터로 반드시 잡혀야 하는 이슈 2건 (검증용 기대값)**:
1. 관계 19번째 행(`melpomene-fresco --subverts--> muse-subversion`): object가 삭제된 엔티티 → **dangling reference,
   해당 엣지 스킵**
2. `performsMediation`을 쓰는 3건 중 2건(`yu-portrait`, `dreyer-still`이 주어): subject Type이 `Object`라
   Domain(`Person`) 위반 → **반영은 하되 로그에 남김**

**다중 작품이 되면 추가로 로깅해야 할 issue_type** (지금은 작품이 1개라 발생하지 않지만 코드에는 미리 넣어둘 것):
- `"엔티티 병합 (label+Type fallback)"` — Primary URI도 Entity ID도 안 맞아서 라벨+Type만으로 병합한 경우.
  오탐 위험이 있으므로 항상 로그에 남기고, 병합된 두 원본 Entity ID를 `detail`에 명시
- `"동일 ID, 다른 정의"` — 두 작품이 같은 Entity ID를 썼는데 `Type`이나 `prefLabel`이 다른 경우 (데이터 충돌,
  자동으로 해결하지 말고 로그만 남기고 먼저 등록된 작품의 정의를 유지)

**② 터미널 요약** (형식은 이전과 동일, 두 스크립트 공통):
```
========================================================
JSON-LD 빌드 결과 요약 (build-jsonld.py)
========================================================
엔티티 CSV 원본 행:        57건  ->  JSON-LD 노드:  57건  (100.0%)
외부 URI 매핑(equivalent): 24건  (42.1%)
--------------------------------------------------------
관계 CSV 원본 행:          27건  ->  JSON-LD 관계:  26건  (96.3%)
  매칭 실패(dangling):      1건  (3.7%)
  스키마 위반 (반영은 함):  2건  (7.4%)
--------------------------------------------------------
발생한 이슈 총 N건 -> 상세 내용: logs/build-jsonld-{timestamp}.log.csv
========================================================
graph.jsonld 저장 완료: public/data/graph.jsonld
```

### 4-2. ② `scripts/build-graph-json.py` — graph.jsonld → Cytoscape용 평면 JSON

1. `@graph` 배열을 순회하며 노드를 평평한 객체로 변환: `@id`→`id`, `@type`→`group`,
   `identified_by`→`label_en`/`label_ko`, `referred_to_by`→`description`, `equivalent`→`equivalentUri`,
   `skos:broader`/`skos:closeMatch`→같은 이름의 배열 필드, `documentedIn`→그대로 유지 (작품별 필터는
   이번 UI 스코프 밖이지만 데이터는 미리 갖고 있는다)
2. 각 노드의 `dict:{predicate}` 필드를 순회하며 엣지 배열 생성 (`source`/`target`/`predicate`/`documentedIn`만 —
   `pageRef`/`note`/`status`는 모델링 대상이 아니므로 넣지 않는다)
3. 출력: `public/data/graph.json` (nodes/edges 배열)

**실행 순서**: `python3 scripts/build-jsonld.py` → `python3 scripts/build-graph-json.py` → `npm run build`

---

## 5. 노드/엣지 시각 스타일

### 노드 색상 (Type별, 이전과 동일)
| Type | 색상 |
|---|---|
| Person | `#3B82F6` |
| Event | `#EF4444` |
| Concept | `#8B5CF6` |
| Object | `#F59E0B` |
| Group | `#10B981` |
| Work | `#EC4899` |

### 엣지 스타일
- 기본: 실선, 화살표
- Evidence Type이 `Modeling`인 엔티티에서 파생된 관계: **점선** (해석적 연결 표시)
- 엣지 라벨: predicate 이름 표시 (`performsMediation` 등)
- 도메인/레인지 위반 엣지(`performsMediation`의 Object 주어 2건): 색을 다르게(예: 회색 테두리 추가)해서
  "스키마상 예외" 표시 — 숨기지 않고 시각적으로만 구분

### 노드 크기
- degree(연결된 엣지 수)에 비례

---

## 6. UI 레이아웃

```
┌─────────────────────────────────────────────────┐
│  Dictée LOD Graph          [필터: Type ▾] [검색 🔍]│
├───────────────────────────────┬───────────────────┤
│                               │  선택된 노드/엣지  │
│         Cytoscape 캔버스      │  상세 패널         │
│         (전체 화면 대부분)     │  - 설명           │
│                               │  - Evidence Type  │
│                               │  - 외부 링크       │
│                               │  (없으면 배지 없음)│
└───────────────────────────────┴───────────────────┘
```

- **노드 클릭** → `description`, `evidenceType`, `equivalentUri`(있으면 Wikidata 링크), `broader`/`closeMatch`
  (있으면 외부 어휘 링크 목록) 표시
- **엣지 클릭** → `predicate`만 표시 (근거/출처는 이 프로그램 스코프 밖)
- **상단 필터**: Type 체크박스만 (Chapter 필터는 제거됨 — 4번 섹션 참고)
- **검색창**: 라벨(en/ko) 부분 일치 시 해당 노드로 이동 + 하이라이트
- **언어 토글**: en/ko 라벨 전환

---

## 7. 폴더 구조

```
dictee-graph/
├── config/
│   └── works.yaml               ← 작품 레지스트리 (4-0 참고) — 새 작품 추가 시 이 파일만 수정
├── data/
│   ├── dictee_entities.csv
│   ├── dictee_relationships.csv
│   └── property_schema_map.csv  ← 모든 작품이 공유 (작품별 파일 아님)
├── scripts/
│   ├── build-jsonld.py
│   └── build-graph-json.py
├── public/
│   └── data/
│       ├── graph.jsonld
│       └── graph.json
├── src/
│   ├── components/
│   │   ├── GraphCanvas.tsx
│   │   ├── DetailPanel.tsx
│   │   ├── FilterBar.tsx
│   │   └── SearchBox.tsx
│   ├── lib/
│   │   ├── graphStyles.ts
│   │   └── types.ts
│   ├── App.tsx
│   └── main.tsx
├── vite.config.ts
└── CLAUDE.md
```

---

## 8. 알려진 데이터 이슈 (구현 시 방어적으로 처리할 것)

1. **관계 19번째 행이 삭제된 엔티티(`muse-subversion`)를 참조함** — dangling reference, 반드시 스킵 + 로그
2. **`performsMediation` 2건이 Domain(Person) 위반** (Object가 주어) — 스킵하지 말고 반영 + 로그
3. **`Chapter(s)`, `Page References`, `internal_Definition`, `page_ref`, `note`는 이 프로그램이 다루지 않음** — 파싱 대상에서 제외 (에러 아님, 의도된 스코프 축소)
4. **Work 엔티티가 `dict:work/dictee` 1건뿐** — 이전 버전에서 상정했던 "관련 작품들과의 관계" UI 요소는 해당 없음
5. **`closeMatch URI`는 세미콜론(`;`)으로 여러 값을 구분** — 단순 문자열로 취급하지 말고 split 필요 (예: `spillers`, `lugones`, `mohanty`, `wynter`는 각각 2~3개 Homosaurus URI를 가짐)
6. **Primary URI 도메인이 `wikidata.org`로 일관되지만, `http://www.wikidata.org/entity/Q...`와 `https://www.wikidata.org/wiki/Q...` 두 형식이 혼재** — 정규화 없이 그대로 `equivalent`에 넣어도 무방하나, 통일하고 싶다면 후처리 정규식 필요
7. **엔티티 reconciliation 로직(4-0)이 실제 다중 작품으로 검증된 적이 없음** — 지금은 `config/works.yaml`에 작품이 1개뿐이라, "라벨+Type만으로 병합" 같은 fallback 경로가 한 번도 실행되지 않았다. 두 번째 작품 CSV가 들어오면 병합 로그를 반드시 사람이 검토할 것

---

## 9. 구현 단계 (Claude Code 작업 순서)

1. Vite + React + TS + Tailwind 스캐폴딩, `cytoscape`/`react-cytoscapejs`/`cytoscape-cose-bilkent` 설치
2. `config/works.yaml` 작성 (dictee 1개 항목) + `scripts/build-jsonld.py` 작성 — **처음부터 4-0의 순회
   구조(works 리스트를 for 루프)로 짤 것, "일단 하드코딩하고 나중에 리팩터링"하지 말 것**
3. 실행 → `public/data/graph.jsonld` 생성, 터미널 요약이 "노드 57건, 관계 26건(27건 중 1건 스킵)"과 일치하는지 확인
4. `scripts/build-graph-json.py` 작성 → `public/data/graph.json` 생성 확인
5. `GraphCanvas.tsx`: graph.json fetch → Cytoscape 로드, 타입별 색상 스타일 적용
6. `DetailPanel.tsx`: 노드/엣지 클릭 이벤트, 외부 URI 링크 렌더링
7. `FilterBar.tsx`(Type만), `SearchBox.tsx` 추가
8. `vite.config.ts`에 `base` 설정 후 `npm run build` 로컬 확인
9. GitHub Actions로 `gh-pages` 배포

---

## 10. 다음 단계 (이번 스코프 밖, 참고용)

- **두 번째 작품 CSV 확보 시**: `config/works.yaml`에 항목 추가 + `data/`에 CSV 2개 추가만으로 끝나는지 실제로
  검증 (안 되면 4-0 설계가 잘못된 것)
- reconciliation 병합 로그를 사람이 검토하는 절차 마련 (7번 이슈)
- `performsMediation` 스키마 위반 2건, 연구자에게 Domain 확장(Any 포함) 여부 확인 요청
- `muse-subversion` 관계 처리 방향 확인 (엔티티 자체를 되살릴지, 관계를 삭제할지)
- Wikibase SPARQL 스냅샷 동기화 스크립트 연결
- 작품이 2개 이상 되면 그래프 뷰어 UI에 `documentedIn` 기반 작품별 필터 추가 (데이터 필드는 이미 준비됨)
- Chapter/page_ref 데이터를 프로그램에 포함시킬 필요가 생기면 4번 섹션의 "제외 컬럼" 표에서 제거하고 매핑 규칙 추가
