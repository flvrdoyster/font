# 도깨비DNR 고딕 — 로드맵

**최종 목표**: 도깨비 디나루를 Regular(2px 줄기)·Light(1px 줄기) 두 웨이트의 현대적
픽셀 서체로 재설계하고, 그 Light 한글을 [gensei-pc98](../../gensei-pc98) PC-98
에뮬레이터의 실제 한글 폰트로 납품한다. 규모를 단계로 나눠, **완성형 2,350자로 먼저
쓸 수 있는 폰트를 완성**(Phase 2, 완료)한 뒤 gensei-pc98에 납품(Phase 3)하고,
마지막에 **전체 11,172자로 확장**한다.

## 공통 설계

- 웨이트는 Regular(2px)/Light(1px) 2종. 둘 다 정적 폰트, 같은 각진 도깨비DNR 디자인의
  굵기 차이. Light는 Regular의 세로 줄기를 1px로 얇힌 것.
  - 라틴/숫자: Regular를 손으로 그리고 Light는 얇혀 파생(`tools/thin_vertical.py`).
  - 한글: Regular는 원본 도깨비 디나루를 픽셀-정확 벡터화한 것(각진 2px, 이미 완성).
    Light는 이를 1px로 얇힌 뒤 손으로 다듬어 확정.
- 획 문법: Regular는 세로 줄기 2px·가로 바 1px·대각선 1px 계단. Light는 세로 줄기만
  1px.
- 수직 밴드: 한글은 13행(상하 1px 여백), 라틴은 cap~baseline 11행에 x-height·어센더·
  디센더.
- 에디터(`tools/pixel_editor.html`)는 Regular/Light를 상단 탭으로 분리, 저장 파일도
  웨이트별 독립. 빌드(`scripts/build_ufo.py --weight regular|light`)는 두 웨이트 지원.

## Phase 1 — Regular 라틴/숫자 (완료)

- 라틴 대/소문자 + 숫자, 반각/전각 전부 완성. Light는 얇혀서 파생 완료.

## Phase 2 — 완성형 2,350자 Regular/Light 두 폰트 완성 (완료)

완성형 2,350자(KS X 1001) + 라틴/숫자를 커버하는 **쓸 수 있는 두 웨이트 폰트**.

- [x] **Regular 한글**: 원본 도깨비 디나루 벡터화로 완성(11,172자 전부). `--all` 빌드.
- [x] **Regular 라틴/숫자**: 반각/전각 손그림 124자(`glyphs_regular.json`) 완성.
- [x] **Light 한글 2,350자**: 손확정(`glyphs_light.json`에 1,002자 + 나머지 조합, 2,350/2,350
      커버).
- [x] **Light 라틴/숫자 반각·전각 124자**: 손확정 완료(`glyphs_light.json`, 124/124).
      `build_ufo.py`의 `build_light`이 확정본을 그대로 쓰고, 안 그린 것만 얇혀서 채우는
      confirmed-first 원칙 — 지금은 얇힘 의존 0.
- 에디터 빌드 버튼은 현재 탭과 무관하게 Regular→Light 둘 다 빌드한다.

## Phase 3 — gensei-pc98 납품 + 가나/반각 (진행 예정)

완성된 Light 폰트를 gensei-pc98이 쓸 수 있게 만든다.

- **font.bmp 추출**: `scripts/build_pc98_bmp.py` (신규) — 원본 `gensei-pc98/docs/bios/
  font.bmp`를 복사해서 완성형 한글 칸(`tools/pc98_hangul_map.json`, col16-40)은
  `build/light_hangul.json`으로, 반각 한글 칸(아래 참고)은 `tools/glyphs_halfwidth.json`
  으로 교체 — 그 외(가나·한자·기호 등)는 원본 그대로 보존. 지금은 테스트/미리보기
  출력(`build/font_light.bmp`)만 만들고 `../gensei-pc98` 자체는 건드리지 않는다.
- **가나(히라가나·가타카나, PC-98 기준 169자)**: Light부터 손으로 그리는 중.
  - **PC-98 font.bmp에 가나 원본이 실제로 있음을 확인**(초반엔 없다고 잘못 판단했다가
    정정) — col4=히라가나(ku4), col5=가타카나(ku5), `row=32+ten`(표준 JIS X 0208
    ku4/ku5 순서, ten=1부터). `scripts/pc98_kana_map.py` → `tools/pc98_kana_map.json`
    (169자, 반각가타카나는 이 ROM에 없음). **미확정 가나는 원본 HANKBC 비트맵 대신
    이 PC-98 데이터로 폴백**하도록 `editor_server.py`의 `/api/text`·`/api/pc98`을
    수정(두 웨이트 공통) — 확정본(`glyphs_light.json`)이 있으면 항상 그게 우선.
  - 참조 오버레이(보라색, 가나 전용): Meiryo. 사용자의 Microsoft Office 설치본
    (`/Applications/Microsoft Word.app/.../DFonts/meiryo.ttc`)에서 **그 자리에서
    읽기만** 하고 저장소엔 복사·커밋하지 않는다 — 라이선스 재배포 문제 없이 로컬
    참조 전용으로만 쓴다. **모양만 참고**하고 실제 픽셀 데이터는 이식하지 않으며
    PC-98 때와 같은 방식(참조 보며 손으로 각진 스타일로 새로 그림)이라 저작권 고지
    의무도 없다(도안 자체의 저작권 비보호는 `docs/PROVENANCE.md` 참고). 정렬을
    폰트 메트릭 기반으로 다시 스케일해본 적이 있으나 되돌림 — 지금은 16px 고정
    크기 + baseline row 13 그대로.
  - 에디터: `/api/kana`(글자 목록), `/api/meiryo`(참조 렌더, Light 탭·가나 전용)
