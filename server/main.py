"""OpenArtifacts 服务端:发布 API + 沙箱查看器。

运行: uvicorn server.main:app --port 8787
"""

import html
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import storage
from .render import render_document

TEMPLATES = Path(__file__).parent / "templates"

app = FastAPI(title="OpenArtifacts")
storage.init_db()

# artifact 内容页的严格 CSP(对齐官方):禁止一切外部请求,
# 只允许内联脚本/样式和 data: URI 资源。
ARTIFACT_CSP = (
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; "
    "img-src data: blob:; "
    "media-src data: blob:; "
    "font-src data:; "
    "connect-src 'none'; "
    "form-action 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'self'"
)


class PublishRequest(BaseModel):
    source_path: str = Field(description="发布端源文件的绝对路径,决定 URL 复用")
    title: str = Field(min_length=1, max_length=200)
    favicon: str = Field(default="📄", max_length=8)
    content: str
    content_type: str = Field(pattern="^(html|markdown|slides)$")
    label: str | None = Field(default=None, max_length=60)
    artifact_id: str | None = Field(
        default=None, description="更新已有 artifact:其 id;省略时按 source_path 匹配"
    )


@app.post("/api/publish")
def publish(req: PublishRequest):
    rendered = render_document(req.content, req.content_type, req.title)
    if len(rendered.encode()) > storage.MAX_RENDERED_SIZE:
        raise HTTPException(413, "渲染后页面超过 16 MiB 上限")
    try:
        result = storage.publish(
            source_path=req.source_path,
            title=req.title,
            favicon=req.favicon,
            content=req.content,
            content_type=req.content_type,
            label=req.label,
            artifact_id=req.artifact_id,
        )
    except KeyError:
        raise HTTPException(404, "要更新的 artifact 不存在(可能已被删除)")
    return {**result, "url": f"/a/{result['artifact_id']}"}


@app.get("/api/artifacts")
def list_artifacts():
    return storage.list_artifacts()


@app.get("/api/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    art = storage.get_artifact(artifact_id)
    if not art:
        raise HTTPException(404, "artifact 不存在")
    return art


@app.delete("/api/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str):
    if not storage.delete_artifact(artifact_id):
        raise HTTPException(404, "artifact 不存在")
    return JSONResponse({"deleted": True})


@app.get("/a/{artifact_id}", response_class=HTMLResponse)
def viewer(artifact_id: str):
    art = storage.get_artifact(artifact_id)
    if not art:
        raise HTTPException(404, "artifact 不存在")
    import json

    page = (
        (TEMPLATES / "viewer.html")
        .read_text(encoding="utf-8")
        .replace("__TITLE__", html.escape(art["title"]))
        .replace("__FAVICON__", art["favicon"])
        .replace("__META_JSON__", json.dumps(art))
    )
    return HTMLResponse(page)


@app.get("/a/{artifact_id}/raw", response_class=HTMLResponse)
def raw(artifact_id: str, v: int | None = None):
    art = storage.get_artifact(artifact_id)
    if not art:
        raise HTTPException(404, "artifact 不存在")
    ver = storage.get_version(artifact_id, v)
    if not ver:
        raise HTTPException(404, "版本不存在")
    rendered = render_document(ver["content"], ver["content_type"], art["title"])
    return HTMLResponse(
        rendered,
        headers={
            "Content-Security-Policy": ARTIFACT_CSP,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@app.get("/", response_class=HTMLResponse)
def gallery():
    items = storage.list_artifacts()
    if items:
        cards = "\n".join(
            f"""<a class="card" href="/a/{a['id']}">
  <div class="head"><span class="emoji">{a['favicon']}</span>
  <span class="name">{html.escape(a['title'])}</span></div>
  <div class="meta">v{a['latest_version']} · 更新于 {a['updated_at'][:16].replace('T', ' ')}</div>
</a>"""
            for a in items
        )
    else:
        cards = '<div class="empty">还没有 artifact,用 skill 发布第一个吧。</div>'
    page = (TEMPLATES / "gallery.html").read_text(encoding="utf-8").replace("__ITEMS__", cards)
    return HTMLResponse(page)
