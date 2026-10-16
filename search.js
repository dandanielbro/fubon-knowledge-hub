// 搜尋與分類篩選。沒有 JS 時，首頁仍會列出全部條目。
(function () {
  var index = window.SEARCH_INDEX || [];
  var panel = document.getElementById("search");
  var input = document.getElementById("q");
  var results = document.getElementById("results");
  var status = document.getElementById("status");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".entry"));
  var category = "";
  var LIMIT = 60;
  panel.hidden = false;

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  function snippet(text, term) {
    var i = text.toLowerCase().indexOf(term);
    var start = Math.max(0, i - 40);
    var end = Math.min(text.length, i + term.length + 80);
    var part = (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
    var re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    return esc(part).replace(re, function (m) { return "<mark>" + m + "</mark>"; });
  }

  function run() {
    var terms = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    cards.forEach(function (card) {
      card.hidden = category !== "" && card.dataset.category !== category;
    });
    results.innerHTML = "";
    if (!terms.length) {
      status.textContent = category ? "分類：" + category : "";
      return;
    }
    var hits = index.filter(function (d) {
      if (category && d.category !== category) return false;
      var t = d.text.toLowerCase() + " " + d.chapter.toLowerCase();
      return terms.every(function (term) { return t.indexOf(term) !== -1; });
    });
    status.textContent = hits.length ? "找到 " + hits.length + " 筆" + (hits.length > LIMIT ? "，顯示前 " + LIMIT + " 筆" : "") : "找不到符合的內容，換個關鍵字試試。";
    results.innerHTML = hits.slice(0, LIMIT).map(function (d) {
      var term = terms.find(function (x) { return d.text.toLowerCase().indexOf(x) !== -1; }) || terms[0];
      return '<li><a href="' + d.href + '"><span class="kind">' + d.kind + "</span>" +
        "<strong>" + esc(d.entry) + "</strong><span class=\"where\">" + esc(d.chapter) + (d.time ? " · " + d.time : "") + "</span>" +
        "<span class=\"snip\">" + snippet(d.text, term) + "</span></a></li>";
    }).join("");
  }

  input.addEventListener("input", run);
  document.querySelectorAll(".tag[data-q]").forEach(function (b) {
    b.addEventListener("click", function () { input.value = b.dataset.q; run(); input.focus(); });
  });
  document.querySelectorAll(".tag[data-cat]").forEach(function (b) {
    b.addEventListener("click", function () {
      category = category === b.dataset.cat ? "" : b.dataset.cat;
      document.querySelectorAll(".tag[data-cat]").forEach(function (x) { x.classList.toggle("on", x.dataset.cat === category); });
      run();
    });
  });
  var q = new URLSearchParams(location.search).get("q");
  if (q) { input.value = q; }
  run();
})();
