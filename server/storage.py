"""SQLite 存储层:artifact 元数据 + 版本内容。

单用户场景,内容直接存 SQLite(单版本上限 16 MiB,与官方一致)。

artifact 身份的两条线(详见 docs/identity-and-versions.md):
- 显式句柄:发布时指定 artifact_id(来自 --url)→ 直接追加版本,
  并把 source_path 重绑定到本次路径,后续裸路径发布也能续上;
- 路径兜底:同一 source_path 重复发布 → 同一 artifact 的新版本。
source_path 可空:重绑定时新路径若被其他 artifact 占用,占用者被解绑。
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "artifacts.db"

MAX_RENDERED_SIZE = 16 * 1024 * 1024  # 16 MiB


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id          TEXT PRIMARY KEY,
                source_path TEXT UNIQUE,
                title       TEXT NOT NULL,
                favicon     TEXT NOT NULL DEFAULT '📄',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                artifact_id  TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
                version      INTEGER NOT NULL,
                content      TEXT NOT NULL,
                content_type TEXT NOT NULL,
                label        TEXT,
                created_at   TEXT NOT NULL,
                PRIMARY KEY (artifact_id, version)
            );
            """
        )
        _migrate_source_path_nullable(conn)


def _migrate_source_path_nullable(conn: sqlite3.Connection) -> None:
    """老库的 source_path 带 NOT NULL;重绑定解绑占用者时需要它可空。"""
    col = next(
        c for c in conn.execute("PRAGMA table_info(artifacts)") if c["name"] == "source_path"
    )
    if not col["notnull"]:
        return
    # SQLite 改列约束只能重建表;本连接未开 FK 检查,DROP 期间 versions 的引用不受影响
    conn.executescript(
        """
        CREATE TABLE artifacts_new (
            id          TEXT PRIMARY KEY,
            source_path TEXT UNIQUE,
            title       TEXT NOT NULL,
            favicon     TEXT NOT NULL DEFAULT '📄',
            created_at  TEXT NOT NULL
        );
        INSERT INTO artifacts_new SELECT id, source_path, title, favicon, created_at FROM artifacts;
        DROP TABLE artifacts;
        ALTER TABLE artifacts_new RENAME TO artifacts;
        """
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def publish(
    source_path: str,
    title: str,
    favicon: str,
    content: str,
    content_type: str,
    label: str | None = None,
    artifact_id: str | None = None,
) -> dict:
    """发布一个版本。

    artifact_id 指定时(--url 更新)直接追加版本,并把 source_path 重绑定到
    本次路径;否则按 source_path 匹配:已存在则追加版本,不存在则新建。
    artifact_id 不存在时抛 KeyError。
    """
    with _connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        created = False
        if artifact_id:
            if not conn.execute(
                "SELECT 1 FROM artifacts WHERE id = ?", (artifact_id,)
            ).fetchone():
                raise KeyError(artifact_id)
            # 身份重绑定到本次路径:先解绑占用该路径的其他 artifact,
            # 之后对这个文件的裸路径发布会继续更新本 artifact
            conn.execute(
                "UPDATE artifacts SET source_path = NULL WHERE source_path = ? AND id != ?",
                (source_path, artifact_id),
            )
            conn.execute(
                "UPDATE artifacts SET source_path = ?, title = ?, favicon = ? WHERE id = ?",
                (source_path, title, favicon, artifact_id),
            )
        else:
            row = conn.execute(
                "SELECT id FROM artifacts WHERE source_path = ?", (source_path,)
            ).fetchone()
            if row:
                artifact_id = row["id"]
                # 标题和图标随最新一次发布更新
                conn.execute(
                    "UPDATE artifacts SET title = ?, favicon = ? WHERE id = ?",
                    (title, favicon, artifact_id),
                )
            else:
                created = True
                artifact_id = uuid.uuid4().hex[:12]
                conn.execute(
                    "INSERT INTO artifacts (id, source_path, title, favicon, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (artifact_id, source_path, title, favicon, _now()),
                )

        next_version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM versions WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()["v"]
        conn.execute(
            "INSERT INTO versions (artifact_id, version, content, content_type, label, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (artifact_id, next_version, content, content_type, label, _now()),
        )
        return {"artifact_id": artifact_id, "version": next_version, "created": created}


def list_artifacts() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.title, a.favicon, a.source_path, a.created_at,
                   MAX(v.version) AS latest_version,
                   MAX(v.created_at) AS updated_at
            FROM artifacts a JOIN versions v ON v.artifact_id = a.id
            GROUP BY a.id ORDER BY updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_artifact(artifact_id: str) -> dict | None:
    with _connect() as conn:
        art = conn.execute(
            "SELECT id, title, favicon, source_path, created_at FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        if not art:
            return None
        versions = conn.execute(
            "SELECT version, label, content_type, created_at FROM versions"
            " WHERE artifact_id = ? ORDER BY version",
            (artifact_id,),
        ).fetchall()
        return {**dict(art), "versions": [dict(v) for v in versions]}


def get_version(artifact_id: str, version: int | None = None) -> dict | None:
    """取指定版本内容;version 为 None 时取最新版。"""
    with _connect() as conn:
        if version is None:
            row = conn.execute(
                "SELECT * FROM versions WHERE artifact_id = ? ORDER BY version DESC LIMIT 1",
                (artifact_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM versions WHERE artifact_id = ? AND version = ?",
                (artifact_id, version),
            ).fetchone()
        return dict(row) if row else None


def delete_artifact(artifact_id: str) -> bool:
    with _connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        return cur.rowcount > 0
