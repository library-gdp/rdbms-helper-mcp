# DB Graph JSON 형식 (format_version 1)

ERD 하나(= database 하나)를 그래프 하나로 표현한다. 그래프 하나는 JSON 파일 하나다.

- 저장 위치: 작업 디렉터리 기준 `.rdb-info/dbgraph/{graph_name}.json`
- Vertex = 테이블, Edge = 테이블 간 논리적 관계
- 저장은 항상 `scripts/dbgraph_write.py`로 한다. 이 스크립트가 아래 규칙을 검증하고 정규화한다.

## 전체 구조

```json
{
  "format_version": 1,
  "graph_name": "company",
  "source": {
    "format": "mermaid",
    "files": ["docs/company-erd.mmd"],
    "description": null
  },
  "vertices": [ /* Vertex */ ],
  "edges": [ /* Edge */ ],
  "notes": []
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `format_version` | `1` | 이 문서의 형식 버전. 항상 `1` |
| `graph_name` | string | 그래프 이름 = 입력 ERD가 나타내는 database 이름. `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. 파일 이름이 된다 |
| `source.format` | string | `mermaid`, `drawio`, `pptx`, `image`, `pdf`, `sql-ddl`, `dbml`, `plantuml`, `text`, `other` 중 하나 |
| `source.files` | string[] | 입력 파일 경로(작업 디렉터리 기준 상대 경로). 채팅에 붙여 넣은 입력이면 `[]` |
| `source.description` | string \| null | 입력에 대한 보충 설명(예: "ppt 3–5쪽의 ERD") |
| `notes` | string[] | 그래프 전체에 대한 가정·누락·모호점. 없으면 `[]` |

## Vertex (테이블)

