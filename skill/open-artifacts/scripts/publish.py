#!/usr/bin/env python3
"""把本地 HTML/Markdown 文件发布为 OpenArtifacts 页面(仅用标准库)。

用法:
    python3 publish.py <file.html|file.md> --title "标题" [--favicon 📊] [--label "版本说明"]
    python3 publish.py <file> --title "标题" --url <已发布链接>   # 迭代已有页面

环境变量:
    OPEN_ARTIFACTS_SERVER     服务地址,默认 http://127.0.0.1:8787
    OPEN_ARTIFACTS_AUTO_OPEN  设为 0 时发布后不自动打开浏览器

版本语义(详见 docs/identity-and-versions.md):
- 带 --url = 迭代该页面:URL 不变、版本 +1,文件路径/文件名/类型都可以变;
- 不带 --url 时按文件路径兜底:同一路径重复发布续同一 URL,新路径 = 新 artifact。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="要发布的 .html/.htm/.md 文件")
    parser.add_argument("--title", required=True, help="artifact 标题")
    parser.add_argument("--favicon", default="📄", help="浏览器标签图标(1-2 个 emoji)")
    parser.add_argument("--label", default=None, help="本次版本的简短说明")
    parser.add_argument(
        "--url",
        dest="artifact_url",
        default=None,
        help="迭代已发布页面:传该页面的链接(或 artifact id),URL 不变、版本 +1",
    )
    parser.add_argument(
        "--type",
        dest="content_type",
        choices=["html", "markdown", "slides"],
        default=None,
        help="内容类型;默认按扩展名推断(*.slides.html → slides)",
    )
    parser.add_argument(
        "--server",
        default=os.environ.get("OPEN_ARTIFACTS_SERVER", "http://127.0.0.1:8787"),
    )
    args = parser.parse_args()

    path = Path(args.file).resolve()
    if not path.is_file():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1
    suffix = path.suffix.lower()
    if args.content_type:
        content_type = args.content_type
    elif path.name.lower().endswith((".slides.html", ".slides.htm")):
        content_type = "slides"
    elif suffix in (".html", ".htm"):
        content_type = "html"
    elif suffix == ".md":
        content_type = "markdown"
    else:
        print(f"错误: 仅支持 .html/.htm/.md,收到 {suffix}", file=sys.stderr)
        return 1
    if content_type == "slides" and suffix not in (".html", ".htm"):
        print("错误: slides 仅支持 HTML 文件", file=sys.stderr)
        return 1

    artifact_id = None
    if args.artifact_url:
        # 接受完整链接(http://host/a/<id>)或裸 id
        artifact_id = args.artifact_url.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]
        if not artifact_id:
            print(f"错误: 无法从 --url 解析 artifact id: {args.artifact_url}", file=sys.stderr)
            return 1

    payload = json.dumps(
        {
            "source_path": str(path),
            "title": args.title,
            "favicon": args.favicon,
            "content": path.read_text(encoding="utf-8"),
            "content_type": content_type,
            "label": args.label,
            "artifact_id": artifact_id,
        }
    ).encode()

    req = urllib.request.Request(
        f"{args.server.rstrip('/')}/api/publish",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"错误: 服务端返回 {e.code}: {detail}", file=sys.stderr)
        if e.code == 404 and artifact_id:
            print("提示: --url 指向的页面不存在(可能已删除);去掉 --url 可发布为新页面", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"错误: 无法连接 OpenArtifacts 服务 ({args.server}): {e}", file=sys.stderr)
        print("提示: 先启动服务: uvicorn server.main:app --port 8787", file=sys.stderr)
        return 1

    url = f"{args.server.rstrip('/')}{result['url']}"
    created = result.get("created", result["version"] == 1)
    print(f"{'已创建' if created else '已更新'}: {args.title} (v{result['version']})")
    print(url)
    if created and not artifact_id:
        print("注意: 这是一个新页面(新 URL)。若本意是迭代已有页面,应改用 --url <该页面链接> 重发。")
    print(f"迭代此页面(包括改文件名/改类型)时: 发布命令加 --url {url}")

    if os.environ.get("OPEN_ARTIFACTS_AUTO_OPEN", "1") != "0" and created:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
