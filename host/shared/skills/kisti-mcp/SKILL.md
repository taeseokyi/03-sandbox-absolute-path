---
name: kisti-mcp
description: "KISTI AIDA MCP를 통해 ScienceON(논문·특허·보고서), NTIS(R&D 과제·분류), DataON(연구데이터)을 검색·조회한다. Use when searching or retrieving metadata from KISTI AIDA: papers, patents, reports, R&D projects, research datasets. Keywords: KISTI, ScienceON, NTIS, DataON, 논문, 특허, 보고서, 연구데이터, R&D과제, 과학기술분류"
allowed-tools:
  - mcp__kisti-aida__search_scienceon_papers
  - mcp__kisti-aida__search_scienceon_paper_details
  - mcp__kisti-aida__search_scienceon_patents
  - mcp__kisti-aida__search_scienceon_patent_details
  - mcp__kisti-aida__search_scienceon_patent_citations
  - mcp__kisti-aida__search_scienceon_reports
  - mcp__kisti-aida__search_scienceon_report_details
  - mcp__kisti-aida__search_ntis_rnd_projects
  - mcp__kisti-aida__search_ntis_science_tech_classifications
  - mcp__kisti-aida__search_ntis_related_content_recommendations
  - mcp__kisti-aida__search_dataon_research_data
  - mcp__kisti-aida__search_dataon_research_data_details
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

### ScienceON 논문
```
# 저자·기관으로 검색
search_scienceon_papers(keyword="<연구주제>", author="<저자명>", organization="<기관명>")

# ID로 상세 조회
search_scienceon_paper_details(paper_id="<논문ID>")
```

### ScienceON 특허
```
# 키워드·출원인으로 검색
search_scienceon_patents(keyword="<기술명>", applicant="<기관명>")

# 특허 상세 및 인용 관계
search_scienceon_patent_details(patent_id="<특허번호>")
search_scienceon_patent_citations(patent_id="<특허번호>")
```

### ScienceON 보고서
```
search_scienceon_reports(keyword="<주제>", organization="<기관명>")
search_scienceon_report_details(report_id="<보고서ID>")
```

### NTIS R&D 과제
```
# 기관명·연도로 과제 검색
search_ntis_rnd_projects(keyword="<과제명>", organization="<기관명>", year="<연도>")

# 과학기술표준분류 코드 조회
search_ntis_science_tech_classifications(keyword="<연구분야>")

# 과제 연관 콘텐츠 추천
search_ntis_related_content_recommendations(project_id="<과제번호>")
```

### DataON 연구데이터
```
# 중복 확인 및 기존 데이터 조회
search_dataon_research_data(keyword="<데이터셋명>", organization="<기관명>")
search_dataon_research_data_details(data_id="<데이터셋ID>")
```

## 파이프라인 연계 패턴

### 패턴 A — 분류코드 자동 부여
```
1. search_ntis_science_tech_classifications(keyword=<연구분야>)
2. 반환된 분류코드 → DataON JSON `기본.분류` 필드 삽입
```

### 패턴 B — 관련과제 연결
```
1. search_ntis_rnd_projects(organization=<기관명>, year=<수집연도>)
2. 데이터셋과 연관되는 과제번호 선택
3. DataON JSON `관련과제` 필드 삽입
```

### 패턴 C — DataON 중복 검사
```
1. search_dataon_research_data(keyword=<데이터셋 제목>)
2. 동일·유사 데이터셋 존재 시 사용자에게 확인 요청
3. 중복 없으면 등록 진행
```

### 패턴 D — 논문·특허 연관 콘텐츠 수집
```
1. search_scienceon_papers(organization=<기관명>)
2. search_scienceon_patents(applicant=<기관명>)
3. DataON JSON `관련논문`, `관련특허` 필드 삽입
```

