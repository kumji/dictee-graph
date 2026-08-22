# CLAUDE.md — Dictée LOD 인터랙티브 그래프 (GitHub Pages 테스트 프로토타입)

## 0. 이 문서의 목적

지금까지 정리한 Dictée 엔티티(67개)·관계(25건 확정 + 라벨매칭 후보) 데이터를
**GitHub Pages에 띄우는 최소 기능 인터랙티브 그래프**로 시각화하는 테스트 프로젝트의 스펙이다.
이 문서를 CLAUDE.md로 두고 바이브 코딩(Claude Code)으로 구현한다.

**이건 프로토타입이다.** Wikibase 반영, 다중 작품 확장, 실시간 동기화는 이번 스코프에 없다.
지금 가진 정적 CSV 스냅샷으로 "그래프가 실제로 어떻게 보이는지" 빠르게 확인하는 게 목표다.

---

## 1. 목표 / 비목표

### 목표
- 67개 엔티티를 노드로, 확정된 관계를 엣지로 그리는 인터랙티브 그래프
- 노드 클릭 시 상세 정보(설명, Evidence Type, Page Reference, Wikidata/Wikibase 링크) 패널 표시
- 타입별 색상 구분 (Person/Event/Concept/Object/Group/Work)
- Evidence Type 필터 (Textual/Biographical/Modeling 등으로 관계 신뢰도 시각적 구분)
- Chapter(뮤즈) 필터
- GitHub Pages에 정적 배포

### 비목표 (이번 스코프 아님)
- Wikibase에 쓰기(write-back)
- 실시간 SPARQL 연동 (지난 논의대로, 이번엔 정적 스냅샷 JSON만 사용)
- 다중 작품(Exilée 등) 지원 — 데이터 구조는 나중 확장을 고려해서 설계하되, UI는 Dictée 하나만
- 사용자 인증, 편집 기능

---

## 2. 그래프 라이브러리 선택: Cytoscape.js

### 비교했던 대안들

| 라이브러리 | 장점 | 이 프로젝트에 안 맞는 이유 |
|---|---|---|
| **Cytoscape.js** ✅ | 속성 기반 스타일링(`node[type="Person"]`)이 강력함. 레이아웃 다양. React 래퍼 존재 | 없음 — 채택 |
| react-force-graph | 설정 없이도 물리 시뮬레이션이 예쁘게 나옴, WebGL이라 빠름 | 노드/엣지에 여러 메타데이터(Evidence Type, 신뢰도)를 세밀하게 스타일링하기엔 API가 덜 유연함 |
| D3.js (직접 force-directed) | 완전한 커스터마이징 | 이번 스코프엔 과함 — 직접 짜야 할 보일러플레이트가 너무 많음 |
| vis.js Network | 배우기 쉬움 | 유지보수가 예전만 못하고, 커스텀 스타일링 한계 있음 |

### 채택 이유
- 데이터가 "타입 있는 노드 + predicate 라벨 붙은 방향성 엣지" 구조라 Cytoscape의 스타일시트 문법과 정확히 맞음
- `cose`(물리 기반), `breadthfirst`(계층형), `concentric`(방사형) 레이아웃을 데이터 바꿔가며 바로 실험 가능
- `react-cytoscapejs`로 기존 React+TS 스택에 그대로 통합

---

## 3. 기술 스택

- **React 18 + TypeScript + Vite** (기존 프로젝트들과 동일 스택)
- **Tailwind CSS** (스타일링)
- **cytoscape** + **react-cytoscapejs** (그래프 렌더링)
- **cytoscape-cose-bilkent** (더 나은 force-directed 레이아웃 플러그인, 기본 `cose`보다 결과가 좋음)
- 상태관리는 최소한으로 — React 기본 `useState`/`useMemo`면 충분 (데이터 규모가 작음, 67 노드/수십 엣지)
- 배포: **GitHub Pages** (Vite `base` 설정 + `gh-pages` 패키지 또는 GitHub Actions)

---

## 4. 데이터 파이프라인 (2단계: CSV → 진짜 JSON-LD → Cytoscape용 평면 JSON)

⚠️ **이전 버전 문서는 CSV를 곧바로 Cytoscape용 평면 JSON(`graph.json`)으로 변환했다. 이건 이 그래프 뷰어 하나에는
충분했지만, 프로젝트 원래 목표("CSV를 JSON-LD로 변환해 LOD화")를 만족시키지 못했다 — `graph.json`은 Linked Art
`@context`도, `@id`도 없는 Cytoscape 전용 임시 포맷이라 Wikibase나 다른 LOD 시스템과 상호운용이 안 된다.**
그래서 파이프라인을 두 단계로 나눈다:

