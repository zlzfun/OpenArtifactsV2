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


def render_document(content: str, content_type: str, title: str) -> str:
    """渲染最终交付给 iframe 的完整 HTML 文档。"""
    if content_type == "markdown":
        body = markdown.markdown(
            content,
            extensions=["tables", "fenced_code", "toc", "sane_lists"],
        )
        extra_css = MARKDOWN_CSS
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
</body>
</html>"""
