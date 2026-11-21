# 입력 형식별 해석 가이드

공통 원칙

- ERD에 **보이는 것만** 옮긴다. 보이지 않는 column, 타입, NULL 여부, 관계를 지어내지 않는다.
- 결정적으로 추출할 수 있는 형식은 먼저 `scripts/`의 추출기를 실행하고 그 JSON을 해석한다. 원본 XML·텍스트를 직접 읽어 추측하지 않는다.
- 해석으로 채운 값은 edge의 `assumptions` 또는 그래프의 `notes`에 근거와 함께 적는다.
- 아래 "사용자 확인" 항목에 해당하면 저장 전에 묻는다.

스크립트 경로는 skill base 디렉터리 기준이다. 예: `python3 <skill-base>/scripts/extract_drawio.py erd.drawio`

## Mermaid (`erDiagram`)

- 파일(`.mmd`, `.md`) 또는 채팅의 코드 블록. 채팅 입력은 stdin(`-`)으로 넘긴다.
- `scripts/parse_mermaid.py INPUT --graph-name NAME`이 draft 그래프를 바로 만든다. `--graph-name`을 생략하면 front matter의 `title`을 쓴다.
- 파서가 하는 일: entity·attribute(`PK`/`FK`/`UK`, 주석), 관계 기호(`||`, `|o`, `}o`, `}|` 등)와 별칭(`one or more`, `zero or one`, `to`/`optionally to`), 실선 `--` = 식별 관계, 점선 `..` = 비식별 관계.
- 파서가 못 하는 일과 후속 처리:
  - draft의 `notes`에 `unparsed line`이 있으면 원문을 보고 반영하거나 사용자에게 알린다.
  - FK column은 `{부모테이블}_{PK}` 등 이름이 하나로 맞을 때만 추론한다. 자기 참조(`manager_id`)나 이름이 다른 FK는 `source_columns`/`target_columns`가 `[]`로 남는다. FK로 표시된 column과 부모 PK가 명확히 대응되면 채우고 `assumptions`에 적는다.
  - Mermaid에는 NULL 여부와 schema가 없다. `nullable`은 `null`로 둔다(PK는 스크립트가 `false`로 채운다).
  - entity alias(`EMP["직원"]`)는 `description`으로 들어간다.

## draw.io (`.drawio`, `.xml`, `.drawio.svg`)

1. `scripts/extract_drawio.py INPUT`을 실행한다. 압축된 페이지도 풀어 준다. 페이지가 여럿이면 `--page`로 고르거나 각 페이지가 무엇인지 사용자에게 확인한다.
2. 결과의 `shapes`에서 테이블을 찾는다. 흔한 형태:
   - **ER 테이블 shape** (`shape: table` 또는 swimlane 컨테이너): 컨테이너의 `text`가 테이블 이름이고, `parent`가 그 컨테이너인 자식 shape들이 column 행이다. 행 안에 다시 셀(`PK`/`FK` 표시 칸, 이름 칸, 타입 칸)이 자식으로 있으면 `geometry.x` 순서로 이어 붙여 한 column으로 본다.
   - **HTML 라벨 하나에 표 전체**: `text`에 줄바꿈과 탭으로 행·칸이 나뉘어 있다. 첫 줄이 테이블 이름이다.
   - **`shape: ext` 등 일반 상자 + 텍스트**: 텍스트의 첫 줄을 테이블 이름, 나머지를 column으로 본다.
3. `edges`로 관계를 만든다. 끝점이 column 행에 붙어 있으면 `source_top_level`/`target_top_level`이 테이블 컨테이너 id다. column 행에 붙은 끝점은 그 column이 FK/PK라는 근거로 쓴다.
4. cardinality: `start_marker`는 source 끝, `end_marker`는 target 끝에 그려진 표시이며 각각 그 끝 테이블의 다중도다(이미 `min`/`max`로 해석되어 있다). marker가 없고 `labels`에 `1`, `N`, `0..1` 같은 글자가 있으면 위치상 가까운 끝에 대응시킨다. 판단할 수 없으면 사용자에게 확인한다.
5. `dashed: true`는 보통 비식별 관계다. 범례가 다르면 범례를 따른다.
6. `.drawio.png`는 지원하지 않는다. `.drawio` 또는 `.svg`로 내보내 달라고 하거나, 이미지로 처리한다.

