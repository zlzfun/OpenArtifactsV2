#!/usr/bin/env python3
"""把本地 HTML/Markdown 文件发布为 OpenArtifacts 页面(仅用标准库)。

用法:
    python3 publish.py <file.html|file.md> --title "标题" [--favicon 📊] [--label "版本说明"]

环境变量:
    OPEN_ARTIFACTS_SERVER     服务地址,默认 http://127.0.0.1:8787
    OPEN_ARTIFACTS_AUTO_OPEN  设为 0 时发布后不自动打开浏览器

同一文件路径重复发布会更新同一个 artifact(URL 不变,版本 +1);
换一个文件路径则创建新的 artifact。
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
        "--server",
        default=os.environ.get("OPEN_ARTIFACTS_SERVER", "http://127.0.0.1:8787"),
    )
    args = parser.parse_args()

    path = Path(args.file).resolve()
    if not path.is_file():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        content_type = "html"
    elif suffix == ".md":
        content_type = "markdown"
    else:
        print(f"错误: 仅支持 .html/.htm/.md,收到 {suffix}", file=sys.stderr)
        return 1

    payload = json.dumps(
        {
            "source_path": str(path),
            "title": args.title,
            "favicon": args.favicon,
            "content": path.read_text(encoding="utf-8"),
            "content_type": content_type,
            "label": args.label,
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
    except urllib.error.URLError as e:
        print(f"错误: 无法连接 OpenArtifacts 服务 ({args.server}): {e}", file=sys.stderr)
        print("提示: 先启动服务: uvicorn server.main:app --port 8787", file=sys.stderr)
        return 1

    url = f"{args.server.rstrip('/')}{result['url']}"
    print(f"已发布: {args.title} (v{result['version']})")
    print(url)

    if os.environ.get("OPEN_ARTIFACTS_AUTO_OPEN", "1") != "0" and result["version"] == 1:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
