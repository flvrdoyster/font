// Local-only extension for /preview. scripts/editor_server.py injects this
// into web/index.html when serving it -- the public specimen page and the
// editor preview are ONE file, and this script is the entire difference.
//
// What it adds: a second render box below the textarea that draws the
// CURRENT SAVED glyph data (tools/glyphs_*.json, plus the composed-Hangul
// fallbacks /api/text provides) laid out with the same advance/shift/kern
// numbers the build writes -- so a glyph can be checked before any font is
// compiled. The textarea above keeps rendering through the LAST BUILT woff2
// (served from build/ by the same server), so the two boxes double as a
// built-vs-saved comparison for free.
//
// Hooks into the page by element id (tester/presets/weightSeg/sizeRange/
// status) and the PRESETS global -- web/index.html's head comment declares
// those stable for this script's sake.
(() => {
  const textarea = document.getElementById("tester");
  const presetsEl = document.getElementById("presets");
  const weightSegEl = document.getElementById("weightSeg");
  const sizeRangeEl = document.getElementById("sizeRange");
  const statusEl = document.getElementById("status");

  // 검수: 이 로컬 프리뷰 전용 QA 프리셋이라 preview_presets.js가 아니라 여기서
  // 얹는다(공개 페이지에 내놓기엔 문맥 없는 음절 나열). 문맥 품질(이웃 글자
  // 간격, 한/영 경계, 문장부호 주변)을 고정 표본으로 훑는 용도: 1행은 실사용
  // 코퍼스 기준 미확정(조합 출력) 음절 상위 50(scripts/freq_worklist.py,
  // OpenSubtitles 2018 스냅샷), 2행은 2px 줄기 체에 걸린 20자(--stems).
  PRESETS.review =
    "혻됬깄쫒잌됀썻슌됏핳 젋봣맄낰뵜찟됭눞졋섍 딫뼡뵒꾨썪뤀쾶뷱뼱톸 쎘쒖퀬햝헸뭥빐줐괞맽 쓣밷퀠먄맟꿧맀뿰븣쫫\n" +
    "뒦뛐뷖뷯쀀쀢쉮슇쒺쓓 쥫쮞쮷츃퀔퀶큍큏퓥퓧";
  const reviewBtn = document.createElement("button");
  reviewBtn.type = "button";
  reviewBtn.dataset.preset = "review";
  reviewBtn.textContent = "검수";
  presetsEl.appendChild(reviewBtn);

  const style = document.createElement("style");
  style.textContent = `
    .lines-box { resize: both; overflow: auto; min-width: 200px; min-height: 60px;
                 max-width: 100%; padding: 4px; }
    .lines { display: flex; flex-direction: column; gap: 2px; width: max-content; }
    .line { display: flex; align-items: flex-end; }
    .line:empty::before { content: ""; display: block; height: 1em; }
    .glyph canvas { image-rendering: pixelated; display: block; }
  `;
  document.head.appendChild(style);

  const card = document.createElement("div");
  card.className = "card";
  card.style.marginTop = "16px";
  card.innerHTML = `<div class="lines-box"><div class="lines"></div></div>`;
  document.querySelector(".card").after(card);
  const linesEl = card.querySelector(".lines");

  // 페이지의 컨트롤 값을 이 렌더러의 어휘로 번역해서 그대로 따른다 --
  // 컨트롤을 하나도 새로 만들지 않는 것이 이 파일의 존재 조건.
  const weightOf = { "400": "light", "700": "regular" }; // font-weight -> glyphs_*.json 키
  function currentWeight() {
    const btn = weightSegEl.querySelector('button[aria-pressed="true"]');
    return weightOf[btn ? btn.dataset.weight : "400"] || "light";
  }
  function currentScale() {
    // px 크기 -> 정수 확대율. 캔버스는 16px 셀이라 정수 배율만 또렷하다.
    return Math.min(8, Math.max(1, Math.round(Number(sizeRangeEl.value) / 16)));
  }

  const cache = {};     // weight -> { ch: {rows, adv, shift}|null }
  const kernCache = {}; // weight -> { "X\tY": px }

  function glyphCanvas(ch, info, scale) {
    // Canvas width is the glyph's ADVANCE and ink lands at its x_shift --
    // the same numbers build_ufo writes into the font.
    const wrap = document.createElement("span");
    wrap.className = "glyph";
    const cv = document.createElement("canvas");
    const rows = info ? info.rows : null;
    const w = rows ? (info.adv ?? rows[0].length) : 16;
    cv.width = w; cv.height = 16;
    cv.style.height = (16 * scale) + "px";
    cv.style.width = (w * scale) + "px";
    if (rows) {
      const ctx = cv.getContext("2d");
      ctx.fillStyle = "#191c22";
      const shift = info.shift || 0;
      for (let y = 0; y < 16; y++)
        for (let x = 0; x < rows[0].length; x++)
          if (rows[y][x] === "#") ctx.fillRect(x + shift, y, 1, 1);
    } else {
      cv.title = ch + " (없음)";
      cv.style.opacity = "0.15";
    }
    wrap.appendChild(cv);
    return wrap;
  }

  async function fetchMissing(weight, chars) {
    const bucket = cache[weight] || (cache[weight] = {});
    const need = [...new Set(chars)].filter(ch => !(ch in bucket) && ch !== "\n");
    if (!need.length) return;
    const res = await fetch("api/text?weight=" + weight + "&s=" + encodeURIComponent(need.join("")),
                            { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    const j = await res.json();
    for (const c of j.chars) bucket[c.ch] = c.rows ? c : null;
  }

  async function fetchKern(weight) {
    if (kernCache[weight]) return;
    const res = await fetch("api/kern_pairs?weight=" + weight, { cache: "no-store" });
    kernCache[weight] = res.ok ? (await res.json()).pairs || {} : {};
  }

  function render() {
    const scale = currentScale();
    const weight = currentWeight();
    const bucket = cache[weight] || {};
    const kern = kernCache[weight] || {};
    linesEl.innerHTML = "";
    for (const line of textarea.value.split("\n")) {
      const lineEl = document.createElement("div");
      lineEl.className = "line";
      let prev = null;
      for (const ch of line) {
        const el = glyphCanvas(ch, bucket[ch], scale);
        const k = prev === null ? 0 : (kern[prev + "\t" + ch] || 0);
        if (k) el.style.marginLeft = (k * scale) + "px";
        lineEl.appendChild(el);
        prev = ch;
      }
      linesEl.appendChild(lineEl);
    }
  }

  async function refresh() {
    const weight = currentWeight();
    try {
      await Promise.all([
        fetchMissing(weight, [...textarea.value].filter(ch => ch !== "\n")),
        fetchKern(weight),
      ]);
    } catch (e) {
      statusEl.textContent = "저장 글리프 불러오기 실패";
      return;
    }
    render();
  }

  // 기존 리스너(값 갱신)가 먼저 돌고 이쪽(다시 그리기)이 나중에 돈다 -- 이
  // 스크립트는 </body> 직전에 주입되므로 등록 순서가 그걸 보장한다.
  let debounce;
  textarea.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(refresh, 150);
  });
  presetsEl.addEventListener("click", e => {
    if (e.target.closest("button[data-preset]")) refresh();
  });
  weightSegEl.addEventListener("click", e => {
    if (e.target.closest("button[data-weight]")) refresh();
  });
  sizeRangeEl.addEventListener("input", render);

  refresh();
})();
