/* Chapter V (By Post): the subscribe letter, and the letter that opens when someone arrives from
   an email link (?confirm=, ?manage=, ?unsub=). Talks to the "desk" Supabase function. */
(function () {
  "use strict";
  var D = window.SD_DATA || {}, DESK = D.desk, TOPICS = D.topics || [];
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var MARKS = { "no-code": "Nc", agents: "Ag", health: "He", education: "Ed", trust: "Tr", business: "Bu" };
  var ROT = [-8, 5, -3, 7, -6, 3, -9, 6];

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function sfx(name) { var s = window.SDSFX; if (s && s[name]) s[name](); }

  var SEAL = (function () {
    var out = [];
    for (var i = 0; i < 96; i++) {
      var a = (i / 96) * Math.PI * 2, r = 45 * (1 + (2.4 * Math.sin(a * 9) + 1.3 * Math.sin(a * 21 + 0.7)) / 45);
      out.push((50 + r * Math.cos(a)).toFixed(1) + "," + (50 + r * Math.sin(a)).toFixed(1));
    }
    return out.join(" ");
  })();
  function bigSeal(cls, text) {
    return '<svg class="' + cls + '" viewBox="0 0 100 100" aria-hidden="true"><polygon points="' + SEAL + '" fill="#7A2620"></polygon>' +
      '<circle cx="50" cy="50" r="39.5" fill="none" stroke="#A8463C" stroke-width="1" stroke-dasharray="2 2.2"></circle>' +
      '<circle cx="50" cy="50" r="35" fill="#62201B"></circle><text x="50" y="61" text-anchor="middle" fill="#EBD29B" ' +
      'style="font:italic 600 30px var(--display)">' + esc(text) + '</text></svg>';
  }

  /* ---------- topic seals (used in the letter and in the change-topics card) ---------- */
  function sealPicker(box, chosen) {
    var all = !chosen || !chosen.length;
    box.innerHTML = TOPICS.map(function (t, i) {
      var on = all || chosen.indexOf(t.slug) >= 0;
      var mark = MARKS[t.slug] || t.label.slice(0, 2);
      return '<button type="button" class="tseal" style="--rot:' + ROT[i % ROT.length] + 'deg" data-slug="' + esc(t.slug) + '" aria-pressed="' + on + '">' +
        '<svg viewBox="0 0 100 100" aria-hidden="true"><polygon class="ts-wax" points="' + SEAL + '"></polygon>' +
        '<circle class="ts-in" cx="50" cy="50" r="34"></circle><text class="ts-m" x="50" y="59">' + esc(mark) + '</text></svg>' +
        '<span class="ts-l">' + esc(t.label) + '</span></button>';
    }).join("");
    box.addEventListener("click", function (e) {
      var b = e.target.closest(".tseal");
      if (!b) return;
      var on = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(on));
      if (on && !reduce) { b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop"); }
      sfx(on ? "thud" : "tick");
    });
    return function picked() {
      return [].slice.call(box.querySelectorAll('.tseal[aria-pressed="true"]')).map(function (b) { return b.dataset.slug; });
    };
  }

  function call(body) {
    return fetch(DESK.fn, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok || !d.ok) throw new Error(d.error || "Something went wrong. Please try again in a minute.");
          return d;
        });
      }, function () { throw new Error("Couldn't reach the desk. Check your connection and try again."); });
  }
  function labelsText(labels) { return (labels || []).join(" · "); }

  /* ---------- the claim checker's links: only once it's switched on ---------- */
  if (DESK && DESK.checker) {
    document.querySelectorAll("[data-examiner]").forEach(function (el) { el.hidden = false; });
  }

  /* ---------- Chapter V: the subscribe letter ---------- */
  var section = $("letters");
  if (section && DESK && DESK.subscribe && TOPICS.length) {
    section.hidden = false;
    document.querySelectorAll('[data-chapter="letters"]').forEach(function (el) { el.hidden = false; });
    var today = new Date();
    $("ltDate").textContent = today.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    $("envArt").innerHTML = '<svg viewBox="0 0 320 200" aria-hidden="true"><defs><linearGradient id="envG" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="#EDE3CC"></stop><stop offset="1" stop-color="#D6C6A2"></stop></linearGradient></defs>' +
      '<rect x="4" y="4" width="312" height="192" rx="3" fill="url(#envG)" stroke="#B79F6E"></rect>' +
      '<path d="M4 196 L134 104 M316 196 L186 104" stroke="#C2AD82" stroke-width="1.5" fill="none"></path>' +
      '<path d="M4 4 L160 122 L316 4" fill="#E4D6B6" stroke="#B79F6E" stroke-width="1.5"></path>' +
      '<g class="env-seal"><g transform="translate(128 88) scale(.64)"><polygon points="' + SEAL + '" fill="#7A2620"></polygon>' +
      '<circle cx="50" cy="50" r="35" fill="#62201B"></circle><text x="50" y="61" text-anchor="middle" fill="#EBD29B" ' +
      'style="font:italic 600 30px var(--display)">SD</text></g></g></svg>';
    var picked = sealPicker($("ltSeals"), null);
    var form = $("letterForm"), msg = $("ltMsg"), send = $("ltSend");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = $("ltEmail").value.trim(), topics = picked();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.textContent = "That email address doesn't look right."; $("ltEmail").focus(); return; }
      if (!topics.length) { msg.textContent = "Press at least one seal, so the desk knows what to send."; return; }
      msg.textContent = "";
      send.disabled = true;
      send.textContent = "Sealing…";
      call({ action: "subscribe", email: email, topics: topics, website: form.elements.website.value })
        .then(function () {
          $("envTo").textContent = email;
          form.classList.add("sent");
          sfx("whoosh");
          setTimeout(function () { sfx("thud"); }, reduce ? 0 : 1150);
        })
        .catch(function (err) { msg.textContent = err.message; })
        .then(function () { send.disabled = false; send.textContent = "Seal and send"; });
    });
    $("ltAgain").addEventListener("click", function () { form.classList.remove("sent"); $("ltEmail").value = ""; $("ltEmail").focus(); });
  } else {
    /* no subscribe chapter yet: the Colophon keeps its old number */
    var colo = document.querySelector('#colophon .numeral');
    if (colo) colo.textContent = "Chapter V";
    var tocColo = document.querySelector('.toc a[href="#colophon"]');
    if (tocColo && tocColo.firstChild) tocColo.firstChild.nodeValue = "V";
  }

  /* ---------- arriving from an email link ---------- */
  if (!DESK || !DESK.fn) return;
  var q = new URLSearchParams(location.search);
  var token = q.get("confirm") || q.get("manage") || q.get("unsub");
  if (!token) return;
  var mode = q.get("confirm") ? "confirm" : q.get("manage") ? "manage" : "unsub";
  try { history.replaceState(null, "", location.pathname + location.hash); } catch (e) { /* old browsers: leave the address as it is */ }

  var veil = document.createElement("div");
  veil.className = "post-veil";
  veil.setAttribute("role", "dialog");
  veil.setAttribute("aria-modal", "true");
  veil.setAttribute("aria-labelledby", "pvTitle");
  veil.innerHTML = '<div class="post-card"><button type="button" class="pv-x" aria-label="Close">×</button>' +
    '<p class="pv-kicker">The Scholar’s Desk</p><div id="pvBody"></div></div>';
  document.body.appendChild(veil);
  requestAnimationFrame(function () { veil.classList.add("on"); });
  var body = $("pvBody");
  function close() { veil.classList.remove("on"); setTimeout(function () { veil.remove(); }, reduce ? 0 : 350); }
  veil.addEventListener("click", function (e) { if (e.target === veil || e.target.closest(".pv-x") || e.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && veil.isConnected) close(); });
  function show(html) { body.innerHTML = html; var h = body.querySelector("h3"); if (h) { h.id = "pvTitle"; h.tabIndex = -1; h.focus({ preventScroll: true }); } }
  function failed(err) {
    show('<h3>Hmm.</h3><p class="pv-p">' + esc(err.message) + '</p><div class="pv-actions"><button type="button" class="pv-btn" data-close>Close</button></div>');
  }

  function manage(info) {
    show('<h3>Your seat at the desk</h3><p class="pv-p quiet">Letters go to ' + esc(info.email) + '. Press the seals for the topics you want.</p>' +
      '<div class="lt-seals" id="pvSeals"></div><div class="pv-actions"><button type="button" class="pv-btn main" id="pvSave">Save my topics</button></div>' +
      '<p class="pv-msg" id="pvMsg" aria-live="polite"></p><p class="pv-p quiet" style="margin-top:14px">Want to stop? <button type="button" class="pv-link" id="pvLeave">Unsubscribe</button></p>');
    var pick = sealPicker($("pvSeals"), info.topics);
    $("pvSave").addEventListener("click", function () {
      var topics = pick();
      if (!topics.length) { $("pvMsg").textContent = "Press at least one seal."; return; }
      this.disabled = true;
      call({ action: "topics", token: token, topics: topics })
        .then(function (d) { $("pvMsg").style.color = "var(--sage)"; $("pvMsg").textContent = "Saved. From tomorrow: " + labelsText(d.labels) + "."; sfx("thud"); })
        .catch(function (err) { $("pvMsg").textContent = err.message; })
        .then(function () { $("pvSave").disabled = false; });
    });
    $("pvLeave").addEventListener("click", leave);
  }

  function leave() {
    show('<h3>Leave the desk?</h3><p class="pv-p">No more morning emails. You can come back any time from this page.</p>' +
      '<div class="pv-actions"><button type="button" class="pv-btn red" id="pvYes">Yes, unsubscribe</button><button type="button" class="pv-btn" data-close>Keep my seat</button></div>' +
      '<p class="pv-msg" id="pvMsg" aria-live="polite"></p>');
    $("pvYes").addEventListener("click", function () {
      this.disabled = true;
      call({ action: "unsubscribe", token: token })
        .then(function () {
          show('<h3>Done.</h3><p class="pv-p">You won’t get any more emails. Thank you for reading.</p>' +
            '<div class="pv-actions"><button type="button" class="pv-btn" data-close>Close</button></div>');
        })
        .catch(function (err) { $("pvMsg").textContent = err.message; $("pvYes").disabled = false; });
    });
  }

  if (mode === "confirm") {
    show('<h3 class="pv-dots">Breaking the seal</h3>');
    call({ action: "confirm", token: token, topics: q.get("t") || "" })
      .then(function (d) {
        show(bigSeal("pv-wax", "SD") + "<h3>You’re in.</h3>" +
          '<p class="pv-p">Your first letter comes at 6:17 AM India time, on the next morning with new papers.</p>' +
          '<p class="pv-p quiet">Topics: ' + esc(labelsText(d.labels)) + '</p>' +
          '<div class="pv-actions"><a class="pv-btn main" href="#folio" data-close>Read today’s papers</a><button type="button" class="pv-btn" id="pvChange">Change topics</button></div>');
        sfx("thud");
        $("pvChange").addEventListener("click", function () { manage(d); });
      })
      .catch(failed);
  } else if (mode === "manage") {
    show('<h3 class="pv-dots">Finding your seat</h3>');
    call({ action: "me", token: token }).then(manage).catch(failed);
  } else {
    leave();
  }
})();
