"""把用户上传的 HTML 片段 / Markdown 包装成完整的、自包含的 HTML 文档。

对应官方行为:发布的文件会被包进一个 document shell(doctype/head/body),
并附带一份最小 CSS reset,页面本身只需要写 body 内容。
"""

import html

import markdown

# 最小 reset + 主题适配的基础样式,注入到每个 artifact 文档里
BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; -webkit-font-smoothing: antialiased; }
img, svg, video, canvas { max-width: 100%; height: auto; }
:root { color-scheme: light dark; }
"""

# Markdown 渲染时使用的排版样式(仿 GitHub 风格,深浅色自适应)
MARKDOWN_CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", sans-serif;
  line-height: 1.7;
  max-width: 820px;
  margin: 0 auto;
  padding: 48px 24px 96px;
  color: #1f2328;
  background: #ffffff;
}
h1, h2, h3, h4 { line-height: 1.3; margin: 1.6em 0 0.6em; }
h1 { font-size: 2em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
a { color: #0969da; }
code, pre {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.9em;
}
code { background: rgba(129, 139, 152, 0.18); padding: 0.15em 0.4em; border-radius: 4px; }
pre { background: rgba(129, 139, 152, 0.12); padding: 16px; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { margin: 1em 0; padding: 0 1em; color: #59636e; border-left: 4px solid #d1d9e0; }
table { border-collapse: collapse; display: block; overflow-x: auto; }
th, td { border: 1px solid #d1d9e0; padding: 6px 13px; }
tr:nth-child(2n) { background: rgba(129, 139, 152, 0.08); }
hr { border: none; border-top: 1px solid #d1d9e0; margin: 2em 0; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0d1117; }
  h1, h2 { border-color: #30363d; }
  a { color: #4493f8; }
  blockquote { color: #9198a1; border-color: #30363d; }
  th, td { border-color: #30363d; }
  hr { border-color: #30363d; }
}
"""

# ── slides 运行时 ──────────────────────────────────────────────
# 内容契约:每页一个顶层 <section class="slide">,尺寸用 rem、布局流式。
# 放映模式 = 固定 1280×720 画布 + scale 适配 + 大根字号;
# 滚动模式 = 去掉画布约束的自然文档流 + 文档根字号。
# 同一份 DOM,两种看法;<section class="slide canvas"> 为像素画布逃生舱。

SLIDES_CANVAS_W = 1280
SLIDES_CANVAS_H = 720

