---
name: url2dataon
description: "임의 연구데이터 URL을 DataON 국가연구데이터플랫폼 등록 JSON으로 변환하는 범용 스킬. 기관별 전용 스킬이 없는 경우 사용. Jina AI 마크다운 변환 후 에이전트가 직접 메타데이터 추출. Keywords: url2dataon, DataON, 범용변환, URL, 연구데이터등록"
---

# url2dataon — 범용 DataON 변환 스킬

## 목적

임의의 연구데이터 포털 URL(기관 종류 무관)을
DataON 국가연구데이터플랫폼 등록 형식(`DataON_연구데이터등록` JSON)으로 변환한다.

기관별 사전 필드 매핑 없이, Jina AI로 페이지를 마크다운 텍스트로 변환한 뒤
에이전트(LLM)가 직접 내용을 분석하여 DataON 필드를 채운다.

## 사용 조건

- **사용할 때**: kopri·kier·kigam·kaeri·kfe 전용 스킬이 없는 기관의 URL을 DataON에 등록할 때
- **사용하지 말 것**: 전용 스킬이 존재하는 기관(위 5개) 데이터 처리

## 동작 순서

시작 전 진행 상황을 기록한다:

```python
write_todos(todos=[
    "1. 환경 파악 및 스키마 확인",
    "2. URL 내용 수집 (Jina AI)",
    "3. 메타데이터 추출",
    "4. NTIS 과제 조회 (선택)",
    "5. DataON JSON 작성",
    "6. 스키마 검증",
    "7. 최종 출력",
])
```

---

### 1단계: 환경 파악 및 스키마 확인

```python
read_file(file_path="host/shared/skills/workspace-awareness/SKILL.md")
read_file(file_path="host/data_pipeline/skills/url2dataon/field_guide.md")
read_file(file_path="host/data_pipeline/skills/url2dataon/schema_template.json")
```

```python
write_todos(todos=[
    "~~1. 환경 파악 및 스키마 확인~~",
    "2. URL 내용 수집 (Jina AI)",
    "3. 메타데이터 추출",
    "4. NTIS 과제 조회 (선택)",
    "5. DataON JSON 작성",
    "6. 스키마 검증",
    "7. 최종 출력",
])
```

---

### 2단계: URL 내용 수집

**Jina AI 사용 (마크다운 변환 — 권장):**

환경 변수 `JINA_API_KEY`가 설정되어 있는지 먼저 확인한다.

```python
execute(command="echo $JINA_API_KEY")
```

설정된 경우:

```python
execute(command='curl -s -H "Authorization: Bearer $JINA_API_KEY" "https://r.jina.ai/{입력URL}" -o page_content.md')
read_file(file_path="page_content.md")
```

**`JINA_API_KEY` 없을 때 (HTML 직접 수집 fallback):**

```python
execute(command='curl -sL "{입력URL}" -o page_content.html')
read_file(file_path="page_content.html")
```

수집 결과가 비어 있거나 오류 페이지이면 `curl -v` 로 상태를 확인한 후 재시도한다.

```python
write_todos(todos=[
    "~~1. 환경 파악 및 스키마 확인~~",
    "~~2. URL 내용 수집 (Jina AI)~~",
    "3. 메타데이터 추출",
    "4. NTIS 과제 조회 (선택)",
    "5. DataON JSON 작성",
    "6. 스키마 검증",
    "7. 최종 출력",
])
```

---

### 3단계: 메타데이터 추출

페이지 내용을 읽고 아래 항목을 직접 분석하여 추출한다.
상세 규칙은 `field_guide.md`(1단계에서 읽음)를 참조한다.

