# HANKBC Restored

프린세스 메이커 2 도스 한글판에서 쓰인 16×16 비트맵 글꼴 **HANKBC**를,
픽셀(계단) 모양을 그대로 보존하는 현대 벡터(TrueType/OpenType) 폰트로 복원하는 프로젝트.

## 원본 정보

- 원본: `original/HANKBC.ttf` — 16×16 1비트 임베디드 비트맵 폰트 (EBDT/EBLC + 레거시 bdat/bloc)
- name 레코드: `BIG.ENG + HANKBC.HAN + SMD.KSG → HANKBC-ISO10646-1.TTF`
  (영문·한글·기호 도스 비트맵 3종을 유니코드로 재조립한 것)
- 커버리지: 현대 한글 완성형 11,172자 완비 + 가나/키릴/그리스/라틴/기호, **한자 없음**, 총 12,354 글리프
- 폭: ASCII 8px(512 units) 반각 / 한글 등 16px(1024 units) 전각
- upem 1024 → 1픽셀 = 정확히 64 units

## 복원 방식

"켜진 픽셀 = 64×64 정사각형". 인접 픽셀의 공유 변을 상쇄(edge-cancellation)해
병합 폴리곤을 만들고, 카운터(구멍)는 반대 winding으로 자동 분리 → non-zero 채우기로 항상 정확.
곡선 트레이싱을 쓰지 않으므로 아무리 키워도 계단이 100% 보존됨.

## 파이프라인

```
original/HANKBC.ttf  ──(tools/pixelfont.py)──▶  merged rectilinear contours
                     ──(scripts/build_ufo.py)─▶  build/HANKBC.ufo   ◀── 수작업 수정
                     ──(fontmake)────────────▶  build/HANKBC.ttf / .otf
                     ──(scripts/poc_verify.py)▶  픽셀 단위 회귀 검증
```

## 사용법

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 지오메트리 픽셀-정확성 전수 검증
.venv/bin/python scripts/poc_verify.py

# UFO 빌드 (서브셋 PoC / 전체)
.venv/bin/python scripts/build_ufo.py --out build/HANKBC-PoC.ufo
.venv/bin/python scripts/build_ufo.py --all --out build/HANKBC.ufo

# 컴파일
.venv/bin/fontmake -u build/HANKBC.ufo -o ttf --output-path build/HANKBC.ttf
```

## 상태

- [x] Phase 0: 원본 분석, 커버리지 조사
- [x] Phase 1: 픽셀→폴리곤 변환 엔진 + PoC (전수 12,354자 픽셀-정확 일치 0 mismatch)
- [ ] Phase 2: 전체 글리프 UFO 빌드
- [ ] Phase 3: 메타데이터/테이블 현대화 (name, OS/2, 레거시 비트맵 제거 등)
- [ ] Phase 4: 검증 (fontbakery, 렌더)
- [ ] Phase 5: 선택 글리프 수작업 리드로잉

## 라이선스

원작자 미상(HANKBC, 프린세스 메이커 2 도스 한글판에서 추출). 배포 라이선스 미정(SIL OFL 1.1 검토 중).
한국 판례상 글자체 도안 자체는 저작권 보호 대상이 아니며, 본 프로젝트는 비트맵을 새 벡터로 재작성함.
