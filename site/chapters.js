(function () {
  "use strict";
  var D = window.SD_DATA, papers = D.today;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
  var COLORS = ["#6B231E", "#1E3A2B", "#1B2A45", "#4A3020", "#3B1F33", "#1E3B3F", "#5A4A1C", "#2D2A4A", "#4A1E2E", "#28382A"];
  var TOPIC = {};
  (D.topics || []).forEach(function (t) { TOPIC[t.name] = t.label; });
  function topicOf(p) { return TOPIC[p.topics[0]] || p.topics[0] || "The Scholar’s Desk"; }
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var sm = function (x, a, b) { x = clamp((x - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function sfx(name) { var s = window.SDSFX; if (s && s[name]) s[name](); }
  function shortName(p) { return D.short[p.id] || p.title.split(":")[0]; }
  function authors(p) {
    var last = p.authors.map(function (a) { return a.split(" ").slice(-1)[0]; }).join(", ");
    return p.more_authors ? last + " + " + p.more_authors + " more" : last;
  }
  function tally(p) { return [p.claims.filter(function (c) { return c.ok; }).length, p.claims.length]; }
  function isPhone() { return window.matchMedia("(max-width:700px)").matches; }
  function onceVisible(el, fn, threshold) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var io = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting) { io.disconnect(); fn(); }
    }, { threshold: threshold || 0.3 });
    io.observe(el);
  }
  var SEAL = (function () {
    var out = [];
    for (var i = 0; i < 120; i++) {
      var a = (i / 120) * Math.PI * 2, r = 45 * (1 + (2.4 * Math.sin(a * 9) + 1.3 * Math.sin(a * 21 + 0.7)) / 45);
      out.push((50 + r * Math.cos(a)).toFixed(2) + "," + (50 + r * Math.sin(a)).toFixed(2));
    }
    return out.join(" ");
  })();
  function waxSVG(cls, top, big) {
    return '<svg class="' + cls + '" viewBox="0 0 100 100" aria-hidden="true">' +
      '<polygon points="' + SEAL + '" fill="#7A2620"></polygon>' +
      '<circle cx="50" cy="50" r="39.5" fill="none" stroke="#A8463C" stroke-width="1" stroke-dasharray="2 2.2"></circle>' +
      '<circle cx="50" cy="50" r="35" fill="#62201B"></circle>' +
      '<text class="wl" x="50" y="40">' + top + '</text><text class="wv" x="50" y="68">' + big + '</text></svg>';
  }
  function coverInner(vol, title, foot) {
    return '<span class="cv">' + esc(vol) + '</span><span class="ct">' + esc(title) + '</span>' +
      '<span class="cr"><i></i><b></b><i></i></span><span class="cb">' + esc(foot) + '</span>';
  }
  function book3d(color, vol, title, foot, spineText, attrs) {
    return '<button type="button" class="b3" style="--c:' + color + '" ' + attrs + '>' +
      '<span class="f fr cover">' + coverInner(vol, title, foot) + '</span>' +
      '<span class="f bk"></span>' +
      '<span class="f sp spine"><span>' + esc(spineText) + '</span></span>' +
      '<span class="f pg"></span><span class="f tp"></span><span class="f bt"></span></button>';
  }

  /* ================= I. Folio ================= */
  var row = document.getElementById("bookRow");
  row.style.setProperty("--n", papers.length);
  row.innerHTML = papers.map(function (p, i) {
    return book3d(COLORS[i], "Today · " + ROMAN[i], shortName(p), topicOf(p), ROMAN[i] + " · " + shortName(p),
      'data-i="' + i + '" aria-pressed="false" aria-label="Open paper ' + ROMAN[i] + ': ' + esc(p.title) + '"');
  }).join("");

  var fb = document.getElementById("fb"), fbPrev = document.getElementById("fbPrev"), fbNext = document.getElementById("fbNext"), fbCount = document.getElementById("fbCount");
  var LEAVES = 3, st = { i: 0, n: 0, side: "r" }, flipTimer = null;

  function pages(i) {
    var p = papers[i], pr = p.project, t = tally(p), short = shortName(p), topic = topicOf(p);
    var proofItems = p.claims.map(function (c) {
      var note = c.ok ? "From the abstract: “" + esc(c.evidence) + "”" : "Struck. " + esc(c.note);
      return '<li class="' + (c.ok ? "" : "x") + '"><span class="t">' + esc(c.text) + '</span><span class="n">' + note + '</span></li>';
    }).join("");
    return {
      cover: coverInner("Today · " + ROMAN[i], short, topic),
      title:
        '<p class="pg-kicker">Vol. ' + ROMAN[i] + ' · ' + esc(topic) + '</p>' +
        '<h3 class="pg-h">' + esc(p.title) + '</h3>' +
        '<p class="pg-meta">' + esc(authors(p)) + '</p>' +
        '<div class="pg-rule"><i></i><b></b><i></i></div>' +
        '<p class="pg-meta">arXiv ' + esc(p.id) + ' · ' + esc(p.cat) + '</p>' +
        '<a class="pg-btn" href="' + esc(p.url) + '" target="_blank" rel="noopener">Read the paper ↗</a>' +
        '<div class="pg-foot"><span>i</span><span>Today’s Folio</span></div>',
      p1:
        (p.reason ? '<p class="pg-kicker">Why I picked it</p><p class="pg-p lead">' + esc(p.reason) + '</p>' +
        '<div class="pg-rule"><i></i><b></b><i></i></div>' : '') +
        '<p class="pg-kicker">What they did</p><p class="pg-p">' + esc(p.explanation) + '</p>' +
        '<div class="pg-foot"><span>1</span><span>' + esc(short) + '</span></div>',
      p2:
        '<p class="pg-kicker">Why it matters to you</p><p class="pg-p">' + esc(p.why) + '</p>' +
        '<div class="pg-rule"><i></i><b></b><i></i></div>' +
        '<p class="pg-kicker">How sure are we?</p><p class="pg-p">' + t[0] + ' of the ' + t[1] +
        ' lines on these pages were proven by a quote from the abstract. The proof is two pages on.</p>' +
        '<div class="pg-foot"><span>2</span><span>' + esc(short) + '</span></div>',
      p3:
        '<p class="pg-kicker">Weekend project</p><h3 class="pg-h">' + esc(pr.title) + '</h3>' +
        '<div class="chips"><span class="chip">' + esc(pr.difficulty) + '</span><span class="chip">' + esc(pr.time_estimate) + '</span></div>' +
        '<div class="vers"><div class="ver"><b>With code</b><p class="pg-p">' + esc(pr.description) + '</p></div>' +
        '<div class="ver"><b>No code</b><p class="pg-p">' + esc(pr.no_code_version) + '</p></div></div>' +
        '<div class="pg-foot"><span>3</span><span>' + esc(short) + '</span></div>',
      proof:
        '<p class="pg-kicker">The proof</p><ul class="proof">' + proofItems + '</ul>' +
        '<div class="pg-foot"><span>4</span><span>Checked by Groq</span></div>',
      last:
        '<p class="pg-kicker">Checked and sealed</p>' +
        '<div class="page-stamp">' + waxSVG("wax-page", "PROVEN", t[0] + "/" + t[1]) + '</div>' +
        '<p class="pg-p">Lines without proof were struck before this page was printed. See them in the margins.</p>' +
        '<button type="button" class="pg-btn" data-proof="' + i + '">See it in the margins →</button>' +
        (i < papers.length - 1 ? '<button type="button" class="pg-btn" data-nextbook="' + (i + 1) + '">Next book →</button>' : '') +
        '<div class="pg-foot"><span>5</span><span>The end</span></div>'
    };
  }
  function leaf(k, front, back, frontCls) {
    return '<div class="leaf" data-k="' + k + '"><div class="side front ' + (frontCls || "pageface") + '">' + front +
      '</div><div class="side back pageface">' + back + '</div></div>';
  }
  function buildBook(i) {
    var pg = pages(i);
    fb.style.setProperty("--leaf-c", COLORS[i]);
    fb.innerHTML = '<div class="lastpg pageface">' + pg.last + '</div>' +
      leaf(2, pg.p3, pg.proof) + leaf(1, pg.p1, pg.p2) +
      leaf(0, pg.cover, pg.title, "coverface cover");
    fb.querySelector(".coverface").style.setProperty("--c", COLORS[i]);
    fb.querySelectorAll(".wax-page").forEach(function (s) { s.setAttribute("width", "96"); s.setAttribute("height", "96"); });
  }
  function render(moving) {
    fb.querySelectorAll(".leaf").forEach(function (el) {
      var k = +el.dataset.k, f = k < st.n;
      el.classList.toggle("flipped", f);
      el.style.zIndex = k === moving ? 40 : (f ? 10 + k : 20 - k);
      el.querySelectorAll("a, button").forEach(function (b) { b.tabIndex = -1; });
    });
    fb.classList.toggle("closed", st.n === 0);
    fb.classList.toggle("open-l", st.n > 0);
    var phone = isPhone();
    fb.classList.toggle("view-l", phone && st.n > 0 && st.side === "l");
    fb.classList.toggle("view-r", phone && !(st.n > 0 && st.side === "l"));
    var visible = [];
    if (st.n > 0) visible.push(fb.querySelector('.leaf[data-k="' + (st.n - 1) + '"] .back'));
    visible.push(st.n < LEAVES ? fb.querySelector('.leaf[data-k="' + st.n + '"] .front') : fb.querySelector(".lastpg"));
    visible.forEach(function (v) { if (v) v.querySelectorAll("a, button").forEach(function (b) { b.tabIndex = 0; }); });
    if (phone) {
      var idx = st.n === 0 ? 1 : (st.side === "l" ? 2 * st.n : 2 * st.n + 1);
      fbCount.textContent = "Page " + idx + " of 7";
      fbNext.disabled = st.n === LEAVES && st.side === "r";
    } else {
      fbCount.textContent = st.n === 0 ? "Cover" : "Spread " + st.n + " of 3";
      fbNext.disabled = st.n === LEAVES;
    }
    fbPrev.disabled = st.n === 0;
    fbNext.textContent = st.n === 0 ? (phone ? "Open →" : "Open the book →") : (phone ? "Turn →" : "Turn the page →");
  }
  function flip(k) {
    sfx("page");
    render(k);
    clearTimeout(flipTimer);
    flipTimer = setTimeout(function () { render(); }, 1100);
  }
  function next() {
    if (!isPhone()) { if (st.n < LEAVES) { st.n++; flip(st.n - 1); } return; }
    if (st.side === "r") { if (st.n < LEAVES) { st.n++; st.side = "l"; flip(st.n - 1); } }
    else { st.side = "r"; render(); }
  }
  function prev() {
    if (!isPhone()) { if (st.n > 0) { st.n--; flip(st.n); } return; }
    if (st.side === "l") { st.n--; st.side = "r"; flip(st.n); }
    else if (st.n > 0) { st.side = "l"; render(); }
  }
  var openTimer = null;
  function openBook(i, scroll) {
    st.i = i; st.n = 0; st.side = "r";
    buildBook(i); render();
    row.querySelectorAll(".b3").forEach(function (b, j) { b.setAttribute("aria-pressed", String(j === i)); });
    if (scroll) document.getElementById("stand").scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    clearTimeout(openTimer);
    openTimer = setTimeout(function () { st.n = 1; st.side = isPhone() ? "l" : "r"; flip(0); }, reduce ? 0 : (scroll ? 750 : 500));
  }
  window.SD_openFolioBook = function (i) {
    document.getElementById("folio").scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    setTimeout(function () { openBook(i, true); }, reduce ? 0 : 650);
  };
  row.addEventListener("click", function (e) { var b = e.target.closest(".b3"); if (b) { sfx("whoosh"); openBook(+b.dataset.i, true); } });
  fbNext.addEventListener("click", next);
  fbPrev.addEventListener("click", prev);
  fb.addEventListener("click", function (e) {
    var proofBtn = e.target.closest("[data-proof]");
    if (proofBtn) { showMargins(+proofBtn.dataset.proof, true); document.getElementById("margins").scrollIntoView({ behavior: reduce ? "auto" : "smooth" }); return; }
    var nb = e.target.closest("[data-nextbook]");
    if (nb) { openBook(+nb.dataset.nextbook, false); return; }
    if (e.target.closest("a, button")) return;
    var lf = e.target.closest(".leaf");
    if (lf && lf.classList.contains("flipped")) prev(); else next();
  });
  window.addEventListener("keydown", function (e) {
    var r = fb.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) return;
    if (e.key === "ArrowRight") next();
    if (e.key === "ArrowLeft") prev();
  });
  window.addEventListener("resize", function () { render(); });
  buildBook(0); render();
  onceVisible(document.getElementById("stand"), function () {
    if (st.n === 0) { setTimeout(function () { if (st.n === 0) { st.n = 1; st.side = isPhone() ? "l" : "r"; flip(0); row.querySelector(".b3").setAttribute("aria-pressed", "true"); } }, reduce ? 0 : 400); }
  }, 0.45);

  /* ================= II. Margins ================= */
  var picker = document.getElementById("picker"), mpage = document.getElementById("mpage");
  var mIndex = Math.max(0, papers.findIndex(function (p) { return p.claims.some(function (c) { return !c.ok; }); }));
  picker.innerHTML = papers.map(function (p, i) {
    return '<button type="button" data-i="' + i + '"><span class="rn">' + ROMAN[i] + '</span><span class="pt">' + esc(shortName(p)) + '</span></button>';
  }).join("");
  var shakeTimer = null;
  function showMargins(i, animate) {
    mIndex = i;
    var p = papers[i], t = tally(p);
    picker.querySelectorAll("button").forEach(function (b, j) { b.setAttribute("aria-pressed", String(j === i)); });
    var rows = p.claims.map(function (c, n) {
      var note = c.ok ? '<span class="tg">❧ From the abstract</span>“' + esc(c.evidence) + '”' : '<span class="tg">Struck</span>' + esc(c.note);
      var src = c.src === "reason" ? "Why I picked it" : "What they did";
      var mark = c.ok
        ? '<svg class="mk ok" viewBox="0 0 30 30" aria-label="proven"><circle cx="15" cy="15" r="13"></circle><path d="M8 15.5 l5 5 l9 -11"></path></svg>'
        : '<svg class="mk no" viewBox="0 0 30 30" aria-label="struck"><circle cx="15" cy="15" r="13"></circle><path d="M9.5 9.5 l11 11 M20.5 9.5 l-11 11"></path></svg>';
      return '<div class="mrow' + (c.ok ? "" : " x") + '" style="--i:' + n + '"><p class="mtext"><span class="src">' + src +
        '</span><sup>' + "abcdefghij"[n] + '</sup><span class="w">' + esc(c.text) + '</span></p>' + mark + '<p class="mnote">' + note + '</p></div>';
    }).join("");
    mpage.style.setProperty("--n", p.claims.length);
    var CLIP = '<svg class="clip" viewBox="0 0 34 84" aria-hidden="true"><path d="M10 70 V14 a7 7 0 0 1 14 0 V62 a11 11 0 0 1 -22 0 V22" fill="none" stroke="url(#brassG)" stroke-width="3.2" stroke-linecap="round"></path></svg>';
    var WATER = '<svg class="mwater" viewBox="0 0 100 100" aria-hidden="true"><polygon points="' + SEAL + '" fill="#5C3D14"></polygon><text x="50" y="61" text-anchor="middle" font-family="Playfair Display, Georgia, serif" font-style="italic" font-weight="600" font-size="32" fill="#EFE6D0">SD</text></svg>';
    mpage.innerHTML = CLIP + WATER + waxSVG("wax", "PROVEN", t[0] + "/" + t[1]) +
      '<div class="mhead"><div style="flex:1 1 320px;min-width:0"><p class="m-kicker">Proof sheet · ' + ROMAN[i] + ' of ' + ROMAN[papers.length - 1] + ' · ' + esc(D.dateLabel) + '</p><h3>' + esc(p.title) + '</h3></div></div>' + rows +
      '<div class="msign"><p class="by">Checked line by line by Groq (gpt-oss-120b). A line counts as proven only if its quote is really in the abstract and every number matches.</p></div>';
    if (animate && !reduce) {
      mpage.classList.remove("play", "shake"); void mpage.offsetWidth; mpage.classList.add("play");
      clearTimeout(shakeTimer);
      shakeTimer = setTimeout(function () { mpage.classList.add("shake"); sfx("thud"); }, (p.claims.length * 0.35 + 1.1 + 0.3) * 1000);
    }
  }
  picker.addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) showMargins(+b.dataset.i, true); });
  showMargins(mIndex, false);
  onceVisible(mpage, function () { showMargins(mIndex, true); }, 0.35);
  if (!reduce) {
    window.addEventListener("pointermove", function (e) {
      var r = mpage.getBoundingClientRect();
      if (!r.width || r.bottom < 0 || r.top > window.innerHeight) return;
      var dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
      var near = Math.max(0, 1 - Math.hypot(dx, dy) / 900);
      mpage.style.setProperty("--rx", (clamp(-dy / r.height, -1, 1) * 4 * near).toFixed(2) + "deg");
      mpage.style.setProperty("--ry", (clamp(dx / r.width, -1, 1) * 6 * near).toFixed(2) + "deg");
    });
  }

  /* the route draws itself once, in gold ink */
  var plates = document.getElementById("plates");
  onceVisible(plates, function () { plates.classList.add("on"); }, 0.3);

  /* ledger rows ink in one by one, numbers count up */
  var ledger = document.getElementById("ledger");
  ledger.querySelectorAll(".lrow").forEach(function (r, k) { r.style.setProperty("--r", k % 6); });
  var penDDs = [].slice.call(ledger.querySelectorAll(".lrow dd"));
  if (!reduce) penDDs.forEach(function (dd) { dd.innerHTML = '<span class="pen">' + dd.innerHTML + "</span>"; });
  onceVisible(ledger, function () {
    ledger.classList.add("on");
    if (reduce) return;
    penDDs.forEach(function (dd, k) {
      setTimeout(function () { dd.classList.add("w"); if (window.SD_AUD) window.SD_AUD.scratch(); }, 650 + k * 300);
    });
  }, 0.4);

  /* ================= IV. Stacks ================= */
  var DAY_COLORS = ["#3E2A16", "#5E1C17", "#1F3A2B", "#22305A", "#3B1F33", "#4A3020"];
  var days = D.days.map(function (d, i) {
    return { label: d.label, vol: d.weekday, title: d.short, c: DAY_COLORS[i % DAY_COLORS.length], papers: d.papers, spine: d.spine, roman: d.roman, year: d.year };
  });
  var shelf = document.getElementById("shelfBooks"), slip = document.getElementById("slip");
  var DECOR_LYING = '<span class="decor lying" aria-hidden="true"><i style="--c:#3B1F33;--w:96px;--x:6px"></i><i style="--c:#1E3A2B;--w:86px;--x:0px"></i><i style="--c:#4A3020;--w:100px;--x:3px"></i></span>';
  var DECOR_END = '<svg class="decor bookend" viewBox="0 0 40 150" width="34" height="128" aria-hidden="true"><path d="M4 148 V44 Q4 8 36 8 V148 Z" fill="url(#brassG)"></path><path d="M10 146 V46 Q10 16 32 15" stroke="rgba(255,240,200,.45)" fill="none"></path></svg>';
  var DECOR_CANDLE = '<svg class="decor candle" viewBox="0 0 64 150" width="54" height="128" aria-hidden="true">' +
    '<ellipse cx="32" cy="143" rx="28" ry="5" fill="url(#brassG)"></ellipse><path d="M8 141 Q32 126 56 141 Z" fill="url(#brassG)"></path>' +
    '<rect x="28" y="106" width="8" height="30" fill="url(#brassG)"></rect><ellipse cx="32" cy="106" rx="14" ry="4" fill="url(#brassG)"></ellipse>' +
    '<rect x="24" y="54" width="16" height="52" rx="2" fill="#EFE6CF"></rect><path d="M25 57 q3 7 0 14" stroke="#D9CBAA" stroke-width="2" fill="none"></path>' +
    '<line x1="32" y1="54" x2="32" y2="47" stroke="#3A2C20" stroke-width="1.4"></line>' +
    '<path class="flame" d="M32 16 C41 31 39 44 32 48 C25 44 23 31 32 16 Z" fill="url(#flameG)"></path></svg>';
  var DECOR_INK = '<svg class="decor ink" viewBox="0 0 60 130" width="52" height="112" aria-hidden="true">' +
    '<path d="M28 112 C33 80 40 42 55 5 C46 30 39 62 32 110 Z" fill="#EAE0C8"></path><path d="M29 110 L53 9" stroke="#B7A27A" stroke-width="1"></path>' +
    '<rect x="17" y="88" width="22" height="5" rx="1" fill="url(#brassG)"></rect><rect x="20" y="92" width="16" height="9" fill="#241B14"></rect>' +
    '<path d="M7 101 h42 v21 q0 6 -6 6 h-30 q-6 0 -6 -6 z" fill="url(#glassG)" stroke="#3A2C20"></path><path d="M12 105 v17" stroke="rgba(255,240,210,.3)" stroke-width="2"></path></svg>';
  shelf.innerHTML = DECOR_LYING + days.map(function (d, i) {
    return book3d(d.c, d.vol, d.title, d.papers.length + " papers", d.label, 'data-day="' + i + '" aria-pressed="false" aria-label="Show papers from ' + d.label + '"');
  }).join("") + (function () {
    return D.nextDays.map(function (n) { return n.label; });
  })().map(function (l) {
    return '<span class="ghost" aria-hidden="true"><span>' + l + '</span></span>';
  }).join("") + DECOR_END + DECOR_CANDLE + DECOR_INK;
  shelf.querySelectorAll(".b3").forEach(function (b) { b.style.margin = "0 calc((var(--t) - var(--w)) / 2)"; });
  var stackSel = days.length - 1;
  function showDay(i, anim) {
    stackSel = i;
    shelf.querySelectorAll(".b3").forEach(function (b, j) { b.setAttribute("aria-pressed", String(j === i)); });
    var d = days[i];
    slip.innerHTML = "<h3>" + d.label + " · " + d.papers.length + " papers</h3><ol>" + d.papers.map(function (p) {
      return '<li><a href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(p.title) + "</a></li>";
    }).join("") + "</ol>";
    if (anim && !reduce) { slip.classList.remove("in"); void slip.offsetWidth; slip.classList.add("in"); }
  }
  shelf.addEventListener("click", function (e) { var b = e.target.closest(".b3"); if (b) { sfx("page"); showDay(+b.dataset.day, true); } });
  showDay(days.length - 1, false);
  /* ----- The Stacks as a real 3D bookcase. Without WebGL the flat shelf above stays. ----- */
  (function shelf3d() {
    if (!window.THREE) return;
    var T = window.THREE;
    var bookcase = document.querySelector(".bookcase"), inner = bookcase.querySelector(".bc-inner");
    var canvas = document.createElement("canvas");
    canvas.className = "shelf-gl";
    canvas.setAttribute("aria-hidden", "true");
    var started = false;
    function go() {
      if (started) return;
      started = true;
      var ready = (document.fonts && document.fonts.load) ? Promise.all([
        document.fonts.load('600 40px "Cinzel"'),
        document.fonts.load('italic 600 40px "Playfair Display"')
      ]).catch(function () {}) : Promise.resolve();
      Promise.race([ready, new Promise(function (r) { setTimeout(r, 2500); })]).then(build);
    }
    if ("IntersectionObserver" in window) {
      var io0 = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { io0.disconnect(); go(); } }, { rootMargin: "700px 0px" });
      io0.observe(bookcase);
    } else go();

    function build() {
      var renderer;
      try { renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, powerPreference: "high-performance" }); }
      catch (e) { return; }
      if (!renderer.getContext()) return;
      inner.insertBefore(canvas, inner.firstChild);
      var tagsEl = document.createElement("div");
      tagsEl.className = "shelf-tags"; tagsEl.setAttribute("aria-hidden", "true");
      inner.insertBefore(tagsEl, canvas.nextSibling);
      bookcase.classList.add("gl");

      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputEncoding = T.sRGBEncoding;
      renderer.toneMapping = T.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.22;
      renderer.setClearColor(0x0B0907, 1);
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = T.PCFSoftShadowMap;
      var aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy ? renderer.capabilities.getMaxAnisotropy() : 1);

      var seed = 291026;
      function R() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
      function C(hex) { return new T.Color(hex).convertSRGBToLinear(); }
      function cv(w, h) { var c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
      function tx(c, srgb) { var t = new T.CanvasTexture(c); if (srgb !== false) t.encoding = T.sRGBEncoding; t.anisotropy = aniso; return t; }
      function goldFill(g, w) {
        var gr = g.createLinearGradient(0, 0, w, 0);
        gr.addColorStop(0, "#8A6A2E"); gr.addColorStop(0.45, "#F0D9A4"); gr.addColorStop(0.7, "#C9A35E"); gr.addColorStop(1, "#86622A");
        return gr;
      }

      /* ---------- textures ---------- */
      function wood(w, h, base, horiz, lines, planks) {
        var c = cv(w, h), g = c.getContext("2d");
        g.fillStyle = base; g.fillRect(0, 0, w, h);
        var Lg = horiz ? w : h, A = horiz ? h : w;
        for (var i = 0; i < lines; i++) {
          var p = R() * A, amp = 1 + R() * 5, fr = 0.003 + R() * 0.012, ph = R() * 6.28;
          g.strokeStyle = R() < 0.65 ? "rgba(0,0,0," + (0.05 + R() * 0.14).toFixed(3) + ")" : "rgba(255,210,160," + (0.02 + R() * 0.05).toFixed(3) + ")";
          g.lineWidth = 0.6 + R() * 2;
          g.beginPath();
          for (var s = 0; s <= Lg; s += 8) {
            var o = p + Math.sin(s * fr + ph) * amp + Math.sin(s * fr * 3.1 + ph * 2) * amp * 0.4;
            if (horiz) { if (s === 0) g.moveTo(s, o); else g.lineTo(s, o); }
            else { if (s === 0) g.moveTo(o, s); else g.lineTo(o, s); }
          }
          g.stroke();
        }
        if (planks) {
          for (var k = 1; k < planks; k++) {
            var x = Math.round((k / planks) * w);
            g.fillStyle = "rgba(0,0,0,.6)"; g.fillRect(x - 2, 0, 3, h);
            g.fillStyle = "rgba(255,210,160,.07)"; g.fillRect(x + 1, 0, 1, h);
          }
        }
        for (var n = 0; n < (w * h) / 70; n++) {
          g.fillStyle = R() < 0.5 ? "rgba(0,0,0,.08)" : "rgba(255,230,200,.03)";
          g.fillRect(R() * w, R() * h, 1 + R() * 2, 1 + R() * 2);
        }
        return c;
      }
      function leather(w, h, base) {
        var c = cv(w, h), g = c.getContext("2d");
        g.fillStyle = base; g.fillRect(0, 0, w, h);
        for (var n = 0; n < (w * h) / 12; n++) {
          g.fillStyle = R() < 0.5 ? "rgba(0,0,0,.10)" : "rgba(255,235,200,.035)";
          g.fillRect(R() * w, R() * h, 1 + R() * 2, 1 + R() * 2);
        }
        var vg = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.2, w / 2, h / 2, Math.max(w, h) * 0.75);
        vg.addColorStop(0, "rgba(255,230,190,.06)"); vg.addColorStop(1, "rgba(0,0,0,.38)");
        g.fillStyle = vg; g.fillRect(0, 0, w, h);
        return c;
      }
      function spineCanvas(base, top, mid, bot) {
        var w = 192, h = 1024, c = leather(w, h, base), g = c.getContext("2d");
        var sh = g.createLinearGradient(0, 0, w, 0);
        sh.addColorStop(0, "rgba(0,0,0,.55)"); sh.addColorStop(0.32, "rgba(255,225,180,.08)");
        sh.addColorStop(0.55, "rgba(255,225,180,.12)"); sh.addColorStop(1, "rgba(0,0,0,.62)");
        g.fillStyle = sh; g.fillRect(0, 0, w, h);
        var gold = goldFill(g, w);
        function band(y) {
          g.fillStyle = "rgba(0,0,0,.55)"; g.fillRect(0, y - 10, w, 4);
          g.fillStyle = "rgba(255,225,180,.22)"; g.fillRect(0, y - 6, w, 8);
          g.fillStyle = "rgba(0,0,0,.45)"; g.fillRect(0, y + 2, w, 6);
        }
        function rule(y) { g.fillStyle = gold; g.fillRect(16, y, w - 32, 3); g.fillRect(16, y + 7, w - 32, 1.5); }
        [0.1, 0.24, 0.76, 0.9].forEach(function (f) { band(f * h); });
        [0.045, 0.13, 0.205, 0.785, 0.86, 0.94].forEach(function (f) { rule(f * h); });
        g.fillStyle = gold; g.textAlign = "center"; g.textBaseline = "middle";
        g.font = '600 30px "Cinzel", Georgia, serif'; g.fillText(top, w / 2, 0.168 * h);
        g.font = '600 22px "Cinzel", Georgia, serif'; g.fillText(bot, w / 2, 0.823 * h);
        g.save(); g.translate(w / 2, 0.5 * h); g.rotate(-Math.PI / 2);
        g.shadowColor = "rgba(0,0,0,.65)"; g.shadowBlur = 3; g.shadowOffsetY = 2;
        g.font = '600 62px "Cinzel", Georgia, serif';
        g.fillStyle = goldFill(g, 300);
        g.fillText(mid, 0, 4);
        g.restore();
        return c;
      }
      function spineBump() {
        var w = 32, h = 1024, c = cv(w, h), g = c.getContext("2d");
        g.fillStyle = "#808080"; g.fillRect(0, 0, w, h);
        [0.1, 0.24, 0.76, 0.9].forEach(function (f) {
          var y = f * h, gr = g.createLinearGradient(0, y - 12, 0, y + 12);
          gr.addColorStop(0, "#808080"); gr.addColorStop(0.5, "#ffffff"); gr.addColorStop(1, "#808080");
          g.fillStyle = gr; g.fillRect(0, y - 12, w, 24);
        });
        return c;
      }
      function lyingSpine(base) {
        var w = 512, h = 64, c = leather(w, h, base), g = c.getContext("2d");
        var sh = g.createLinearGradient(0, 0, 0, h);
        sh.addColorStop(0, "rgba(0,0,0,.5)"); sh.addColorStop(0.45, "rgba(255,225,180,.1)"); sh.addColorStop(1, "rgba(0,0,0,.6)");
        g.fillStyle = sh; g.fillRect(0, 0, w, h);
        g.fillStyle = goldFill(g, w);
        [0.08, 0.1, 0.3, 0.7, 0.9, 0.92].forEach(function (f) { g.fillRect(f * w, 8, 3, h - 16); });
        g.fillRect(0.45 * w, h / 2 - 2, 0.1 * w, 3);
        return c;
      }
      function pageTop() {
        var c = cv(64, 256), g = c.getContext("2d");
        g.fillStyle = "#E4D6B6"; g.fillRect(0, 0, 64, 256);
        for (var x = 0; x < 64; x += 2) { g.fillStyle = "rgba(90,70,40," + (0.05 + R() * 0.1).toFixed(3) + ")"; g.fillRect(x, 0, 1, 256); }
        return c;
      }
      function cardCanvas(text, wide) {
        var w = wide ? 640 : 256, h = 96, c = cv(w, h), g = c.getContext("2d");
        var br = g.createLinearGradient(0, 0, 0, h);
        br.addColorStop(0, "#F0D9A4"); br.addColorStop(0.35, "#C9A35E"); br.addColorStop(1, "#6B4A1A");
        g.fillStyle = br; g.fillRect(0, 0, w, h);
        if (wide) {
          g.strokeStyle = "rgba(60,40,15,.55)"; g.lineWidth = 2; g.strokeRect(14, 14, w - 28, h - 28);
          g.fillStyle = "#2B1E10"; g.textAlign = "center"; g.textBaseline = "middle";
          g.font = '700 36px "Cinzel", Georgia, serif'; g.fillText(text, w / 2, h / 2 + 2);
          g.fillStyle = "rgba(255,240,200,.35)"; g.fillText(text, w / 2, h / 2 + 3.5);
          g.fillStyle = "#2B1E10"; g.fillText(text, w / 2, h / 2 + 2);
        } else {
          g.fillStyle = "rgba(0,0,0,.4)"; g.fillRect(12, 14, w - 24, h - 28);
          g.fillStyle = "#EDE3CC"; g.fillRect(15, 17, w - 30, h - 34);
          g.fillStyle = "#3A2A1A"; g.textAlign = "center"; g.textBaseline = "middle";
          g.font = '600 30px "Cinzel", Georgia, serif'; g.fillText(text, w / 2, h / 2 + 2);
        }
        g.fillStyle = "#4A3412";
        [[7, h / 2], [w - 7, h / 2]].forEach(function (p) { g.beginPath(); g.arc(p[0], p[1], 3.5, 0, 6.3); g.fill(); });
        return c;
      }
      function featherCanvas() {
        var w = 128, h = 512, c = cv(w, h), g = c.getContext("2d");
        g.save();
        g.beginPath();
        g.moveTo(64, 470);
        g.bezierCurveTo(20, 400, 22, 160, 70, 8);
        g.bezierCurveTo(112, 150, 104, 380, 64, 470);
        var fg = g.createLinearGradient(0, 0, w, 0);
        fg.addColorStop(0, "#BFB49C"); fg.addColorStop(0.5, "#F2EAD8"); fg.addColorStop(1, "#C9BEA6");
        g.fillStyle = fg; g.fill();
        g.clip();
        for (var y = 20; y < 470; y += 4) {
          g.strokeStyle = "rgba(90,78,60," + (0.18 + R() * 0.2).toFixed(3) + ")"; g.lineWidth = 1;
          g.beginPath(); g.moveTo(66, y); g.lineTo(0, y + 26); g.stroke();
          g.beginPath(); g.moveTo(66, y); g.lineTo(w, y + 22); g.stroke();
        }
        for (var k = 0; k < 5; k++) { var yy = 120 + R() * 300; g.clearRect(R() < 0.5 ? 0 : 90, yy, 40, 3); }
        g.restore();
        g.strokeStyle = "#E9E0CC"; g.lineWidth = 3;
        g.beginPath(); g.moveTo(64, 512); g.bezierCurveTo(63, 380, 64, 200, 70, 8); g.stroke();
        return c;
      }
      function flameCanvas() {
        var c = cv(64, 128), g = c.getContext("2d");
        var gr = g.createRadialGradient(32, 92, 2, 32, 82, 56);
        gr.addColorStop(0, "rgba(255,255,240,1)"); gr.addColorStop(0.25, "rgba(255,226,150,.95)");
        gr.addColorStop(0.55, "rgba(255,150,60,.55)"); gr.addColorStop(1, "rgba(255,90,20,0)");
        g.fillStyle = gr;
        g.beginPath(); g.moveTo(32, 6); g.bezierCurveTo(52, 50, 54, 92, 32, 116); g.bezierCurveTo(10, 92, 12, 50, 32, 6); g.fill();
        return c;
      }
      function dotCanvas() {
        var c = cv(128, 128), g = c.getContext("2d");
        var gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
        gr.addColorStop(0, "rgba(255,190,110,.9)"); gr.addColorStop(0.3, "rgba(255,160,80,.35)"); gr.addColorStop(1, "rgba(255,140,60,0)");
        g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
        return c;
      }

      /* ---------- a warm room to reflect in brass and glass ---------- */
      var env = (function () {
        var c = cv(256, 128), g = c.getContext("2d");
        var gr = g.createLinearGradient(0, 0, 0, 128);
        gr.addColorStop(0, "#2A1D12"); gr.addColorStop(0.5, "#6B4A2A"); gr.addColorStop(1, "#140E09");
        g.fillStyle = gr; g.fillRect(0, 0, 256, 128);
        var sp = g.createRadialGradient(170, 48, 0, 170, 48, 40);
        sp.addColorStop(0, "rgba(255,236,200,1)"); sp.addColorStop(1, "rgba(255,200,140,0)");
        g.fillStyle = sp; g.fillRect(0, 0, 256, 128);
        var es = new T.Scene();
        es.add(new T.Mesh(new T.SphereGeometry(10, 32, 16), new T.MeshBasicMaterial({ map: tx(c), side: T.BackSide })));
        var pm = new T.PMREMGenerator(renderer);
        var t = pm.fromScene(es, 0.03).texture;
        pm.dispose();
        return t;
      })();

      var scene, camera, books, cand, flame, halo, dust, pickables, layout, sel = days.length - 1, hov = -1, needs = true;
      var brass = new T.MeshStandardMaterial({ color: C("#C8973F"), metalness: 0.92, roughness: 0.32, envMap: env, envMapIntensity: 1.1 });

      function makeScene(phone) {
        seed = 291026;
        scene = new T.Scene();
        var halfIn = phone ? 1.95 : 3.4, Wfull = halfIn * 2 + 0.44;
        layout = { halfIn: halfIn, phone: phone };

        /* light */
        scene.add(new T.AmbientLight(0xffe2c0, 0.24));
        scene.add(new T.HemisphereLight(0xffd9a8, 0x0b0907, 0.22));
        var key = new T.DirectionalLight(0xffe4c0, 0.85);
        key.position.set(-3, 5, 6); key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        var sc = key.shadow.camera; sc.left = -5; sc.right = 5; sc.top = 4; sc.bottom = -2; sc.near = 1; sc.far = 20;
        key.shadow.bias = -0.0006;
        key.target.position.set(0, 0.8, 0);
        scene.add(key); scene.add(key.target);

        /* the case: back planks, shelf, sides, top */
        var backTex = tx(wood(1024, 512, "#2A1A10", false, 160, phone ? 4 : 6));
        var back = new T.Mesh(new T.PlaneGeometry(Wfull, 3.2), new T.MeshStandardMaterial({ map: backTex, roughness: 0.86 }));
        back.position.set(0, 1.05, -0.75); back.receiveShadow = true; scene.add(back);
        var boardTex = tx(wood(1024, 128, "#5A3820", true, 70));
        var boardMat = new T.MeshStandardMaterial({ map: boardTex, roughness: 0.62 });
        var shelfBoard = new T.Mesh(new T.BoxGeometry(Wfull, 0.18, 1.45), boardMat);
        shelfBoard.position.set(0, -0.09, -0.025); shelfBoard.receiveShadow = true; scene.add(shelfBoard);
        var lip = new T.Mesh(new T.BoxGeometry(Wfull, 0.035, 0.05), new T.MeshStandardMaterial({ color: C("#6E4628"), roughness: 0.5 }));
        lip.position.set(0, -0.005, 0.69); scene.add(lip);
        var sideTex = tx(wood(128, 512, "#4A2E1A", false, 40));
        var sideMat = new T.MeshStandardMaterial({ map: sideTex, roughness: 0.66 });
        [-1, 1].forEach(function (s) {
          var sd = new T.Mesh(new T.BoxGeometry(0.22, 3.6, 1.45), sideMat);
          sd.position.set(s * (halfIn + 0.11), 1.05, -0.025); sd.receiveShadow = true; scene.add(sd);
        });
        var top = new T.Mesh(new T.BoxGeometry(Wfull, 0.22, 1.45), boardMat);
        top.position.set(0, 2.36, -0.025); top.receiveShadow = true; scene.add(top);
        var plate = new T.Mesh(new T.PlaneGeometry(phone ? 1.95 : 1.8, 0.17), new T.MeshStandardMaterial({ map: tx(cardCanvas("", true)), metalness: 0.55, roughness: 0.38, envMap: env }));
        plate.position.set(0, 2.36, 0.702); scene.add(plate);

        /* books */
        var maxBooks = phone ? 3 : 5, first = Math.max(0, days.length - maxBooks);
        var specs = days.slice(first).map(function (d, k) {
          var di = first + k;
          return { day: di, c: d.c, top: d.roman, mid: d.spine, bot: d.year, label: d.title, t: 0.38 + (di % 3) * 0.03, h: 1.68 + ((di * 7) % 5) * 0.035 };
        });
        var x0 = phone ? -halfIn + 0.36 : -halfIn + 1.35;
        var pageMat = new T.MeshStandardMaterial({ map: tx(pageTop()), roughness: 0.9 });
        var pageSide = new T.MeshStandardMaterial({ color: C("#DCCDAA"), roughness: 0.92 });
        var bump = tx(spineBump(), false);
        books = []; pickables = [];
        var x = x0;
        specs.forEach(function (d, i) {
          var g = new T.Group(), dep = 1.05, t = d.t, h = d.h, board = 0.03;
          var cover = new T.MeshStandardMaterial({ map: tx(leather(128, 512, d.c)), roughness: 0.6, metalness: 0.04, emissive: C("#FFB060"), emissiveIntensity: 0 });
          var spineMat = new T.MeshStandardMaterial({ map: tx(spineCanvas(d.c, d.top, d.mid, d.bot)), bumpMap: bump, bumpScale: 0.025, roughness: 0.48, metalness: 0.06, emissive: C("#FFB060"), emissiveIntensity: 0 });
          var bL = new T.Mesh(new T.BoxGeometry(board, h, dep), cover); bL.position.x = -t / 2 + board / 2;
          var bR = new T.Mesh(new T.BoxGeometry(board, h, dep), cover); bR.position.x = t / 2 - board / 2;
          var pages = new T.Mesh(new T.BoxGeometry(t - board * 2, h - 0.05, dep - 0.05), [pageSide, pageSide, pageMat, pageSide, pageSide, pageSide]);
          pages.position.z = -0.025;
          var spine = new T.Mesh(new T.CylinderGeometry(t / 2, t / 2, h, 28, 1, false, -Math.PI / 2, Math.PI), [spineMat, cover, cover]);
          spine.scale.z = 0.36; spine.position.z = dep / 2;
          [bL, bR, pages, spine].forEach(function (m) { m.castShadow = true; m.receiveShadow = true; m.userData.day = d.day; g.add(m); pickables.push(m); });
          x += (i === 0 ? 0 : specs[i - 1].t / 2 + 0.015) + t / 2;
          g.position.set(x, h / 2, -0.72 + dep / 2);
          g.userData = { x0: g.position.x, y0: g.position.y, z0: g.position.z, mats: [cover, spineMat], day: d.day, label: d.label };
          scene.add(g); books.push(g);
        });
        var afterBooks = x + specs[specs.length - 1].t / 2 + 0.02;

        /* brass bookend, flat side against the books */
        var s = new T.Shape();
        s.moveTo(0, 0); s.lineTo(0, 1.05); s.lineTo(0.05, 1.05);
        s.quadraticCurveTo(0.3, 1.02, 0.3, 0.74); s.lineTo(0.3, 0.06); s.lineTo(0.4, 0.04); s.lineTo(0.4, 0); s.lineTo(0, 0);
        var endGeo = new T.ExtrudeGeometry(s, { depth: 0.55, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 2, curveSegments: 16 });
        var bookend = new T.Mesh(endGeo, brass);
        bookend.position.set(afterBooks, 0, -0.7); bookend.castShadow = true; bookend.receiveShadow = true; scene.add(bookend);

        /* labels on the shelf edge: one per day, the empty ones are days still to come */
        var labels = [];
        books.forEach(function (b) { labels.push({ x: b.userData.x0, text: b.userData.label, day: b.userData.day }); });
        var slotW = 0.42, sx = afterBooks + 0.42 + slotW / 2 + 0.06, candleX = phone ? 0.72 : 1.55;
        for (var k = 0; k < D.nextDays.length && sx + k * slotW < candleX - 0.3; k++) {
          labels.push({ x: sx + k * slotW, text: D.nextDays[k].short, future: true });
        }
        var holderMat = new T.MeshStandardMaterial({ map: tx(cardCanvas("", false)), metalness: 0.3, roughness: 0.5, envMap: env, envMapIntensity: 0.6 });
        labels.forEach(function (l) {
          var m = new T.Mesh(new T.PlaneGeometry(phone ? 0.36 : 0.405, 0.135), holderMat);
          m.position.set(l.x, -0.09, 0.703); scene.add(m);
        });
        tagsEl.innerHTML = "";
        layout.tags = labels.map(function (l) {
          var el = document.createElement("span");
          el.className = "shelf-tag" + (l.future ? " future" : "");
          el.textContent = phone ? l.text.split(" ")[0] : l.text;
          tagsEl.appendChild(el);
          return { el: el, x: l.x, y: -0.09, z: 0.71 };
        });
        var pl = document.createElement("span");
        pl.className = "shelf-tag brassplate"; pl.textContent = "The Stacks · MMXXVI";
        tagsEl.appendChild(pl);
        layout.tags.push({ el: pl, x: 0, y: 2.36, z: 0.71 });

        /* a stack of old books lying down */
        if (!phone) {
          [["#3B1F33", 0.98, 0.17, 0.02], ["#1E3A2B", 0.88, 0.15, -0.05], ["#4A3020", 1.02, 0.18, 0.04]].reverse().forEach(function (b, n, arr) {
            var y = 0; for (var q = 0; q < n; q++) y += arr[q][2];
            var cov = new T.MeshStandardMaterial({ map: tx(leather(256, 128, b[0])), roughness: 0.62 });
            var sp = new T.MeshStandardMaterial({ map: tx(lyingSpine(b[0])), roughness: 0.52 });
            var m = new T.Mesh(new T.BoxGeometry(b[1], b[2], 0.78), [pageSide, pageSide, cov, cov, sp, pageSide]);
            m.position.set(-halfIn + 0.66 + b[3], y + b[2] / 2, -0.28); m.rotation.y = b[3] * 1.4;
            m.castShadow = true; m.receiveShadow = true; scene.add(m);
          });
        }

        /* candle in a brass holder */
        var cx = phone ? 0.72 : 1.55;
        var hp = [[0, 0], [0.3, 0], [0.32, 0.015], [0.31, 0.04], [0.14, 0.07], [0.07, 0.11], [0.055, 0.36], [0.075, 0.4], [0.13, 0.43], [0.14, 0.47], [0.11, 0.47], [0.085, 0.45], [0, 0.45]]
          .map(function (p) { return new T.Vector2(p[0], p[1]); });
        var holder = new T.Mesh(new T.LatheGeometry(hp, 48), brass);
        holder.position.set(cx, 0, 0.05); holder.castShadow = true; holder.receiveShadow = true; scene.add(holder);
        var wax = new T.Mesh(new T.CylinderGeometry(0.072, 0.078, 0.72, 32), new T.MeshStandardMaterial({ color: C("#EFE6CF"), roughness: 0.55, emissive: C("#FF9A40"), emissiveIntensity: 0.06 }));
        wax.position.set(cx, 0.45 + 0.36, 0.05); wax.receiveShadow = true; scene.add(wax);
        var drip = new T.Mesh(new T.SphereGeometry(0.03, 12, 8), wax.material); drip.scale.set(1, 2.2, 0.8); drip.position.set(cx + 0.06, 1.1, 0.09); scene.add(drip);
        var wick = new T.Mesh(new T.CylinderGeometry(0.005, 0.006, 0.06, 6), new T.MeshBasicMaterial({ color: 0x1a120c }));
        wick.position.set(cx, 1.2, 0.05); scene.add(wick);
        flame = new T.Sprite(new T.SpriteMaterial({ map: tx(flameCanvas()), transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
        flame.position.set(cx, 1.3, 0.05); flame.scale.set(0.085, 0.2, 1); scene.add(flame);
        halo = new T.Sprite(new T.SpriteMaterial({ map: tx(dotCanvas()), transparent: true, depthWrite: false, blending: T.AdditiveBlending, opacity: 0.32 }));
        halo.position.set(cx, 1.28, 0.06); halo.scale.set(1.1, 1.1, 1); scene.add(halo);
        var NM = phone ? 40 : 70, dpos = new Float32Array(NM * 3), dcol = new Float32Array(NM * 3), dseeds = [];
        for (var q = 0; q < NM; q++) {
          dpos[q * 3] = cx + (R() - 0.5) * 2.6; dpos[q * 3 + 1] = 0.15 + R() * 2.0; dpos[q * 3 + 2] = -0.55 + R() * 1.15;
          dseeds.push({ v: 0.025 + R() * 0.05, ph: R() * 6.28 });
        }
        var dgeo = new T.BufferGeometry();
        dgeo.setAttribute("position", new T.BufferAttribute(dpos, 3));
        dgeo.setAttribute("color", new T.BufferAttribute(dcol, 3));
        var mote = cv(32, 32), mg = mote.getContext("2d"), mgr = mg.createRadialGradient(16, 16, 0, 16, 16, 16);
        mgr.addColorStop(0, "rgba(255,255,255,1)"); mgr.addColorStop(0.35, "rgba(255,255,255,.5)"); mgr.addColorStop(1, "rgba(255,255,255,0)");
        mg.fillStyle = mgr; mg.fillRect(0, 0, 32, 32);
        dust = new T.Points(dgeo, new T.PointsMaterial({ map: tx(mote), size: 0.075, vertexColors: true, transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
        dust.userData = { seeds: dseeds, cx: cx, cy: 1.3, cz: 0.05 };
        scene.add(dust);
        cand = new T.PointLight(0xffa457, 2.4, 7.5, 2);
        cand.position.set(cx, 1.33, 0.12); cand.castShadow = !phone;
        cand.shadow.mapSize.set(512, 512); cand.shadow.bias = -0.003; cand.shadow.camera.near = 0.05;
        scene.add(cand);

        /* inkwell and quill */
        var ix = phone ? 1.48 : 2.6;
        var ip = [[0, 0], [0.2, 0], [0.235, 0.03], [0.245, 0.12], [0.21, 0.2], [0.11, 0.245], [0.07, 0.26], [0.07, 0.31], [0, 0.31]]
          .map(function (p) { return new T.Vector2(p[0], p[1]); });
        var glass = new T.MeshPhysicalMaterial({ color: C("#1A2230"), roughness: 0.06, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.04, envMap: env, envMapIntensity: 1.4 });
        var well = new T.Mesh(new T.LatheGeometry(ip, 48), glass);
        well.position.set(ix, 0, 0.12); well.castShadow = true; scene.add(well);
        var collar = new T.Mesh(new T.TorusGeometry(0.073, 0.016, 10, 40), brass);
        collar.rotation.x = Math.PI / 2; collar.position.set(ix, 0.3, 0.12); scene.add(collar);
        var quill = new T.Mesh(new T.PlaneGeometry(0.34, 1.35), new T.MeshStandardMaterial({ map: tx(featherCanvas()), alphaTest: 0.35, side: T.DoubleSide, roughness: 0.8 }));
        var qg = new T.Group(); qg.position.set(ix + 0.01, 0.27, 0.12); qg.rotation.set(-0.12, -0.5, -0.36);
        quill.position.y = 0.6; qg.add(quill); scene.add(qg);

        camera = new T.PerspectiveCamera(17, 2, 0.1, 80);
        needs = true;
      }

      /* ---------- size, camera ---------- */
      var A = 2.5;
      function fit() {
        var w = Math.max(1, inner.clientWidth), phone = w < 560;
        if (!scene || phone !== layout.phone) makeScene(phone);
        var half = layout.halfIn + 0.3;
        A = (half * 2) / 2.86;
        var h = Math.round(w / A);
        canvas.style.height = h + "px";
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        var dist = half / (Math.tan((camera.fov / 2) * Math.PI / 180) * camera.aspect) + 0.7;
        camera.position.set(0, 1.07 + dist * 0.085, dist);
        if (dust) dust.material.size = 5 * dist / (h / 2);
        camera.lookAt(0, 1.07, 0);
        camera.updateProjectionMatrix();
        camera.updateMatrixWorld();
        var v = new T.Vector3();
        layout.tags.forEach(function (tg) {
          v.set(tg.x, tg.y, tg.z).project(camera);
          tg.el.style.left = ((v.x + 1) / 2 * w).toFixed(1) + "px";
          tg.el.style.top = ((1 - v.y) / 2 * h).toFixed(1) + "px";
        });
        needs = true;
      }
      fit();
      window.addEventListener("resize", fit);

      /* ---------- pointer ---------- */
      var ray = new T.Raycaster(), mv = new T.Vector2();
      function pickAt(e) {
        var r = canvas.getBoundingClientRect();
        mv.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
        ray.setFromCamera(mv, camera);
        var hit = ray.intersectObjects(pickables, false)[0];
        return hit ? hit.object.userData.day : -1;
      }
      canvas.addEventListener("pointermove", function (e) {
        var d = pickAt(e);
        if (d !== hov) { hov = d; canvas.style.cursor = d >= 0 ? "pointer" : ""; needs = true; }
      });
      canvas.addEventListener("pointerleave", function () { hov = -1; canvas.style.cursor = ""; needs = true; });
      canvas.addEventListener("click", function (e) {
        var d = pickAt(e);
        if (d >= 0) { sfx("page"); showDay(d, true); }
      });
      shelf.querySelectorAll(".b3").forEach(function (b) {
        b.addEventListener("focus", function () { hov = +b.dataset.day; needs = true; });
        b.addEventListener("blur", function () { hov = -1; needs = true; });
      });

      /* ---------- loop: only while on screen ---------- */
      var visible = true, raf = 0, last = performance.now();
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (es) {
          visible = es[0].isIntersecting;
          if (visible && !raf) { last = performance.now(); raf = requestAnimationFrame(loop); }
        }, { rootMargin: "100px 0px" }).observe(canvas);
      }
      function loop(now) {
        raf = 0;
        if (!visible || document.hidden) return;
        var dt = Math.min(0.05, (now - last) / 1000); last = now;
        var k = 1 - Math.pow(0.0015, dt), moving = false;
        sel = stackSel;
        books.forEach(function (b, i) {
          var u = b.userData, on = u.day === sel, ho = u.day === hov && !on;
          var tz = u.z0 + (on ? 0.3 : ho ? 0.12 : 0), ty = u.y0 + (on ? 0.035 : 0), ry = on ? -0.07 : 0;
          b.position.z += (tz - b.position.z) * k; b.position.y += (ty - b.position.y) * k; b.rotation.y += (ry - b.rotation.y) * k;
          var em = on ? 0.05 : ho ? 0.035 : 0;
          u.mats.forEach(function (m) { m.emissiveIntensity += (em - m.emissiveIntensity) * k; });
          if (Math.abs(tz - b.position.z) > 0.0005 || Math.abs(ry - b.rotation.y) > 0.0005) moving = true;
        });
        if (dust) {
          var pa = dust.geometry.attributes.position, ca = dust.geometry.attributes.color, du = dust.userData, tt = now / 1000;
          for (var q = 0; q < du.seeds.length; q++) {
            var sd = du.seeds[q], ix = q * 3;
            if (!reduce) {
              pa.array[ix + 1] += sd.v * dt;
              pa.array[ix] += Math.sin(tt * 0.5 + sd.ph) * 0.03 * dt;
              if (pa.array[ix + 1] > 2.15) pa.array[ix + 1] = 0.15;
            }
            var ddx = pa.array[ix] - du.cx, ddy = pa.array[ix + 1] - du.cy, ddz = pa.array[ix + 2] - du.cz;
            var b = Math.max(0, 1 - Math.sqrt(ddx * ddx + ddy * ddy + ddz * ddz) / 1.6);
            b = Math.min(1, b * b * 1.35 * (0.55 + 0.45 * Math.sin(tt * 2.3 + sd.ph)));
            ca.array[ix] = b; ca.array[ix + 1] = b * 0.84; ca.array[ix + 2] = b * 0.58;
          }
          pa.needsUpdate = true; ca.needsUpdate = true;
        }
        if (!reduce) {
          var t = now / 1000;
          var f = 0.88 + 0.06 * Math.sin(t * 7.3) + 0.04 * Math.sin(t * 13.1 + 1.3) + 0.03 * Math.sin(t * 23.7 + 0.4);
          cand.intensity = 2.4 * f;
          flame.scale.set(0.085 * (1.6 - f * 0.6), 0.2 * f, 1);
          flame.position.x = cand.position.x + Math.sin(t * 3.1) * 0.004;
          halo.material.opacity = 0.3 * f;
          moving = true;
        }
        if (moving || needs) { renderer.render(scene, camera); needs = false; }
        raf = requestAnimationFrame(loop);
      }
      raf = requestAnimationFrame(loop);
    }
  })();

  /* the address opens Gmail on a laptop and the mail app on a phone; Copy is the backup */
  var copyBtn = document.getElementById("copyMail"), mailAddr = document.getElementById("mailAddr");
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) mailAddr.href = document.getElementById("mailApp").href;
  copyBtn.addEventListener("click", function () {
    var done = function () { copyBtn.textContent = "Copied"; setTimeout(function () { copyBtn.textContent = "Copy"; }, 1600); };
    var select = function () { var r = document.createRange(); r.selectNodeContents(mailAddr); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); };
    try { navigator.clipboard.writeText(mailAddr.textContent).then(done, select); } catch (e) { select(); }
  });

  /* ================= V. Colophon ================= */
  var colo = document.getElementById("colo");
  document.querySelectorAll(".colo [data-seal]").forEach(function (p) { p.setAttribute("points", SEAL); });
  onceVisible(colo, function () { colo.classList.add("play"); setTimeout(function () { sfx("thud"); }, 300); }, 0.4);

  /* ================= small details: sound, dust, stamps, pen, Seal Book ================= */

  /* our own quiet sounds: pen scratch, soft tap, and a slow calm tune.
     They follow the hero's sound button. */
  var AUD = (function () {
    var ctx = null, out = null, amb = null, playing = false, timer = 0;
    function soundOn() { return !window.SDSFX || window.SDSFX.isOn(); }
    function ensure() {
      if (!ctx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        try { ctx = new AC(); } catch (e) { return null; }
        out = ctx.createGain(); out.gain.value = 1; out.connect(ctx.destination);
      }
      if (ctx.state === "suspended" && !document.hidden) ctx.resume();
      return ctx;
    }
    function noiseBuf(dur) {
      var n = Math.floor(ctx.sampleRate * dur), b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0);
      for (var j = 0; j < n; j++) d[j] = (Math.random() * 2 - 1) * (1 - j / n);
      return b;
    }
    function scratch() {
      if (!soundOn() || !ensure()) return;
      var t = ctx.currentTime;
      for (var i = 0; i < 3; i++) {
        var dur = 0.05 + Math.random() * 0.05, s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
        s.buffer = noiseBuf(dur); f.type = "bandpass"; f.frequency.value = 2600 + Math.random() * 2400; f.Q.value = 1.3;
        var st = t + i * (0.06 + Math.random() * 0.04);
        g.gain.setValueAtTime(0.0001, st); g.gain.exponentialRampToValueAtTime(0.045, st + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, st + dur);
        s.connect(f); f.connect(g); g.connect(out); s.start(st); s.stop(st + dur + 0.02);
      }
    }
    function tap() {
      if (!soundOn() || !ensure()) return;
      var t = ctx.currentTime, o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.setValueAtTime(130, t); o.frequency.exponentialRampToValueAtTime(48, t + 0.22);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.22, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
      o.connect(g); g.connect(out); o.start(t); o.stop(t + 0.3);
    }
    function hz(m) { return 440 * Math.pow(2, (m - 69) / 12); }
    var CHORDS = [[45, 52, 55, 60, 64], [41, 48, 52, 57, 60], [48, 55, 59, 64, 67], [43, 50, 55, 59, 62]];
    var MEL = [69, 72, 74, 76, 79, 81];
    function startAmb() {
      if (playing || !soundOn() || !ensure()) return;
      playing = true;
      var now = ctx.currentTime;
      amb = ctx.createGain(); amb.gain.setValueAtTime(0.0001, now); amb.gain.exponentialRampToValueAtTime(0.85, now + 6);
      var lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1300;
      var len = Math.floor(ctx.sampleRate * 3.4), rb = ctx.createBuffer(2, len, ctx.sampleRate);
      for (var c = 0; c < 2; c++) { var d = rb.getChannelData(c); for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6); }
      var rv = ctx.createConvolver(); rv.buffer = rb;
      var wet = ctx.createGain(); wet.gain.value = 0.6; var dry = ctx.createGain(); dry.gain.value = 0.55;
      lp.connect(dry); lp.connect(rv); rv.connect(wet); dry.connect(amb); wet.connect(amb); amb.connect(out);
      var ci = 0, next = now + 0.3;
      function chord(at, notes) {
        notes.forEach(function (m, k) {
          var o = ctx.createOscillator(), g = ctx.createGain(), peak = k === 0 ? 0.032 : 0.012;
          o.type = k === 0 ? "sine" : "triangle"; o.frequency.value = hz(m); o.detune.value = (Math.random() - 0.5) * 8;
          g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(peak, at + 3.4);
          g.gain.setValueAtTime(peak, at + 7); g.gain.exponentialRampToValueAtTime(0.0001, at + 11.5);
          o.connect(g); g.connect(lp); o.start(at); o.stop(at + 11.7);
        });
      }
      function pluck(at, m) {
        var o = ctx.createOscillator(), g = ctx.createGain();
        o.type = "sine"; o.frequency.value = hz(m);
        g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(0.018, at + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, at + 3.6);
        o.connect(g); g.connect(lp); o.start(at); o.stop(at + 3.7);
      }
      (function schedule() {
        if (!playing) return;
        while (next < ctx.currentTime + 12) {
          chord(next, CHORDS[ci % CHORDS.length]);
          for (var p = 0, n = 2 + Math.floor(Math.random() * 2); p < n; p++) {
            if (Math.random() < 0.75) pluck(next + 1.4 + p * (2 + Math.random() * 1.4), MEL[Math.floor(Math.random() * MEL.length)]);
          }
          next += 8; ci++;
        }
        timer = setTimeout(schedule, 3000);
      })();
    }
    function stopAmb() {
      if (!playing) return;
      playing = false; clearTimeout(timer);
      var a = amb; amb = null;
      if (a && ctx) {
        var t = ctx.currentTime;
        a.gain.cancelScheduledValues(t); a.gain.setValueAtTime(Math.max(0.0001, a.gain.value), t); a.gain.exponentialRampToValueAtTime(0.0001, t + 1.5);
        setTimeout(function () { try { a.disconnect(); } catch (e) {} }, 1800);
      }
    }
    document.addEventListener("visibilitychange", function () {
      if (!ctx) return;
      if (document.hidden) ctx.suspend(); else if (soundOn()) ctx.resume();
    });
    return { scratch: scratch, tap: tap, startAmb: startAmb, stopAmb: stopAmb, soundOn: soundOn };
  })();
  ["pointerdown", "keydown", "touchstart"].forEach(function (ev) {
    window.addEventListener(ev, function () { if (AUD.soundOn()) AUD.startAmb(); }, { once: true, passive: true });
  });
  var soundBtn = document.getElementById("soundBtn");
  if (soundBtn) soundBtn.addEventListener("click", function () {
    setTimeout(function () { if (AUD.soundOn()) AUD.startAmb(); else AUD.stopAmb(); }, 0);
  });

  /* tiny shiny dust drifting over the whole page */
  (function sparkle() {
    if (reduce) return;
    var c = document.createElement("canvas");
    c.className = "sparkle"; c.setAttribute("aria-hidden", "true");
    document.body.appendChild(c);
    var g = c.getContext("2d"), W = 0, H = 0, P = [];
    function size() {
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      W = window.innerWidth; H = window.innerHeight;
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    size(); window.addEventListener("resize", size);
    function spawn(p, fresh) {
      p.x = Math.random() * W; p.y = fresh ? Math.random() * H : H + 8;
      p.r = 0.5 + Math.random() * 1.25; p.vy = -(4 + Math.random() * 9); p.vx = (Math.random() - 0.5) * 3;
      p.ph = Math.random() * 6.28; p.sp = 0.5 + Math.random() * 1.6; p.a = 0.3 + Math.random() * 0.5;
    }
    for (var i = 0, N = W < 700 ? 22 : 40; i < N; i++) { var p = {}; spawn(p, true); P.push(p); }
    var last = performance.now();
    function frame(now) {
      if (document.hidden) { last = now; requestAnimationFrame(frame); return; }
      var dt = Math.min(0.05, (now - last) / 1000), t = now / 1000; last = now;
      g.clearRect(0, 0, W, H);
      g.fillStyle = "#F4DFA6";
      for (var k = 0; k < P.length; k++) {
        var q = P[k];
        q.y += q.vy * dt; q.x += (q.vx + Math.sin(t * 0.6 + q.ph) * 3) * dt;
        if (q.y < -8) spawn(q, false);
        var tw = 0.5 + 0.5 * Math.sin(t * q.sp * 2 + q.ph), a = q.a * (0.2 + 0.8 * tw * tw);
        g.globalAlpha = a * 0.18; g.beginPath(); g.arc(q.x, q.y, q.r * 3.2, 0, 6.283); g.fill();
        g.globalAlpha = a; g.beginPath(); g.arc(q.x, q.y, q.r, 0, 6.283); g.fill();
        if (q.r > 1.3 && tw > 0.86) {
          g.globalAlpha = a * 0.55;
          g.fillRect(q.x - q.r * 3.4, q.y - 0.35, q.r * 6.8, 0.7);
          g.fillRect(q.x - 0.35, q.y - q.r * 3.4, 0.7, q.r * 6.8);
        }
      }
      g.globalAlpha = 1;
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  })();

  /* the wax seal over each chapter is stamped as it comes into view */
  if (!reduce) {
    document.querySelectorAll(".ch-head .orn").forEach(function (orn) {
      orn.classList.add("wait");
      onceVisible(orn, function () {
        orn.classList.remove("wait"); orn.classList.add("stamp");
        setTimeout(AUD.tap, 240);
      }, 0.9);
    });
  }

  /* ================= The Seal Book: a hidden guestbook on the last page ================= */
  var WAX = {
    oxblood: ["#7A2620", "#62201B", "#C26A5C"],
    forest: ["#1F4A36", "#173A2A", "#6FA585"],
    midnight: ["#22305A", "#1A2547", "#7F93CC"]
  };
  function cleanInit(s) { return String(s == null ? "" : s).toUpperCase().replace(/[^A-Z]/g, "").slice(0, 3); }
  function sealSVG(init, col, cls) {
    var w = WAX[col] || WAX.oxblood, big = init.length > 2;
    return '<svg class="' + cls + '" viewBox="0 0 100 100" aria-hidden="true"><polygon points="' + SEAL + '" fill="' + w[0] + '"></polygon>' +
      '<circle cx="50" cy="50" r="39.5" fill="none" stroke="' + w[2] + '" stroke-width="1" stroke-dasharray="2 2.2" opacity=".8"></circle>' +
      '<circle cx="50" cy="50" r="36" fill="' + w[1] + '"></circle>' +
      '<text x="50" y="' + (big ? 59 : 61) + '" text-anchor="middle" font-family="Playfair Display, Georgia, serif" font-style="italic" font-weight="600" font-size="' + (big ? 25 : 31) + '" fill="' + w[2] + '">' + esc(init || "?") + '</text></svg>';
  }
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDay(iso) { var d = new Date(iso); return isNaN(d) ? "" : d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear(); }
  function rotFor(id) { var h = 0; for (var i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0; return ((Math.abs(h) % 17) - 8) + "deg"; }

  var coloSeal = document.querySelector(".colo-seal"), sealHint = document.getElementById("sealHint"), book = document.getElementById("sealbook");
  if (coloSeal && book) {
    var sbInit = document.getElementById("sbInit"), sbPrev = document.getElementById("sbPreview"), sbPress = document.getElementById("sbPress"),
      sbMsg = document.getElementById("sbMsg"), sbCount = document.getElementById("sbCount"), wall = document.getElementById("sealWall"),
      colorBtns = [].slice.call(book.querySelectorAll(".sb-colors button"));
    // Seals are kept in a small free database (Supabase). Its public key is meant to be in the page;
    // the table only lets visitors add and read seals. Without it, the seal is pressed but not kept.
    var STORE = D.seals && D.seals.url && D.seals.key ? D.seals : null;
    var SB = { color: "oxblood", started: false, pressed: false };
    function myLast() { try { return JSON.parse(localStorage.getItem("sd-my-seal") || "null"); } catch (e) { return null; } }
    function rememberMine(row) { try { localStorage.setItem("sd-my-seal", JSON.stringify({ id: row.id, at: row.created_at })); } catch (e) {} }
    function showSigned(row) {  // already signed from this browser: show their seal instead of the form
      book.classList.add("signed");
      sbPrev.innerHTML = sealSVG(cleanInit(row.initials), WAX[row.color] ? row.color : "oxblood", "sb-seal");
      sbMsg.textContent = SB.pressed ? "Sealed. Thank you for stopping by." : "You left your seal here on " + fmtDay(row.created_at) + ". Thank you for stopping by.";
    }
    function api(path, opts) {
      opts = opts || {};
      var headers = { apikey: STORE.key, "Content-Type": "application/json" };
      if (STORE.key.split(".").length === 3) headers.Authorization = "Bearer " + STORE.key;  // older anon keys are JWTs
      for (var h in opts.headers || {}) headers[h] = opts.headers[h];
      return fetch(STORE.url.replace(/\/$/, "") + "/rest/v1/" + path, {
        method: opts.method || "GET", headers: headers, body: opts.body ? JSON.stringify(opts.body) : undefined
      }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
    }
    function drawPreview() { sbPrev.innerHTML = sealSVG(cleanInit(sbInit.value), SB.color, "sb-seal"); }
    drawPreview();
    sbInit.addEventListener("input", function () {
      var v = cleanInit(sbInit.value);
      if (sbInit.value !== v) sbInit.value = v;
      drawPreview();
    });
    colorBtns.forEach(function (b) {
      b.addEventListener("click", function () {
        SB.color = b.dataset.c;
        colorBtns.forEach(function (x) { x.setAttribute("aria-checked", String(x === b)); });
        drawPreview();
      });
    });

    var taps = 0, tapTimer = 0;
    function tapSeal() {
      if (!book.hidden) { book.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" }); return; }
      taps++; clearTimeout(tapTimer);
      tapTimer = setTimeout(function () { taps = 0; }, 1600);
      coloSeal.classList.remove("tap"); void coloSeal.getBoundingClientRect(); coloSeal.classList.add("tap");
      AUD.tap();
      if (taps >= 3) { taps = 0; openBook(); }
    }
    coloSeal.addEventListener("click", tapSeal);
    coloSeal.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tapSeal(); } });

    function openBook() {
      book.hidden = false;
      if (sealHint) sealHint.textContent = "You found it.";
      sfx("page");
      setTimeout(function () { book.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" }); }, 120);
      if (SB.started) return;
      SB.started = true;
      if (!STORE) { sbCount.textContent = ""; wall.hidden = true; return; }
      loadWall();
    }
    function loadWall() {
      api("seals?select=id,initials,color,created_at&order=created_at.desc&limit=120").then(renderWall, function () {
        sbCount.textContent = "The Seal Book could not be opened right now.";
      });
    }
    function renderWall(rows) {
      var mine = myLast();
      sbCount.textContent = rows.length === 0 ? "No seals yet. Yours can be the first." : rows.length === 1 ? "1 seal in the book" : rows.length + " seals in the book";
      var own = mine && rows.filter(function (v) { return String(v.id) === String(mine.id); })[0];
      if (own) showSigned(own);
      wall.innerHTML = rows.map(function (v) {
        var id = String(v.id), col = WAX[v.color] ? v.color : "oxblood", me = mine && String(mine.id) === id;
        return '<figure class="sw' + (me ? " me" : "") + '" style="--rot:' + rotFor(id) + '">' +
          sealSVG(cleanInit(v.initials), col, "sw-seal") + "<figcaption>" + esc(fmtDay(v.created_at)) + "</figcaption></figure>";
      }).join("");
    }
    sbPress.addEventListener("click", function () {
      var init = cleanInit(sbInit.value);
      if (!init) { sbMsg.textContent = "Type one to three letters first."; sbInit.focus(); return; }
      if (STORE && myLast()) { sbMsg.textContent = "You have already signed the book from this browser. One seal each."; return; }
      sbPrev.classList.remove("pressed"); void sbPrev.getBoundingClientRect(); sbPrev.classList.add("pressed");
      SB.pressed = true;
      setTimeout(function () { sfx("thud"); }, 260);
      if (!STORE) { sbMsg.textContent = "Pressed. Your seal is set in wax."; return; }
      sbPress.disabled = true;
      api("seals", { method: "POST", headers: { Prefer: "return=representation" }, body: { initials: init, color: SB.color } }).then(function (rows) {
        if (rows && rows[0]) rememberMine(rows[0]);
        sbMsg.textContent = "Sealed. Thank you for stopping by.";
        loadWall();
      }, function () {
        sbMsg.textContent = "Could not save right now. Try again in a moment.";
      }).then(function () { sbPress.disabled = false; });
    });
  }

  window.SD_AUD = AUD;

  /* ================= top bar + contents ================= */
  var topbar = document.getElementById("topbar"), stage = document.getElementById("stage");
  var tocLinks = [].slice.call(document.querySelectorAll(".toc a"));
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { topbar.classList.toggle("show", !es[0].isIntersecting); }, { threshold: 0.08 }).observe(stage);
    var spy = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) tocLinks.forEach(function (a) { a.classList.toggle("on", a.getAttribute("href") === "#" + en.target.id); });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    ["folio", "margins", "desk", "stacks", "colophon"].forEach(function (id) { spy.observe(document.getElementById(id)); });
  }
})();