```
data/*.csv
   ↓ ① scripts/build-jsonld.py
public/data/graph.jsonld     ← 진짜 JSON-LD (Linked Art @context, @id, dictv: 커스텀 predicate)
                                 이게 프로젝트의 "진짜" 산출물 — 인용·재사용·향후 Wikibase 연동용
   ↓ ② scripts/build-graph-json.py
public/data/graph.json       ← ①을 Cytoscape 전용으로 한 번 더 평평하게 변환한 파생 뷰
                                 이건 순전히 "이 웹페이지 하나를 그리기 위한" 내부용 파일
```

②는 ①의 파생물일 뿐이므로, **②가 CSV를 직접 읽는 일은 없다.** CSV를 아는 코드는 ①에만 존재한다.

### 입력 파일 (프로젝트 `data/` 폴더에 둘 것)
```
data/
├── dictee_entities.csv              ← 67개 엔티티 (Entity ID, Type, prefLabel 등)
├── dictee_relationships.csv         ← 25개 확정 관계 (subject_uri, predicate, object_uri)
├── entity_qid_crosswalk.csv         ← dict_id ↔ Wikibase QID 대조표
└── property_schema_map.csv          ← 연구자가 제공한 공식 predicate 스키마 (P1~P18, 도메인/레인지 정의)
```

---

### 4-1. ① `scripts/build-jsonld.py` — CSV → 진짜 JSON-LD

**컨텍스트**: Linked Art 공식 컨텍스트 + 이 프로젝트 전용 `dictv:` 네임스페이스를 함께 선언.
```json
"@context": [
  "https://linked.art/ns/v1/linked-art.json",
  { "dict": "https://dictee-lod.wikibase.cloud/entity/",
    "dictv": "https://dictee-lod.wikibase.cloud/prop/direct/" }
]
```

**클래스 매핑** (`Type` 컬럼 → `@type`):
| Type | @type |
|---|---|
| Person | `Person` |
| Event | `Period` |
| Concept | `Type` |
| Group | `Group` |
| Object | `HumanMadeObject` (단, `Linked Art Class`가 `LinguisticObject`인 행은 그대로 `LinguisticObject`) |
| Work | `HumanMadeObject`/`LinguisticObject` (CSV의 `Linked Art Class` 컬럼 값을 그대로 사용) |

**Predicate 매핑 — `property_schema_map.csv`의 공식 스키마(P1~P18)를 그대로 따른다.** 이전에 워크북에서 임의로
만들었던 `authorOf`, `allegoricalParallelOf` 같은 predicate는 전부 폐기하고 아래 공식 목록만 쓴다:

| P# | Property | Domain | Range | 비고 |
|---|---|---|---|---|
| P2 | `broader` | Concept | Concept | SKOS 그대로 |
| P4 | `subverts` | Object | Concept |  |
| P5 | `isPartIn` | Person | Chapter |  |
| P6 | `refersTo` | Any | Any | 범용 약한 연결자 |
| P7 | `critiques` | Person | Concept |  |
| P8 | `evidenceType` | Concept | Evidence Type | Concepts CSV(④)의 canonical 값 |
| P9 | `composedOf` | Work | Chapter |  |
| P10 | `creator` | **Work → Person** | | ⚠️ 방향 확정: Work가 주어. 예: `dict:work/dictee --creator--> dict:person/cha-theresa` (Person이 주어가 아님) |
| P11 | `hasNarrator` | Work | Person(Diseuse) |  |
| P12 | `narrates` | Person(Diseuse) | Chapter | P3 `channels`는 DEPRECATED — 이 predicate로 통일 |
| P13 | `hasExchangeableIdentity` | Person | Person | symmetric |
| P14 | `hasPostcolonialParallel` | Event | Event | symmetric. ⚠️ 실제 관계 데이터에 Person↔Person, Object↔Person으로도 쓰인 사례 있음 — 스키마 위반이니 4-1-1 로그에 남기고 값은 그대로 반영 (연구자 판단 대기) |
| P15 | `performsMediation` | Person(Diseuse) | Person | ⚠️ 마찬가지로 Object가 주어인 사례 있음 — 로그만 남기고 반영 |
| P16 | `prefigures` | Any(Object/Concept) | Any(Concept) |  |
| P17 | `silences` | Event/Concept | Person |  |
| P18 | `isRecurrenceOf` | Event | Event |  |

