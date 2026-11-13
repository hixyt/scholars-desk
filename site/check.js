/* The Examiner: send a post and a paper link to the desk function, then show each claim with its verdict.
   A result has its own link (check.html?c=ID), so it can be shared. */
(function () {
  "use strict";
  var DESK = window.SD_DESK || {};
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var LABEL = { supported: "In the paper", overstated: "Stretched", contradicted: "Paper says otherwise", not_in_abstract: "Not in the abstract" };
  var COLOR = { supported: "var(--sage)", overstated: "var(--amber)", contradicted: "var(--red-ink)", not_in_abstract: "var(--slate)" };
  var ORDER = ["supported", "overstated", "contradicted", "not_in_abstract"];
  var EXAMPLE = {
    post: "Wild new study \u{1F92F} AI agents are being trained on apps that blind people can't even use. In the old Rico dataset only 17.74% " +
      "of buttons had labels, versus 57.27% in the new one. That's a 3x jump in accessibility! The researchers say this will make every " +
      "AI agent fully accessible by 2027.\n\n(Example post, made up for this demo.)",
    paper: "https://arxiv.org/abs/2611.16107"
  };

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  var seal = [];
  for (var i = 0; i < 96; i++) {
    var a = (i / 96) * Math.PI * 2, r = 45 * (1 + (2.4 * Math.sin(a * 9) + 1.3 * Math.sin(a * 21 + 0.7)) / 45);
    seal.push((50 + r * Math.cos(a)).toFixed(1) + "," + (50 + r * Math.sin(a)).toFixed(1));
  }
  document.querySelectorAll("[data-seal]").forEach(function (p) { p.setAttribute("points", seal.join(" ")); });

  var form = $("docket"), post = $("post"), paper = $("paper"), go = $("go"), msg = $("msg"), work = $("work"), out = $("verdict");
  var open = !!(DESK.fn && DESK.checker);
  if (!open) {
    $("closed").hidden = false;
    [post, paper, go, $("example")].forEach(function (el) { el.disabled = true; });
  }

  function count() { $("count").textContent = post.value.length + " / 3000"; }
  post.addEventListener("input", count);
  $("example").addEventListener("click", function () { post.value = EXAMPLE.post; paper.value = EXAMPLE.paper; count(); post.focus(); });

  function call(body) {
    return fetch(DESK.fn, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok || !d.ok) throw new Error(d.error || "Something went wrong. Please try again in a minute.");
          return d;
        });
      }, function () { throw new Error("Couldn't reach the Examiner. Check your connection and try again."); });
  }

  var stepTimer = null;
  function steps(on) {
    var items = work.querySelectorAll("li");
    clearTimeout(stepTimer);
    items.forEach(function (li) { li.className = ""; });
    work.hidden = !on;
    if (!on) return;
    var k = 0;
    (function next() {
      items.forEach(function (li, j) { li.className = j < k ? "done" : j === k ? "now" : ""; });
      if (k < items.length - 1) { k++; stepTimer = setTimeout(next, k === 1 ? 1400 : 2600); }
    })();
  }

  function headline(c, total) {
    if (!total) return "No claim about the paper was found.";
    if (c.supported === total) return total === 1 ? "That claim is in the paper." : "Every claim is in the paper.";
    if (!c.supported) return total === 1 ? "That claim isn’t backed by the abstract." : "None of the " + total + " claims is backed by the abstract.";
    return c.supported + " of " + total + " claims " + (c.supported === 1 ? "is" : "are") + " in the paper.";
  }

  function render(d) {
    var claims = d.claims || [], c = d.counts || {}, total = claims.length;
    var p = d.paper || {};
    var authors = (p.authors || []).map(function (n) { return n.split(" ").slice(-1)[0]; }).join(", ") + (p.more_authors ? " and " + p.more_authors + " more" : "");
    var rest = ORDER.slice(1).filter(function (k) { return c[k]; }).map(function (k) { return c[k] + " " + LABEL[k].toLowerCase(); });
    var html =
      '<article class="card v-paper"><p class="v-kicker">The paper</p><h2 class="v-title"><a href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(p.title) + '</a></h2>' +
      '<p class="v-meta">' + esc(authors) + ' · arXiv ' + esc(p.id) + '</p></article>' +
      '<div class="v-sum"><h2>' + esc(headline(c, total)) + '</h2>' + (rest.length ? '<p>' + esc(rest.join(" · ")) + '</p>' : '') + '</div>';
    if (total) {
      html += '<div class="v-bar" role="img" aria-label="' + esc(ORDER.map(function (k) { return (c[k] || 0) + " " + LABEL[k]; }).join(", ")) + '">' +
        ORDER.map(function (k) { return c[k] ? '<span style="width:' + (100 * c[k] / total) + '%;background:' + COLOR[k] + '"></span>' : ""; }).join("") + '</div>' +
        '<p class="v-keys">' + ORDER.filter(function (k) { return c[k]; }).map(function (k) { return '<span><b style="background:' + COLOR[k] + '"></b>' + LABEL[k] + ' ' + c[k] + '</span>'; }).join("") + '</p>' +
        '<ol class="claims">' + claims.map(function (cl, n) {
          return '<li class="card claim v-' + esc(cl.verdict) + '" style="--i:' + n + '"><span class="stamp s-' + esc(cl.verdict) + '">' + esc(LABEL[cl.verdict] || cl.verdict) + '</span>' +
            '<p class="c-text">“' + esc(cl.text) + '”</p>' +
            (cl.evidence ? '<p class="c-proof"><b>The abstract says</b>“' + esc(cl.evidence) + '”</p>' : '') +
            '<p class="c-why"><b>Why</b>' + esc(cl.reason) + '</p></li>';
        }).join("") + '</ol>' +
        '<p class="v-note">Checked against the abstract only. “Not in the abstract” doesn’t mean false: it means this paper’s own summary doesn’t say it, so the claim needs a better source. Every quote above was matched to the abstract by plain code before it was shown.</p>';
    } else {
      html += '<p class="card v-empty">' + esc(d.note || "Try pasting the part of the post that talks about the paper’s results.") + '</p>';
    }
    if (d.text) html += '<details class="v-post"><summary>Show the post that was checked</summary><blockquote>' + esc(d.text) + '</blockquote></details>';
    html += '<div class="v-share">' + (d.id ? '<button type="button" class="btn gold" id="copy">Copy the link</button>' +
      '<a class="btn" id="linkedin" target="_blank" rel="noopener">Share on LinkedIn</a>' : '') +
      '<button type="button" class="btn" id="again">Check another</button></div>';
    out.innerHTML = html;
    out.hidden = false;
    if (d.id) {
      var link = location.origin + location.pathname + "?c=" + d.id;
      $("linkedin").href = "https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(link);
      $("copy").addEventListener("click", function () {
        var btn = this, done = function () { btn.textContent = "Link copied"; setTimeout(function () { btn.textContent = "Copy the link"; }, 2200); };
        if (navigator.clipboard) navigator.clipboard.writeText(link).then(done, function () { prompt("Copy this link:", link); });
        else prompt("Copy this link:", link);
      });
    }
    $("again").addEventListener("click", function () {
      out.hidden = true; form.hidden = false; post.value = ""; paper.value = ""; count();
      try { history.pushState(null, "", location.pathname); } catch (e) { /* ignore */ }
      form.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }); post.focus();
    });
    out.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!open) return;
    var text = post.value.trim(), link = paper.value.trim();
    if (text.length < 15) { msg.textContent = "Paste the post or claim you want to check (a sentence or more)."; post.focus(); return; }
    if (!/\d{4}\.\d{4,5}/.test(link + " " + text)) { msg.textContent = "Add the paper’s arXiv link, like arxiv.org/abs/2611.16107."; paper.focus(); return; }
    msg.textContent = "";
    go.disabled = true;
    out.hidden = true;
    steps(true);
    call({ action: "check", text: text, paper: link })
      .then(function (d) {
        steps(false);
        if (d.id) { try { history.pushState(null, "", "?c=" + d.id); } catch (e2) { /* ignore */ } }
        form.hidden = true;
        render(d);
      })
      .catch(function (err) { steps(false); msg.textContent = err.message; })
      .then(function () { go.disabled = false; });
  });

  var shared = new URLSearchParams(location.search).get("c");
  if (shared && DESK.fn) {
    form.hidden = true;
    out.hidden = false;
    out.innerHTML = '<p class="v-sum"><span class="dek">Opening the case…</span></p>';
    call({ action: "get", id: shared }).then(render).catch(function (err) {
      out.innerHTML = '<p class="card v-empty">' + esc(err.message) + '</p>';
      form.hidden = false;
    });
  }
  window.addEventListener("popstate", function () { location.reload(); });
})();