| 추출 항목 | 비고 |
|-----------|------|
| 제목 (한국어) | 없으면 영어 제목을 에이전트가 직접 번역하여 채움 |
| 제목 (영어) | 있으면 부언어로 기록 |
| 설명/초록 (한국어) | 없으면 영어 설명을 번역하여 채움 |
| 설명/초록 (영어) | 있으면 부언어로 기록 |
| 키워드 (한국어) | 없으면 영어 키워드를 번역하여 채움 |
| 키워드 (영어) | 있으면 부언어로 기록 |
| 저자·기관명 | 이름(한글/영문) 및 소속 기관 |
| 생성·등록일자 | `yyyy-mm-dd` 형식으로 정규화 |
| 좌표 (위도·경도) | 있으면 수집지역 `Point`로 기록. JS 변수 안에 있어 마크다운에 없는 경우 `geoLocationPlace` 로 지역명 기록 |
| 수집 기간 | 시작일·종료일 |
| 라이선스 | CC 표기 → `field_guide.md` 매핑표 참조 |
| **NTIS 과제번호** | **숫자 10자리** — 직접 보이면 4단계 진행. 아래 심화 탐색 참조 |
| DOI | 있으면 `파일.출처URL`에 추가 |
| 과학기술표준분류 | 기관·키워드 기반으로 NTIS 분류 추론 (`field_guide.md` 참조) |

**NTIS 10자리 번호 심화 탐색 (직접 노출되지 않는 경우):**

페이지에 "NTIS", "NTIS Connect", "과제번호" 등의 링크 또는 프로젝트 코드(예: `PM18050`, `PE25090`, `PM숫자`)가 있으면, 해당 링크를 따라가 10자리 숫자를 찾는다.

```python
# 예: KPDC 과제 페이지에서 NTIS 10자리 추출
execute(command='curl -s "https://{기관도메인}/pjt/{프로젝트코드}" | grep -o "NTIS No\. [0-9]*"')
```

10자리 숫자 확인 후 4단계 진행. 찾지 못하면 4단계를 건너뛴다.

---

### 4단계: NTIS 과제번호 조회 (선택 — 숫자 10자리 확인 시)

3단계에서 숫자 10자리 NTIS 과제번호를 추출한 경우에만 수행한다.
KISTI AIDA MCP로 과제 상세정보를 조회하여 `연관.과제목록`에 채운다.

```
kisti-mcp_search_ntis_rnd_projects(query="<10자리 숫자>", max_results=1)
```

조회 결과를 다음과 같이 매핑한다:

| MCP 응답 필드 | DataON 과제정보 필드 |
|---------------|---------------------|
| `ProjectNumber` | `식별자` |
| `ProjectTitle.Korean` | `과제명_한글` |
| `Ministry.Name` | `부처명` |
| `ResearchAgency.Name` | `과제수행기관` |
| `Manager.Name` | `과제책임자.책임자명_한글` |
| `ProjectPeriod.TotalStart` | `상세입력.연구기간_시작일` |
| `ProjectPeriod.TotalEnd` | `상세입력.연구기간_종료일` |
| `TotalFunds` | `상세입력.총연구비` |
| `Keyword.Korean` | `상세입력.키워드_한글` (쉼표 분리 → list) |
| `Keyword.English` | `상세입력.키워드_영문` (쉼표 분리 → list) |

고정값: `관계유형`: `"isOutputOf"`, `식별자유형`: `"NTIS"`

MCP 조회 실패 시 `field_guide.md`의 과제 JSON 예시 구조로 직접 채우고 계속 진행한다.

```python
write_todos(todos=[
    "~~1. 환경 파악 및 스키마 확인~~",
    "~~2. URL 내용 수집 (Jina AI)~~",
    "~~3. 메타데이터 추출~~",
    "~~4. NTIS 과제 조회 (선택)~~",
    "5. DataON JSON 작성",
    "6. 스키마 검증",
    "7. 최종 출력",
])
```

---

### 5단계: DataON JSON 작성

`schema_template.json`(1단계에서 읽음)의 구조를 기반으로
3·4단계에서 추출한 값을 채워 파일로 저장한다.

