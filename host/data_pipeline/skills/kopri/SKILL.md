---
name: kopri
description: "극지연구소(KOPRI) KPDC 데이터셋을 DataON 국가연구데이터플랫폼 등록 형식으로 변환. Use when processing KOPRI/KPDC research data from a KPDC URL or file for DataON registration. Keywords: KOPRI, 극지연구소, KPDC, 극지, 남극, 북극, polar, Antarctic, Arctic, DataON, 연구데이터등록"
allowed-tools: Read, Write, Bash(python -m shared.skills.kopri.main *)
---
# kopri — 극지연구소 DataON 변환 스킬

## 목적
KOPRI(극지연구소) KPDC(Korea Polar Data Center) 데이터셋 페이지 URL 또는 파일을
DataON 등록 형식(`DataON_연구데이터등록`)으로 변환하여 JSON으로 출력한다.

## 사용 조건
- 사용할 때: KPDC URL(`https://kpdc.kopri.re.kr/search/{uuid}`) 또는 KOPRI 메타데이터 파일을 DataON에 등록할 때
- 사용하지 말 것: 다른 기관 데이터 (각 기관별 스킬 사용), DataON 직접 등록 API 호출

## 동작 순서
1. 사용자로부터 KPDC URL 또는 파일 경로 수령
2. 아래 명령으로 변환 실행:
   ```
   python -m shared.skills.kopri.main --source https://kpdc.kopri.re.kr/search/{uuid} --output kopri_dataon.json
   ```
3. 출력된 JSON을 검토하고 누락 필드(한국어 제목, 키워드 등) 수동 보완
4. 완성된 JSON을 DataON 등록 화면에 입력

## NTIS 과제정보 자동 연동
KPDC URL 입력 시 NTIS 과제정보를 자동으로 조회하여 DataON 과제목록에 채운다.

**처리 흐름:**
1. KPDC 데이터셋 페이지 스크래핑 → KPDC 과제번호(예: PM18050) 추출
2. `https://kpdc.kopri.re.kr/pjt/{과제번호}` 조회 → NTIS 과제번호(10자리) 추출
3. KISTI AIDA MCP API(`search_ntis_rnd_projects`) 호출 → 과제 상세정보 조회
4. DataON `과제정보` 필드 자동 입력:
   - `식별자유형`: NTIS
   - `식별자`: NTIS 과제번호
   - `과제명_한글`: NTIS 한글 과제명
   - `부처명`, `과제수행기관`, `과제책임자`: NTIS 메타
   - `상세입력`: 연구기간(총사업기간), 총연구비, 한/영 키워드

**NTIS 조회 실패 시:** KPDC 과제번호 + 영문 과제명 번역으로 fallback

## 출력 형식
`DataON_연구데이터등록` Pydantic 모델의 `model_dump()` JSON 형식.
KPDC 특화 필드: `추가.데이터수집지역`(Point 좌표), `추가.데이터수집기간`, 복수 `인물정보`, DOI,
`연관.과제목록`(NTIS 과제정보)

## 예시

입력: `python main.py --source https://kpdc.kopri.re.kr/search/4e6d7eb3-c9e5-41a7-a01a-36e9b3f00d1b`
출력: stdout에 DataON 등록 JSON 출력 (과제목록에 NTIS 1525008151 정보 포함)

입력: `python main.py --source metadata.xlsx --output kopri_dataon.json`
출력: DataON 등록 JSON 파일

## KISTI LLM 활용 구조

KPDC 페이지의 HTML 구조 변동성에 대응하기 위해 KISTI LLM을 구조화 추출에 활용한다.

| 역할 | 방법 | 이유 |
|------|------|------|
| 제목(JS data0)·좌표·DOI·날짜·라이선스·과제번호 | regex | 정밀도 필수 |
| 설명·키워드·저자·과제명 | KISTI LLM (`extract_structured`) | HTML 구조 변경 대응 |
| EN→KO 번역 | KISTI LLM (`translate_en_to_ko`) | 학술 한국어 품질 |
| 저자 한글명 매핑 | KISTI LLM (`map_author_names`) + NTIS Researchers | 영문↔한글 대조 |

**KISTI LLM은 텍스트와 이미지(멀티모달) 모두 처리 가능.**
페이지 스크린샷을 base64로 인코딩하여 `extract_structured(image_b64=..., prompt=...)` 로 전달할 수 있다.

## Additional resources
- DataON 스키마 모델: [lib/dataon_reg.py](../../lib/dataon_reg.py)
- KPDC 스크래퍼 (LLM+regex 혼합): [scraper.py](scraper.py)
- KISTI LLM 클라이언트: [translator.py](translator.py)
- NTIS 클라이언트: [ntis_client.py](ntis_client.py)
- 파이프라인 공통 도구: [lib/](../../lib/)
