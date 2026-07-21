# 도깨비DNR 고딕 / Dokkaebi DNR Gothic

**도깨비 디나루** 16×16 비트맵 글꼴을 출발점으로, 픽셀(계단) 미학을 그대로 보존한
**비례폭 픽셀 파생 서체**. 자동 변환된 픽셀-정확 벡터 베이스 위에서 글자 다듬기·커버리지
확장·자폭 재설계를 진행한다.

> 이름에 대하여: "도깨비 디나루"(원본)와 "도깨비 고딕체"(역사적 별개 글꼴), 그리고 기존
> 복원본 "Dokkaebi Dinaru"(Juwan Park)와 혼동을 피하기 위해 `DNR`(디나루의 자음) 마커를
> 넣고 실제 장르(고딕)를 명시했다. 자세한 출처·계보는 [docs/PROVENANCE.md](docs/PROVENANCE.md).

## 성격

- 원본: `도깨비 디나루` (파일명 `HANKBC.HAN`), 한글도깨비(DKBB) DOS 소프트웨어 계열의 16×16 비트맵
- 커버리지(현재): 현대 한글 완성형 11,172자 + 라틴·가나·키릴·그리스·기호, 한자 없음
- upem 1024 → 1픽셀 = 64 units. 라틴/기호는 비례폭, 한글은 전각
- 라이선스: **SIL Open Font License 1.1** (예약 글꼴 이름 `Dokkaebi DNR`) — [OFL.txt](OFL.txt)

## 복원·파생 방식

"켜진 픽셀 = 64×64 정사각형". 인접 픽셀의 공유 변을 상쇄(edge-cancellation)해 병합 폴리곤을
만들고, 카운터(구멍)는 반대 winding으로 자동 분리 → non-zero 채우기로 항상 정확. 곡선 트레이싱을
쓰지 않으므로 아무리 키워도 계단이 100% 보존된다. 비례폭은 각 글자의 잉크 범위에서 자동 산출.

## 파이프라인

```
original/HANKBC.ttf
  └ tools/pixelfont.py   픽셀→병합 폴리곤 (픽셀-정확)
  └ tools/spacing.py     잉크 기준 비례폭 산출
  └ tools/metadata.py    이름/OS2/gasp 등 메타데이터
  └ scripts/build_ufo.py → build/DokkaebiDNRGothic.ufo  ◀── 수작업 리드로잉
  └ fontmake             → .ttf / .otf
  └ scripts/finalize.py  한국어 로컬라이즈 이름 추가
  └ scripts/verify_ttf.py       픽셀-정확 회귀 검증
  └ scripts/coverage_report.py  빠진 흔한 문자 리포트
```

## 빌드

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python scripts/build_ufo.py --all --proportional --out build/DokkaebiDNRGothic.ufo
.venv/bin/fontmake -u build/DokkaebiDNRGothic.ufo -o ttf otf --output-dir build/
.venv/bin/python scripts/finalize.py build/DokkaebiDNRGothic.ttf build/DokkaebiDNRGothic.otf

# 검증 / 리포트
.venv/bin/python scripts/verify_ttf.py build/DokkaebiDNRGothic.ttf
.venv/bin/python scripts/coverage_report.py build/DokkaebiDNRGothic.ttf
```

## 진행 상태

- [x] Phase 0: 원본 분석·커버리지 조사
- [x] Phase 1: 픽셀→폴리곤 변환 엔진 (전수 12,354자 픽셀-정확, 0 mismatch)
- [x] Phase 2: 전체 빌드 + 빌드 폰트 픽셀-정확 검증
- [x] 방향 전환: 충실 복원본이 이미 존재 → **파생·리디자인**으로
- [x] Phase 3: 메타데이터·OFL·gasp 그리드핏 억제, 비례폭 적용, 이름 확정
- [ ] 리디자인 ①: 글자 다듬기 (개별 글리프 수작업)
- [ ] 리디자인 ②: 커버리지 확장 (예: ₩ · — · © 등, `coverage_report.py` 참고)
- [ ] 리디자인 ③: 자폭/간격 미세 조정
- [ ] 최종 검증(fontbakery) · 배포

## 참고

- 출처·라이선스 조사: [docs/PROVENANCE.md](docs/PROVENANCE.md)
- 1차 사료: [article.txt](article.txt) (김윤수 「글꼴 모음 #002」, 1994)
