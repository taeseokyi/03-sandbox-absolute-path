---
name: kisti-mcp
description: "KISTI AIDA MCP를 통해 ScienceON(논문·특허·보고서), NTIS(R&D 과제·분류), DataON(연구데이터)을 검색·조회한다. Use when searching or retrieving metadata from KISTI AIDA: papers, patents, reports, R&D projects, research datasets. Keywords: KISTI, ScienceON, NTIS, DataON, 논문, 특허, 보고서, 연구데이터, R&D과제, 과학기술분류"
allowed-tools: mcp__kisti-aida__search_scienceon_papers, mcp__kisti-aida__search_scienceon_paper_details, mcp__kisti-aida__search_scienceon_patents, mcp__kisti-aida__search_scienceon_patent_details, mcp__kisti-aida__search_scienceon_patent_citations, mcp__kisti-aida__search_scienceon_reports, mcp__kisti-aida__search_scienceon_report_details, mcp__kisti-aida__search_ntis_rnd_projects, mcp__kisti-aida__search_ntis_science_tech_classifications, mcp__kisti-aida__search_ntis_related_content_recommendations, mcp__kisti-aida__search_dataon_research_data, mcp__kisti-aida__search_dataon_research_data_details
---
# kisti-mcp — KISTI AIDA MCP 검색 스킬

## 목적
KISTI AIDA MCP 도구를 사용하여 ScienceON, NTIS, DataON에서 연구 메타데이터를 검색·조회한다.  
기관별 파이프라인 스킬이 DataON 등록 JSON을 완성하는 과정에서 보조 도구로 상시 활용된다.

## 사용 조건
- 사용할 때:
  - DataON 등록 시 `관련과제`, `분류코드`, `관련논문/특허` 필드를 채워야 할 때
  - 기관 데이터셋의 DataON 중복 여부를 확인할 때
  - 연구자·기관의 논문·특허 목록이 필요할 때
- 사용하지 말 것: DataON 등록 API 직접 호출(별도 스킬), 원문 파일 다운로드

## 도구별 사용법

> **공통**: 검색 도구는 `query` (★필수) + `max_results` (선택, 기본 10).
> 상세 조회 도구는 검색 결과에서 얻은 ID를 그대로 사용.

### ScienceON 논문

```python
# 키워드로 목록 검색 — query는 한국어 권장
mcp__kisti-aida__search_scienceon_papers(query="북극해 해저지질", max_results=10)
# 반환: { query, total_count, count, papers: [{cn, title, author, ...}] }

# 검색 결과의 cn으로 상세 조회
mcp__kisti-aida__search_scienceon_paper_details(cn="<논문 CN번호>")
# 반환: { cn, paper: {title, abstract, authors, references, ...} }
```

### ScienceON 특허

```python
# 키워드로 목록 검색
mcp__kisti-aida__search_scienceon_patents(query="수소연료전지", max_results=10)
# 반환: { query, total_count, count, patents: [{cn, title, applicant, ...}] }

# 검색 결과의 cn으로 상세/인용 조회
mcp__kisti-aida__search_scienceon_patent_details(cn="<특허 CN번호>")
mcp__kisti-aida__search_scienceon_patent_citations(cn="<특허 CN번호>")
# citations 반환: { cn, total_count, citations: [{cn, title, ...}] }
```

### ScienceON 보고서

```python
mcp__kisti-aida__search_scienceon_reports(query="탄소중립 해양", max_results=10)
# 반환: { query, total_count, count, reports: [{cn, title, organization, ...}] }

mcp__kisti-aida__search_scienceon_report_details(cn="<보고서 CN번호>")
# 반환: { cn, report: {title, abstract, authors, ...} }
```

### NTIS R&D 과제