`P1 Evidence Type`, `P3 channels`는 DEPRECATED — 새 JSON-LD에는 만들지 않는다.
스키마에 아예 없는 predicate(`sharesNameWith`, `performsAs`, `mythologicalParallelOf`, `requiresExcavationBy`,
`embodiesPunctuation` 등)는 **버리지 말고 `dictv:` 네임스페이스에 그대로 살려서 넣되**, 4-1-1 로그에
"스키마 미정의 predicate"로 기록한다 — 연구자가 나중에 공식 스키마에 편입할지 결정할 수 있게.

**속성 매핑 (엔티티)**:
| CSV 컬럼 | JSON-LD 속성 |
|---|---|
| `Entity ID` | `@id` (`dict:` 접두어 그대로 유지) |
| `prefLabel (en)`/`(ko)` | `identified_by: [{type:"Name", content, language}]` (⚠️ `(Q18)` 꼬리표는 en/ko 둘 다 정규식으로 제거) |
| `Primary URI` | `equivalent: [{id: ...}]` (Mapping Status가 `matched`/`closeMatch`일 때만) |
| `Definition / Scope Note` | `referred_to_by: [{type:"LinguisticObject", content, classified_as:"description"}]` |
| `Chapter(s)` | `dictv:isPartIn` 배열로 분리 (`ALL`/`—`/`→` 특수 토큰은 4-1-1 로그에 남기고 원문 그대로 보존) |

**도메인/레인지 검증**: 관계 하나를 JSON-LD로 쓰기 전에 subject/object의 실제 `Type`이 위 표의 Domain/Range와
맞는지 검사한다. 안 맞아도 **막지 않고 그대로 반영하되, 반드시 로그에 남긴다** (아래 4-1-1).

**출력**: `public/data/graph.jsonld` — 엔티티는 `@graph` 배열의 노드, 관계는 각 엔티티의 `dictv:{predicate}` 필드로 표현.

---

### 4-1-1. 로깅 + 매칭률 리포트 (①·② 공통 요구사항)

CSV 데이터가 계속 수정되는 중이라 완벽하게 매칭/검증되지 않는 게 정상이다. **매칭 실패, 임의 처리(fallback),
스키마 위반이 한 건이라도 발생하면 절대 조용히 넘어가지 말고, 두 스크립트 모두 아래 두 가지를 남긴다:**

**① 로그 파일** — `logs/build-jsonld-{timestamp}.log.csv` / `logs/build-graph-{timestamp}.log.csv` (스크립트별로 분리)
| 컬럼 | 내용 |
|---|---|
| `source_file` | 어느 CSV에서 발생했는지 |
| `row_number` | 그 CSV의 몇 번째 행인지 |
| `field` | 어느 컬럼에서 문제가 났는지 |
| `raw_value` | 원본 값 그대로 |
| `issue_type` | 문제 종류 (예: "매칭 실패 (dangling reference)", "QID 미확보", "도메인/레인지 스키마 위반", "스키마 미정의 predicate") |
| `detail` | 왜 문제인지 설명 |
| `action_taken` | 코드가 실제로 어떻게 처리했는지 (스킵/null 처리/그대로 반영 등 — 침묵 처리 금지, 반드시 명시) |

**② 터미널 요약** (스크립트 실행 시 항상 출력, 두 스크립트 모두 동일 포맷):
```
========================================================
JSON-LD 빌드 결과 요약 (build-jsonld.py)
========================================================
엔티티 CSV 원본 행:        67건  ->  JSON-LD 노드:  67건  (100.0%)
Wikibase QID 확보:         36건  (53.7%)
--------------------------------------------------------
관계 CSV 원본 행:          25건  ->  JSON-LD 관계:  25건  (100.0%)
  스키마 위반 (반영은 함):  3건  (12.0%)
  스키마 미정의 predicate:  9건  (36.0%)
--------------------------------------------------------
발생한 이슈 총 N건 -> 상세 내용: logs/build-jsonld-20260821-xxxxxx.log.csv
========================================================
graph.jsonld 저장 완료: public/data/graph.jsonld
```
퍼센티지는 항상 "원본 CSV 행 수 대비"로 계산.

