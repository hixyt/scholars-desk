(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canHover = window.matchMedia && window.matchMedia("(hover: hover)").matches;
  var stage = document.getElementById("stage");
  var canvas = document.getElementById("gl");
  var labelEl = document.getElementById("label");
  var bookGo = document.getElementById("bookGo");
  bookGo.addEventListener("click", function () { if (window.SD_openFolioBook) window.SD_openFolioBook(+bookGo.dataset.paper); });
  var fadeEl = document.getElementById("fade");
  var loadingEl = document.getElementById("loading");
  var imprintsEl = document.getElementById("imprints");
  var svgNS = "http://www.w3.org/2000/svg";

  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var ease = function (x) { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };
  var easeOut = function (x) { x = clamp(x, 0, 1); return 1 - Math.pow(1 - x, 3); };
  function rng(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function sealPoints(cx, cy, r, n) {
    var out = [];
    for (var i = 0; i < n; i++) {
      var a = (i / n) * Math.PI * 2;
      var rr = r * (1 + (2.4 * Math.sin(a * 9) + 1.3 * Math.sin(a * 21 + 0.7)) / 45);
      out.push([cx + rr * Math.cos(a), cy + rr * Math.sin(a)]);
    }
    return out;
  }
  var SEAL_SVG = sealPoints(50, 50, 45, 120).map(function (p) { return p[0].toFixed(2) + "," + p[1].toFixed(2); }).join(" ");
  document.querySelectorAll("[data-seal]").forEach(function (p) { p.setAttribute("points", SEAL_SVG); });

  /* ---------- Sound (synthesised, off until the viewer turns it on) ---------- */
  var SFX = (function () {
    var ctx = null, master = null, on = true;
    function ensure() {
      if (!ctx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        try { ctx = new AC(); } catch (e) { return null; }
        master = ctx.createGain(); master.gain.value = 0.55; master.connect(ctx.destination);
      }
      if (ctx.state === "suspended") ctx.resume();
      return ctx;
    }
    function noise(dur) {
      var n = Math.floor(ctx.sampleRate * dur), b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0);
      for (var i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
      var s = ctx.createBufferSource(); s.buffer = b; return s;
    }
    function env(g, t, peak, a, dcy) {
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(peak, t + a);
      g.gain.exponentialRampToValueAtTime(0.0001, t + a + dcy);
    }
    function page() {
      if (!on || !ensure()) return;
      var t = ctx.currentTime, s = noise(0.5), f = ctx.createBiquadFilter(), g = ctx.createGain();
      f.type = "bandpass"; f.Q.value = 0.7;
      f.frequency.setValueAtTime(1500, t); f.frequency.exponentialRampToValueAtTime(5200, t + 0.16); f.frequency.exponentialRampToValueAtTime(2200, t + 0.42);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.32, t + 0.05); g.gain.exponentialRampToValueAtTime(0.1, t + 0.2); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
      s.connect(f); f.connect(g); g.connect(master); s.start(t); s.stop(t + 0.5);
    }
    function whoosh() {
      if (!on || !ensure()) return;
      var t = ctx.currentTime, s = noise(0.5), f = ctx.createBiquadFilter(), g = ctx.createGain();
      f.type = "bandpass"; f.Q.value = 1.2;
      f.frequency.setValueAtTime(300, t); f.frequency.exponentialRampToValueAtTime(1800, t + 0.42);
      env(g, t, 0.16, 0.3, 0.15);
      s.connect(f); f.connect(g); g.connect(master); s.start(t); s.stop(t + 0.5);
    }
    function thud() {
      if (!on || !ensure()) return;
      var t = ctx.currentTime, o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.3);
      env(g, t, 0.9, 0.006, 0.38);
      o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.42);
      var s = noise(0.08), f = ctx.createBiquadFilter(), g2 = ctx.createGain();
      f.type = "lowpass"; f.frequency.value = 900; env(g2, t, 0.35, 0.003, 0.06);
      s.connect(f); f.connect(g2); g2.connect(master); s.start(t); s.stop(t + 0.08);
    }
    function chime() {
      if (!on || !ensure()) return;
      var t = ctx.currentTime;
      [880, 1320].forEach(function (fr, i) {
        var o = ctx.createOscillator(), g = ctx.createGain();
        o.type = "sine"; o.frequency.value = fr; env(g, t + i * 0.06, 0.07, 0.01, 1.1);
        o.connect(g); g.connect(master); o.start(t + i * 0.06); o.stop(t + 1.3);
      });
    }
    return { set: function (v) { on = v; if (v) { ensure(); chime(); } }, isOn: function () { return on; }, unlock: function () { if (on) ensure(); }, page: page, whoosh: whoosh, thud: thud };
  })();
  window.SDSFX = SFX;
  ["pointerdown", "keydown", "touchstart"].forEach(function (ev) {
    window.addEventListener(ev, function () { SFX.unlock(); }, { once: true, passive: true });
  });
  (function soundToggle() {
    var btn = document.getElementById("soundBtn");
    btn.addEventListener("click", function () {
      var v = !SFX.isOn(); SFX.set(v);
      btn.setAttribute("aria-pressed", String(v));
      btn.querySelector(".st").textContent = v ? "Sound on" : "Sound off";
    });
  })();
  /* ---------- Quill cursor (fine pointers only) ---------- */
  (function quill() {
    if (reduce || !window.matchMedia || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    var q = document.getElementById("quill");
    document.body.classList.add("quill-on");
    var x = 0, y = 0, qx = 0, qy = 0, shown = false;
    window.addEventListener("pointermove", function (e) {
      x = e.clientX; y = e.clientY;
      if (!shown) { qx = x; qy = y; shown = true; q.classList.add("show"); }
      var hot = (e.target.closest && e.target.closest("button, a, .face, .leaf, .lastpg, .b3")) || (e.target === canvas && canvas.style.cursor === "pointer");
      q.classList.toggle("hot", !!hot);
    });
    document.documentElement.addEventListener("pointerleave", function () { q.classList.remove("show"); shown = false; });
    window.addEventListener("pointerdown", function (e) {
      q.classList.add("press");
      var d = document.createElement("span");
      d.className = "ink"; d.style.left = e.clientX + "px"; d.style.top = e.clientY + "px";
      document.body.appendChild(d); setTimeout(function () { d.remove(); }, 650);
    });
    window.addEventListener("pointerup", function () { q.classList.remove("press"); });
    (function tick() {
      qx += (x - qx) * 0.38; qy += (y - qy) * 0.38;
      q.style.transform = "translate(" + (qx - 5).toFixed(1) + "px," + (qy - 25).toFixed(1) + "px)";
      requestAnimationFrame(tick);
    })();
  })();

  /* ---------- Bookplate ---------- */
  (function bookplate() {
    var plate = document.getElementById("plate");
    var tilt = document.getElementById("plateTilt");
    var tagBtns = Array.prototype.slice.call(document.querySelectorAll(".exlib-tag"));
    var scrim = document.getElementById("plateScrim");
    function flip() { plate.classList.toggle("flipped"); SFX.page(); }
    plate.querySelectorAll("[data-flip]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); flip(); });
    });
    plate.addEventListener("click", function (e) { if (e.target.closest("a, button")) return; flip(); });
    function setExpanded(v) { tagBtns.forEach(function (b) { b.setAttribute("aria-expanded", v); }); }
    function openPlate() { plate.classList.add("open"); scrim.classList.add("open"); setExpanded("true"); }
    function closePlate() { plate.classList.remove("open", "flipped"); scrim.classList.remove("open"); setExpanded("false"); }
    tagBtns.forEach(function (b) { b.addEventListener("click", openPlate); });
    scrim.addEventListener("click", closePlate);
    window.addEventListener("keydown", function (e) { if (e.key === "Escape") closePlate(); });
    if (reduce) return;
    window.addEventListener("pointermove", function (e) {
      var r = plate.getBoundingClientRect();
      if (!r.width) return;
      var dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
      var near = Math.max(0, 1 - Math.hypot(dx, dy) / 560);
      tilt.style.setProperty("--rx", (clamp(-dy / r.height, -1, 1) * 10 * near).toFixed(2) + "deg");
      tilt.style.setProperty("--ry", (clamp(dx / r.width, -1, 1) * 14 * near).toFixed(2) + "deg");
      plate.style.setProperty("--mx", (((e.clientX - r.left) / r.width) * 100).toFixed(1) + "%");
      plate.style.setProperty("--my", (((e.clientY - r.top) / r.height) * 100).toFixed(1) + "%");
    });
  })();

  (function grain() {
    try {
      var c = document.createElement("canvas"); c.width = c.height = 140;
      var g = c.getContext("2d"); var d = g.createImageData(140, 140);
      for (var i = 0; i < d.data.length; i += 4) { var v = (Math.random() * 255) | 0; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
      g.putImageData(d, 0, 0);
      document.getElementById("grain").style.backgroundImage = "url(" + c.toDataURL("image/png") + ")";
    } catch (e) {}
  })();

  if (typeof THREE === "undefined") { loadingEl.textContent = "The 3D library didn’t load. Refresh the page to try again."; return; }

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, powerPreference: "high-performance" });
  } catch (e) {
    loadingEl.textContent = "This browser couldn’t start 3D. Try a recent Chrome or Safari.";
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.06;
  renderer.setClearColor(0x0B0907, 1);
  var maxAniso = Math.min(8, renderer.capabilities.getMaxAnisotropy ? renderer.capabilities.getMaxAnisotropy() : 1);

  var camera = new THREE.PerspectiveCamera(40, 1, 0.1, 200);
  var TANH = Math.tan((20 * Math.PI) / 180);
  var ray = new THREE.Raycaster();
  var W = 1, H = 1;
  var L = { headerBottom: 80, hintTop: 700, copyRight: 600, copyTop: 500 };
  var CTR = { x: 0, y: 0 };

  function distFactor() {
    var a = W / H;
    if (a < 0.62) return 1.6;
    if (a < 0.8) return 1.38;
    if (a < 1.1) return 1.16;
    return 1;
  }
  function textRight(el) {
    if (!el) return 0;
    try { var r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().right; }
    catch (e) { return el.getBoundingClientRect().right; }
  }
  function measure() {
    var sr = stage.getBoundingClientRect();
    var hi = document.querySelector(".hintbar").getBoundingClientRect();
    var cp = document.querySelector(".copy").getBoundingClientRect();
    var right = Math.max(textRight(document.querySelector(".copy h1")), textRight(document.querySelector(".copy .sub")), textRight(document.querySelector(".copy .eyebrow")));
    L.hintTop = hi.top - sr.top; L.copyTop = cp.top - sr.top; L.copyRight = right - sr.left;
    L.headerBottom = document.querySelector(".top").getBoundingClientRect().bottom - sr.top;
  }
  function resize() {
    var r = stage.getBoundingClientRect();
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    renderer.setSize(W, H, false);
    measure();
    var wide = W >= 900;
    CTR.x = wide ? (L.copyRight + 24 + W - 26) / 2 : W / 2;
    CTR.y = wide ? (L.headerBottom + 6 + L.hintTop - 8) / 2 : (L.headerBottom + 6 + L.copyTop + 28) / 2;
    camera.setViewOffset(W, H, W / 2 - CTR.x, H / 2 - CTR.y, W, H);
    camera.updateProjectionMatrix();
  }

  function C(hex) { return new THREE.Color(hex).convertSRGBToLinear(); }
  function tex(c, srgb) {
    var t = new THREE.CanvasTexture(c);
    if (srgb) t.encoding = THREE.sRGBEncoding;
    t.anisotropy = maxAniso;
    return t;
  }
  var DOT = (function () {
    var c = document.createElement("canvas"); c.width = c.height = 64;
    var g = c.getContext("2d");
    var gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,255,255,1)");
    gr.addColorStop(0.18, "rgba(255,255,255,0.85)");
    gr.addColorStop(0.45, "rgba(255,255,255,0.22)");
    gr.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    var t = new THREE.CanvasTexture(c); t.__shared = true; return t;
  })();
  function addMat(o) {
    return Object.assign({ map: DOT, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }, o);
  }
  function pointsFrom(vs, o) {
    var a = new Float32Array(vs.length * 3);
    vs.forEach(function (v, i) { a[i * 3] = v.x; a[i * 3 + 1] = v.y; a[i * 3 + 2] = v.z; });
    var g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3));
    return new THREE.Points(g, new THREE.PointsMaterial(addMat({ size: o.size, color: o.color, opacity: o.opacity, sizeAttenuation: true })));
  }
  function makeDust(n, box, color, size, opacity) {
    var a = new Float32Array(n * 3), seed = new Float32Array(n);
    for (var i = 0; i < n; i++) {
      a[i * 3] = (Math.random() - 0.5) * box.x;
      a[i * 3 + 1] = (Math.random() - 0.5) * box.y;
      a[i * 3 + 2] = (Math.random() - 0.5) * box.z;
      seed[i] = Math.random();
    }
    var g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(a, 3));
    var p = new THREE.Points(g, new THREE.PointsMaterial(addMat({ size: size, color: color, opacity: opacity })));
    var lt = null;
    p.userData.tick = function (t) {
      var dt = lt === null ? 0 : Math.min(0.05, t - lt); lt = t;
      if (reduce) return;
      for (var i = 0; i < n; i++) {
        var s = seed[i];
        a[i * 3 + 1] += (0.05 + s * 0.13) * dt;
        a[i * 3] += Math.sin(t * 0.4 + s * 20) * 0.05 * dt;
        if (a[i * 3 + 1] > box.y / 2) a[i * 3 + 1] = -box.y / 2;
      }
      g.attributes.position.needsUpdate = true;
    };
    return p;
  }

  var ptr = { x: 0, y: 0, sx: 0, sy: 0, has: false, down: false, moved: 0, lx: 0, ly: 0, gx0: 0, gy0: 0, gx: 0, gy: 0, dragX: 0, vx: 0 };
  function setPtr(e) {
    var r = canvas.getBoundingClientRect();
    ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  }
  canvas.addEventListener("pointerdown", function (e) {
    setPtr(e); ptr.has = true; ptr.down = true; ptr.moved = 0;
    ptr.lx = ptr.gx0 = e.clientX; ptr.ly = ptr.gy0 = e.clientY; ptr.gx = ptr.gy = 0; ptr.vx = 0;
    try { canvas.setPointerCapture(e.pointerId); } catch (err) {}
  });
  canvas.addEventListener("pointermove", function (e) {
    setPtr(e); ptr.has = true;
    if (ptr.down) {
      var dx = e.clientX - ptr.lx, dy = e.clientY - ptr.ly;
      ptr.moved += Math.abs(dx) + Math.abs(dy);
      ptr.vx = dx * 0.006; ptr.dragX += ptr.vx;
      ptr.gx = e.clientX - ptr.gx0; ptr.gy = e.clientY - ptr.gy0;
      ptr.lx = e.clientX; ptr.ly = e.clientY;
    }
  });
  function endPtr(e) {
    if (!ptr.down) return;
    ptr.down = false; ptr.gx = ptr.gy = 0;
    if (ptr.moved < 8 && hero && hero.tap) { setPtr(e); hero.tap(ptr.x, ptr.y); }
    if (e.pointerType !== "mouse") ptr.has = false;
  }
  canvas.addEventListener("pointerup", endPtr);
  canvas.addEventListener("pointercancel", function () { ptr.down = false; ptr.has = false; ptr.gx = ptr.gy = 0; });
  canvas.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse" && !ptr.down) ptr.has = false; });
  canvas.addEventListener("wheel", function (e) { ptr.vx += clamp(e.deltaY * 0.0006, -0.05, 0.05); }, { passive: true });

  function showLabel(world, small, text) {
    var v = world.clone().project(camera);
    var x = clamp((v.x * 0.5 + 0.5) * W, 130, W - 130), y = clamp((-v.y * 0.5 + 0.5) * H, 90, H);
    labelEl.style.left = x + "px"; labelEl.style.top = y + "px";
    if (labelEl.dataset.key !== small + text) {
      labelEl.replaceChildren();
      var s = document.createElement("small"); s.textContent = small;
      var d = document.createElement("span"); d.textContent = text;
      labelEl.append(s, d); labelEl.dataset.key = small + text;
    }
    labelEl.hidden = false;
  }
  function hideLabel() { if (!labelEl.hidden) labelEl.hidden = true; }

  /* ---------- Books ---------- */
  var TOPICS = [
    { title: "Attention", vol: "Vol. I", css: "#6B231E" },
    { title: "Agents", vol: "Vol. II", css: "#1E3A2B" },
    { title: "Retrieval", vol: "Vol. III", css: "#1B2A45" },
    { title: "Diffusion", vol: "Vol. IV", css: "#4A3020" },
    { title: "Alignment", vol: "Vol. V", css: "#3B1F33" },
    { title: "Reasoning", vol: "Vol. VI", css: "#6B231E" },
    { title: "Vision", vol: "Vol. VII", css: "#1E3A2B" },
    { title: "Speech", vol: "Vol. VIII", css: "#1B2A45" },
    { title: "Robotics", vol: "Vol. IX", css: "#4A3020" },
    { title: "Evaluation", vol: "Vol. X", css: "#3B1F33" },
    { title: "Prompting", vol: "Vol. XI", css: "#6B231E" },
    { title: "Memory", vol: "Vol. XII", css: "#1E3A2B" },
    { title: "Safety", vol: "Vol. XIII", css: "#1B2A45" },
    { title: "Multimodal", vol: "Vol. XIV", css: "#4A3020" },
    { title: "Planning", vol: "Vol. XV", css: "#3B1F33" }
  ];
  var SD = window.SD_DATA || { today: [], short: {} };
  var ROMAN_N = ["I", "II", "III", "IV", "V"];
  var PAPER_BOOKS = SD.today.map(function (p, i) {
    return { title: SD.short[p.id] || p.title.split(":")[0], vol: "Today · " + ROMAN_N[i], css: ["#6B231E", "#1E3A2B", "#1B2A45", "#4A3020", "#3B1F33"][i], paper: i };
  });
  function wrapLines(g, text, maxW) {
    var words = String(text).split(/\s+/), lines = [], cur = "";
    words.forEach(function (w) { var tryL = cur ? cur + " " + w : w; if (g.measureText(tryL).width > maxW && cur) { lines.push(cur); cur = w; } else cur = tryL; });
    if (cur) lines.push(cur);
    return lines;
  }
  function paperPageTex(info) {
    var p = SD.today[info.paper], Wc = 768, Hc = 1080, c = document.createElement("canvas"); c.width = Wc; c.height = Hc; var g = c.getContext("2d");
    g.fillStyle = "#EDE3CA"; g.fillRect(0, 0, Wc, Hc);
    var vg = g.createRadialGradient(Wc / 2, Hc / 2, Hc * 0.25, Wc / 2, Hc / 2, Hc * 0.78);
    vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(120,88,48,0.24)"); g.fillStyle = vg; g.fillRect(0, 0, Wc, Hc);
    g.textAlign = "center"; g.textBaseline = "alphabetic";
    g.fillStyle = "#7A2620"; g.font = '600 30px "Cinzel", Georgia, serif'; g.fillText(info.vol.toUpperCase(), Wc / 2, 120);
    g.fillStyle = "#2B2118";
    var fs = 84; g.font = 'italic 500 ' + fs + 'px "Playfair Display", Georgia, serif';
    while (g.measureText(info.title).width > Wc - 120 && fs > 46) { fs -= 4; g.font = 'italic 500 ' + fs + 'px "Playfair Display", Georgia, serif'; }
    g.fillText(info.title, Wc / 2, 230);
    g.fillStyle = "#B08E52"; g.fillRect(Wc / 2 - 110, 272, 80, 3); g.fillRect(Wc / 2 + 30, 272, 80, 3);
    g.save(); g.translate(Wc / 2, 273); g.rotate(Math.PI / 4); g.fillRect(-7, -7, 14, 14); g.restore();
    g.fillStyle = "#6B5A45"; g.font = '600 26px "Cinzel", Georgia, serif'; g.fillText("WHY READ IT", Wc / 2, 360);
    g.fillStyle = "#2B2118"; g.font = 'italic 400 38px "Spectral", Georgia, serif';
    var lines = wrapLines(g, p.reason || p.explanation, Wc - 140).slice(0, 9);
    lines.forEach(function (l, n) { g.fillText(l, Wc / 2, 430 + n * 54); });
    g.fillStyle = "#7A2620"; g.font = '600 26px "Cinzel", Georgia, serif'; g.fillText("READ IT IN THE FOLIO BELOW", Wc / 2, Hc - 110);
    g.fillRect(Wc / 2 - 1, Hc - 90, 2, 30);
    return tex(c, true);
  }
  function endpaperTex(info) {
    var Wc = 384, Hc = 556, c = document.createElement("canvas"); c.width = Wc; c.height = Hc; var g = c.getContext("2d");
    g.fillStyle = "#2A1D14"; g.fillRect(0, 0, Wc, Hc);
    g.strokeStyle = "rgba(201,164,92,.7)"; g.lineWidth = 2; g.strokeRect(26, 26, Wc - 52, Hc - 52);
    g.fillStyle = "#C9A45C"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = '600 17px "Cinzel", Georgia, serif'; g.fillText("EX LIBRIS", Wc / 2, 150);
    g.font = 'italic 600 120px "Playfair Display", Georgia, serif'; g.fillText(ROMAN_N[info.paper], Wc / 2, Hc / 2);
    g.font = '600 13px "Cinzel", Georgia, serif'; g.fillText("THE SCHOLAR’S DESK", Wc / 2, Hc - 140);
    return tex(c, true);
  }
  var texCache = {};
  function coverTex(b) {
    if (texCache["c" + b.title]) return texCache["c" + b.title];
    texCache["c" + b.title] = coverTexDraw(b);
    return texCache["c" + b.title];
  }
  function coverTexDraw(b) {
    var Wc = 384, Hc = 556, c = document.createElement("canvas"); c.width = Wc; c.height = Hc;
    var g = c.getContext("2d");
    g.fillStyle = b.css; g.fillRect(0, 0, Wc, Hc);
    for (var i = 0; i < 3200; i++) {
      g.fillStyle = Math.random() < 0.5 ? "rgba(0,0,0,0.07)" : "rgba(255,255,255,0.025)";
      g.fillRect(Math.random() * Wc, Math.random() * Hc, 1 + Math.random() * 2, 1 + Math.random() * 2);
    }
    var vg = g.createRadialGradient(Wc / 2, Hc / 2, Hc * 0.15, Wc / 2, Hc / 2, Hc * 0.7);
    vg.addColorStop(0, "rgba(255,240,210,0.06)"); vg.addColorStop(1, "rgba(0,0,0,0.42)");
    g.fillStyle = vg; g.fillRect(0, 0, Wc, Hc);
    g.strokeStyle = "#C9A45C"; g.lineWidth = 4; g.strokeRect(22, 22, Wc - 44, Hc - 44);
    g.lineWidth = 1.2; g.strokeRect(33, 33, Wc - 66, Hc - 66);
    g.fillStyle = "#C9A45C";
    [[33, 33], [Wc - 33, 33], [33, Hc - 33], [Wc - 33, Hc - 33]].forEach(function (p) {
      g.save(); g.translate(p[0], p[1]); g.rotate(Math.PI / 4); g.fillRect(-5, -5, 10, 10); g.restore();
    });
    g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = "#D9BC7A";
    g.font = '600 19px "Cinzel", Georgia, serif'; g.fillText(b.vol.toUpperCase(), Wc / 2, 128);
    var fs = 70; g.font = "italic 500 " + fs + 'px "Playfair Display", Georgia, serif';
    while (g.measureText(b.title).width > Wc - 96 && fs > 30) { fs -= 3; g.font = "italic 500 " + fs + 'px "Playfair Display", Georgia, serif'; }
    g.fillText(b.title, Wc / 2, Hc * 0.45);
    var ry = Hc * 0.45 + fs * 0.62;
    g.fillRect(Wc / 2 - 70, ry, 52, 2); g.fillRect(Wc / 2 + 18, ry, 52, 2);
    g.save(); g.translate(Wc / 2, ry + 1); g.rotate(Math.PI / 4); g.fillRect(-5, -5, 10, 10); g.restore();
    g.font = '600 15px "Cinzel", Georgia, serif'; g.fillText("THE SCHOLAR’S DESK", Wc / 2, Hc - 82);
    return tex(c, true);
  }
  function spineTex(css) {
    if (texCache["s" + css]) return texCache["s" + css];
    texCache["s" + css] = spineTexDraw(css);
    return texCache["s" + css];
  }
  function spineTexDraw(css) {
    var c = document.createElement("canvas"); c.width = 64; c.height = 556; var g = c.getContext("2d");
    g.fillStyle = css; g.fillRect(0, 0, 64, 556);
    var vg = g.createLinearGradient(0, 0, 64, 0); vg.addColorStop(0, "rgba(0,0,0,0.35)"); vg.addColorStop(0.5, "rgba(255,230,190,0.08)"); vg.addColorStop(1, "rgba(0,0,0,0.35)");
    g.fillStyle = vg; g.fillRect(0, 0, 64, 556);
    g.fillStyle = "#C9A45C";
    [52, 62, 492, 502].forEach(function (y) { g.fillRect(6, y, 52, 3); });
    g.save(); g.translate(32, 278); g.rotate(Math.PI / 4); g.fillRect(-7, -7, 14, 14); g.restore();
    return tex(c, true);
  }
  function pageTex(title) {
    var Wc = 384, Hc = 540, c = document.createElement("canvas"); c.width = Wc; c.height = Hc; var g = c.getContext("2d");
    g.fillStyle = "#E9DFC6"; g.fillRect(0, 0, Wc, Hc);
    var vg = g.createRadialGradient(Wc / 2, Hc / 2, Hc * 0.2, Wc / 2, Hc / 2, Hc * 0.75);
    vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(120,88,48,0.22)");
    g.fillStyle = vg; g.fillRect(0, 0, Wc, Hc);
    g.fillStyle = "#5A4632"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = 'italic 500 34px "Playfair Display", Georgia, serif'; g.fillText(title, Wc / 2, 86);
    g.fillRect(Wc / 2 - 30, 114, 60, 2);
    g.fillStyle = "rgba(70,52,36,0.26)";
    var y = 150;
    while (y < Hc - 54) { g.fillRect(48, y, (Wc - 96) * (0.72 + Math.random() * 0.28), 5); y += 20; if (Math.random() < 0.12) y += 14; }
    return tex(c, true);
  }
  function makeBook(b, w, h, t, shared, mats) {
    mats = mats || {};
    var g = new THREE.Group();
    var plain = new THREE.MeshStandardMaterial({ color: C(b.css), roughness: 0.62, metalness: 0.06 });
    var cover = new THREE.MeshStandardMaterial({ map: coverTex(b), roughness: 0.5, metalness: 0.1, emissive: C("#4A3412"), emissiveIntensity: 0 });
    var spine = new THREE.MeshStandardMaterial({ map: spineTex(b.css), roughness: 0.55, metalness: 0.08 });
    var back = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.035), plain); back.position.z = -t / 2; g.add(back);
    var sp = new THREE.Mesh(new THREE.BoxGeometry(0.035, h, t + 0.035), [plain, spine, plain, plain, plain, plain]); sp.position.x = -w / 2; g.add(sp);
    var pages = new THREE.Mesh(new THREE.BoxGeometry(w - 0.05, h - 0.07, t - 0.04), [shared.edge, shared.edge, shared.edge, shared.edge, mats.front || shared.front, shared.edge]);
    pages.position.x = 0.01; g.add(pages);
    var pivot = new THREE.Group(); pivot.position.set(-w / 2, 0, t / 2); g.add(pivot);
    var front = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.035), [plain, plain, plain, plain, cover, mats.inside || shared.inside]);
    front.position.x = w / 2; pivot.add(front);
    [back, sp, pages, front].forEach(function (m) { m.userData.book = g; });
    g.userData.pivot = pivot; g.userData.h = h; g.userData.cover = cover;
    return g;
  }

  /* ---------- Seal ---------- */
  function sealCapTextures() {
    var S = 1024, k = S / 3.6, cx = S / 2;
    var mc = document.createElement("canvas"); mc.width = mc.height = S; var m = mc.getContext("2d");
    var bc = document.createElement("canvas"); bc.width = bc.height = S; var b = bc.getContext("2d");
    var grd = m.createRadialGradient(cx - 120, cx - 140, 40, cx, cx, S * 0.55);
    grd.addColorStop(0, "#94352B"); grd.addColorStop(0.6, "#7A2620"); grd.addColorStop(1, "#5E1B16");
    m.fillStyle = grd; m.fillRect(0, 0, S, S);
    b.fillStyle = "#808080"; b.fillRect(0, 0, S, S);
    for (var i = 0; i < 9000; i++) {
      var v = (110 + Math.random() * 40) | 0; b.fillStyle = "rgb(" + v + "," + v + "," + v + ")";
      var r = Math.random() * 2.2; b.fillRect(Math.random() * S, Math.random() * S, r, r);
    }
    function arcText(ctx, text, center, rad, span, weight, track, top) {
      var chars = Array.from(text);
      function widths(f) {
        ctx.font = weight + " " + f.toFixed(1) + 'px "Cinzel", Georgia, serif';
        return chars.map(function (ch) { return ctx.measureText(ch).width + (track * f) / 100; });
      }
      var fs = 100, ws = widths(fs), sum = ws.reduce(function (s2, w2) { return s2 + w2; }, 0);
      fs = Math.min(fs, (fs * span * rad) / sum);
      ws = widths(fs); sum = ws.reduce(function (s2, w2) { return s2 + w2; }, 0);
      var tot = sum / rad, a;
      if (top) {
        a = center - tot / 2;
        chars.forEach(function (ch, n) { a += ws[n] / 2 / rad; ctx.save(); ctx.rotate(a + Math.PI / 2); ctx.fillText(ch, 0, -rad); ctx.restore(); a += ws[n] / 2 / rad; });
      } else {
        a = center + tot / 2;
        chars.forEach(function (ch, n) { a -= ws[n] / 2 / rad; ctx.save(); ctx.rotate(a - Math.PI / 2); ctx.fillText(ch, 0, rad); ctx.restore(); a -= ws[n] / 2 / rad; });
      }
    }
    function emboss(ctx, color, dx, dy) {
      ctx.save(); ctx.translate(cx + (dx || 0), cx + (dy || 0)); ctx.strokeStyle = color; ctx.fillStyle = color;
      ctx.lineWidth = 20; ctx.beginPath(); ctx.arc(0, 0, 1.32 * k, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(0, 0, 0.8 * k, 0, Math.PI * 2); ctx.stroke();
      for (var j = 0; j < 60; j++) { var a = (j / 60) * Math.PI * 2; ctx.beginPath(); ctx.arc(Math.cos(a) * 1.2 * k, Math.sin(a) * 1.2 * k, 4, 0, Math.PI * 2); ctx.fill(); }
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      arcText(ctx, "HIMANI DALVI", -Math.PI / 2, 1.0 * k, 2.7, 700, 14, true);
      arcText(ctx, "EST · MMXXVI", Math.PI / 2, 1.0 * k, 1.7, 600, 12, false);
      [0, Math.PI].forEach(function (a2) {
        ctx.save(); ctx.translate(Math.cos(a2) * 1.0 * k, Math.sin(a2) * 1.0 * k); ctx.rotate(Math.PI / 4); ctx.fillRect(-11, -11, 22, 22); ctx.restore();
      });
      ctx.font = 'italic 600 270px "Playfair Display", Georgia, serif'; ctx.fillText("SD", 0, 22);
      ctx.restore();
    }
    emboss(m, "rgba(40,8,6,0.55)", 4, 5);
    emboss(m, "#C26A5C");
    try { b.filter = "blur(2.5px)"; } catch (e) {}
    emboss(b, "#F4F4F4");
    try { b.filter = "none"; } catch (e) {}
    var map = tex(mc, true), bump = tex(bc, false);
    [map, bump].forEach(function (t) { t.repeat.set(1 / 3.6, 1 / 3.6); t.offset.set(0.5, 0.5); });
    return { map: map, bump: bump };
  }
  function raysTex() {
    var c = document.createElement("canvas"); c.width = c.height = 512; var g = c.getContext("2d");
    g.translate(256, 256);
    for (var i = 0; i < 64; i++) {
      g.rotate((Math.PI * 2) / 64);
      var w = Math.random() * 0.03 + 0.006, len = 160 + Math.random() * 90;
      var gr = g.createLinearGradient(0, 0, 0, -len);
      gr.addColorStop(0, "rgba(255,220,160,0)"); gr.addColorStop(0.3, "rgba(255,220,160,0.55)"); gr.addColorStop(1, "rgba(255,220,160,0)");
      g.fillStyle = gr; g.beginPath(); g.moveTo(0, 0); g.lineTo(Math.tan(w) * len, -len); g.lineTo(-Math.tan(w) * len, -len); g.closePath(); g.fill();
    }
    return tex(c, true);
  }
  function stampImprint(x, y, size) {
    var s = document.createElementNS(svgNS, "svg");
    s.setAttribute("viewBox", "0 0 100 100"); s.setAttribute("class", "imprint");
    s.style.left = x + "px"; s.style.top = y + "px"; s.style.width = size + "px"; s.style.height = size + "px";
    s.style.setProperty("--r", (Math.random() * 30 - 15).toFixed(1) + "deg");
    var poly = document.createElementNS(svgNS, "polygon"); poly.setAttribute("points", SEAL_SVG); poly.setAttribute("style", "fill:var(--oxblood)");
    var ring = document.createElementNS(svgNS, "circle"); ring.setAttribute("cx", "50"); ring.setAttribute("cy", "50"); ring.setAttribute("r", "39.5"); ring.setAttribute("style", "fill:none;stroke:var(--wax-hi);stroke-width:1;stroke-dasharray:2 2.2");
    var inner = document.createElementNS(svgNS, "circle"); inner.setAttribute("cx", "50"); inner.setAttribute("cy", "50"); inner.setAttribute("r", "36"); inner.setAttribute("style", "fill:var(--wax-deep)");
    var txt = document.createElementNS(svgNS, "text"); txt.setAttribute("x", "50"); txt.setAttribute("y", "60");
    txt.setAttribute("style", "fill:var(--wax-hi);font-family:var(--display);font-size:30px;font-style:italic;font-weight:600;text-anchor:middle"); txt.textContent = "SD";
    s.append(poly, ring, inner, txt);
    imprintsEl.appendChild(s);
    while (imprintsEl.children.length > 4) imprintsEl.firstChild.remove();
    setTimeout(function () { s.remove(); }, 3100);
  }

  /* ---------- The sealed library ----------
     Everything is laid out in "seal units" (seal radius = 1) and mapped to the
     space actually free on screen every frame, so no book leaves the frame. */
  var SEAL_GEO_R = 1.75;
  function buildHero() {
    var phone = W < 700;
    var SHELLS = phone ? [1.32, 1.7] : [1.34, 1.66, 1.98];
    var EXTU = phone ? 2.08 : 2.36;
    var R = rng(20261028);
    var scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0B0907, 10, 26);

    scene.add(new THREE.AmbientLight(0xffe2c0, 0.22));
    scene.add(new THREE.HemisphereLight(0xffd9a0, 0x0b0907, 0.3));
    var key = new THREE.SpotLight(0xffd7a0, 2.0, 40, 0.7, 0.6, 1); key.position.set(4, 5, 9); scene.add(key);
    var rimL = new THREE.PointLight(0xd4a050, 2.4, 24, 1.5); rimL.position.set(-3, 2.5, -3.5); scene.add(rimL);
    var fillL = new THREE.DirectionalLight(0x6a7cb0, 0.32); fillL.position.set(-5, -2, 4); scene.add(fillL);
    var movL = new THREE.PointLight(0xfff0d0, 1.0, 12, 1.5); scene.add(movL);
    var torch = new THREE.PointLight(0xffc27a, 0, 6.5, 2); scene.add(torch);
    var core = new THREE.PointLight(0xff9a50, 1.0, 7, 2); core.position.set(0, 0, 0.8); scene.add(core);

    var rays = new THREE.Sprite(new THREE.SpriteMaterial({ map: raysTex(), color: 0xCFAE6B, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
    rays.position.z = -2.4; scene.add(rays);
    var glow = new THREE.Sprite(new THREE.SpriteMaterial(addMat({ color: 0x8A3A26, opacity: 0 }))); glow.position.z = -1.8; scene.add(glow);

    var shape = new THREE.Shape(), NS = 200;
    for (var i = 0; i <= NS; i++) {
      var a = (i / NS) * Math.PI * 2;
      var r = 1.5 * (1 + ((2.4 * Math.sin(a * 9) + 1.3 * Math.sin(a * 21 + 0.7)) / 45) * 1.6);
      if (i === 0) shape.moveTo(r * Math.cos(a), r * Math.sin(a)); else shape.lineTo(r * Math.cos(a), r * Math.sin(a));
    }
    var geo = new THREE.ExtrudeGeometry(shape, { depth: 0.26, bevelEnabled: true, bevelThickness: 0.14, bevelSize: 0.12, bevelSegments: 8, curveSegments: 12, steps: 1 });
    geo.center();
    var caps = sealCapTextures();
    var capMat = new THREE.MeshPhysicalMaterial({ map: caps.map, bumpMap: caps.bump, bumpScale: 0.075, roughness: 0.38, metalness: 0, clearcoat: 0.8, clearcoatRoughness: 0.22 });
    var sideMat = new THREE.MeshPhysicalMaterial({ color: C("#6E211B"), roughness: 0.42, clearcoat: 0.6, clearcoatRoughness: 0.3 });
    var sealMesh = new THREE.Mesh(geo, [capMat, sideMat]);
    var sealGroup = new THREE.Group(); sealGroup.add(sealMesh); scene.add(sealGroup);
    key.target = sealGroup;

    var orbit = new THREE.Group(); scene.add(orbit);
    var ringMat = new THREE.MeshBasicMaterial({ color: 0xCFAE6B, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    var ringA = new THREE.Mesh(new THREE.TorusGeometry(1, 0.0035, 6, 240), ringMat); ringA.rotation.x = 0.12; orbit.add(ringA);
    var ringB = new THREE.Mesh(new THREE.TorusGeometry(1, 0.0028, 6, 300), ringMat); ringB.rotation.x = -0.1; ringB.rotation.y = 0.14; orbit.add(ringB);
    var RA = SHELLS[0] + 0.18, RB = SHELLS[SHELLS.length - 1] + 0.12;

    var shared = {
      edge: new THREE.MeshStandardMaterial({ color: C("#E3D6B8"), roughness: 0.9 }),
      front: new THREE.MeshStandardMaterial({ map: pageTex("Chapter one"), roughness: 0.85 }),
      inside: new THREE.MeshStandardMaterial({ color: C("#2A1D14"), roughness: 0.8 })
    };

    var N = phone ? 10 : 15, NSH = SHELLS.length;
    var perShell = SHELLS.map(function () { return 0; });
    for (var c0 = 0; c0 < N; c0++) perShell[c0 % NSH]++;
    var books = [], hitList = [sealMesh];
    for (var bi = 0; bi < N; bi++) {
      var shell = bi % NSH, kk = Math.floor(bi / NSH);
      var isPaper = bi < PAPER_BOOKS.length;
      var info = isPaper ? PAPER_BOOKS[bi] : TOPICS[(bi - PAPER_BOOKS.length) % TOPICS.length];
      var bw = 0.62 + R() * 0.2, bh = 0.92 + R() * 0.26, bt = 0.14 + R() * 0.14;
      var mats = isPaper ? {
        front: new THREE.MeshStandardMaterial({ map: paperPageTex(info), roughness: 0.85 }),
        inside: new THREE.MeshStandardMaterial({ map: endpaperTex(info), roughness: 0.8 })
      } : null;
      var book = makeBook(info, bw, bh, bt, shared, mats);
      var u = book.userData;
      u.info = info;
      u.r = SHELLS[shell] + (R() - 0.5) * 0.14;
      u.th = (kk / perShell[shell]) * Math.PI * 2 + shell * 0.9 + (R() - 0.5) * 0.5;
      u.tilt = new THREE.Euler((R() - 0.5) * 0.36, (R() - 0.5) * 0.36, 0);
      u.speed = (0.11 - shell * 0.022) * (0.85 + R() * 0.3);
      u.dz = (R() - 0.5) * 0.5;
      u.base = [(R() - 0.5) * 0.5, (R() - 0.5) * 1.0, (R() - 0.5) * 0.9];
      u.wob = [0.15 + R() * 0.15, 0.2 + R() * 0.2, 0.25 + R() * 0.3, R() * 6.28];
      u.ajar = R() < 0.3 ? 0.18 + R() * 0.25 : 0;
      u.open = 0; u.hl = 0; u.sx = 0; u.sv = 0; u.kickAt = -1;
      orbit.add(book); books.push(book);
      book.traverse(function (o) { if (o.isMesh) hitList.push(o); });
    }

    /* background drifters: a second, deeper layer of books that fills the corners */
    var drifters = [];
    var spots = phone
      ? [[0.13, 0.16], [0.87, 0.15], [0.14, 0.82], [0.86, 0.83], [0.5, 0.1]]
      : [[0.12, 0.16], [0.34, 0.12], [0.66, 0.13], [0.88, 0.17], [0.1, 0.5], [0.9, 0.5], [0.12, 0.85], [0.35, 0.88], [0.65, 0.87], [0.88, 0.83]];
    spots.forEach(function (sp2, di) {
      var info2 = TOPICS[(di * 7 + 3) % TOPICS.length];
      var db = makeBook(info2, 0.62 + R() * 0.2, 0.92 + R() * 0.26, 0.14 + R() * 0.12, shared);
      var du = db.userData;
      du.spot = sp2; du.z = -3.0 - R() * 2.4;
      du.base = [(R() - 0.5) * 0.7, (R() - 0.5) * 1.4, (R() - 0.5) * 1.2];
      du.wob = [0.2 + R() * 0.2, 0.25 + R() * 0.25, 0.3 + R() * 0.3, R() * 6.28];
      du.pivot.rotation.y = R() < 0.45 ? -(0.25 + R() * 0.7) : 0;
      scene.add(db); drifters.push(db);
    });

    var loose = [];
    for (var pI = 0; pI < (phone ? 2 : 4); pI++) {
      var pg = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.7), new THREE.MeshStandardMaterial({ map: shared.front.map, roughness: 0.9, side: THREE.DoubleSide }));
      pg.userData.ph = pI * 2.1 + 0.5; scene.add(pg); loose.push(pg);
    }

    var beads = pointsFrom([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()], { size: 0.12, color: 0xEBD29B, opacity: 1 }); orbit.add(beads);
    var dust = makeDust(phone ? 170 : 260, { x: 14, y: 9, z: 9 }, 0xCFAE6B, 0.04, 0.45); scene.add(dust);

    var SP = 90, spPos = new Float32Array(SP * 3), spVel = new Float32Array(SP * 3);
    var spg = new THREE.BufferGeometry(); spg.setAttribute("position", new THREE.BufferAttribute(spPos, 3));
    var spMat = new THREE.PointsMaterial(addMat({ size: 0.07, color: 0xF0CF8A, opacity: 0 }));
    scene.add(new THREE.Points(spg, spMat));
    var sparkT = -1;

    var hovered = null, selected = null, hoverSeal = false, sealHL = 0;
    var introT = reduce ? 1 : 0, ts = 1, lastDragX = ptr.dragX, lastT = 0;
    var stampT = -1, impacted = false, impactZ = 4;
    var fx = 1, fy = 1, first = true;
    var spr = { x: 0, y: 0, vx: 0, vy: 0 };
    var tmpV = new THREE.Vector3(), tmpQ = new THREE.Quaternion(), tmpE = new THREE.Euler(), dummy = new THREE.Object3D();
    var target = new THREE.Vector3(), look = new THREE.Vector3(0, 0, 0), torchDir = new THREE.Vector3();

    function pick(x, y) {
      ray.setFromCamera({ x: x, y: y }, camera);
      var hit = ray.intersectObjects(hitList, false);
      if (!hit.length) return null;
      return hit[0].object === sealMesh ? "seal" : hit[0].object.userData.book;
    }
    function impact() {
      SFX.thud();
      var sScale = sealGroup.scale.x;
      var cc = new THREE.Vector3(sealGroup.position.x, sealGroup.position.y, impactZ).project(camera);
      var ee = new THREE.Vector3(sealGroup.position.x + 1.65 * sScale, sealGroup.position.y, impactZ).project(camera);
      var x = (cc.x * 0.5 + 0.5) * W, y = (-cc.y * 0.5 + 0.5) * H;
      stampImprint(x, y, clamp(Math.abs(ee.x - cc.x) * W, 110, Math.min(W, H) * 0.65));
      if (!reduce) { stage.classList.remove("shake"); void stage.offsetWidth; stage.classList.add("shake"); }
      for (var i = 0; i < SP; i++) {
        var a = Math.random() * Math.PI * 2, sp = 1.5 + Math.random() * 3.5;
        spPos[i * 3] = Math.cos(a) * 1.2 * sScale; spPos[i * 3 + 1] = Math.sin(a) * 1.2 * sScale; spPos[i * 3 + 2] = impactZ;
        spVel[i * 3] = Math.cos(a) * sp; spVel[i * 3 + 1] = Math.sin(a) * sp; spVel[i * 3 + 2] = (Math.random() - 0.5) * 1.5;
      }
      sparkT = 0;
      books.forEach(function (b) { b.userData.kickAt = lastT + Math.max(0, b.userData.r - 1.25) * 0.22; });
    }
    function startStamp() {
      if (stampT < 0 && introT >= 1) { impactZ = camera.position.z * 0.42; stampT = 0; impacted = false; SFX.whoosh(); }
    }

    return {
      scene: scene,
      cam: { pos: [0, 0.35, 9.2], look: [0, 0, 0] },
      replay: function () { introT = 0; selected = null; },
      update: function (t, dt) {
        lastT = t;
        introT = Math.min(1, introT + dt / 2.6);
        var ie = easeOut(introT);

        /* fit the library into the free part of the frame */
        var wpp = (2 * camera.position.length() * TANH) / H;
        var wide = W >= 900;
        var roomT = CTR.y - L.headerBottom - 6;
        var roomB = (wide ? L.hintTop - 8 : L.copyTop + 28) - CTR.y;
        var roomR = W - CTR.x - 26;
        var roomL = wide ? CTR.x - L.copyRight - 24 : CTR.x - 26;
        var ax = Math.max(60, Math.min(roomL, roomR)) * wpp * 0.94;
        var ay = Math.max(60, Math.min(roomT, roomB)) * wpp * 0.94;
        var gx = ax / EXTU, gy = ay / EXTU;
        var unit = Math.min(gx, gy);
        gx = Math.min(gx, unit * 1.75); gy = Math.min(gy, unit * 1.75);
        if (first) { fx = gx; fy = gy; first = false; }
        fx += (gx - fx) * 0.12; fy += (gy - fy) * 0.12;
        var su = Math.min(fx, fy);
        var bookK = su * 0.62;
        var camDist = camera.position.length();
        var fr = wide
          ? { x0: L.copyRight + 24, x1: W - 26, y0: L.headerBottom + 6, y1: L.hintTop - 8 }
          : { x0: 26, x1: W - 26, y0: L.headerBottom + 6, y1: L.copyTop + 28 };
        drifters.forEach(function (b) {
          var u = b.userData, wo2 = reduce ? 0 : 1;
          var px = fr.x0 + (fr.x1 - fr.x0) * u.spot[0], py = fr.y0 + (fr.y1 - fr.y0) * u.spot[1];
          var wd = (2 * (camDist - u.z) * TANH) / H;
          var far = 1 + 1.6 * (1 - ie);
          b.position.set(
            (px - CTR.x) * wd * far + wo2 * Math.sin(t * 0.2 + u.wob[3]) * 0.1,
            -(py - CTR.y) * wd * far + wo2 * Math.sin(t * 0.27 + u.wob[3]) * 0.12,
            u.z
          );
          b.rotation.set(
            u.base[0] + wo2 * u.wob[0] * Math.sin(t * 0.21 + u.wob[3]),
            u.base[1] + wo2 * u.wob[1] * Math.sin(t * 0.17 + u.wob[3] * 1.3),
            u.base[2] + wo2 * u.wob[2] * Math.sin(t * 0.14 + u.wob[3] * 0.7)
          );
          b.scale.setScalar(su * 0.72 * (0.3 + 0.7 * ie));
        });

        var hv = (canHover && ptr.has && !ptr.down && stampT < 0 && introT >= 1) ? pick(ptr.x, ptr.y) : null;
        hoverSeal = hv === "seal";
        hovered = hv && hv !== "seal" ? hv : null;
        ts += ((selected ? 0.15 : 1) - ts) * 0.06;
        var dX = ptr.dragX - lastDragX; lastDragX = ptr.dragX;

        /* rubber band: the whole library follows the finger, then springs home */
        var tgx = ptr.down ? Math.sign(ptr.gx) * Math.min(Math.abs(ptr.gx), 260) * 0.32 : 0;
        var tgy = ptr.down ? Math.sign(ptr.gy) * Math.min(Math.abs(ptr.gy), 220) * 0.32 : 0;
        var sdt = Math.min(dt, 0.033);
        spr.vx += (-38 * (spr.x - tgx) - 6.5 * spr.vx) * sdt; spr.x += spr.vx * sdt;
        spr.vy += (-38 * (spr.y - tgy) - 6.5 * spr.vy) * sdt; spr.y += spr.vy * sdt;
        orbit.position.set(spr.x * wpp, -spr.y * wpp, 0);
        orbit.rotation.x = -ptr.sy * 0.08 + spr.y * 0.0016;
        orbit.rotation.y = ptr.sx * 0.12 + spr.x * 0.0016;
        orbit.updateMatrixWorld();

        target.copy(camera.position).sub(look).multiplyScalar(0.5).add(look);
        if (wide) target.x += 0.15;
        var targetLocal = orbit.worldToLocal(target.clone());
        dummy.position.copy(target); dummy.lookAt(camera.position);
        var targetQ = orbit.quaternion.clone().invert().multiply(dummy.quaternion);

        books.forEach(function (b) {
          var u = b.userData;
          u.th += u.speed * ts * (reduce ? 0.3 : 1) * dt + dX * 0.9;
          if (u.kickAt >= 0 && t >= u.kickAt) { u.sv += 3.0; u.kickAt = -1; }
          var acc = -30 * u.sx - 4.6 * u.sv; u.sv += acc * sdt; u.sx += u.sv * sdt;
          var goal = b === selected ? 1 : 0; u.open += (goal - u.open) * 0.085; var e = ease(u.open);
          var hgoal = b === hovered && !selected ? 1 : 0; u.hl += (hgoal - u.hl) * 0.15;
          var rr = (u.r + u.sx) * (1 + 2.2 * (1 - ie));
          var ang = u.th + (1 - ie) * 2.8;
          tmpV.set(rr * Math.cos(ang), rr * Math.sin(ang), u.dz).applyEuler(u.tilt);
          tmpV.y += reduce ? 0 : Math.sin(t * 0.8 + u.wob[3]) * 0.05;
          tmpV.x *= fx; tmpV.y *= fy; tmpV.z *= su;
          b.position.copy(tmpV).lerp(targetLocal, e);
          var wo = reduce ? 0 : 1;
          tmpE.set(
            u.base[0] + wo * u.wob[0] * Math.sin(t * 0.31 + u.wob[3]) + u.sx * 0.6,
            u.base[1] + wo * u.wob[1] * Math.sin(t * 0.23 + u.wob[3] * 1.3),
            u.base[2] + wo * u.wob[2] * Math.sin(t * 0.19 + u.wob[3] * 0.7) + u.sx * 0.9
          );
          tmpQ.setFromEuler(tmpE);
          b.quaternion.copy(tmpQ).slerp(targetQ, e);
          u.pivot.rotation.y = -(u.ajar + (1.95 - u.ajar) * e);
          var k = bookK + (1 - bookK) * e;
          b.scale.setScalar((1 + 0.12 * u.hl + 0.4 * e) * k * (0.4 + 0.6 * ie));
          u.cover.emissiveIntensity = 0.55 * u.hl;
        });

        sealHL += ((hoverSeal ? 1 : 0) - sealHL) * 0.12;
        var srx = -ptr.sy * 0.22 + (reduce ? 0 : Math.sin(t * 0.37) * 0.08);
        var sry = ptr.sx * 0.35 + (reduce ? 0 : Math.sin(t * 0.5) * 0.3);
        var z = 0, sc = 1, blend = 1;
        if (stampT >= 0) {
          stampT += dt / 0.95;
          var s = stampT;
          blend = s < 0.5 ? 1 - ease(s / 0.3) : ease((s - 0.5) / 0.5);
          if (s < 0.35) z = -0.9 * ease(s / 0.35);
          else if (s < 0.5) { var q = (s - 0.35) / 0.15; z = -0.9 + (impactZ + 0.9) * q * q; sc = 1 + 0.1 * q; }
          else {
            if (!impacted) { impacted = true; impact(); }
            var q2 = Math.min(1, (s - 0.5) / 0.5); z = impactZ * (1 - easeOut(q2)); sc = 1.1 - 0.1 * q2;
          }
          if (stampT >= 1) stampT = -1;
        }
        sealGroup.rotation.set(srx * blend, sry * blend, 0);
        sealGroup.position.set(spr.x * wpp * 0.3, -spr.y * wpp * 0.3 - 0.9 * su * (1 - ie), z);
        sealGroup.scale.setScalar((su / SEAL_GEO_R) * (0.55 + 0.45 * ie) * sc * (1 + 0.04 * sealHL));

        rays.scale.setScalar(Math.max(12.5, 9.5 * su)); glow.scale.setScalar(Math.max(7.5, 5.6 * su));
        rays.material.opacity = 0.26 * ie * (1 + 0.3 * sealHL);
        rays.material.rotation = reduce ? 0 : t * 0.05;
        glow.material.opacity = (0.42 + (reduce ? 0 : 0.06 * Math.sin(t * 1.3))) * ie;
        ringMat.opacity = 0.2 * ie;
        ringA.scale.set(RA * fx, RA * fy, 1); ringB.scale.set(RB * fx, RB * fy, 1);
        ringA.rotation.z = reduce ? 0 : t * 0.05; ringB.rotation.z = reduce ? 0 : -t * 0.035;
        for (var bI = 0; bI < 3; bI++) {
          var ba = t * (0.3 + bI * 0.1) + bI * 2.1, rad = bI === 1 ? RB : RA;
          tmpV.set(Math.cos(ba) * rad * fx, Math.sin(ba) * rad * fy, 0).applyEuler(bI === 1 ? ringB.rotation : ringA.rotation);
          beads.geometry.attributes.position.setXYZ(bI, tmpV.x, tmpV.y, tmpV.z);
        }
        beads.geometry.attributes.position.needsUpdate = true;
        beads.material.opacity = ie;

        movL.position.set(Math.cos(t * 0.6) * 4, 1.5 + Math.sin(t * 0.4), 4 + Math.sin(t * 0.6) * 1.5);
        core.intensity = (0.95 + 0.15 * Math.sin(t * 1.7)) * ie;
        if (ptr.has) {
          torchDir.set(ptr.sx, ptr.sy, 0.5).unproject(camera).sub(camera.position).normalize();
          var tt = (1.6 - camera.position.z) / torchDir.z;
          torch.position.copy(camera.position).addScaledVector(torchDir, tt);
        }
        torch.intensity += ((ptr.has ? 1.1 : 0) - torch.intensity) * 0.08;

        loose.forEach(function (pg) {
          var ph = pg.userData.ph, sl = reduce ? 0 : 1;
          pg.position.set(Math.cos(t * 0.09 * sl + ph) * 2.3 * fx, Math.sin(t * 0.13 * sl + ph) * 1.8 * fy, -2.2 + Math.sin(t * 0.11 * sl + ph) * 1.2);
          pg.rotation.set(t * 0.3 * sl + ph, Math.sin(t * 0.5 * sl + ph) * 1.2, t * 0.2 * sl);
          pg.scale.setScalar(su * 0.8 * ie);
        });

        if (sparkT >= 0) {
          sparkT += dt;
          for (var i = 0; i < SP; i++) {
            spPos[i * 3] += spVel[i * 3] * dt; spPos[i * 3 + 1] += spVel[i * 3 + 1] * dt; spPos[i * 3 + 2] += spVel[i * 3 + 2] * dt;
            spVel[i * 3 + 1] -= 2.5 * dt;
          }
          spg.attributes.position.needsUpdate = true;
          spMat.opacity = Math.max(0, 1 - sparkT / 1.1);
          if (sparkT > 1.1) sparkT = -1;
        }
        dust.userData.tick(t);

        var showB = selected || hovered;
        if (showB) {
          tmpV.set(0, showB.userData.h * 0.62, 0); showB.localToWorld(tmpV);
          showLabel(tmpV, showB.userData.info.vol + (showB === selected ? " · Tap to close" : " · Tap to open"), showB.userData.info.title);
          if (selected && selected.userData.info.paper != null && selected.userData.open > 0.8) {
            tmpV.set(0, -selected.userData.h * 0.6, 0); selected.localToWorld(tmpV);
            var vv = tmpV.clone().project(camera);
            bookGo.style.left = clamp((vv.x * 0.5 + 0.5) * W, 120, W - 120) + "px";
            bookGo.style.top = clamp((-vv.y * 0.5 + 0.5) * H + 10, 80, H - 70) + "px";
            bookGo.dataset.paper = selected.userData.info.paper; bookGo.hidden = false;
          } else bookGo.hidden = true;
        } else if (hoverSeal) {
          tmpV.set(0, 1.55, 0); sealGroup.localToWorld(tmpV);
          showLabel(tmpV, "The seal", "Tap to stamp");
        } else { hideLabel(); }
        if (!selected || selected.userData.info.paper == null) bookGo.hidden = true;
        canvas.style.cursor = (hovered || hoverSeal) ? "pointer" : (ptr.down ? "grabbing" : "grab");
      },
      tap: function (x, y) {
        if (introT < 1) return;
        var hit = pick(x, y);
        if (hit === "seal") { selected = null; startStamp(); }
        else if (hit) { selected = hit === selected ? null : hit; SFX.page(); }
        else { if (selected) SFX.page(); selected = null; }
      }
    };
  }

  var hero = null, builtPhone = null;
  function disposeScene(s) {
    s.scene.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) {
          ["map", "bumpMap"].forEach(function (key) { if (m[key] && !m[key].__shared) m[key].dispose(); });
          m.dispose();
        });
      }
    });
  }
  function build() {
    if (hero) disposeScene(hero);
    builtPhone = W < 700;
    hero = buildHero();
    hideLabel();
  }
  window.addEventListener("resize", function () {
    resize();
    if (hero && (W < 700) !== builtPhone) build();
  });
  document.getElementById("replay").addEventListener("click", function () { if (hero) hero.replay(); });


  var heroVisible = true;
  if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { heroVisible = es[0].isIntersecting; }).observe(stage);
  var t0 = performance.now(), last = t0;
  function loop(now) {
    requestAnimationFrame(loop);
    if (document.hidden || !hero || !heroVisible) { last = now; return; }
    var dt = Math.min(0.05, (now - last) / 1000); last = now;
    var t = (now - t0) / 1000;
    if (!ptr.down) { ptr.dragX += ptr.vx; ptr.vx *= 0.93; }
    var tx = ptr.has ? ptr.x : 0, ty = ptr.has ? ptr.y : 0;
    ptr.sx += (tx - ptr.sx) * 0.05; ptr.sy += (ty - ptr.sy) * 0.05;
    var c = hero.cam, f = distFactor();
    camera.position.set(c.pos[0] * f + ptr.sx * 0.3, c.pos[1] * f + ptr.sy * 0.18, c.pos[2] * f);
    camera.lookAt(c.look[0], c.look[1], c.look[2]);
    hero.update(t, dt);
    renderer.render(hero.scene, camera);
  }

  function start() {
    try {
      resize();
      build();
      requestAnimationFrame(loop);
      var wait = reduce ? 0 : Math.max(0, 1700 - performance.now());
      setTimeout(function () {
        resize();
        if (hero) hero.replay();
        loadingEl.classList.add("done");
        fadeEl.classList.add("off");
        setTimeout(function () { loadingEl.hidden = true; }, 650);
      }, wait);
    } catch (e) {
      loadingEl.textContent = "The 3D scene couldn’t start on this device. Refresh once to try again.";
    }
  }
  var fontLoads = [];
  if (document.fonts && document.fonts.load) {
    fontLoads = [
      document.fonts.load('700 60px "Cinzel"'),
      document.fonts.load('italic 600 60px "Playfair Display"'),
      document.fonts.load('400 24px "IM Fell English SC"'),
      document.fonts.load('600 60px "Playfair Display"'),
      document.fonts.load('italic 500 60px "Playfair Display"'),
      document.fonts.load('italic 400 20px "Spectral"'),
      document.fonts.load('600 12px "Cinzel"'),
      document.fonts.load('20px "Great Vibes"')
    ];
  }
  Promise.race([Promise.all(fontLoads), new Promise(function (r) { setTimeout(r, 2500); })]).then(start, start);
})();