```json
{
  "id": "employee",
  "table": "employee",
  "schema": null,
  "description": "직원",
  "columns": [
    {
      "name": "id",
      "type": "bigint",
      "nullable": false,
      "primary_key": true,
      "unique": false,
      "foreign_key": false,
      "default": null,
      "description": null
    }
  ]
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 그래프 안에서 유일한 식별자. `schema`가 있으면 `"{schema}.{table}"`, 없으면 `table`과 같다 |
| `table` | string | ERD에 적힌 물리 테이블 이름을 그대로 쓴다(대소문자 유지) |
| `schema` | string \| null | DB schema(namespace). ERD에 없으면 `null` |
| `description` | string \| null | 논리명·주석 등 |
| `columns` | Column[] | ERD에 나타난 순서대로. ERD에 column이 없으면 `[]`이고 `notes`에 적는다 |

### Column

| 필드 | 타입 | 설명 |
|---|---|---|
| `name` | string | column 이름. vertex 안에서 유일 |
| `type` | string \| null | ERD에 적힌 데이터 타입 문자열 그대로(예: `varchar(255)`). 없으면 `null` |
| `nullable` | boolean \| null | ERD가 NULL 허용 여부를 표시할 때만 true/false. 표시가 없으면 `null`. PK column은 `false` |
| `primary_key` | boolean | PK(복합 PK의 일부 포함) |
| `unique` | boolean | ERD에 UNIQUE/UK로 **명시된** 경우만 true. PK라는 이유만으로 true로 하지 않는다 |
| `foreign_key` | boolean | ERD에 FK로 표시되었거나 어떤 edge의 `source_columns`에 포함되면 true |
| `default` | string \| null | 기본값 표현식 문자열. 없으면 `null` |
| `description` | string \| null | 논리명·주석 |

모르는 값은 추측하지 말고 `null`(boolean 필드 `primary_key`/`unique`/`foreign_key`는 `false`)로 둔다.

## Edge (관계)

```json
{
  "id": "employee.department_id->department.id",
  "source": "employee",
  "target": "department",
  "source_columns": ["department_id"],
  "target_columns": ["id"],
  "cardinality": {
    "source": { "min": 0, "max": "many" },
    "target": { "min": 1, "max": "one" }
  },
  "relationship": "many-to-one",
  "identifying": false,
  "label": "belongs to",
  "assumptions": []
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 그래프 안에서 유일. 생략하면 스크립트가 만든다(아래 규칙) |
| `source` | string | 참조하는 쪽(FK를 가진 자식 테이블)의 vertex `id` |
| `target` | string | 참조되는 쪽(부모 테이블)의 vertex `id` |
| `source_columns` | string[] | source의 FK column들. ERD에서 알 수 없으면 `[]` |
| `target_columns` | string[] | target의 참조 대상 column들(보통 PK). `source_columns`와 길이가 같아야 한다. 모르면 `[]` |
| `cardinality` | object | 양 끝의 다중도(아래) |
| `relationship` | string | `one-to-one`, `one-to-many`, `many-to-one`, `many-to-many`. `cardinality`에서 파생되며 스크립트가 다시 계산한다 |
| `identifying` | boolean \| null | 식별 관계(FK가 자식 PK의 일부)면 true, 비식별이면 false, 모르면 `null` |
| `label` | string \| null | ERD에 적힌 관계 이름 |
| `assumptions` | string[] | 이 edge에서 ERD에 명시되지 않아 추론한 내용. 없으면 `[]` |

### 방향 규칙

- FK가 어느 쪽에 있는지 알 수 있으면 FK를 가진 쪽이 `source`다.
- FK 위치를 모르면: 한쪽 max가 `many`이고 다른 쪽이 `one`이면 `many` 쪽이 `source`다. 1:1이나 N:M처럼 판단할 수 없으면 ERD에 그려진 순서(왼쪽/시작점)를 `source`로 하고 `assumptions`에 적는다.
- 자기 참조(`source == target`)도 허용한다.

### Cardinality 의미

crow's foot 표기와 같은 의미다. 각 끝의 값은 **반대쪽 한 행에 연결될 수 있는 그 끝 테이블의 행 수**다.

- `cardinality.source` = target 한 행에 연결되는 source 행의 수
- `cardinality.target` = source 한 행에 연결되는 target 행의 수
- `min`: `0`(선택) 또는 `1`(필수). ERD가 최솟값을 표시하지 않으면 `null`
- `max`: `"one"` 또는 `"many"`. 반드시 정해야 한다. ERD에서 읽을 수 없으면 사용자에게 확인한다

예: 부서 1 — 직원 N, 직원은 반드시 부서에 속하고 부서에는 직원이 없을 수도 있다.

```text
source = employee, target = department
cardinality.source = { min: 0, max: "many" }   # 부서 하나에 직원 0..N
cardinality.target = { min: 1, max: "one" }    # 직원 하나에 부서 정확히 1
relationship = "many-to-one"
```

`relationship`은 `"{source.max}-to-{target.max}"`이다(`one`/`many`).

표기별 변환:

| 표기 | min | max |
|---|---|---|
| crow's foot `\|\|` / mermaid `\|\|` / draw.io `ERmandOne` | 1 | one |
| `o\|` `\|o` / `ERzeroToOne` | 0 | one |
| `\|{` `}\|` / `ERoneToMany` | 1 | many |
| `o{` `}o` / `ERzeroToMany` | 0 | many |
| draw.io `ERone` (막대 하나) | null | one |
| draw.io `ERmany` (까마귀발만) | null | many |
| `1`, `0..1`, `1..*`, `0..*`, `N`, `M`, `*` (UML/Chen) | `1`→1/one, `0..1`→0/one, `1..*`→1/many, `0..*`·`*`→0/many, `N`·`M`→null/many |

FK column의 `nullable`이 명시되어 있으면 `cardinality.target.min`과 맞춘다(`nullable: false` → 1, `true` → 0). 충돌하면 ERD의 관계 표기를 따르고 `assumptions`에 적는다.

### N:M 관계

- ERD에 교차(junction) 테이블이 있으면 교차 테이블을 vertex로 두고 각 부모와의 N:1 edge 두 개로 표현한다.
- ERD가 교차 테이블 없이 N:M 선만 그렸으면 `many-to-many` edge 하나로 두고 `source_columns`/`target_columns`는 `[]`로 둔다.

### Edge id 생성 규칙

`id`를 생략하면 스크립트가 다음과 같이 만든다.

- column을 알 때: `"{source}.{c1,c2}->{target}.{c1,c2}"`
- 모를 때: `"{source}->{target}"`, label이 있으면 `"{source}->{target}:{label}"`
- 중복되면 뒤에 `#2`, `#3`을 붙인다.

## 정규화 (스크립트가 수행)

- `vertices`는 `id` 순, `edges`는 `id` 순으로 정렬한다. column 순서는 유지한다.
- `relationship`을 `cardinality`에서 다시 계산한다.
- edge의 `source_columns`에 포함된 column은 `foreign_key: true`로 바꾼다.
- 생략된 선택 필드는 기본값(`null`, `false`, `[]`)으로 채운다.
- 출력은 UTF-8, 2칸 들여쓰기, 비ASCII 문자를 escape하지 않는다.
