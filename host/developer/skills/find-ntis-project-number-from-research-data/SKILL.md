---
name: find-ntis-project-number-from-research-data
description: "연구데이터 제목으로 DataON과 NTIS를 순차적으로 검색하여 국가 R&D 과제번호(10자리 숫자)를 찾는다. Use when user provides a research data title and wants to find the corresponding NTIS national R&D task number. Do NOT use when task number is already known, when research data has no DOI, or when the request is not related to Korean national R&D projects. Keywords: NTIS, 과제번호, 국가과제, 연구데이터, DataON, R&D, 과제번호 찾기, task number, research data, 국가R&D, KOPRI, KPDC, DOI"
allowed-tools: write_todos, execute, mcp__kisti-aida__search_dataon_research_data, mcp__kisti-aida__search_dataon_research_data_details, mcp__kisti-aida__search_ntis_rnd_projects
---

# find-ntis-project-number-from-research-data

## 목적
연구데이터 제목을 입력받아 DataON 검색 → DOI 랜딩페이지 분석 → **과제명 한국어 번역** → NTIS 검색의
단계를 거쳐 NTIS 국가과제 번호(10자리 숫자)를 찾는다.

## 입력
사용자가 제공한 연구데이터 제목을 사용한다.  
제목이 명확하지 않으면 사용자에게 연구데이터 제목을 다시 확인한다.

## 사용 조건

### 이 스킬을 사용해야 하는 경우
- 연구데이터 제목이 주어지고 해당 데이터의 NTIS 국가과제 번호를 찾아야 할 때
- DataON에 등록된 연구데이터의 과제 연계 정보를 확인해야 할 때
- 연구데이터의 DOI가 있고 원본 랜딩페이지에서 과제 정보를 추적해야 할 때
- 한국 국가 R&D 과제와 연구데이터의 연결 관계를 파악해야 할 때

### 이 스킬을 사용하지 말아야 하는 경우
- 과제번호가 이미 알려져 있는 경우
- 연구데이터에 DOI가 없는 경우
- DataON에 등록되지 않은 해외 연구데이터인 경우
- 한국 국가 R&D 과제와 무관한 연구데이터인 경우
- 과제 제목만 있고 연구데이터 제목이 없는 경우

## 공통 규칙
- **모든 단계는 자동으로 연속 실행한다 (사용자 명령 대기 없음)**
- 데이터셋 생산 연도는 과제 수행 연도와 일치하여야 한다
- NTIS 과제번호는 숫자 10자리이다
- 시작 전 아래 4단계를 write_todos로 리스트를 만들고 체크하면서 진행한다

## 단계별 수행

### Step 1. DataON 연구데이터 검색

mcp__kisti-aida__search_dataon_research_data 도구를 사용하여 연구데이터 제목 전체로 검색한다.

- 검색 결과가 없으면 → **중지**: "DataON 검색 결과 없음" 보고

---

### Step 2. 연구데이터 상세정보 조회

mcp__kisti-aida__search_dataon_research_data_details 도구를 사용하여 Step 1의 `svc_id`로 상세정보를 조회한다.

아래 항목을 확인한다.

| 필드 | 확인 내용 |
|---|---|
| `dataset_title_etc_main` | 데이터셋 제목 |
| `dataset_doi` / `dataset_lndgpg` | DOI 및 랜딩페이지 URL |
| `dataset_creator_etc_main`, `dataset_cntrbtr_etc` | 연구자 정보 |
| `cltfm_pc` | 수집기관 |
| `pjt_nm_kor` / `pjt_nm_etc` | 과제명 (있으면 조기 완료) |

- 데이터셋 생산 연도는 데이터 제목에 연도가 있으면, 최우선적으로 데이터셋의 연도로 본다.
- `pjt_nm_kor` 또는 `pjt_nm_etc`가 존재하면 → **중지**: 과제번호/제목 보고 후 완료
- `dataset_lndgpg`가 없으면 → **중지**: "DOI 랜딩페이지 URL 없음" 보고
- 중시사유가 없으면, Step 3 으로 이동한다.

---

### Step 3. DOI 랜딩페이지에서 과제 제목 추출

#### 3-1. 리다이렉트 최종 URL 확인
```bash
curl -sI --connect-timeout 10 --max-time 20 -4 "Mozilla/5.0" -4 "{dataset_lndgpg}" | grep -i "^location:"
```

#### 3-2. 최종 URL 페이지 저장
```bash
curl -sL --connect-timeout 10 --max-time 20 -4 "Mozilla/5.0" -4 "{최종_URL}" > landing_page.html && ls -la landing_page.html
```

#### 3-3. 과제 제목 파싱 (최대 5회 시도)
```bash
grep -A 5 "Project" landing_page.html
```

"<dt>Project</dt>" 바로 아래 "<dd>" 블록에서 과제 제목(영문), PI를 추출한다.

```html
<!-- 추출 패턴 예시 -->
<dt>Project</dt>
<dd class="dview_link_list"><ul>
  <li>
    <a href="/browse/research/PM24050">
      <strong>PM24050</strong>, Survey of Geology and Seabed Enviromental Change in the Arctic Seas.
      <strong>PI.Jong Kuk Hong</strong>
    </a>
  </li>
```

- 과제 제목 발견 시 → Step 4 진행

---

### Step 4. NTIS 과제 검색 및 과제번호 확인

#### 4-1. 과제명 한국어 번역
DOI 랜딩페이지에서 추출한 **영문 과제명**을 한국어로 번역한다.

#### 4-2. NTIS 검색
mcp__kisti-aida__search_ntis_rnd_projects 도구를 사용하여 **번역된 한국어 과제명**으로 검색한다.

결과가 없으면, 한국어 핵심 키워드로 축약하여 재 검색 (최대 3회)

#### 4-3 데이터셋 연도와 일치하는 과제 확인 (수행 연도 필수 + 1개 이상 추가 일치)

| 항목 | 확인 방법 | 필수 여부 |
|---|---|---|
| 수행 연도 | `ProjectYear`가 연구데이터 생산 연도와 일치 | ✅ 필수 |
| PI/책임자 | `Manager.Name`이 연구자명과 일치 | 선택 |
| 소속기관 | `ResearchAgency.Name`이 수집기관과 일치 | 선택 |
| 연구 주제 | `Keyword` 또는 `Abstract`가 주제와 유사 | 선택 |

- 조건 미달 시 → "적합한 과제를 찾을 수 없음" 보고

---

### 최종 출력 형식

✅ 최종 결과

| 항목            | 내용 |
|---|---|
| 연구데이터 제목 | {제목} |
| DOI             | {DOI} |
| 과제번호 (NTIS) | {10자리 숫자} |
| 과제제목        | {한국어 과제명} |
| 수행연도        | {연도} |
| PI              | {책임자명} |
| 소속기관        | {기관명} |
| 일치 항목       | 연도 ✅ / PI ✅ / 소속 ✅ / 주제 ✅ |

---

### 중지 조건 요약

| 단계 | 중지 사유 |
|---|---|
| Step 1 | DataON 검색 결과 없음 |
| Step 2 | DOI 랜딩페이지 URL 없음 |
| Step 2 | 과제정보가 메타데이터에 이미 존재 (조기 완료) |
| Step 3 | 5회 시도 후 과제 정보 미발견 |
| Step 4 | 3회 검색 후 적합 과제 없음 |
