# 도깨비DNR 고딕 / Dokkaebi DNR Gothic

**도깨비 디나루** 16×16 비트맵 글꼴을 Regular(2px 줄기)·Light(1px 줄기) 두 웨이트를
가진 현대적 픽셀 스타일 서체로 다듬는 프로젝트다. Light 웨이트는 완성 후
[gensei-pc98](../../gensei-pc98) PC-98 에뮬레이터 프로젝트의 실제 한글 폰트로
삽입한다 — 원본 발굴·복원에서 그치지 않고 실사용 산출물을 목표로 한다.

이름에 `DNR`(디나루의 자음) 마커를 붙인 이유와 원본의 정체·계보는
[docs/PROVENANCE.md](docs/PROVENANCE.md)에 정리했다.

## 개요

- 원본: `도깨비 디나루`(파일명 `HANKBC.HAN`), 한글도깨비(DKBB) DOS 소프트웨어 계열의 16×16 비트맵
- 목표 산출물: Regular/Light 두 웨이트 서체 + gensei-pc98용 한글 `font.bmp`
- 커버리지: 한글 완성형 11,172자 + 라틴·가나·키릴·그리스·기호 (한자 없음)
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

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python scripts/build_ufo.py --all --proportional --out build/DokkaebiDNRGothic.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic.ttf build/DokkaebiDNRGothic.otf

.venv/bin/python scripts/verify_ttf.py build/DokkaebiDNRGothic.ttf
.venv/bin/python scripts/coverage_report.py build/DokkaebiDNRGothic.ttf
```

## 픽셀 에디터

```bash
.venv/bin/python scripts/editor_server.py       # http://localhost:8000
```

브라우저에서 픽셀을 클릭·드래그해 편집한다. Regular/Light 웨이트는 상단 탭으로
분리되어 있고, 저장하면 각 웨이트의 글리프 파일에 바로 기록된다. Regular는
저장 후 버튼 한 번으로 TTF까지 재빌드할 수 있다. 서버 없이
[tools/pixel_editor.html](tools/pixel_editor.html)만 열어도 복사 방식으로 쓸 수 있다.
