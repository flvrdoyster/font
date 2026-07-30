# 도깨비DNR 고딕 / Dokkaebi DNR Gothic

**도깨비 디나루** 16×16 비트맵 글꼴을 굵기 두 종(1px 줄기·2px 줄기)을 가진 현대적
픽셀 스타일 서체로 다듬는 프로젝트다. 두 굵기는 **하나의 패밀리 Regular(1px, 기본)·
Bold(2px)** 로 묶여 나오므로, 앱에서 볼드를 걸면(Cmd+B 등) 두꺼운 쪽으로 전환된다.
얇은 쪽(Regular, 1px)은 완성 후 [gensei-pc98](../../gensei-pc98) PC-98 에뮬레이터
프로젝트의 실제 한글 폰트로 삽입한다 — 원본 발굴·복원에서 그치지 않고 실사용
산출물을 목표로 한다.

이름에 `DNR`(디나루의 자음) 마커를 붙인 이유와 원본의 정체·계보는
[docs/PROVENANCE.md](docs/PROVENANCE.md)에 정리했다.

## 개요

- 원본: `도깨비 디나루`(파일명 `HANKBC.HAN`), 한글도깨비(DKBB) DOS 소프트웨어 계열의 16×16 비트맵
- 목표 산출물: Regular(1px)·Bold(2px) 한 패밀리 서체 + gensei-pc98용 한글 `font.bmp`
- 커버리지: Bold(2px)는 한글 11,172자 전부, Regular(1px)는 완성형 2,350자(KS X 1001).
  둘 다 라틴·가나·키릴·그리스·기호 포함, 한자 없음. Regular를 11,172자로 넓히는
  작업이 진행 중이다 — [docs/ROADMAP.md](docs/ROADMAP.md) 참고
- 라이선스: SIL Open Font License 1.1, 예약 글꼴 이름 `Dokkaebi DNR` — [OFL.txt](OFL.txt)
- 변환 방식: 픽셀을 64×64 유닛 정사각형으로 보고 인접 픽셀의 공유 변을 상쇄해 병합
  폴리곤을 만든다. 곡선 트레이싱을 쓰지 않으므로 확대해도 계단이 그대로 보존된다.

## 작업 계획

전체 로드맵(웨이트별 진행 상황, 디자인 문법, 한글 재설계 트랙)은
[docs/ROADMAP.md](docs/ROADMAP.md)를 참고한다.

## 구조

```
original/HANKBC.ttf       원본(읽기 전용)
tools/                    변환 엔진, 손으로 그린 글리프 데이터, 픽셀 에디터
scripts/                  빌드·검증·리포트 스크립트
build/                    빌드 산출물(UFO/TTF/OTF)
docs/                     계보·로드맵 문서
```

빌드 파이프라인: 원본 비트맵 → 커스텀 글리프 오버레이 → 폴리곤 변환·자폭 산출 →
UFO → fontmake → 메타데이터/로컬라이즈 이름 부여 → 검증.

## 빌드

한 패밀리의 두 멤버(1px=Regular, 2px=Bold)를 각각 빌드한다. `build_ufo.py`의
`--weight light`가 1px→Regular, `--all`이 2px→Bold를 만든다(내부 weight 키
`light`/`regular`는 줄기 두께를 뜻하며 그대로 유지 — 컴파일된 스타일 이름만
Regular/Bold).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Regular 멤버 (1px 줄기)
.venv/bin/python scripts/build_ufo.py --weight light --proportional --out build/DokkaebiDNRGothic-Regular.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic-Regular.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic-Regular.ttf build/DokkaebiDNRGothic-Regular.otf

# Bold 멤버 (2px 줄기, 전체 11,172자)
.venv/bin/python scripts/build_ufo.py --all --proportional --out build/DokkaebiDNRGothic-Bold.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic-Bold.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic-Bold.ttf build/DokkaebiDNRGothic-Bold.otf

.venv/bin/python scripts/verify_ttf.py build/DokkaebiDNRGothic-Bold.ttf
.venv/bin/python scripts/coverage_report.py build/DokkaebiDNRGothic-Bold.ttf
```

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
.venv/bin/python scripts/compose_components.py --build      # 검토용 11,172자 출력
```

반각 한글은 별도 도구(`/half`)를 쓴다. 서버는 시작할 때 어느 페이지를 열지
묻는다.