**참고 구현**: `scripts/build-graph-json.py`(② 단계, CSV 직접 읽던 구버전)는 이미 이 로깅 요구사항을 반영해서
작성 및 실행 검증까지 마쳤다 (별도 첨부 파일 — 단, ①이 추가되면 이 스크립트는 CSV 대신 `graph.jsonld`를 읽도록
입력만 바꾸면 되고 로깅 로직은 그대로 재사용 가능하다). ①(`build-jsonld.py`)은 이번에 새로 작성해야 한다.

### 4-2. ② `scripts/build-graph-json.py` — graph.jsonld → Cytoscape용 평면 JSON

입력이 CSV 3종에서 **`public/data/graph.jsonld` 하나**로 바뀐다는 것만 구버전과 다르다. 처리 규칙:

1. `graph.jsonld`의 `@graph` 배열을 순회하며 각 노드를 평평한 객체로 변환:
   - `@id` → `id`, `@type` → `group`
   - `identified_by`에서 language별 Name 추출 → `label_en`/`label_ko`
   - `referred_to_by`의 description → `description`
   - `equivalent`가 있으면 QID 추출 → `wikibaseUrl`
2. 각 노드의 `dictv:{predicate}` 필드를 순회하며 엣지 배열 생성 (`source`/`target`/`predicate`)
3. 출력 형식은 구버전과 동일 (`public/data/graph.json`, nodes/edges 배열) — Cytoscape 쪽 코드(`GraphCanvas.tsx`)는 수정 불필요

**실행 순서**: `python3 scripts/build-jsonld.py` → `python3 scripts/build-graph-json.py` → `npm run build`
(둘 다 `npm run build` 전에 수동 실행. 이번 프로토타입에선 순서만 지키면 되고 자동 체이닝은 불필요)

---

## 5. 노드/엣지 시각 스타일

### 노드 색상 (Type별)
| Type | 색상 (Tailwind 기준) | 비고 |
|---|---|---|
| Person | `#3B82F6` (blue-500) | |
| Event | `#EF4444` (red-500) | |
| Concept | `#8B5CF6` (violet-500) | |
| Object | `#F59E0B` (amber-500) | |
| Group | `#10B981` (emerald-500) | |
| Work | `#EC4899` (pink-500) | |

### 엣지 스타일
- 기본: 실선, 화살표 (방향 있음을 명확히)
- `note`에 "Textual" 근거가 명시된 것: 실선 유지
- Evidence Type이 `Modeling`(연구자 해석)인 관계에서 파생된 엣지: **점선** — 원문 직접 근거가 아니라 해석적 연결임을 시각적으로 구분 (지난 논의에서 나온 요구사항)
- 엣지 라벨: predicate 이름을 그대로 표시 (`performsMediation` 등). 너무 길면 hover 시에만 툴팁으로

### 노드 크기
- 연결된 엣지 수(degree)에 비례 — 그래프에서 중심 인물(차학경, 유관순, Diseuse)이 자연스럽게 커 보이게

---

## 6. UI 레이아웃

```
┌─────────────────────────────────────────────────┐
│  Dictée LOD Graph          [필터: Type ▾] [Chapter ▾] [검색 🔍]│
├───────────────────────────────┬───────────────────┤
│                               │                   │
│                               │  선택된 노드/엣지  │
│         Cytoscape 캔버스      │  상세 패널         │
│         (전체 화면 대부분)     │  - 설명           │
│                               │  - Evidence Type  │
│                               │  - Page Ref       │
│                               │  - Wikibase 링크  │
│                               │  (없으면 "미등록") │
└───────────────────────────────┴───────────────────┘
```

- **노드 클릭** → 오른쪽 패널에 `description`, `evidenceType`, `pageReferences`, `wikibaseUrl`(있으면 링크, 없으면 회색 "Wikibase 미등록" 배지) 표시
- **엣지 클릭** → 패널에 `predicate`, `note`, `pageRef`, `status` 표시
- **상단 필터**: Type 체크박스(다중 선택), Chapter 드롭다운 — 선택 시 해당 안 되는 노드/엣지는 `opacity: 0.15`로 흐리게 처리 (완전히 숨기지 않음 — 전체 구조 속 위치 파악용)
- **검색창**: 라벨(en/ko) 부분 일치 시 해당 노드로 카메라 이동 + 하이라이트
- **언어 토글**: en/ko 라벨 전환 버튼 (우측 상단)

---

## 7. 폴더 구조

