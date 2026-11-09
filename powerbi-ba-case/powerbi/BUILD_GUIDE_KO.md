# Power BI 제작 가이드 (한국어)

이 가이드대로 하면 4페이지 리포트가 완성됩니다. 데이터 모델·관계·측정값 21개는 PBIP 파일에 이미 들어 있어서, 직접 하는 일은 **시각화 배치**뿐입니다. 예상 시간은 1.5~2시간입니다.

메뉴 이름은 영어판 기준이고 괄호 안에 한국어판 이름을 적었습니다.

## 0. 준비 (5분)

1. Power BI Desktop → File(파일) → Options and settings(옵션 및 설정) → Options(옵션) → **Preview features(미리 보기 기능)**
   - "Power BI Project (.pbip) save option"과 "Store semantic model using TMDL format" 항목이 보이면 둘 다 켭니다. 안 보이면 이미 기본 기능이라 그냥 넘어가면 됩니다.
2. Power BI Desktop을 다시 시작합니다.

## 1. 프로젝트 열기 (5분)

1. `powerbi/BREWLY_Commercial.pbip`를 더블클릭하거나 File → Open에서 엽니다.
2. 상단 **Refresh(새로 고침)** 를 누릅니다. 테이블 13개와 `_Measures`가 오른쪽 Data(데이터) 창에 보이면 성공입니다.
3. 폴더 위치를 옮겼다면: 저장소 루트에서 `python powerbi-ba-case/src/build_pbip.py`를 다시 실행하면 새 경로로 모델 파일이 만들어집니다.
4. **오류가 나면** 오류 메시지 전체를 복사해서 알려 주세요. 바로 고치겠습니다. 급하면 맨 아래 "B안: 수동 구성"으로 진행해도 됩니다.

확인: 왼쪽 **Model view(모델 보기)** 에서 관계선 15개가 보이고, `Dim Member`–`Dim Week` 선만 점선(비활성)이어야 합니다.

## 2. 테마 적용 (2분)

View(보기) → Themes(테마) → Browse for themes(테마 찾아보기) → `powerbi/brewly_theme.json` 선택.

## 3. 공통 슬라이서 (페이지 1에서 만들고 복사)

| 슬라이서 | 필드 | 스타일 |
|---|---|---|
| 연도 | `Dim Week[iso_year]` | Tile(타일), 단일 선택 |
| 분기 | `Dim Week[quarter]` | Dropdown(드롭다운) |
| 권역 | `Dim Region[region_name]` | Tile(타일) |

세 개를 만든 뒤 함께 선택 → 복사 → 2·3페이지에 붙여 넣습니다. "Sync visuals(시각적 개체 동기화)" 메시지가 뜨면 **Sync(동기화)** 를 고릅니다.

## 4. 페이지 1 — Overview

| 위치 | 시각화 | 필드 |
|---|---|---|
| 상단 4칸 | Card(카드) ×4 | `Refill Revenue (KRW)` / `Active Members (8w)` / `New Members` / `Retail Net Revenue (KRW)` |
| 가운데 왼쪽 (넓게) | Line chart(꺾은선형 차트) | X축 `Dim Week[week_start]`, Y축 `Refill Orders`, 범례 `Dim Region[region_name]` |
| 가운데 오른쪽 | Clustered bar chart(묶은 가로 막대형) | Y축 `Dim Store[partner]`, X축 `Retail Net Revenue (KRW)` |
| 하단 작은 카드 | Card(카드) | `Sell-out Store Coverage` |
| 하단 텍스트 상자 | Text box(텍스트 상자) | "Retail figures exclude weeks still waiting for partner files (coverage below 95%)." |

팁: 꺾은선 X축이 계층(연·분기·월·일)으로 바뀌면 필드 옆 화살표에서 `week_start`(계층 아님)를 고릅니다.

## 5. 페이지 2 — Acquisition

| 위치 | 시각화 | 필드 |
|---|---|---|
| 상단 왼쪽 | Stacked column chart(누적 세로 막대형) | X축 `Dim Week[quarter]`, Y축 `Acquisition Spend (KRW)`, 범례 `Dim Channel[channel_name]` |
| 상단 오른쪽 | Line and clustered column chart(꺾은선형 및 묶은 세로 막대형) | X축 `Dim Week[quarter]`, 막대 `New Members`, 선 `Blended CAC (KRW)` |
| 하단 | Table(테이블) | `Dim Region[region_name]`, `Acquisition Spend (KRW)`, `New Members`, `Blended CAC (KRW)` |
| 하단 텍스트 상자 | Text box | "Channel-level CAC is out of scope for this release (US-07): members are not tagged with an acquisition channel. Use the MMM in the main project." |

## 6. 페이지 3 — Retention and CX

| 위치 | 시각화 | 필드 |
|---|---|---|
| 상단 4칸 | Card ×4 | `Lapsed Members (12w+)` / `CX SLA Met %` / `Median Resolution Days` / `Tickets per 1,000 Active Members` |
| 왼쪽 | Matrix(행렬) | 행 `Fact Cohort Retention[join_cohort]`, 열 `Fact Cohort Retention[months_since_join]`, 값 `Retention %` |
| 오른쪽 위 | Clustered bar chart | Y축 `Fact CX Tickets[category]`, X축 `CX Tickets`, Tooltips(도구 설명)에 `CX SLA Met %` |
| 오른쪽 아래 | Table | `Fact CX Tickets[category]`, `CX Tickets`, `CX SLA Met %`, `Median Resolution Days` |

