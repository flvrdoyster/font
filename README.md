# 도깨비DNR 고딕 / Dokkaebi DNR Gothic

**도깨비 디나루** 16×16 비트맵 글꼴을 굵기 두 종(1px 줄기·2px 줄기)을 가진 현대적
픽셀 스타일 서체로 다듬는 프로젝트다. 두 굵기는 **하나의 패밀리 Regular(1px, 기본)·
Bold(2px)** 로 묶여 나오므로, 앱에서 볼드를 걸면(Cmd+B 등) 두꺼운 쪽으로 전환된다.
얇은 쪽(Regular, 1px)은 완성 후 [gensei-pc98](../../gensei-pc98) PC-98 에뮬레이터
프로젝트의 실제 한글 폰트로 삽입한다 — 원본 발굴·복원에서 그치지 않고 실사용
산출물을 목표로 한다. TTF/OTF 두 멤버는 웹폰트(WOFF2)로도 빌드되어 main에 push될
때마다 GitHub Pages로 자동 배포된다.

이름에 `DNR`(디나루의 자음) 마커를 붙인 이유와 원본의 정체·계보는
[docs/PROVENANCE.md](docs/PROVENANCE.md)에 정리했다.

## 개요

- 원본: `도깨비 디나루`(파일명 `HANKBC.HAN`), 한글도깨비(DKBB) DOS 소프트웨어 계열의 16×16 비트맵
- 목표 산출물: Regular(1px)·Bold(2px) 한 패밀리 서체(+ 웹폰트) + gensei-pc98용
  한글 `font.bmp`
- 커버리지: Bold(2px)·Regular(1px) 둘 다 한글 11,172자 전부. 손그림 4,101자가
  우선이고 나머지는 자모 부품 조합으로 채운다 — [docs/ROADMAP.md](docs/ROADMAP.md)
  참고. 둘 다 라틴·가나·키릴·그리스·기호 포함, 한자 없음(가나는 간격 다듬는 중이라
  `--exclude-kana`로 빌드에서 잠시 뺀 상태 — 글리프 자체는 그대로 있음)
- 라이선스: SIL Open Font License 1.1, 예약 글꼴 이름 `Dokkaebi DNR` — [OFL.txt](OFL.txt)
- 변환 방식: 픽셀을 64×64 유닛 정사각형으로 보고 인접 픽셀의 공유 변을 상쇄해 병합
  폴리곤을 만든다. 곡선 트레이싱을 쓰지 않으므로 확대해도 계단이 그대로 보존된다.

## 작업 계획

전체 로드맵(웨이트별 진행 상황, 디자인 문법, 한글 재설계 트랙)은
[docs/ROADMAP.md](docs/ROADMAP.md)를 참고한다.

## 구조

```
original/HANKBC.ttf       Bold 원본(읽기 전용)
original/pc98_font.bmp    Regular 부품 추출용 순정 PC-98 참조(읽기 전용,
                          gensei-pc98에 우리 폰트가 납품되기 전 상태)
tools/                    변환 엔진, 손으로 그린 글리프 데이터, 픽셀 에디터
tools/component_library.json  11,172자 확장용 부품 라이브러리(고정본, 빌드가 읽는 것)
scripts/                  빌드·검증·리포트 스크립트
build/                    빌드 산출물(UFO/TTF/OTF/WOFF2), 전부 gitignore
web/                      GitHub Pages에 배포되는 웹폰트 데모 페이지
.github/workflows/        push마다 웹폰트를 빌드해 GitHub Pages로 배포하는 CI
docs/                     계보·로드맵 문서
```

빌드 파이프라인: Bold는 원본 비트맵 → 커스텀 글리프 오버레이 → 폴리곤 변환 →
UFO → fontmake → 메타데이터 → 검증. Regular 한글은 손그림이 최우선이고, 안 그린
글자는 고정해둔 부품 라이브러리를 조합해 채운다(PC-98 참조는 그 라이브러리를 다시
뽑을 때만 필요 — 아래 "부품 라이브러리" 참고, 평소 빌드엔 안 쓰인다).

## 빌드

한 패밀리의 두 멤버(1px=Regular, 2px=Bold)를 각각 빌드한다. `build_ufo.py`의
`--weight light`가 1px→Regular, `--all`이 2px→Bold를 만든다(내부 weight 키
`light`/`regular`는 줄기 두께를 뜻하며 그대로 유지 — 컴파일된 스타일 이름만
Regular/Bold).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Regular 멤버 (1px 줄기)
.venv/bin/python scripts/build_ufo.py --weight light --proportional --exclude-kana --out build/DokkaebiDNRGothic-Regular.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic-Regular.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic-Regular.ttf build/DokkaebiDNRGothic-Regular.otf

# Bold 멤버 (2px 줄기, 전체 11,172자)
.venv/bin/python scripts/build_ufo.py --all --proportional --exclude-kana --out build/DokkaebiDNRGothic-Bold.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic-Bold.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic-Bold.ttf build/DokkaebiDNRGothic-Bold.otf