- **반각 한글**: 폰트 빌드와 별개인 전용 도구로 착수 — `tools/halfwidth_editor.html`
  (`editor_server.py`가 `/halfwidth`로 서빙). `build_ufo.py`는 이 데이터를 전혀
  안 읽는다.
  - `font.bmp`의 col10-11(완성형 '가'에서 왼쪽 6-7칸)에 PC-98 자체 반각 한글 표가
    있음을 발견 — KS X 1001도 유니코드 반각 자모 블록도 아닌 ROM 고유 배열이라
    슬롯을 `"{col}-{ten}"`으로 식별(`scripts/pc98_halfwidth_map.py` →
    `tools/pc98_halfwidth_map.json`). 188칸(94×2) 중 122칸에 원본 잉크, 66칸은
    ROM에서도 빈 칸.
  - 8×16 캔버스에 파란 PC-98 참조 오버레이를 보며 손으로 그려 `tools/
    glyphs_halfwidth.json`에 저장 — **122/122 슬롯 완료**.
  - 슬롯이 어떤 유니코드 글자에 대응하는지는 자동 매칭이 신뢰도 있게 안 돼서
    (반각 디자인은 전각을 단순 축소한 게 아니라 별도로 그려짐) 사용자가 직접
    타이핑해서 지정(`tools/halfwidth_char_map.json`) — 지정하면 그 글자의 Light
    완성형 글리프를 좌우로 절반 접어(OR-fold) 빨간 보조 오버레이로 보여준다.
  - `build_pc98_bmp.py`가 완성형과 함께 이 122칸도 `font_light.bmp`에 반영(8px
    글리프를 16px 칸 왼쪽에, 나머지 8칸은 비움).
- (원본 약물/기호 결손분 신규 드로잉도 필요 시 여기서 함 — `coverage_report.py` 목록.)

## 최종 — 전체 11,172자 확장 (도구 개선 필요)

Phase 2/3로 완성형 폰트를 낸 뒤, 조합형 전체 11,172자로 확장한다.

- **왜 새 도구가 필요한가**: 2,350자는 PC-98 비트맵을 베이스로 자음만 교체해 만들었는데
  (아래 참고), PC-98엔 2,350자밖에 없어 나머지 ~8,822자(조합형에만 존재)는 이 방식으로
  못 만든다. 대신 **확정된 2,350자에서 초성·중성·종성 부품을 뽑아 PC-98 없이 부품만으로
  순수 조합**하는 도구가 필요하다(`scripts/compose_components.py`).
- 현재 상태(v1, 검증 결과):
  - 부품 라이브러리: 초성 390 / 중성 63 / 종성 165 (세분 버킷 + 거친 버킷 폴백)
  - 11,172자 부품 커버리지: 90% (10,009자)
  - **정확도 부족**: 2,350자 확정본을 이 도구로 재구성하면 69%만 완전 일치(평균
    1.92px 오차) — 다수결 부품 + 고정위치 union 방식이 개별 글자 디테일과 받침 수직
    정렬을 뭉갠다. **아직 신규 생성에 쓸 품질이 아니다.**
- 다음 작업: 부품 추출·정렬 개선(받침 baseline 고정, 버킷 재설계, 다수결 대신 최근접
  이식 등)으로 재구성 정확도를 끌어올린 뒤 확장 착수.
- 확정본(2,350자)은 항상 그대로 보존 — 도구는 안 그린 글자만 채운다.

## 참고 — 완성형 2,350자를 만든 방식

Phase 2의 Light 한글 2,350자가 어떻게 확정됐는지 기록.

- 소규모 대표 음절(초성 19×6블록 + 홑받침 16×3 + 겹받침 11종, 총 166자)을 PC-98 BIOS
  폰트의 둥근모꼴(모음 골격 참조)과 원본 도깨비 디나루를 겹쳐 보며 손으로 그리고,
  자음을 블록타입별로 나머지 글자에 이식해 2,350자를 채웠다(`compose_light.py`).
- 이후 조합 결과를 검수하며 직접 다듬어 **2,350자 전부 확정본**
  (`tools/glyphs_light.json`). 안 고친 글자는 조합 결과가 이미 만족스러워 그대로 둔 것.
- `compose_light.py`는 PC-98을 베이스로 깔고 자음만 교체해서, 자음이 안 닿는 곳엔
  PC-98 둥근 픽셀이 남는다. 2,350자는 손으로 확정했으니 문제 없지만, 이 한계 때문에
  이 도구는 위 최종 확장엔 못 쓴다.
- 참조 데이터: `tools/pc98_hangul_map.json`(유니코드→PC-98 좌표),
  `scripts/pc98_hangul_map.py`로 재생성.

## 검증 참고

`scripts/verify_ttf.py`(픽셀-정확 회귀 테스트)는 손대지 않은 한글에만 유효하다.
Phase 2 이후 한글도 변형되므로, 그 이후에는 이 테스트 대신 시각 QA + fontbakery로
검증한다.