## PowerPoint (`.pptx`)

1. `scripts/extract_pptx.py INPUT --media-dir <임시 디렉터리>`를 실행한다. ERD가 일부 슬라이드에만 있으면 `--slides`로 좁힌다.
2. 테이블 후보: `tables`(PowerPoint 표, 보통 첫 행 또는 표 위 텍스트 상자가 테이블 이름)와 `shapes`(첫 문단이 이름, 이후 문단이 column). 그룹(`group`)으로 묶인 텍스트 상자들이 하나의 테이블일 수 있다. `geometry`가 겹치거나 인접한 것을 함께 본다.
3. 관계: `connectors`의 `start_shape`/`end_shape`가 연결된 shape id다. 연결되지 않은 선(`null`)은 `geometry`의 시작·끝 좌표(flip 반영)에 가장 가까운 테이블로 대응시키고 `assumptions`에 적는다.
4. PowerPoint 선 끝(`head_end`/`tail_end`: `triangle`, `arrow`, `oval`, `diamond` 등)에는 crow's foot이 없다. 선 근처 텍스트 상자의 `1`, `N`, `M`, `0..1`, `1..*` 같은 표기를 좌표로 대응시킨다. 화살표만 있으면 보통 화살표가 가리키는 쪽이 참조되는 부모(target)이지만, 범례를 우선한다.
5. ERD가 그림으로 붙어 있으면(`pictures`의 `extracted_to`) 아래 "이미지" 절차를 따른다.
6. `.ppt`(바이너리)는 지원하지 않는다. `.pptx`나 PDF로 변환해 달라고 요청한다.

## 이미지 (`.png`, `.jpg`, 스크린샷), PDF

- 결정적 추출기가 없다. 이미지를 직접 보고 해석한다. PDF는 텍스트가 추출되면 텍스트와 그림을 함께 본다.
- 표기법을 먼저 판별한다: crow's foot(IE), Chen(마름모 관계, `1`/`N`), UML(`0..*`), IDEF1X(검은 점). `graph-format.md`의 변환표로 cardinality를 정한다.
- 글자가 흐리거나 선이 겹쳐 어느 테이블에 닿는지 불분명하면 추측하지 말고 해당 부분을 목록으로 사용자에게 확인한다.
- `source.format`은 `image` 또는 `pdf`.

## 텍스트 계열 (SQL DDL, DBML, PlantUML, 표/목록 형태의 문서)

- SQL DDL: `CREATE TABLE`의 column, `NOT NULL`, `DEFAULT`, `PRIMARY KEY`, `UNIQUE`, `REFERENCES`/`FOREIGN KEY`를 옮긴다. FK는 확정적이다. cardinality는 FK column이 NOT NULL이면 target `min: 1`, 아니면 `0`; FK column(들)에 UNIQUE가 있으면 source `max: "one"`, 아니면 `"many"`. source `min`은 DDL로 알 수 없으므로 `null`.
- DBML: `Ref: a.x > b.y`(many-to-one), `<`(one-to-many), `-`(one-to-one), `<>`(many-to-many). `[pk]`, `[not null]`, `[unique]`, `[default: ...]`, `[note: ...]`를 옮긴다.
- PlantUML(IE 표기): `|o--o{` 등은 Mermaid 기호와 같은 의미다. `entity`의 `*` 접두사는 NOT NULL(또는 PK), `<<FK>>`/`<<PK>>` 스테레오타입을 반영한다.
- 위 형식은 모델이 직접 draft JSON을 작성한다.

## 사용자 확인이 필요한 경우

- 그래프 이름(database 이름)을 입력에서 알 수 없을 때
- 같은 파일에 서로 다른 database의 ERD가 섞여 있을 때(그래프를 나눌지)
- 관계선의 양 끝 테이블이나 `max`(one/many)를 읽을 수 없을 때
- 같은 이름의 테이블이 다른 schema에 있는지 단순 중복인지 불분명할 때
- 이미 같은 이름의 그래프 파일이 있을 때(덮어쓸지)