.venv/bin/python scripts/verify_ttf.py build/DokkaebiDNRGothic-Bold.ttf
.venv/bin/python scripts/verify_ttf.py build/DokkaebiDNRGothic-Regular.ttf
.venv/bin/python scripts/coverage_report.py build/DokkaebiDNRGothic-Bold.ttf
```

## 웹폰트

OTF(CFF)가 TTF보다 압축이 더 잘 된다 -- 픽셀 폰트라 글리프당 포인트 수가 워낙 적어서
서브셋이 따로 필요 없다(11,172자 한글 + 라틴 + 가나 + 기호 전량 포함해도 웨이트당
150KB 아래).

```bash
.venv/bin/python scripts/build_webfont.py build/DokkaebiDNRGothic-Regular.otf build/DokkaebiDNRGothic-Bold.otf
```

```css
@font-face {
  font-family: "Dokkaebi DNR Gothic";
  src: url("DokkaebiDNRGothic-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "Dokkaebi DNR Gothic";
  src: url("DokkaebiDNRGothic-Bold.woff2") format("woff2");
  font-weight: 700;
}
```

### 자동 배포 (CI)

`.github/workflows/webfont.yml`이 main에 push될 때마다 위 빌드를 전부 다시 돌려
GitHub Pages에 올린다. 폰트 빌드가 자기 완결적(코퍼스 + `tools/component_library.json`
만 있으면 됨, 아래 "부품 라이브러리" 참고)이라 이 레포 하나만 체크아웃하면 된다.

레포를 처음 쓰는 경우 딱 한 번 수동으로: **Settings → Pages → Build and
deployment → Source**를 "GitHub Actions"로 바꿔야 한다(기본값인 "Deploy from a
branch"로는 이 워크플로우가 배포를 못 함).

## 픽셀 에디터

```bash
.venv/bin/python scripts/editor_server.py       # http://localhost:8000
```

브라우저에서 픽셀을 클릭·드래그해 편집한다. 두 굵기(상단 탭: **Regular** 1px 줄기·
기본 / **Bold** 2px 줄기)는 각각의 글리프 파일(`glyphs_light.json` = 1px,
`glyphs_bold.json` = 2px)에 바로 기록된다. 빌드 버튼은 한 번에 두 멤버를
컴파일한다. 저장에는 서버(`scripts/editor_server.py`)가 필요하다 —
[tools/pixel_editor.html](tools/pixel_editor.html)을 서버 없이 열면 편집은 되지만
저장할 방법이 없다.

Regular를 11,172자로 넓히는 작업은 팔레트의 **부품 셀** 탭에서 한다 — 셀을 고르면
그 셀의 대표 음절이 캔버스로 올라오고, 그려서 저장하면 부품이 자동 추출된다
(`/components`로 들어가도 이 탭으로 온다). 진행 상황은 CLI로도 볼 수 있다:

```bash
.venv/bin/python scripts/compose_components.py --coverage   # 조합 가능률
.venv/bin/python scripts/compose_components.py --missing    # 그려야 할 셀
.venv/bin/python scripts/compose_components.py --blobs      # 3x3 덩어리 남은 음절
.venv/bin/python scripts/compose_components.py --cellreview # 부품 1,156칸 전수 눈검수용 PNG
.venv/bin/python scripts/compose_components.py --build      # 검토용 11,172자 출력
.venv/bin/python scripts/compose_components.py --freeze     # 부품 라이브러리 재추출·고정
```

`--coverage`/`--missing`/`--blobs`/`--cellreview`/`--build`는 기본적으로 고정된
라이브러리(`tools/component_library.json`) 기준이라 PC-98 참조 없이도 된다 — 실제
빌드와 같은 숫자가 나온다. `--freeze` 전에 "지금 다시 뽑으면 어떻게 될지" 미리 보고
싶으면 같이 `--reextract`를 붙인다(PC-98 필요). `--validate`/`--loo`는 추출 알고리즘
자체를 재는 도구라 항상 재추출한다(PC-98 필요).

### 부품 라이브러리 (`tools/component_library.json`)

PC-98 참조본(`original/pc98_font.bmp`)이 필요한 건 **부품을 추출할 때뿐**이다 —
"어느 픽셀이 초성이고 어느 픽셀이 중성인지"는 자모 하나만 바꿔가며 무엇이 움직이는지
봐야 알 수 있고, 그 기준이 PC-98이다. 조합(`compose`)은 이미 추출된 부품을 합치기만
하므로 아무것도 참조하지 않는다.

그래서 추출 결과를 `tools/component_library.json`에 고정해두고, **빌드는 이 파일만
읽는다** — 폰트 빌드가 자기 완결적이라 CI에서도 다른 레포가 필요 없다. 손으로 그린
글자는 조합보다 항상 우선이라 새로 그려도 곧바로 폰트에 들어가고, 재추출(`--freeze`)은
그 글자를 **다른 글자를 조합하는 재료로도** 쓰고 싶을 때만 직접 돌리면 된다(빌드가
자동으로 하지 않는다 — 의도적으로 고정해둔 라이브러리를 조용히 갈아치우면 안 되므로).

반각 한글은 별도 도구(`/half`)를 쓴다. 서버는 시작할 때 어느 페이지를 열지
묻는다.
