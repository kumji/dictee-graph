# CLAUDE.md — Dictée LOD 인터랙티브 그래프 (GitHub Pages 테스트 프로토타입)

## 0. 이 문서의 목적

지금까지 정리한 Dictée 엔티티(67개)·관계(25건 확정 + 라벨매칭 후보) 데이터를
**GitHub Pages에 띄우는 최소 기능 인터랙티브 그래프**로 시각화하는 테스트 프로젝트의 스펙이다.
이 문서를 CLAUDE.md로 두고 바이브 코딩(Claude Code)으로 구현한다.

**이건 프로토타입이다.** Wikibase 반영, 다중 작품 확장, 실시간 동기화는 이번 스코프에 없다.
지금 가진 정적 CSV 스냅샷으로 "그래프가 실제로 어떻게 보이는지" 빠르게 확인하는 게 목표다.
원본 데이터를 임의로 처리하게 되는 경우에 output log 파일을 생성해서 추후에 데이터를 보완하거나 연구자와 논의 후 의도대로 처리할 수 있도록 기록한다.
터미널에 원본 데이터가 그대로 매칭된 확률을 보여줘서 데이터 정합성과 진척사항을 알 수 있도록 한다.

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

## 4. 데이터 파이프라인 (빌드 타임에 CSV → JSON 변환)

이 프로젝트는 CSV를 런타임에 파싱하지 않는다. **빌드 전에 Node/Python 스크립트로 `public/data/graph.json` 하나를 미리 만들어둔다.**
이유: CSV 파싱 로직을 브라우저에 넣으면 번들이 커지고, 데이터 정제(중복 제거, 방향 정리, dangling reference 처리)를 매번 클라이언트에서 할 이유가 없다.

### 입력 파일 (프로젝트 `data/` 폴더에 둘 것)
```
data/
├── dictee_entities.csv              ← 67개 엔티티 (Entity ID, Type, prefLabel 등)
├── dictee_relationships.csv         ← 25개 확정 관계 (subject_uri, predicate, object_uri)
└── entity_qid_crosswalk.csv         ← dict_id ↔ Wikibase QID 대조표 (이미 만들어둔 것)
```

### 변환 스크립트: `scripts/build-graph-json.py`

**처리 규칙 (반드시 이대로 구현할 것):**

1. **엔티티 로딩**
   - `Entity ID` → node `id` (예: `dict:person/cha-theresa`)
   - `Type` → node `group` (색상 매핑에 사용)
   - `prefLabel (en)`, `prefLabel (ko)` → node `label_en`, `label_ko` (⚠️ `(Q18)` 같은 꼬리표는 정규식으로 제거 — `en`/`ko` 양쪽 다 확인할 것, 지난번 이 부분에서 실제로 버그가 났었음)
   - `Definition / Scope Note` → node `description`
   - `Evidence Type`, `Page References`, `Chapter(s)` → node의 부가 필드로 유지
   - crosswalk CSV에서 QID 조회 → 있으면 `wikibaseUrl: "https://dictee-lod.wikibase.cloud/wiki/Item:Q{n}"` 필드 추가 (없으면 `null`, UI에서 "Wikibase 미등록"으로 표시)

2. **관계 로딩**
   - `subject_uri`/`object_uri`에서 `/id/` 뒤 슬러그만 추출 (`person/cha-theresa`)
   - 이 슬러그에 `dict:` 접두어를 붙여서 엔티티의 `id`와 매칭
   - **매칭 실패(dangling reference)는 에러를 던지지 말고 콘솔에 경고만 출력하고 해당 엣지는 스킵할 것** — 데이터가 계속 수정되는 중이라 완벽하지 않을 수 있음
   - `relationship_property_uri`의 마지막 세그먼트(`performsMediation` 등) → edge `predicate`
   - `page_ref`, `note`, `STATUS` → edge의 부가 필드로 유지