```
dictee-graph/
├── data/
│   ├── dictee_entities.csv
│   ├── dictee_relationships.csv
│   ├── entity_qid_crosswalk.csv
│   └── property_schema_map.csv
├── scripts/
│   ├── build-jsonld.py         ← ① CSV → graph.jsonld (진짜 JSON-LD, 이번에 새로 작성)
│   └── build-graph-json.py     ← ② graph.jsonld → graph.json (Cytoscape용, 입력만 CSV에서 jsonld로 교체)
├── public/
│   └── data/
│       ├── graph.jsonld        ← ①의 산출물 — 프로젝트의 "진짜" 결과물, git에 커밋
│       └── graph.json          ← ②의 산출물 — 그래프 뷰어 전용 파생 파일, git에 커밋 (GitHub Pages가 서빙)
├── src/
│   ├── components/
│   │   ├── GraphCanvas.tsx     ← Cytoscape 래핑
│   │   ├── DetailPanel.tsx
│   │   ├── FilterBar.tsx
│   │   └── SearchBox.tsx
│   ├── lib/
│   │   ├── graphStyles.ts      ← Cytoscape stylesheet (타입별 색상 등, 5번 섹션 그대로)
│   │   └── types.ts            ← GraphNode, GraphEdge 타입 정의
│   ├── App.tsx
│   └── main.tsx
├── vite.config.ts              ← base: '/dictee-graph/' 설정 필수 (GitHub Pages 서브패스)
└── CLAUDE.md                   ← 이 문서
```

---

## 8. 알려진 데이터 이슈 (구현 시 방어적으로 처리할 것)

지금까지 대화에서 실제로 발견된 이슈들 — 코드가 이것 때문에 죽지 않게 할 것:

1. **`prefLabel`의 `(Q##)` 꼬리표가 en/ko 컬럼에 불규칙하게 분산되어 있음** — 라벨 정제 시 반드시 en/ko 둘 다 정규식 검사
2. **양방향 중복 관계 존재** (예: Tanam Press↔Dictée가 양쪽에서 다 관계로 잡힘) — 렌더링 시 같은 두 노드 사이 화살표가 겹쳐 보일 수 있음. Cytoscape의 `curve-style: bezier` + 다중 엣지 간격 옵션으로 시각적으로 구분되게 처리
3. **관계 CSV의 URI 필드에 개행 문자가 낀 행이 있었음** (15번째 행) — CSV 파싱 시 원본 재확인 필요, 파싱 실패 시 해당 행 스킵 + 콘솔 경고
4. **67개 중 8개 엔티티는 아직 Wikibase QID가 없음** (crosswalk CSV의 `우선확인대상=O`) — 상세 패널에서 이 경우 링크 대신 "Wikibase 미등록" 배지 표시, 에러 아님
5. **관계 CSV 25건 외에, 라벨매칭으로 뽑은 추가 후보(33건, 연구자 미검수)가 있음** — 이번 프로토타입에는 **포함하지 않는다.** 확정된 25건만 사용. (나중 단계에서 검수 끝나면 추가)

---

## 9. 구현 단계 (Claude Code 작업 순서)

1. Vite + React + TS + Tailwind 프로젝트 스캐폴딩, `cytoscape`/`react-cytoscapejs`/`cytoscape-cose-bilkent` 설치
2. `scripts/build-graph-json.py` 작성 및 실행 → `public/data/graph.json` 생성 확인 (노드 67개, 엣지 25개 이하로 나와야 정상 — 4번 이슈로 인해 스킵되는 엣지가 있을 수 있음)
3. `GraphCanvas.tsx`: graph.json을 fetch해서 Cytoscape에 로드, 기본 스타일시트 적용 (타입별 색상)
4. `DetailPanel.tsx`: 노드/엣지 클릭 이벤트 연결
5. `FilterBar.tsx`, `SearchBox.tsx` 순서로 추가
6. `vite.config.ts`에 `base` 설정 후 `npm run build` 로컬 확인
7. GitHub Actions로 `gh-pages` 브랜치 자동 배포 설정 (또는 `gh-pages` npm 패키지로 수동 배포부터 시작해도 무방)

---

## 10. 다음 단계 (이번 스코프 밖, 참고용)

- 검수된 라벨매칭 후보 관계 추가
- Evidence Type/신뢰도 기반 엣지 필터
- Wikibase SPARQL 스냅샷 동기화 스크립트 연결 (지난 논의의 `sync_from_wikibase.py`)
- 다중 작품 확장 시 `documentedIn` 필드로 작품별 필터 추가