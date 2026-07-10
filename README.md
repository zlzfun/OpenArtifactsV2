# OpenArtifacts

自托管复刻 [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts):Agent 把 HTML/Markdown 发布成可在浏览器查看的页面,发布新版本时页面原地更新。

## 架构

对齐官方的「内置工具 + skill」两层结构:

| 官方 | 本项目 |
| --- | --- |
| `Artifact` 内置工具(上传、URL、版本) | `skill/open-artifacts/scripts/publish.py` |
| `artifact-design` skill(页面设计知识) | `skill/open-artifacts/SKILL.md` |
| claude.ai 托管 + `claudeusercontent.com` 沙箱 | FastAPI 服务 + 严格 CSP 的 iframe 沙箱 |

```
server/            FastAPI 服务端
  main.py          API + 查看器/画廊路由
  storage.py       SQLite 存储(artifact + 版本)
  render.py        Markdown 渲染 / HTML document shell 包装
  templates/       查看器与画廊页面
skill/open-artifacts/   安装到 Claude Code 的 skill
```

## 快速开始

```bash
# 1. 安装依赖并启动服务
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server.main:app --port 8787

# 2. 安装 skill(个人级;也可放到某项目的 .claude/skills/)
ln -s "$(pwd)/skill/open-artifacts" ~/.claude/skills/open-artifacts

# 3. 在 Claude Code 里
#    /open-artifacts 做一个展示本周部署失败率的仪表盘
```

也可以不经过 Claude 手动发布:

```bash
python3 skill/open-artifacts/scripts/publish.py page.html --title "我的页面" --favicon "📊"
```

## 核心语义(与官方一致)

- 迭代已发布页面:发布时带 `--url <该页面链接>` → 同一 URL 的新版本,文件名/类型可变;不带时按文件路径兜底(同一路径续同一 URL,新路径 = 新 artifact)。设计动机见 [docs/identity-and-versions.md](docs/identity-and-versions.md)
- 查看器每 3 秒轮询,跟随「最新」时新版本原地刷新;也可用版本选择器回看历史版本
- 内容在 `sandbox` iframe 中渲染,CSP 禁止一切外部请求(脚本/样式/字体/图片/fetch/XHR/WebSocket)
- 上传 `.md` 自动渲染为带样式的 HTML;上传 HTML 只需写 body 内容,服务端包 document shell
- 渲染后页面上限 16 MiB

## HTML Slides(本项目扩展,官方没有)

`*.slides.html`(或 `--type slides`)发布为放映页:服务端注入统一的翻页运行时,同一份内容获得两种视图——**放映模式**(固定 16:9 画布左右翻页,键盘/点击/触摸,页码进度条,`#/3` 直达,全屏)和**滚动模式**(连贯长页面,非讲义式堆叠),右下角 HUD 切换,打印自动转为每节一页的讲义 PDF。内容契约见 `skill/open-artifacts/SKILL.md`:每页一个 `<section class="slide">`,rem 尺寸 + 流式布局;精确制图页用 `<section class="slide canvas">` 内放整页 SVG。示例:`examples/slides-demo.slides.html`

## 环境变量

| 变量 | 作用 |
| --- | --- |
| `OPEN_ARTIFACTS_SERVER` | 发布脚本指向的服务地址,默认 `http://127.0.0.1:8787` |
| `OPEN_ARTIFACTS_AUTO_OPEN=0` | 首次发布后不自动打开浏览器 |

## 尚未实现(相对官方)

- 多用户 / 登录 / 组织内分享(当前单用户无鉴权,知道 URL 即可访问)
- 版本锁定分享(「始终分享最新版」开关)
- 审计日志、保留策略、Compliance API