```python
# 키워드로 과제 검색 — 연도 단독 사용 금지, 반드시 키워드와 조합
mcp__kisti-aida__search_ntis_rnd_projects(query="극지연구소 해저지질", max_results=10)
mcp__kisti-aida__search_ntis_rnd_projects(query="1525008151")          # 10자리 과제번호 직접 조회
mcp__kisti-aida__search_ntis_rnd_projects(query="홍종국 2024 북극해")  # 이름+연도+주제 조합
# 반환: { query, total_count, count, projects: [{ProjectNumber, ProjectTitle, ...}] }

# 연관 콘텐츠 추천 — pjt_id는 projects[].ProjectNumber (숫자여도 문자열로 전달)
mcp__kisti-aida__search_ntis_related_content_recommendations(pjt_id="1425118980", max_results=15)
# 반환: { pjt_id, related_content: {project, paper, patent, researchreport} }

# 과학기술표준분류 추천 — 두 가지 모드
# 모드 1: 초록 텍스트로 일반 추천 (최소 300바이트)
mcp__kisti-aida__search_ntis_science_tech_classifications(
    query="<연구과제 초록>",
    classification_type="standard",   # "standard"(기본) | "health" | "industry"
    max_results=10
)
# 모드 2: 항목별 세부 추천 (더 정확)
mcp__kisti-aida__search_ntis_science_tech_classifications(
    research_goal="<연구 개발 목표>",
    research_content="<연구 개발 내용>",
    expected_effect="<활용 범위>",
    korean_keywords="키워드1, 키워드2",
    english_keywords="keyword1, keyword2"
)
# 반환: { classification_type, total_count, count, classifications: [{code, name, score}] }
```

### DataON 연구데이터

```python
# 키워드로 목록 검색 — 연도 단독 사용 금지, 0건이면 다른 키워드로 반드시 재시도
mcp__kisti-aida__search_dataon_research_data(query="기후변화 북극", max_results=10)
mcp__kisti-aida__search_dataon_research_data(query="이승우", max_results=20, from_pos=0)   # 페이징
mcp__kisti-aida__search_dataon_research_data(query="해저지질", sort_con="date", sort_arr="desc")
# max_results 최대 100, from_pos로 페이징, sort_con: "date"|"title"|"" (관련도순)
# 반환: API 원본 필드 전체 (svc_id 포함)

# 검색 결과의 svc_id로 상세 조회
mcp__kisti-aida__search_dataon_research_data_details(svc_id="<svcId>")
# 반환: 상세 메타데이터 전체 (dataset_title, dataset_doi, pjt_nm_kor 등)
```

## 파이프라인 연계 패턴

### 패턴 A — 분류코드 자동 부여
```
1. mcp__kisti-aida__search_ntis_science_tech_classifications(query=<연구과제 초록>) 또는
   mcp__kisti-aida__search_ntis_science_tech_classifications(korean_keywords=<키워드>, research_content=<연구내용>)
2. 반환된 분류코드 → DataON JSON `기본.과학기술표준분류` 필드 삽입
```

### 패턴 B — 관련과제 연결
```
1. mcp__kisti-aida__search_ntis_rnd_projects(query="<기관명> <연도> <연구주제>")
2. 데이터셋과 연관되는 과제 선택 → ProjectNumber 획득
3. DataON JSON `연관.과제목록` 필드 삽입
```

### 패턴 C — DataON 중복 검사
```
1. mcp__kisti-aida__search_dataon_research_data(query=<데이터셋 제목>)
2. 동일·유사 데이터셋 존재 시 사용자에게 확인 요청
3. 중복 없으면 등록 진행
```

### 패턴 D — 논문·특허 연관 콘텐츠 수집
```
1. mcp__kisti-aida__search_scienceon_papers(query="<기관명> <연구주제>")
2. mcp__kisti-aida__search_scienceon_patents(query="<기관명> <기술명>")
3. DataON JSON `연관.논문목록`, `연관.특허목록` 필드 삽입
```

## 사용자 요청 → 도구 매핑

| 사용자 요청 | 사용 도구 |
|---|---|
| "논문 검색해줘", "papers about X" | `mcp__kisti-aida__search_scienceon_papers` |
| "특허 찾아줘", "patents for X" | `mcp__kisti-aida__search_scienceon_patents` |
| "보고서 검색", "research reports" | `mcp__kisti-aida__search_scienceon_reports` |
| "국가과제 검색", "NTIS 과제 검색", "R&D projects" | `mcp__kisti-aida__search_ntis_rnd_projects` |
| "연구데이터 찾아줘", "datasets" | `mcp__kisti-aida__search_dataon_research_data` |
| "이 논문 상세 정보" | `mcp__kisti-aida__search_scienceon_paper_details` |
| "특허 인용 관계" | `mcp__kisti-aida__search_scienceon_patent_citations` |

## Tips

- **한국어 키워드**가 더 나은 결과를 반환한다: "인공지능" > "AI", "자연어처리" > "NLP"
- **워크플로우**: 목록 검색 → ID 획득 → `_details` 도구로 상세 조회
- **도구 조합**: 논문 + 특허를 함께 검색하면 종합적인 연구 현황 파악 가능
- 결과는 한국어로 반환된다. 사용자 언어에 맞춰 요약 제공
