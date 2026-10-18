(function () {
  "use strict";

  var COMIC = window.COMIC;
  var pages = COMIC.pages;
  var total = pages.length;
  var END = total + 1; // the "End of Chapter" screen sits after the last page

  var $ = function (id) { return document.getElementById(id); };
  var stage = $("stage"), img = $("page"), end = $("end");
  var prevBtn = $("prev"), nextBtn = $("next"), sidePrev = $("sidePrev"), sideNext = $("sideNext");
  var jump = $("jump"), progress = $("progress");
  var zoom = $("zoom"), zoomImg = $("zoomImg");

  var current = 0;
  var cache = {};

  function nn(n) { return String(n).padStart(3, "0"); }
  function src(n, size) { return "pages/" + size + "/" + nn(n) + ".jpg"; }

  // Phones and small windows get the 960 px page; bigger screens the full one.
  function size() {
    var p = pages[0];
    var w = Math.min(stage.clientWidth, stage.clientHeight * (p.w / p.h));
    return w * (window.devicePixelRatio || 1) > 1000 ? "large" : "small";
  }

  function preload(n) {
    if (n < 1 || n > total) return;
    var s = src(n, size());
    if (cache[s]) return;
    var im = new Image();
    im.decoding = "async";
    im.src = s;
    cache[s] = im;
  }

  function parse() {
    var h = location.hash.replace(/^#\/?/, "").toLowerCase();
    if (h === "end") return END;
    var n = parseInt(h, 10);
    return n >= 1 && n <= total ? n : 1;
  }

  function show(n) {
    n = Math.max(1, Math.min(END, n));
    if (n === current) return;
    current = n;

    var hash = "#" + (n === END ? "end" : n);
    if (location.hash !== hash) history.replaceState(null, "", hash);

    var atEnd = n === END;
    end.hidden = !atEnd;
    img.hidden = atEnd;
    prevBtn.disabled = sidePrev.disabled = n === 1;
    nextBtn.disabled = sideNext.disabled = atEnd;
    progress.style.width = (Math.min(n, total) / total) * 100 + "%";
    jump.value = atEnd ? String(total) : String(n);

    if (atEnd) {
      document.title = "End of Chapter 1 · Blackthorn Castle";
      return;
    }

    var p = pages[n - 1];
    var s = src(n, size());
    img.width = p.w;
    img.height = p.h;
    img.alt = "Blackthorn Castle, Chapter 1, page " + n;
    if (img.getAttribute("src") !== s) {
      img.classList.add("loading");
      img.onload = img.onerror = function () { img.classList.remove("loading"); };
      img.src = s;
    }
    document.title = "Page " + n + " · Blackthorn Castle";
    try { localStorage.setItem("bc-page", String(n)); } catch (e) {}

    preload(n + 1);
    preload(n + 2);
    preload(n - 1);
  }

  function go(d) { if (zoom.hidden) show(current + d); }

  // Page menu
  var opts = "";
  for (var i = 1; i <= total; i++) opts += '<option value="' + i + '">' + i + " / " + total + "</option>";
  jump.innerHTML = opts;
  jump.addEventListener("change", function () { show(parseInt(jump.value, 10)); jump.blur(); });

  prevBtn.addEventListener("click", function () { go(-1); });
  nextBtn.addEventListener("click", function () { go(1); });
  sidePrev.addEventListener("click", function () { go(-1); });
  sideNext.addEventListener("click", function () { go(1); });
  window.addEventListener("hashchange", function () { show(parse()); });

  // Keys
  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target === jump) return;
    if (!zoom.hidden) {
      if (e.key === "Escape") { closeZoom(); e.preventDefault(); }
      return;
    }
    switch (e.key) {
      case "ArrowRight": case "PageDown": case "d": go(1); break;
      case "ArrowLeft": case "PageUp": case "a": go(-1); break;
      case "Home": show(1); break;
      case "End": show(total); break;
      default: return;
    }
    e.preventDefault();
  });

  // Swipe
  var sx = 0, sy = 0, st = 0, multi = false, swiped = 0;
  stage.addEventListener("touchstart", function (e) {
    multi = e.touches.length > 1;
    var t = e.touches[0];
    sx = t.clientX; sy = t.clientY; st = Date.now();
  }, { passive: true });
  stage.addEventListener("touchmove", function (e) {
    if (e.touches.length > 1) multi = true;
  }, { passive: true });
  stage.addEventListener("touchend", function (e) {
    if (multi) return;
    if (window.visualViewport && window.visualViewport.scale > 1.05) return; // pinch-zoomed: let them pan
    var t = e.changedTouches[0];
    var dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5 && Date.now() - st < 800) {
      swiped = Date.now();
      go(dx < 0 ? 1 : -1);
    }
  });

  // Zoom: tap the page to see it large; tap again (or Esc) to close.
  function openZoom(e) {
    if (Date.now() - swiped < 400) return;
    var r = img.getBoundingClientRect();
    var p = pages[current - 1];
    var vw = window.innerWidth, vh = window.innerHeight;
    var w = Math.round(Math.max(vw, Math.min(r.width * 2.2, p.w * 1.4)));
    var h = Math.round(w * p.h / p.w);
    zoomImg.src = src(current, "large");
    zoomImg.alt = img.alt;
    zoomImg.style.width = w + "px";
    zoomImg.style.height = h + "px";
    zoomImg.style.margin = Math.max(0, (vh - h) / 2) + "px auto";
    zoom.hidden = false;
    document.body.style.overflow = "hidden";
    var fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    zoom.scrollLeft = fx * w - vw / 2;
    zoom.scrollTop = fy * h - vh / 2;
    zoom.focus();
  }
  function closeZoom() {
    zoom.hidden = true;
    zoomImg.removeAttribute("src");
    document.body.style.overflow = "";
  }
  img.addEventListener("click", openZoom);
  $("zoomClose").addEventListener("click", function (e) { e.stopPropagation(); closeZoom(); });

  // In the zoom, drag with the mouse to look around; a click without a drag closes it.
  var drag = null, moved = false;
  zoom.tabIndex = -1;
  zoom.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, l: zoom.scrollLeft, t: zoom.scrollTop };
    moved = false;
    e.preventDefault();
  });
  window.addEventListener("mousemove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
    zoom.scrollLeft = drag.l - dx;
    zoom.scrollTop = drag.t - dy;
  });
  window.addEventListener("mouseup", function () { drag = null; });
  zoom.addEventListener("click", function () { if (!moved) closeZoom(); moved = false; });

  show(parse());
})();