```python
write_file(file_path="dataon_output.json", content="""
{
  "collection": "국가연구데이터플랫폼",
  "기본": {
    "국내외": "DOMESTIC",
    "언어": { "주언어": "KO", "부언어": "EN" },
    "제목_주언어": "...",
    "제목_부언어": "...",
    "설명_주언어": "...",
    "설명_부언어": "...",
    "키워드_주언어": ["...", "..."],
    "키워드_부언어": ["...", "..."],
    "과학기술표준분류": ["..."],
    "생성일자": "yyyy-mm-dd"
  },
  "인물정보": [
    {
      "역할": "CREATOR",
      "이름_주언어": "...",
      "이름_부언어": "...",
      "기관_주언어": "...",
      "기관_부언어": "..."
    }
  ],
  "추가": {
    "데이터수집기간": [],
    "데이터수집지역": []
  },
  "공개설정": {
    "공개구분": "PUBLIC",
    "엠바고설정": null,
    "DOI출판": true,
    "라이선스종류": "저작자표시"
  },
  "파일": {
    "note": "데이터 파일 또는 출처URL 중 하나 필수",
    "파일목록": [],
    "출처URL": ["{입력URL}"]
  },
  "연관": {
    "note": "필수 아님. 입력 시 자동완성 추천 목록 제공",
    "과제목록": [],
    "논문목록": []
  }
}
""")
```

`field_guide.md`의 **필수 필드 체크리스트**를 모두 채웠는지 확인한다.

---

### 6단계: 스키마 검증

```python
execute(command="PYTHONPATH=/tmp/workspace/host python host/data_pipeline/skills/url2dataon/validate_dataon.py dataon_output.json")
```

- `[OK] 검증 통과` 출력 → 7단계 진행
- `[FAIL]` 출력 → `[X]` 표시된 필드를 `edit_file`로 수정 후 6단계 재실행
- `[WARN]` 항목은 가능하면 보완하되, 검증에는 영향 없음

```python
write_todos(todos=[
    "~~1. 환경 파악 및 스키마 확인~~",
    "~~2. URL 내용 수집 (Jina AI)~~",
    "~~3. 메타데이터 추출~~",
    "~~4. NTIS 과제 조회 (선택)~~",
    "~~5. DataON JSON 작성~~",
    "~~6. 스키마 검증~~",
    "7. 최종 출력",
])
```

---

### 7단계: 최종 출력

```python
read_file(file_path="dataon_output.json")
```

변환 결과를 사용자에게 보고한다.
값이 비어 있거나 번역이 필요한 필드가 남아 있으면 수동 보완 항목 목록도 함께 안내한다.

```python
write_todos(todos=[
    "~~1. 환경 파악 및 스키마 확인~~",
    "~~2. URL 내용 수집 (Jina AI)~~",
    "~~3. 메타데이터 추출~~",
    "~~4. NTIS 과제 조회 (선택)~~",
    "~~5. DataON JSON 작성~~",
    "~~6. 스키마 검증~~",
    "~~7. 최종 출력~~",
])
```

## 출력 형식

`DataON_연구데이터등록` Pydantic 모델 구조의 JSON.

| 필수 필드 | 비고 |
|-----------|------|
| `기본.국내외` | `"DOMESTIC"` 또는 `"ABROAD"` |
| `기본.제목_주언어` | 한국어 제목 |
| `기본.설명_주언어` | 한국어 설명 |
| `기본.키워드_주언어` | `["키워드1", ...]` |
| `기본.과학기술표준분류` | `["분류1", ...]` |
| `인물정보` | 생성자(`"CREATOR"`) 1명 이상 |
| `파일.출처URL` | 입력 URL 포함 |

## 예시

**한국지질자원연구원(KIGAM) 임의 데이터셋 URL 처리:**

```python
# 2단계: Jina AI로 마크다운 변환
execute(command='curl -s -H "Authorization: Bearer $JINA_API_KEY" "https://r.jina.ai/https://data.kigam.re.kr/dataset/example" -o page_content.md')

# 6단계: 스키마 검증
execute(command="PYTHONPATH=/tmp/workspace/host python host/data_pipeline/skills/url2dataon/validate_dataon.py dataon_output.json")
```

**NTIS 과제번호(숫자 10자리)가 있는 경우 4단계 추가:**

```
# 4단계: NTIS 과제정보 조회
kisti-mcp_search_ntis_rnd_projects(query="1525008151", max_results=1)
```

## Additional resources

- [./field_guide.md](./field_guide.md) — DataON 필드 작성 규칙 빠른 참조
- [./schema_template.json](./schema_template.json) — DataON 등록 빈 양식
- [./validate_dataon.py](./validate_dataon.py) — 스키마 검증 헬퍼 (execute로 실행)