3. **출력 형식** (`public/data/graph.json`):
```json
{
  "generatedAt": "2026-08-21T00:00:00Z",
  "nodes": [
    {
      "id": "dict:person/cha-theresa",
      "label_en": "Theresa Hak Kyung Cha",
      "label_ko": "차학경",
      "group": "Person",
      "description": "Author (1951-1982). Born Busan during Korean War...",
      "evidenceType": "Biographical",
      "pageReferences": "Entire work",
      "chapters": ["ALL"],
      "wikibaseUrl": "https://dictee-lod.wikibase.cloud/wiki/Item:Q18"
    }
  ],
  "edges": [
    {
      "source": "dict:person/cha-theresa",
      "target": "dict:person/therese-lisieux",
      "predicate": "sharesNameWith",
      "pageRef": "ERATO",
      "note": "Cha explores multiple Theresa/Thérèse figures...",
      "status": "ORIGINAL"
    }
  ]
}
```

4. **실행 방법**: `python3 scripts/build-graph-json.py` — `npm run build` 전에 수동 실행 (또는 `package.json`의 `prebuild` 훅에 연결, 이번 프로토타입에선 수동 실행으로 충분)

### 4-1. 매칭 실패 로깅 + 매칭률 리포트 (필수 요구사항)

CSV 데이터가 계속 수정되는 중이라 완벽하게 매칭되지 않는 게 정상이다. **매칭 실패나 임의 처리(fallback)가
한 건이라도 발생하면 절대 조용히 넘어가지 말고, 아래 두 가지를 반드시 남긴다:**

**① 로그 파일 (`logs/build-graph-{timestamp}.log.csv`)**
매칭 실패·fallback이 발생할 때마다 한 행씩 기록. 컬럼:
| 컬럼 | 내용 |
|---|---|
| `source_file` | 어느 CSV에서 발생했는지 (`dictee_entities.csv` 등) |
| `row_number` | 그 CSV의 몇 번째 행인지 (사람이 원본 파일 열어서 바로 찾을 수 있게) |
| `field` | 어느 컬럼에서 문제가 났는지 |
| `raw_value` | 원본 값 그대로 (가공하지 않은 값) |
| `issue_type` | 문제 종류 (예: "매칭 실패 (dangling reference)", "QID 미확보", "URI 필드 내 개행 문자") |
| `detail` | 왜 문제인지 설명 |
| `action_taken` | 코드가 실제로 어떻게 처리했는지 (스킵/null 처리 등 — 침묵 처리 금지, 반드시 명시) |

**② 터미널 요약 (스크립트 실행 시 항상 출력)**
```
========================================================
그래프 빌드 결과 요약
========================================================
엔티티 CSV 원본 행:      67건
  -> 그래프 노드로 변환:  67건  (100.0%)
  -> Wikibase QID 확보:  36건  (53.7%)
--------------------------------------------------------
관계 CSV 원본 행:        25건
  -> 그래프 엣지로 변환:  25건  (100.0%)
  -> 매칭 실패/스킵:      0건  (0.0%)
--------------------------------------------------------
발생한 이슈 총 32건 -> 상세 내용: logs/build-graph-20260821-050709.log.csv
========================================================
graph.json 저장 완료: public/data/graph.json
```
퍼센티지는 항상 "원본 CSV 행 수 대비"로 계산 (그래프에 실제 반영된 것 기준으로 나누면 분모가 왜곡됨).

**참고 구현**: `scripts/build-graph-json.py`는 이미 이 로깅 요구사항을 반영해서 작성해뒀다 (별도 첨부 파일).
실제 데이터로 실행 검증 완료: 엔티티 100%, 관계 100% 매칭, QID 확보 53.7% (31개 엔티티가 아직 Wikibase 미등록 —
이건 코드 버그가 아니라 실제 데이터 상태이며, 로그에 전부 개별 기록됨).

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
│   └── entity_qid_crosswalk.csv
├── scripts/
│   └── build-graph-json.py
├── public/
│   └── data/
│       └── graph.json          ← 빌드 스크립트 산출물 (git에 커밋해서 GitHub Pages가 바로 서빙)
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