행렬 조건부 서식: 값의 `Retention %` 옆 화살표 → Conditional formatting(조건부 서식) → Background color(배경색) → Gradient(그라데이션) 켜기.
테이블의 `CX SLA Met %`도 같은 방식으로 배경색을 넣으면 "Device issue"(약 27%)가 바로 눈에 띕니다.

참고: 행렬은 연도·분기 슬라이서의 영향을 받지 않도록 행렬 선택 → Format(서식) → Edit interactions(상호 작용 편집)에서 슬라이서 → 행렬을 "None(없음)"으로 둡니다.

## 7. 페이지 4 — Data quality

| 위치 | 시각화 | 필드 |
|---|---|---|
| 상단 2칸 | Card ×2 | `DQ Checks Passed` / `DQ Rows Fixed` |
| 가운데 | Table | `DQ Checks`의 `check_id`, `source_table`, `rule`, `rows_checked`, `rows_failed_before`, `fix_applied`, `rows_failed_after`, `status` |
| 하단 | Line chart | X축 `Dim Week[week_start]`, Y축 `Sell-out Store Coverage` |

`status` 열 조건부 서식 → Icons(아이콘) → "Pass"면 초록 체크. 하단 차트에서 마지막 주(2025-W52)가 83%로 떨어지는 것이 DQ-06(늦게 도착한 파트너 파일)입니다.

## 8. 숫자 맞추기 (기능 테스트, 15분)

`tests/expected_values.csv`의 14개 값과 리포트 숫자를 비교합니다. 빈 페이지에 카드를 하나 놓고 필터만 바꿔 가며 확인하면 빠릅니다.

| 테스트 | 측정값 | 필터 | 기대값 |
|---|---|---|---|
| FT-01 | Refill Orders | 연도 2025 | 514,942 |
| FT-02 | Refill Revenue (KRW) | 연도 2025 | 15,798,640,000 |
| FT-03 | Active Members (8w) | 주 2025-W52 (`Dim Week[week_label]`) | 46,936 |
| FT-04 | Active Members (8w) | 주 2025-W52 + Seoul metro | 25,991 |
| FT-05 | New Members | 연도 2025 | 34,400 |
| FT-06 | Acquisition Spend (KRW) | 연도 2025 | 733,537,000 |
| FT-07 | Blended CAC (KRW) | 연도 2025 + Yeongnam | 22,238 |
| FT-08 | Retail Net Revenue (KRW) | 연도 2025 | 1,885,800,000 |
| FT-09 | Device Return Rate | 연도 2025 | 3.5% |
| FT-10 | CRM Messages Sent | 연도 2025 | 1,327,094 |
| FT-11 | CX Tickets | 연도 2025 | 10,495 |
| FT-12 | CX SLA Met % | 연도 2025 | 73.2% |
| FT-13 | Lapsed Members (12w+) | 필터 없음 | 59,029 |
| FT-14 | Retention % | 행렬에서 2024 Q1 × 3 | 46.5% |

다르게 나오는 값이 있으면 알려 주세요. 원인을 찾아 `docs/06_test_cases_uat.md`에 기록하는 것 자체가 포트폴리오의 "테스트" 증거가 됩니다.

## 9. 저장과 내보내기 (10분)

1. File → **Save(저장)**: PBIP 형식으로 저장됩니다.
2. File → **Save as(다른 이름으로 저장)** → `powerbi/BREWLY_Commercial.pbix` (GitHub에서 내려받아 바로 열 수 있는 파일)
3. File → **Export(내보내기)** → Export to PDF(PDF로 내보내기) → `powerbi/BREWLY_Commercial.pdf`
4. 페이지별 스크린샷(Win + Shift + S) → `powerbi/screenshots/` 폴더에 `01_overview.png`, `02_acquisition.png`, `03_retention_cx.png`, `04_data_quality.png`

다 되면 알려 주세요. README에 스크린샷을 넣고 GitHub에 올리겠습니다.

---

## B안: 수동 구성 (PBIP가 열리지 않을 때)

1. Get data(데이터 가져오기) → Text/CSV → `data/model`의 CSV 13개를 하나씩 불러옵니다. (테이블 이름은 `dim_week` → `Dim Week`처럼 바꾸면 측정값을 그대로 쓸 수 있습니다.)
2. Model view(모델 보기)에서 관계를 만듭니다. 목록은 `docs/02_kpi_definitions.md`의 "Model" 절에 있습니다. `Dim Member[join_week_id]` → `Dim Week[week_id]`는 비활성으로 둡니다.
3. Home → Enter data(데이터 입력)로 빈 테이블 `_Measures`를 만들고, `powerbi/measures.dax`의 측정값을 New measure(새 측정값)로 하나씩 붙여 넣습니다.
4. 이후는 3~9단계와 같습니다.
