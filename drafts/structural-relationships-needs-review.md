# 구조적 관계 검토 리스트 (2026-09-21)

`data/dictee_relationships.csv` 27건 중 `creator`, `hasNarrator`, `hasFamilyRelation` predicate는
0번 쓰였습니다 — 스키마(`property_schema_map.csv`)엔 정의돼 있지만 실제 관계 행이 한 번도 없어서
Dictée(Work) 자체와 Cha 가족 3명이 그래프에서 완전히 고립돼 있습니다.

이 파일은 **파이프라인이 읽는 파일이 아닙니다** — 검토용 초안입니다. 아래 표에서 확정한 행만
`data/dictee_relationships.csv`에 옮겨 넣으면(같은 컬럼 순서: 빈칸/relationship_property_uri/object_uri/page_ref/note)
다음 `python3 scripts/build-jsonld.py` 실행 때 반영됩니다.

---

## 1. creator — Dictée의 저자

| subject | predicate | object | page_ref | note |
|---|---|---|---|---|
| `dict:work/dictee` | `dict:rel/creator` | `dict:person/cha-theresa` | ? | ? |

- 스키마상 방향은 **Work→Person 확정**(`dct:creator`)이라 이 방향은 검토 불필요.
- **필요한 것**: `page_ref`(보통 표지/판권 페이지 등 근거 없이도 괜찮다면 공란 가능)와 `note`(예: "1982년 유작 출간"처럼 텍스트적 근거).

## 2. hasNarrator — Dictée의 서사자

| subject | predicate | object | page_ref | note |
|---|---|---|---|---|
| `dict:work/dictee` | `dict:rel/hasNarrator` | `dict:person/diseuse` | ? | ? |

⚠️ **주의**: `cha-theresa` 엔티티 자신의 Definition에 "Not singular narrator but dispersed across
Diseuse and multiple women's voices"라고 명시돼 있습니다. 즉 "Diseuse가 유일한 서사자"라는 단순한
이항 관계로 표현하는 게 연구자의 이론적 입장과 맞는지부터 확인이 필요합니다 — 제가 임의로 넣을 수
없는 판단입니다.

- **필요한 것**: (a) 이 관계를 정말 추가할지 여부, (b) 추가한다면 object가 `diseuse` 하나로 충분한지
  아니면 다른 "voices" 엔티티도 같이 걸어야 하는지, (c) page_ref/note.

## 3. hasFamilyRelation — Cha 가족

현재 가족 엔티티 4명: `cha-theresa`(본인), `huh-hyungsoon`(어머니, 이미 다른 엣지로 연결됨),
`cha-hyungsang`(아버지, 고립), `cha-haksang`(오빠 John Hak Sung Cha, 고립).

| subject | predicate | object | page_ref | note | 비고 |
|---|---|---|---|---|---|
| `dict:person/cha-theresa` | `dict:rel/hasFamilyRelation` | `dict:person/huh-hyungsoon` | ? | ? | 모녀 |
| `dict:person/cha-theresa` | `dict:rel/hasFamilyRelation` | `dict:person/cha-hyungsang` | ? | ? | 부녀 |
| `dict:person/cha-theresa` | `dict:rel/hasFamilyRelation` | `dict:person/cha-haksang` | ? | ? | 남매 |

- `hasFamilyRelation`은 symmetric이고 관계 종류(부녀/모녀/남매)를 구분하는 하위 속성이 스키마에 없습니다
  — 필요하면 `note`에 자유서술로 적는 정도만 가능합니다.
- **필요한 것**: 위 3행을 전부 넣을지, 아니면 텍스트에 실제로 언급된 관계만 선별해서 넣을지(예: 아버지의
  서예가 텍스트에 직접 인용되니 부녀 관계는 명확하지만, 오빠의 4·19 참여는 `dict:event/cha-family-exile-1962`
  Event를 매개로 간접 언급되는 정도라 Person-Person 직접 관계로 넣는 게 맞는지)와 각 행의 page_ref/note.
- 부모(huh-hyungsoon)↔아버지(cha-hyungsang), 부모↔오빠(cha-haksang) 같은 나머지 조합도 추가할지는
  별도로 확인 부탁드립니다 — 일단 표에는 "cha-theresa 기준" 3행만 후보로 넣었습니다.

## 참고: 가족 관계가 아닌 별도 이슈

- `dict:person/gertrud`도 현재 고립 노드지만 **Cha 가족이 아닙니다** — Dreyer 영화 《Gertrud》(1964)의
  등장인물입니다. "unhappy marriage" 서사가 텍스트에서 참조된다고 하니, `mythologicalParallelOf`나
  `hasPostcolonialParallel` 같은 다른 predicate로 다룰 후보로 보이지만 이건 이번 "구조적 관계" 리스트와는
  성격이 달라 별도로 다뤄야 할 것 같습니다.
