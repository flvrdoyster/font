# 도깨비DNR 고딕 / Dokkaebi DNR Gothic

**도깨비 디나루** 16×16 비트맵 글꼴을 굵기 두 종(1px 줄기·2px 줄기)을 가진 현대적
픽셀 스타일 서체로 다듬는 프로젝트. 두 굵기는 **하나의 패밀리 Regular(1px, 기본)·
Bold(2px)** 로 묶여 나오므로, 앱에서 볼드를 걸면(Cmd+B 등) 두꺼운 쪽으로 전환된다.
얇은 쪽(Regular, 1px)은 완성 후 [gensei-pc98](../../gensei-pc98) PC-98 에뮬레이터
프로젝트의 실제 한글 폰트로 삽입한다 — 원본 발굴·복원에서 그치지 않고 실사용
산출물을 목표로 한다. TTF/OTF 두 멤버는 웹폰트(WOFF2)로도 빌드되어 main에 push될
때마다 GitHub Pages로 자동 배포된다.

이름의 `DNR`(디나루의 자음)은 둥근나루체와의 혼동을 피하려고 붙였다 — 실제 서체는
둥근 쪽보다 고딕체에 가깝다.

---

## 개요

- 원본: `도깨비 디나루`(파일명 `HANKBC.HAN`), 한글도깨비(DKBB) DOS 소프트웨어 계열의 16×16 비트맵
- 목표 산출물: Regular(1px)·Bold(2px) 한 패밀리 서체(+ 웹폰트) + gensei-pc98용
  한글 `font.bmp`
- 커버리지: Bold(2px)·Regular(1px) 둘 다 한글 11,172음절 전부 + 호환 자모
  (`ㄱㄴㄷ`·`ㅏㅑㅓ`, 옛한글 포함). 음절은 손그림이 우선이고 나머지는 자모 부품
  조합으로 채운다 — [docs/ROADMAP.md](docs/ROADMAP.md) 참고. 라틴·숫자·핵심
  기호(문장부호·괘선 등)도 포함. **키릴·그리스·원문자·괄호 한글은 범위가
  아니다** — 원본 비트맵에 섞여 있던, 이 서체와 무관한 상속 글리프라 뺐다.
  **일본어(가나·한자)도 범위가 아니다** — 반각 문장부호 ｡｢｣､처럼 전각 짝이
  있는 기호만 남아 있다.
- 라이선스: SIL Open Font License 1.1, 예약 글꼴 이름 `Dokkaebi DNR` — [OFL.txt](OFL.txt)
- 변환 방식: 픽셀을 64×64 유닛 정사각형으로 보고 인접 픽셀의 공유 변을 상쇄해 병합
  폴리곤을 만든다. 곡선 트레이싱을 쓰지 않으므로 확대해도 계단이 그대로 보존된다.

---

## 작업 계획

전체 로드맵(웨이트별 진행 상황, 디자인 문법, 한글 재설계 트랙)은
[docs/ROADMAP.md](docs/ROADMAP.md)를 참고한다.

---

## 웹폰트

OTF(CFF)가 TTF보다 압축이 더 잘 된다 — 픽셀 폰트라 글리프당 포인트 수가 워낙 적어서
서브셋이 따로 필요 없다(한글 전량 + 라틴 + 기호를 다 넣어도 가볍다).

```bash
.venv/bin/python scripts/build_webfont.py build/DokkaebiDNRGothic-Regular.otf build/DokkaebiDNRGothic-Bold.otf
```

### 쓰는 법 — 직접 호스팅

[Releases](https://github.com/flvrdoyster/font/releases)에서 원하는 버전의
`.woff2` 두 개를 받아 CSS 옆에 두고 상대 경로로 가리킨다. Pages에 배포된 절대
URL을 그대로 박아 쓰지는 말 것 — GitHub Pages는 CDN이 아니라 대역폭·가용성
보장이 없다.

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

**업데이트 확인**: 이 레포에서 Watch → Custom → Releases만 켜두면 새 버전이
나올 때 알림이 온다. 받은 파일을 갈아끼우는 건 그때 판단해서 하면 된다.
