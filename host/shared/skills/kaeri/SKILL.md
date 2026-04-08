---
name: kaeri
description: "한국원자력연구원(KAERI) 연구데이터를 DataON 국가연구데이터플랫폼 등록 형식으로 변환. Use when processing KAERI research data files (CSV, Excel, JSON) or API URLs for DataON registration. Keywords: KAERI, 한국원자력연구원, 원자력, 방사선, nuclear, radiation, DataON, 연구데이터등록"
allowed-tools: Read, Write, Bash(python -m skills.kaeri.main *)
---
# kaeri — 한국원자력연구원 DataON 변환 스킬

## 목적
KAERI(한국원자력연구원) 출처의 연구데이터(파일 또는 URL)를 DataON 등록 형식(`DataON_연구데이터등록`)으로 변환하여 JSON으로 출력한다.

## 사용 조건
- 사용할 때: KAERI 연구데이터를 DataON에 등록하기 위한 메타데이터 JSON이 필요할 때
- 사용하지 말 것: 다른 기관 데이터 처리 (각 기관별 스킬 사용), DataON 직접 등록 API 호출

## 동작 순서
1. 사용자로부터 소스 경로 또는 URL 수령
2. 아래 명령으로 변환 실행:
   ```
   python -m skills.kaeri.main --source <경로_또는_URL> --output kaeri_dataon.json
   ```
3. 출력된 `kaeri_dataon.json` 내용을 검토하고 누락 필드(제목, 키워드 등) 수동 보완
4. 완성된 JSON을 DataON 등록 화면에 입력

## 출력 형식
`DataON_연구데이터등록` Pydantic 모델의 `model_dump()` JSON 형식.
주요 필드: `기본.제목_주언어`, `기본.키워드_주언어`, `인물정보`, `파일.출처URL`

## 예시

입력: `python -m skills.kaeri.main --source https://oard.kaeri.re.kr/api/datasets --output out.json`
출력: DataON 등록 JSON 파일 (`out.json`)

입력: `python -m skills.kaeri.main --source nuclear_data.xlsx`
출력: stdout에 DataON 등록 JSON 출력

## Additional resources
- DataON 스키마 모델: [lib/dataon_reg.py](../../lib/dataon_reg.py)
- 기관별 필드 매핑: [utils.py](utils.py)
- 파이프라인 공통 도구: [lib/](../../lib/)