SLIDES_CSS = """
/* 两种模式只动一个旋钮:根字号。内容全用 rem,整套排版跟着走 */
html.oa-deck { font-size: 24px; }
html.oa-scroll { font-size: 17px; }

/* 放映:固定画布,scale 适配窗口,一次一页 */
html.oa-deck, html.oa-deck body { height: 100%; overflow: hidden; }
html.oa-deck section.slide {
  position: fixed; left: 50%; top: 50%;
  width: 1280px; height: 720px;
  transform: translate(-50%, -50%) scale(var(--oa-scale, 1));
  padding: 3.5rem 4.5rem;
  overflow: auto;
  align-content: center;
  visibility: hidden;
}
html.oa-deck section.slide.oa-active { visibility: visible; }
html.oa-deck section.slide.canvas { padding: 0; align-content: start; overflow: hidden; }

/* 滚动:自然文档流,连贯长页面 */
html.oa-scroll body { padding: 2rem 0 6rem; }
html.oa-scroll section.slide {
  max-width: 52rem;
  margin: 0 auto;
  padding: 2.5rem 1.5rem;
}
/* canvas 页 = 整页一个 SVG,滚动模式靠 SVG 自身的响应式等比缩放。
   不用 transform:样式重算改 transform 时 Blink 不重排 SVG 文字(字号因子过期) */
html.oa-scroll section.slide.canvas { padding: 2rem 1.5rem; }
html.oa-scroll section.slide.canvas > svg { display: block; }

/* HUD / 进度条 / 翻页热区(px 尺寸,不随根字号变) */
.oa-hud {
  position: fixed; right: 14px; bottom: 14px; z-index: 999;
  display: flex; align-items: center; gap: 2px;
  padding: 5px 8px; border-radius: 999px;
  background: rgba(22, 27, 33, 0.78); color: #fff;
  font: 13px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI",
    "PingFang SC", "Microsoft YaHei", sans-serif;
  backdrop-filter: blur(8px);
  user-select: none;
}
.oa-hud button {
  all: unset; cursor: pointer; padding: 4px 8px; border-radius: 7px;
  font-size: 13px; line-height: 1.2;
}
.oa-hud button:hover { background: rgba(255, 255, 255, 0.16); }
.oa-hud .oa-counter { padding: 0 5px; font-variant-numeric: tabular-nums; opacity: 0.85; }
html.oa-scroll .oa-deck-only { display: none !important; }
.oa-progress {
  position: fixed; left: 0; bottom: 0; height: 3px; width: 0;
  background: #6d9fd4; z-index: 998; transition: width 0.25s;
}
html.oa-scroll .oa-progress { display: none; }
.oa-zone { position: fixed; top: 0; bottom: 0; width: 7%; z-index: 900; cursor: pointer; }
.oa-zone-l { left: 0; }
.oa-zone-r { right: 0; }
html.oa-scroll .oa-zone { display: none; }

@media print {
  .oa-hud, .oa-progress, .oa-zone { display: none !important; }
  html.oa-scroll section.slide { break-inside: avoid; break-after: page; }
}
"""

