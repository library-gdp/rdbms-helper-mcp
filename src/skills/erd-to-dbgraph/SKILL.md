---
name: erd-to-dbgraph
description: 사용자가 제공한 ERD(Mermaid erDiagram, draw.io, PowerPoint, 이미지/PDF, SQL DDL, DBML, PlantUML 등)를 파싱해 테이블=Vertex, 관계=Edge(cardinality 포함)인 DB 그래프 JSON으로 `.rdb-info/dbgraph/{graph_name}.json`에 저장한다. Use when the user gives an ERD or schema diagram and asks to parse, import, register, or convert it into a graph ("이 ERD 파싱해서 그래프로 저장해줘", "ERD를 dbgraph로"). Do NOT use for querying or editing an already-saved graph, for generating an ERD from a live database, or for drawing a new ERD.
compatibility: Requires python3 (3.9+, standard library only) for the bundled scripts.
metadata:
  output: .rdb-info/dbgraph/{graph_name}.json
  format_version: "1"
---

# ERD → DB Graph

사용자가 준 ERD 하나를 database 하나의 그래프로 바꿔 JSON 파일 하나로 저장한다.

- Vertex = 테이블(column 정보 포함), Edge = 테이블 간 논리적 관계(cardinality 포함)
- 그래프 이름(`graph_name`) = ERD가 나타내는 database 이름 (예: 사내 시스템 DB → `company`)
- 저장 위치: 작업 디렉터리 기준 `.rdb-info/dbgraph/{graph_name}.json`

## 반드시 먼저 읽을 파일

이 skill의 supporting file은 자동으로 읽히지 않는다. 아래 순서로 직접 읽는다(경로는 skill base 디렉터리 기준).

1. `references/graph-format.md` — 출력 JSON 형식, cardinality 의미, edge 방향 규칙. **항상 읽는다.**
2. `references/input-formats.md` — 입력 형식별 해석 방법과 사용자 확인 기준. Mermaid 외 입력이면 반드시 읽는다.

## 스크립트

모두 `python3`, 표준 라이브러리만 쓴다. 실행 경로는 `<skill-base>/scripts/...`.

| 스크립트 | 역할 |
|---|---|
| `scripts/parse_mermaid.py INPUT [--graph-name NAME]` | Mermaid `erDiagram` → draft 그래프 JSON(stdout) |
| `scripts/extract_drawio.py INPUT [--page P]` | draw.io 파일의 shape·connector·ER marker를 구조화 JSON으로 추출 |
| `scripts/extract_pptx.py INPUT [--slides S] [--media-dir D]` | pptx의 텍스트 상자·표·connector·그림을 구조화 JSON으로 추출 |
| `scripts/dbgraph_write.py [DRAFT\|-] [--check] [--overwrite]` | draft를 검증·정규화해 `.rdb-info/dbgraph/{graph_name}.json`에 저장 |

`dbgraph_write.py` 종료 코드: `0` 성공(stdout에 요약 JSON), `1` 검증 실패(stderr에 `경로: 이유` 목록), `2` 입력을 읽지 못함, `3` 파일이 이미 있음.

## 절차

### 1. 입력 확인

- ERD가 파일인지(경로·확장자), 채팅에 붙여 넣은 텍스트인지, 이미지인지 확인한다.
- ERD를 받지 못했으면 요청하고 멈춘다. 지원하지 않는 형식(`.ppt`, `.drawio.png` 등)이면 `references/input-formats.md`의 변환 안내를 따른다.

### 2. 그래프 이름 결정

- ERD 제목, 파일 이름, schema 이름, 사용자의 설명에서 database 이름을 찾는다.
- 확실하지 않으면 후보를 제시하고 사용자에게 확인한다. 추측한 이름으로 저장하지 않는다.
- 형식: `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. 공백·한글 등은 사용자와 합의해 바꾼다.
- `.rdb-info/dbgraph/{graph_name}.json`이 이미 있으면 덮어쓸지 사용자에게 확인한다.

### 3. 추출 → draft 작성

`references/input-formats.md`의 해당 절을 따른다.

- **Mermaid**: `parse_mermaid.py`로 draft를 만든 뒤 draft의 `notes`와 빈 `source_columns`를 검토해 보완한다.
- **draw.io / pptx**: 추출기 JSON을 해석해 draft를 직접 작성한다.
- **이미지 / PDF / DDL / DBML / PlantUML / 기타**: 원본을 읽고 draft를 직접 작성한다.

draft는 `references/graph-format.md`의 형식을 따른다. 작성 규칙:

- ERD에 없는 정보는 `null`(또는 `false`/`[]`)로 둔다. 지어내지 않는다.
- 추론한 값은 edge `assumptions` 또는 그래프 `notes`에 근거와 함께 남긴다.
- cardinality의 `max`(`one`/`many`)는 반드시 정한다. ERD에서 읽을 수 없으면 사용자에게 확인한다.
- `relationship`과 edge `id`는 생략해도 된다(스크립트가 계산한다).

### 4. 검증 후 저장

draft를 임시 파일에 쓰고(작업 디렉터리 밖, 예: `mktemp`로 만든 경로) 먼저 검증만 한다.

```bash
python3 <skill-base>/scripts/dbgraph_write.py /tmp/draft.json --check
```

- 종료 코드 `1`이면 stderr의 각 오류(`$.edges[2].target: unknown vertex ...` 형식)를 고쳐 다시 실행한다. ERD를 다시 확인해야 하는 오류면 원본을 다시 본다.
- 통과하면 `--check` 없이 실행해 저장한다. 2단계에서 덮어쓰기를 승인받은 경우에만 `--overwrite`를 붙인다.
- 작업 디렉터리가 프로젝트 루트가 아니면 `--root <프로젝트 루트>`를 준다.

### 5. 보고

사용자에게 다음을 알린다.

- 저장 경로, 테이블 수, 관계 수
- 스크립트 요약의 `warnings`(column 없는 테이블, 관계 없는 테이블, edge에 쓰이지 않은 FK 등)
- `assumptions`와 `notes`에 남긴 추론·누락 사항 — 사용자가 확인·수정할 수 있도록 목록으로

## 하지 않는 일

- ERD에 없는 테이블·column·관계를 실제 DB나 다른 문서에서 가져와 섞지 않는다. 필요하면 사용자에게 제안만 한다.
- `.rdb-info/dbgraph/` 밖에 결과를 쓰지 않는다. 임시 파일은 끝나면 지운다.
- 저장된 JSON을 손으로 고치지 않는다. 수정이 필요하면 draft를 고쳐 `dbgraph_write.py`로 다시 저장한다.
