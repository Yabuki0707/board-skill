"""board-state.json 的读取、校验和完整增删改查。"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_STATUS_ORDER = ["doing", "todo", "blocked", "waiting", "done", "archived"]
DEFAULT_PRIORITIES = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="minutes")


def _make_id(prefix: str, existing: set[str]) -> str:
    nums = []
    for e in existing:
        m = re.match(rf"{prefix}-(\d+)", e)
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"{prefix}-{n:03d}"


class BoardState:
    """个人侦探线索板状态。"""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"version": 1, "domains": [], "clues": [], "tasks": []}
        self.load()

    # ------------------------------------------------------------------
    #  持久化
    # ------------------------------------------------------------------
    def load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self._ensure_schema()
        self._sync_case_refs()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updatedAt"] = _now()
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_schema(self) -> None:
        patched: list[str] = []

        def _setdefault(obj: dict, key: str, default: Any, label: str) -> None:
            if key not in obj:
                obj[key] = default
                patched.append(label)

        self.data.setdefault("version", 1)
        self.data.setdefault("situation", "")
        self.data.setdefault("domains", [])
        self.data.setdefault("clues", [])
        self.data.setdefault("tasks", [])
        for d in self.data["domains"]:
            did = d.get("id", "?")
            _setdefault(d, "createdAt", _now(), f"领域 [{did}] 缺 createdAt")
            _setdefault(d, "cases", [], f"领域 [{did}] 缺 cases")
        for d in self.data["domains"]:
            for c in d.get("cases", []):
                cid = c.get("id", "?")
                _setdefault(c, "createdAt", _now(), f"案件 [{cid}] 缺 createdAt")
                _setdefault(c, "urgency", "medium", f"案件 [{cid}] 缺 urgency")
                _setdefault(c, "status", "active", f"案件 [{cid}] 缺 status")
                _setdefault(c, "priority", "medium", f"案件 [{cid}] 缺 priority")
                _setdefault(c, "clues", [], f"案件 [{cid}] 缺 clues")
                _setdefault(c, "tasks", [], f"案件 [{cid}] 缺 tasks")
                _setdefault(c, "blocks", [], f"案件 [{cid}] 缺 blocks")
                _setdefault(c, "links", [], f"案件 [{cid}] 缺 links")
                _setdefault(c, "goal", "", f"案件 [{cid}] 缺 goal")
        for cl in self.data.get("clues", []):
            clid = cl.get("id", "?")
            _setdefault(cl, "createdAt", _now(), f"线索 [{clid}] 缺 createdAt")
            _setdefault(cl, "confidence", "medium", f"线索 [{clid}] 缺 confidence")
            _setdefault(cl, "priority", "medium", f"线索 [{clid}] 缺 priority")
        for t in self.data.get("tasks", []):
            tid = t.get("id", "?")
            _setdefault(t, "createdAt", _now(), f"任务 [{tid}] 缺 createdAt")
            _setdefault(t, "status", "todo", f"任务 [{tid}] 缺 status")
            _setdefault(t, "priority", "medium", f"任务 [{tid}] 缺 priority")
            _setdefault(t, "updatedAt", _now(), f"任务 [{tid}] 缺 updatedAt")
            _setdefault(t, "notes", [], f"任务 [{tid}] 缺 notes")

        if patched:
            import sys
            print(f"⚠ board: 自动修复 {len(patched)} 个缺失字段:", file=sys.stderr)
            for p in patched:
                print(f"   {p}", file=sys.stderr)

    def _sync_case_refs(self) -> None:
        """从顶层 clues/tasks 数组重建 case 内的引用列表。"""
        for d in self.data.get("domains", []):
            for c in d.get("cases", []):
                cid = c["id"]
                c["clues"] = [cl["id"] for cl in self.data.get("clues", []) if cl.get("case") == cid]
                c["tasks"] = [t["id"] for t in self.data.get("tasks", []) if t.get("case") == cid]

    # ------------------------------------------------------------------
    #  查询
    # ------------------------------------------------------------------
    @property
    def domains(self) -> list[dict[str, Any]]:
        return self.data["domains"]

    @property
    def clues(self) -> list[dict[str, Any]]:
        return self.data["clues"]

    @property
    def tasks(self) -> list[dict[str, Any]]:
        return self.data["tasks"]

    def domain(self, domain_id: str) -> dict[str, Any] | None:
        for d in self.domains:
            if d["id"] == domain_id:
                return d
        return None

    def case(self, case_id: str) -> dict[str, Any] | None:
        for d in self.domains:
            for c in d.get("cases", []):
                if c["id"] == case_id:
                    return c
        return None

    def clue(self, clue_id: str) -> dict[str, Any] | None:
        for cl in self.clues:
            if cl["id"] == clue_id:
                return cl
        return None

    def task(self, task_id: str) -> dict[str, Any] | None:
        for t in self.tasks:
            if t["id"] == task_id:
                return t
        return None

    def tasks_by_status(self, status: str) -> list[dict[str, Any]]:
        return [t for t in self.tasks if t["status"] == status]

    def active_tasks(self) -> list[dict[str, Any]]:
        return [t for t in self.tasks if t["status"] in ("todo", "doing", "blocked", "waiting")]

    def doing_tasks(self) -> list[dict[str, Any]]:
        return self.tasks_by_status("doing")

    def _domain_for_case(self, case_id: str) -> dict[str, Any] | None:
        for d in self.domains:
            for c in d.get("cases", []):
                if c["id"] == case_id:
                    return d
        return None

    def domain_name(self, domain_id: str) -> str:
        d = self.domain(domain_id)
        return d["name"] if d else domain_id

    def case_title(self, case_id: str) -> str:
        c = self.case(case_id)
        return c["title"] if c else case_id

    # ------------------------------------------------------------------
    #  创建
    # ------------------------------------------------------------------
    def set_situation(self, text: str) -> None:
        self.data["situation"] = text.strip()
        self.save()

    def add_domain(self, name: str, domain_id: str, emoji: str = "📌", situation: str = "") -> dict[str, Any]:
        if self.domain(domain_id):
            raise ValueError(f"Domain already exists: {domain_id}")
        d = {"id": domain_id, "name": name, "emoji": emoji, "situation": situation, "cases": [], "createdAt": _now()}
        self.domains.append(d)
        self.save()
        return d

    def add_case(
        self,
        domain_id: str,
        title: str,
        goal: str = "",
        case_id: str | None = None,
        status: str = "active",
        priority: str = "medium",
        urgency: str = "medium",
        situation: str = "",
    ) -> dict[str, Any]:
        d = self.domain(domain_id)
        if not d:
            raise ValueError(f"Domain not found: {domain_id}")
        existing = {c["id"] for c in d["cases"]}
        cid = case_id or _make_id(domain_id, existing)
        if cid in existing:
            raise ValueError(f"Case already exists: {cid}")
        c = {
            "id": cid,
            "title": title,
            "status": status,
            "priority": priority,
            "urgency": urgency,
            "situation": situation,
            "goal": goal,
            "blocks": [],
            "clues": [],
            "tasks": [],
            "links": [],
            "createdAt": _now(),
        }
        d["cases"].append(c)
        self.save()
        return c

    def add_clue(
        self,
        case_id: str,
        text: str,
        confidence: str = "medium",
        priority: str = "medium",
        clue_id: str | None = None,
    ) -> dict[str, Any]:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        d = self._domain_for_case(case_id)
        existing = {cl["id"] for cl in self.clues}
        cid = clue_id or _make_id("clue", existing)
        clue = {
            "id": cid,
            "text": text,
            "domain": d["id"] if d else "",
            "case": case_id,
            "confidence": confidence,
            "priority": priority,
            "createdAt": _now(),
        }
        self.clues.append(clue)
        c["clues"].append(cid)
        self.save()
        return clue

    def add_task(
        self,
        case_id: str,
        text: str,
        priority: str = "medium",
        status: str = "todo",
        due: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        d = self._domain_for_case(case_id)
        existing = {t["id"] for t in self.tasks}
        tid = task_id or _make_id("task", existing)
        task = {
            "id": tid,
            "text": text,
            "domain": d["id"] if d else "",
            "case": case_id,
            "status": status,
            "priority": priority,
            "due": due,
            "createdAt": _now(),
            "updatedAt": _now(),
            "notes": [],
        }
        self.tasks.append(task)
        c["tasks"].append(tid)
        self.save()
        return task

    # ------------------------------------------------------------------
    #  更新
    # ------------------------------------------------------------------
    def update_case(
        self,
        case_id: str,
        title: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        urgency: str | None = None,
        situation: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        if title is not None:
            c["title"] = title
        if status is not None:
            c["status"] = status
        if priority is not None:
            c["priority"] = priority
        if urgency is not None:
            c["urgency"] = urgency
        if situation is not None:
            c["situation"] = situation
        if goal is not None:
            c["goal"] = goal
        self.save()
        return c

    def update_task(
        self,
        task_id: str,
        text: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        t = self.task(task_id)
        if not t:
            raise ValueError(f"Task not found: {task_id}")
        if text is not None:
            t["text"] = text
        if status is not None:
            t["status"] = status
        if priority is not None:
            t["priority"] = priority
        if due is not None:
            t["due"] = due
        t["updatedAt"] = _now()
        self.save()
        return t

    def move_task(self, task_id: str, status: str) -> dict[str, Any]:
        return self.update_task(task_id, status=status)

    def link_case(self, case_id: str, obsidian_path: str) -> dict[str, Any]:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        path = obsidian_path.removesuffix(".md")
        if path not in c["links"]:
            c["links"].append(path)
        self.save()
        return c

    def unlink_case(self, case_id: str, obsidian_path: str) -> dict[str, Any]:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        path = obsidian_path.removesuffix(".md")
        if path in c["links"]:
            c["links"].remove(path)
        self.save()
        return c

    # ------------------------------------------------------------------
    #  更新
    # ------------------------------------------------------------------
    def update_domain(
        self, domain_id: str,
        name: str | None = None,
        emoji: str | None = None,
        situation: str | None = None,
    ) -> dict[str, Any]:
        d = self.domain(domain_id)
        if not d:
            raise ValueError(f"Domain not found: {domain_id}")
        if name is not None:
            d["name"] = name
        if emoji is not None:
            d["emoji"] = emoji
        if situation is not None:
            d["situation"] = situation
        self.save()
        return d

    # ------------------------------------------------------------------
    #  删除
    # ------------------------------------------------------------------
    def remove_domain(self, domain_id: str) -> None:
        d = self.domain(domain_id)
        if not d:
            raise ValueError(f"Domain not found: {domain_id}")
        case_ids = {c["id"] for c in d.get("cases", [])}
        # 清理关联的 clues 和 tasks
        self.data["clues"] = [cl for cl in self.clues if cl["case"] not in case_ids]
        self.data["tasks"] = [t for t in self.tasks if t["case"] not in case_ids]
        self.data["domains"] = [d for d in self.domains if d["id"] != domain_id]
        self.save()

    def remove_case(self, case_id: str) -> None:
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        d = self._domain_for_case(case_id)
        # 清理关联的 clues 和 tasks
        self.data["clues"] = [cl for cl in self.clues if cl["case"] != case_id]
        self.data["tasks"] = [t for t in self.tasks if t["case"] != case_id]
        if d:
            d["cases"] = [c for c in d["cases"] if c["id"] != case_id]
        self.save()

    def update_clue(
        self,
        clue_id: str,
        text: str | None = None,
        confidence: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        cl = self.clue(clue_id)
        if not cl:
            raise ValueError(f"Clue not found: {clue_id}")
        if text is not None:
            cl["text"] = text
        if confidence is not None:
            cl["confidence"] = confidence
        if priority is not None:
            cl["priority"] = priority
        self.save()
        return cl

    def remove_clue(self, clue_id: str) -> None:
        cl = self.clue(clue_id)
        if not cl:
            raise ValueError(f"Clue not found: {clue_id}")
        case_id = cl["case"]
        c = self.case(case_id)
        if c and clue_id in c.get("clues", []):
            c["clues"].remove(clue_id)
        self.data["clues"] = [x for x in self.clues if x["id"] != clue_id]
        self.save()

    def remove_task(self, task_id: str) -> None:
        t = self.task(task_id)
        if not t:
            raise ValueError(f"Task not found: {task_id}")
        case_id = t["case"]
        c = self.case(case_id)
        if c and task_id in c.get("tasks", []):
            c["tasks"].remove(task_id)
        self.data["tasks"] = [x for x in self.tasks if x["id"] != task_id]
        self.save()

    # ------------------------------------------------------------------
    #  搜索
    # ------------------------------------------------------------------
    def search(self, query: str) -> list[dict[str, Any]]:
        """全文搜索线索、任务、案件标题/案情、领域名。
        
        CJK 查询（含中文）使用双字符 Bigram 模糊匹配：
        "主任年级" 可匹配 "找年级主任谈话"（Bigram "年级" 命中）。
        英文仍用精确子串匹配。
        """
        results: list[dict[str, Any]] = []
        for cl in self.clues:
            if self._match(query, cl["text"]):
                results.append({
                    "type": "clue", "id": cl["id"], "text": cl["text"],
                    "domain": self.domain_name(cl.get("domain", "")),
                    "case": self.case_title(cl.get("case", "")),
                })
        for t in self.tasks:
            if self._match(query, t["text"]):
                results.append({
                    "type": "task", "id": t["id"], "text": t["text"],
                    "domain": self.domain_name(t.get("domain", "")),
                    "case": self.case_title(t.get("case", "")),
                })
        for d in self.domains:
            if self._match(query, d["name"]) or self._match(query, d.get("situation", "")):
                results.append({
                    "type": "domain", "id": d["id"], "text": d["name"],
                    "domain": d["name"], "case": "",
                })
            for c in d.get("cases", []):
                if self._match(query, c["title"]) or self._match(query, c.get("situation", "")):
                    results.append({
                        "type": "case", "id": c["id"], "text": c["title"],
                        "domain": d["name"], "case": c["title"],
                    })
        return results

    @staticmethod
    def _match(query: str, text: str) -> bool:
        """CJK 感知的模糊匹配。"""
        if not query or not text:
            return False
        q = query.lower()
        t = text.lower()
        # 精确子串优先
        if q in t:
            return True
        # 非 CJK 短查询：精确子串未命中则失败
        if len(q) <= 2 and not any('\u4e00' <= ch <= '\u9fff' for ch in q):
            return False
        # CJK：Bigram 交集匹配
        q_grams = {q[i:i+2] for i in range(len(q)-1)}
        t_grams = {t[i:i+2] for i in range(len(t)-1)}
        return bool(q_grams & t_grams)

    def archive_case(self, case_id: str) -> dict[str, Any]:
        """归档案件：标记为 archived，其下未完成任务标记为 archived。"""
        c = self.case(case_id)
        if not c:
            raise ValueError(f"Case not found: {case_id}")
        c["status"] = "archived"
        count = 0
        for t in self.tasks:
            if t.get("case") == case_id and t["status"] not in ("done", "archived"):
                t["status"] = "archived"
                t["updatedAt"] = _now()
                count += 1
        self.save()
        return {"case": c, "archived_tasks": count}

    def stale_tasks(self, days: int) -> list[dict[str, Any]]:
        """返回超过 days 天未更新的活跃任务（todo/doing/blocked）。"""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(timespec="minutes")
        stale: list[dict[str, Any]] = []
        for t in self.tasks:
            if t.get("status") in ("todo", "doing", "blocked"):
                updated = t.get("updatedAt", "")
                if updated and updated < cutoff:
                    stale.append(t)
        return stale

    def due_tasks(self, days: int) -> list[dict[str, Any]]:
        """返回未来 days 天内到期的未完成任务。"""
        now = datetime.datetime.now()
        cutoff = (now + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        result: list[dict[str, Any]] = []
        for t in self.tasks:
            due = t.get("due", "")
            if due and due <= cutoff and due >= today and t.get("status") not in ("done", "archived"):
                result.append(t)
        return result

    def add_note(self, task_id: str, note: str) -> dict[str, Any]:
        """给任务追加一条进度备注。"""
        t = self.task(task_id)
        if not t:
            raise ValueError(f"Task not found: {task_id}")
        t.setdefault("notes", [])
        entry = {"time": _now(), "text": note.strip()}
        t["notes"].append(entry)
        t["updatedAt"] = _now()
        self.save()
        return t

    def backup(self, backup_dir: Path | None = None) -> Path:
        """备份 board-state.json 到带时间戳的文件。"""
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"board-state.{ts}.json"
        dest = (backup_dir or self.path.parent) / name
        dest.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    def validate(self) -> list[str]:
        """校验数据完整性，返回问题列表。"""
        issues: list[str] = []
        domain_ids = {d["id"] for d in self.domains}
        case_ids: set[str] = set()
        for d in self.domains:
            for c in d.get("cases", []):
                case_ids.add(c["id"])
        clue_ids = {cl["id"] for cl in self.clues}
        task_ids = {t["id"] for t in self.tasks}

        for cl in self.clues:
            if cl.get("case") not in case_ids:
                issues.append(f"线索 [{cl['id']}] 引用了不存在的案件 {cl.get('case')}")
            if cl.get("domain") not in domain_ids:
                issues.append(f"线索 [{cl['id']}] 引用了不存在的领域 {cl.get('domain')}")
        for t in self.tasks:
            if t.get("case") not in case_ids:
                issues.append(f"任务 [{t['id']}] 引用了不存在的案件 {t.get('case')}")
            if t.get("domain") not in domain_ids:
                issues.append(f"任务 [{t['id']}] 引用了不存在的领域 {t.get('domain')}")
        for d in self.domains:
            for c in d.get("cases", []):
                for cid in c.get("clues", []):
                    if cid not in clue_ids:
                        issues.append(f"案件 [{c['id']}] 引用了不存在的线索 {cid}")
                for tid in c.get("tasks", []):
                    if tid not in task_ids:
                        issues.append(f"案件 [{c['id']}] 引用了不存在的任务 {tid}")
        for d in self.domains:
            if not d.get("name"):
                issues.append(f"领域 [{d['id']}] 缺少名称")
        for c in case_ids:
            case = self.case(c)
            if case and not case.get("title"):
                issues.append(f"案件 [{c}] 缺少标题")
        return issues

    def today(self) -> dict[str, Any]:
        """返回今天的变更汇总。"""
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        result: dict[str, Any] = {
            "date": today_str,
            "new_tasks": [],
            "new_clues": [],
            "updated_tasks": [],
            "completed_tasks": [],
            "new_notes": [],
            "updated_cases": [],
        }
        for t in self.tasks:
            created = t.get("createdAt", "")[:10]
            updated = t.get("updatedAt", "")[:10]
            if created == today_str:
                result["new_tasks"].append(t)
            elif updated == today_str and t.get("status") == "done":
                result["completed_tasks"].append(t)
            elif updated == today_str:
                result["updated_tasks"].append(t)
            for note in t.get("notes", []):
                if note.get("time", "")[:10] == today_str:
                    result["new_notes"].append({"task_id": t["id"], "task_text": t["text"], "note": note["text"]})
        for cl in self.clues:
            if cl.get("createdAt", "")[:10] == today_str:
                result["new_clues"].append(cl)
        for d in self.domains:
            for c in d.get("cases", []):
                created = c.get("createdAt", "")[:10]
                if created == today_str:
                    result["updated_cases"].append(c)
        return result

    def stats(self) -> dict[str, Any]:
        """返回全局统计面板数据。"""
        tasks = self.tasks
        clues = self.clues
        domains = self.domains
        total_cases = sum(len(d.get("cases", [])) for d in domains)

        # 任务状态分布
        status_counts: dict[str, int] = {}
        for t in tasks:
            s = t.get("status", "todo")
            status_counts[s] = status_counts.get(s, 0) + 1
        done_count = status_counts.get("done", 0)
        blocked_count = status_counts.get("blocked", 0)
        todo_count = status_counts.get("todo", 0)
        doing_count = status_counts.get("doing", 0)

        # 优先级分布
        critical_tasks = sum(1 for t in tasks if t.get("priority") == "critical")
        high_tasks = sum(1 for t in tasks if t.get("priority") == "high")
        active_tasks = todo_count + doing_count + blocked_count + status_counts.get("waiting", 0)

        # 完成率
        total = len(tasks)
        completion = round(done_count / total * 100, 1) if total > 0 else 0

        # 停滞
        now = datetime.datetime.now()
        stale_3d = sum(1 for t in tasks
                       if t.get("status") in ("todo", "doing", "blocked")
                       and t.get("updatedAt", "") < (now - datetime.timedelta(days=3)).isoformat(timespec="minutes"))
        stale_7d = sum(1 for t in tasks
                       if t.get("status") in ("todo", "doing", "blocked")
                       and t.get("updatedAt", "") < (now - datetime.timedelta(days=7)).isoformat(timespec="minutes"))

        # 到期
        cutoff = (now + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        due_soon = sum(1 for t in tasks
                       if t.get("due", "") and t["due"] >= today and t["due"] <= cutoff
                       and t.get("status") not in ("done", "archived"))

        # 热度领域
        active_cases = sum(1 for d in domains for c in d.get("cases", []) if c.get("status") in (None, "active"))
        archived_cases = sum(1 for d in domains for c in d.get("cases", []) if c.get("status") == "archived")

        # 每个领域详情
        domain_stats = []
        for d in domains:
            d_tasks = [t for t in tasks if t.get("domain") == d["id"]]
            d_clues = [cl for cl in clues if cl.get("domain") == d["id"]]
            d_blocked = sum(1 for t in d_tasks if t.get("status") == "blocked")
            d_doing = sum(1 for t in d_tasks if t.get("status") == "doing")
            d_cases = len(d.get("cases", []))
            domain_stats.append({
                "id": d["id"], "name": d["name"], "emoji": d.get("emoji", ""),
                "tasks": len(d_tasks), "clues": len(d_clues),
                "blocked": d_blocked, "doing": d_doing, "cases": d_cases,
            })

        # 最近活跃
        latest = ""
        for t in tasks:
            u = t.get("updatedAt", "")
            if u > latest:
                latest = u

        return {
            "domains": len(domains),
            "cases": total_cases,
            "active_cases": active_cases,
            "archived_cases": archived_cases,
            "clues": len(clues),
            "tasks": total,
            "active_tasks": active_tasks,
            "status": {"todo": todo_count, "doing": doing_count, "blocked": blocked_count,
                        "waiting": status_counts.get("waiting", 0),
                        "done": done_count, "archived": status_counts.get("archived", 0)},
            "critical": critical_tasks,
            "high": high_tasks,
            "completion": completion,
            "stale_3d": stale_3d,
            "stale_7d": stale_7d,
            "due_soon": due_soon,
            "blocked_total": blocked_count,
            "domain_stats": domain_stats,
            "latest_activity": latest[:16] if latest else "",
        }

    # ------------------------------------------------------------------
    #  排序
    # ------------------------------------------------------------------
    def sorted_tasks(self, tasks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        tasks = tasks or self.tasks
        return sorted(
            tasks,
            key=lambda t: (
                DEFAULT_STATUS_ORDER.index(t["status"]) if t["status"] in DEFAULT_STATUS_ORDER else 99,
                -DEFAULT_PRIORITIES.get(t["priority"], 0),
            ),
        )