SLIDES_JS = """
(() => {
  "use strict";
  const root = document.documentElement;
  const slides = Array.from(document.querySelectorAll("section.slide"));
  if (!slides.length) return;

  const CW = 1280, CH = 720;
  const clamp = (i) => Math.max(0, Math.min(slides.length - 1, i));
  let mode = new URLSearchParams(location.search).get("mode") === "scroll" ? "scroll" : "deck";
  let cur = 0;
  const hash = location.hash.match(/^#\\/(\\d+)$/);
  if (hash) cur = clamp(+hash[1] - 1);

  // HUD、进度条、左右翻页热区
  const hud = document.createElement("div");
  hud.className = "oa-hud";
  hud.innerHTML =
    '<button class="oa-deck-only" data-act="prev" title="上一页 (←)">&#8249;</button>' +
    '<span class="oa-counter oa-deck-only"></span>' +
    '<button class="oa-deck-only" data-act="next" title="下一页 (→)">&#8250;</button>' +
    '<button data-act="mode"></button>' +
    '<button data-act="fs" title="全屏">&#x26F6;</button>';
  document.body.appendChild(hud);
  const counter = hud.querySelector(".oa-counter");
  const modeBtn = hud.querySelector('[data-act="mode"]');
  if (!document.fullscreenEnabled) hud.querySelector('[data-act="fs"]').remove();
  const progress = document.createElement("div");
  progress.className = "oa-progress";
  document.body.appendChild(progress);
  const zoneL = document.createElement("div");
  zoneL.className = "oa-zone oa-zone-l";
  const zoneR = document.createElement("div");
  zoneR.className = "oa-zone oa-zone-r";
  document.body.append(zoneL, zoneR);

  function fit() {
    root.style.setProperty(
      "--oa-scale",
      Math.min(innerWidth / CW, innerHeight / CH).toFixed(4)
    );
  }

  function show(i, syncHash = true) {
    cur = clamp(i);
    slides.forEach((s, j) => s.classList.toggle("oa-active", j === cur));
    counter.textContent = (cur + 1) + " / " + slides.length;
    progress.style.width = (((cur + 1) / slides.length) * 100) + "%";
    if (syncHash) history.replaceState(null, "", "#/" + (cur + 1));
  }

  function setMode(next, keepPos = true) {
    mode = next;
    root.classList.toggle("oa-deck", mode === "deck");
    root.classList.toggle("oa-scroll", mode === "scroll");
    modeBtn.textContent = mode === "deck" ? "滚动" : "放映";
    modeBtn.title = mode === "deck" ? "切换为连贯滚动页面" : "切换为放映模式";
    if (mode === "deck") { fit(); show(cur, false); }
    else if (keepPos) {
      requestAnimationFrame(() => slides[cur].scrollIntoView({ block: "start" }));
    }
  }

  hud.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === "prev") show(cur - 1);
    else if (act === "next") show(cur + 1);
    else if (act === "mode") setMode(mode === "deck" ? "scroll" : "deck");
    else if (act === "fs") {
      if (document.fullscreenElement) document.exitFullscreen();
      else root.requestFullscreen().catch(() => {});
    }
  });
  zoneL.addEventListener("click", () => show(cur - 1));
  zoneR.addEventListener("click", () => show(cur + 1));
  addEventListener("resize", () => { if (mode === "deck") fit(); });

  addEventListener("keydown", (e) => {
    if (mode !== "deck" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.closest("input, textarea, select, [contenteditable]")) return;
    const k = e.key;
    if (k === "ArrowRight" || k === "ArrowDown" || k === "PageDown" || k === " ") {
      e.preventDefault(); show(cur + 1);
    } else if (k === "ArrowLeft" || k === "ArrowUp" || k === "PageUp") {
      e.preventDefault(); show(cur - 1);
    } else if (k === "Home") { e.preventDefault(); show(0); }
    else if (k === "End") { e.preventDefault(); show(slides.length - 1); }
  });

  let touchX = null;
  addEventListener("touchstart", (e) => {
    if (mode === "deck") touchX = e.changedTouches[0].clientX;
  }, { passive: true });
  addEventListener("touchend", (e) => {
    if (mode !== "deck" || touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1));
  }, { passive: true });

  // 滚动模式下跟踪当前可见的页:切回放映时从这里继续
  const io = new IntersectionObserver((entries) => {
    if (mode !== "scroll") return;
    let best = null;
    for (const e of entries) {
      if (e.isIntersecting && (!best || e.intersectionRatio > best.intersectionRatio)) best = e;
    }
    if (best) {
      cur = slides.indexOf(best.target);
      history.replaceState(null, "", "#/" + (cur + 1));
    }
  }, { threshold: [0.25, 0.5] });
  slides.forEach((s) => io.observe(s));

  addEventListener("hashchange", () => {
    const m = location.hash.match(/^#\\/(\\d+)$/);
    if (!m) return;
    if (mode === "deck") show(clamp(+m[1] - 1));
    else {
      cur = clamp(+m[1] - 1);
      slides[cur].scrollIntoView({ block: "start" });
    }
  });

  // 打印一律走滚动排版:每节一页,天然是讲义 PDF
  let modeBeforePrint = null;
  addEventListener("beforeprint", () => {
    modeBeforePrint = mode;
    if (mode !== "scroll") setMode("scroll", false);
  });
  addEventListener("afterprint", () => {
    if (modeBeforePrint === "deck") setMode("deck");
    modeBeforePrint = null;
  });

  setMode(mode, false);
  show(cur, false);
  if (mode === "scroll" && hash) slides[cur].scrollIntoView({ block: "start" });
})();
"""


def render_document(content: str, content_type: str, title: str) -> str:
    """渲染最终交付给 iframe 的完整 HTML 文档。"""
    runtime_js = ""
    if content_type == "markdown":
        body = markdown.markdown(
            content,
            extensions=["tables", "fenced_code", "toc", "sane_lists"],
        )
        extra_css = MARKDOWN_CSS
    elif content_type == "slides":
        body = content
        extra_css = SLIDES_CSS
        runtime_js = f"<script>{SLIDES_JS}</script>"
    else:
        body = content
        extra_css = ""

    return f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{BASE_CSS}{extra_css}</style>
</head>
<body>
{body}
{runtime_js}</body>
</html>"""
