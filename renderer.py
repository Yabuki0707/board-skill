"""把 board-state.json 渲染成 Markdown 和 HTML 线索板。"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


STATUS_LABELS = {
    "todo": "待办", "doing": "进行中", "blocked": "停滞",
    "waiting": "等待中", "done": "已完成", "archived": "仅记录",
}

PRIORITY_LABELS = {
    "critical": "🔴 紧急", "high": "🟠 高", "medium": "🟡 中", "low": "🟢 低",
}
PRIORITY_PLAIN = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}

URGENCY_LABELS = {
    "critical": "🔴 紧急", "high": "🟠 高", "medium": "🟡 中", "low": "🟢 低",
}
URGENCY_PLAIN = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}

CONFIDENCE_EMOJI = {"high": "🟢", "medium": "🟡", "low": "⚪"}
CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}

# 领域案件卡片颜色池（ID 哈希选取，确定且可扩展）
_CASE_COLOR_POOL = [
    "#ff9999", "#99ccff", "#ccffcc", "#e6ccff",
    "#ffcc99", "#b6d7a8", "#a4c2f4", "#f4b183",
    "#d5a6bd", "#ffe599",
]


def _hash_rotation(seed: str) -> int:
    """确定性旋转角度 -3~3，相同ID每次渲染一致。"""
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return (h % 7) - 3


def _pick_case_color(domain_id: str) -> str:
    """根据领域ID从颜色池选取，结果确定。"""
    h = sum(ord(ch) for ch in domain_id)
    return _CASE_COLOR_POOL[h % len(_CASE_COLOR_POOL)]


class Renderer:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    # ------------------------------------------------------------------
    #  Markdown
    # ------------------------------------------------------------------
    def render_markdown(self) -> str:
        updated = self.data.get("updatedAt", "")
        lines: list[str] = []
        lines.append("---")
        lines.append("created: " + updated)
        lines.append("modified: " + updated)
        lines.append("tags:")
        lines.append("  - board")
        lines.append("  - tracker")
        lines.append("---")
        lines.append("")
        lines.append("# 🕵️ 个人侦探线索板")
        lines.append("")
        if self.data.get("situation"):
            lines.append(f"> **当前处境**：{self.data['situation']}")
            lines.append("")

        lines.append("## 📋 任务总览")
        lines.append("")
        tasks = sorted(self.data.get("tasks", []), key=lambda t: t.get("status", ""))
        if tasks:
            lines.append("| 任务 | 领域 | 案件 | 状态 | 优先级 |")
            lines.append("|------|------|------|------|--------|")
            for t in tasks:
                lines.append(
                    f"| {t['text']} | {self._domain_name(t.get('domain', ''))} | "
                    f"{self._case_title(t.get('case', ''))} | "
                    f"{STATUS_LABELS.get(t['status'], t['status'])} | "
                    f"{PRIORITY_LABELS.get(t['priority'], t['priority'])} |"
                )
        else:
            lines.append("暂无任务。")
        lines.append("")

        for d in self.data.get("domains", []):
            lines.append(f"## {d.get('emoji', '📌')} {d['name']}")
            lines.append("")
            if d.get("situation"):
                lines.append(f"**处境**：{d['situation']}")
                lines.append("")
            for c in d.get("cases", []):
                lines.append(f"### 🧩 {c['title']}")
                if c.get("goal"):
                    lines.append(f"- **目标**：{c['goal']}")
                if c.get("situation"):
                    lines.append(f"- **案情**：{c['situation']}")
                if c.get("blocks"):
                    lines.append(f"- **阻塞**：{', '.join(c['blocks'])}")
                urgency = URGENCY_LABELS.get(c.get("urgency", "medium"), c.get("urgency", "中"))
                priority = PRIORITY_LABELS.get(c.get("priority", "medium"), c.get("priority", "中"))
                lines.append(
                    f"- **状态**：{c.get('status', 'active')} | "
                    f"**重要度**：{priority} | **优先度**：{urgency}"
                )
                if c.get("links"):
                    links = " ".join(f"[[{l}]]" for l in c["links"])
                    lines.append(f"- **关联笔记**：{links}")
                case_clues = [cl for cl in self.data.get("clues", []) if cl.get("case") == c["id"]]
                if case_clues:
                    lines.append("- **线索**：")
                    for cl in case_clues:
                        emoji = CONFIDENCE_EMOJI.get(cl.get("confidence", "medium"), "🟡")
                        conf_label = CONFIDENCE_LABELS.get(cl.get("confidence", "medium"), "中")
                        prio = PRIORITY_LABELS.get(cl.get("priority", "medium"), "")
                        lines.append(f"  - {emoji} {cl['text']} (置信度:{conf_label}, 重要度:{prio})")
                case_tasks = [t for t in self.data.get("tasks", []) if t.get("case") == c["id"]]
                if case_tasks:
                    lines.append("- **任务**：")
                    for t in case_tasks:
                        checked = "x" if t["status"] == "done" else " "
                        status_label = STATUS_LABELS.get(t["status"], t["status"])
                        priority_label = PRIORITY_LABELS.get(t["priority"], t["priority"])
                        lines.append(
                            f"  - [{checked}] {t['text']} ({status_label}, {priority_label})"
                        )
                lines.append("")

        lines.append("## 🕸️ 关系图")
        lines.append("")
        lines.append("```mermaid")
        lines.append("graph TD")
        for d in self.data.get("domains", []):
            safe_d = self._safe_id(d["id"])
            d_label = d.get("emoji", "") + " " + d["name"]
            lines.append("  " + safe_d + '["' + d_label + '"];')
            for c in d.get("cases", []):
                safe_c = self._safe_id(c["id"])
                c_label = "🧩 " + c["title"]
                lines.append("  " + safe_c + '["' + c_label + '"];')
                lines.append("  " + safe_d + " --> " + safe_c + ";")
                for cl in self.data.get("clues", []):
                    if cl.get("case") == c["id"]:
                        safe_cl = self._safe_id(cl["id"])
                        cl_label = "💡 " + cl["text"][:20] + "..."
                        lines.append("  " + safe_cl + '["' + cl_label + '"];')
                        lines.append("  " + safe_c + " --> " + safe_cl + ";")
                for t in self.data.get("tasks", []):
                    if t.get("case") == c["id"]:
                        safe_t = self._safe_id(t["id"])
                        t_label = "📌 " + t["text"][:20] + "..."
                        lines.append("  " + safe_t + '["' + t_label + '"];')
                        lines.append("  " + safe_c + " --> " + safe_t + ";")
        lines.append("```")
        lines.append("")
        return "\n".join(lines)

    def _domain_name(self, domain_id: str) -> str:
        for d in self.data.get("domains", []):
            if d["id"] == domain_id:
                return d["name"]
        return domain_id

    def _case_title(self, case_id: str) -> str:
        for d in self.data.get("domains", []):
            for c in d.get("cases", []):
                if c["id"] == case_id:
                    return c["title"]
        return case_id

    @staticmethod
    def _safe_id(text: str) -> str:
        result = "n"
        for ch in text:
            if ch.isalnum():
                result += ch
            elif ch == "-":
                result += "_"
            elif ch == ".":
                result += "d"
            else:
                result += "_"
        return result

    # ------------------------------------------------------------------
    #  HTML — 软木板便利贴 + 多列 Grid + 确定性渲染
    # ------------------------------------------------------------------
    def render_html(self) -> str:
        template_path = Path(__file__).parent / "html" / "template.html"
        if not template_path.exists():
            raise FileNotFoundError(f"HTML template not found: {template_path}")
        template = template_path.read_text(encoding="utf-8")
        board_json = json.dumps(self.data, ensure_ascii=False)
        columns_html = self._generate_columns_html()
        return template.replace("{{BOARD_JSON}}", board_json).replace("{{BOARD_HTML}}", columns_html)

    def _generate_columns_html(self) -> str:
        parts: list[str] = []
        for d in self.data.get("domains", []):
            parts.append(self._render_domain_column(d))
        return "\n".join(parts)

    def _chars_per_line(self, width_px: int, font_size_px: int) -> int:
        """估算给定像素宽度下每行中文字符数。"""
        return max(1, width_px // font_size_px)

    def _render_domain_column(self, d: dict[str, Any]) -> str:
        cards: list[str] = []
        y = 20

        # 领域标题卡片（高度动态）
        situation_text = d.get("situation", "")
        cpl = self._chars_per_line(250, 13)
        sit_lines = max(1, (len(situation_text) + cpl - 1) // cpl) if situation_text else 0
        domain_card_h = 52 + sit_lines * 18

        cards.append(self._card_html(
            "domain", d["id"], left=10, top=y, width=250,
            title=d.get("emoji", "📌") + " " + d["name"],
            meta=situation_text, color="#2a2a2a",
            rotation=0, extra_class="",
        ))
        y += domain_card_h + 28

        for c in d.get("cases", []):
            is_archived = c.get("status") == "archived"
            rotation = _hash_rotation(c["id"])
            priority_labels = PRIORITY_PLAIN if is_archived else PRIORITY_LABELS
            urgency_labels = URGENCY_PLAIN if is_archived else URGENCY_LABELS
            urgency = urgency_labels.get(c.get("urgency", "medium"), "")
            priority = priority_labels.get(c.get("priority", "medium"), "")
            status_text = c.get("status", "active")
            if is_archived:
                status_text = status_text + " 已归档"
            case_meta = f'{status_text} | 重要度:{priority} | 优先度:{urgency}'
            case_extra = "status-archived" if is_archived else ""

            # 案件额外信息
            case_body_lines: list[str] = []
            extra_height = 0
            if c.get("goal"):
                case_body_lines.append(
                    f'<div class="case-goal">🎯 {html.escape(c["goal"])}</div>'
                )
                goal_cpl = self._chars_per_line(254, 11)
                goal_lines = max(1, (len(c["goal"]) + goal_cpl - 1) // goal_cpl)
                extra_height += goal_lines * 14 + 4
            if c.get("blocks"):
                blocks_text = " · ".join(c["blocks"])
                case_body_lines.append(
                    f'<div class="case-blocks">🚫 {html.escape(blocks_text)}</div>'
                )
                blk_cpl = self._chars_per_line(254, 11)
                blk_lines = max(1, (len(blocks_text) + blk_cpl - 1) // blk_cpl)
                extra_height += blk_lines * 14 + 4
            if c.get("situation"):
                sit_text = c["situation"][:120]
                case_body_lines.append(
                    f'<div class="case-situation">{html.escape(sit_text)}</div>'
                )
                sit_cpl = self._chars_per_line(254, 11)
                sit_lines = max(1, (len(sit_text) + sit_cpl - 1) // sit_cpl)
                extra_height += sit_lines * 14 + 4
            if c.get("links"):
                links_text = " ".join(f"[[{l}]]" for l in c["links"])
                case_body_lines.append(
                    f'<div class="case-links">📎 {html.escape(links_text)}</div>'
                )
                lnk_cpl = self._chars_per_line(254, 11)
                lnk_lines = max(1, (len(links_text) + lnk_cpl - 1) // lnk_cpl)
                extra_height += lnk_lines * 14 + 4
            case_body = "\n".join(case_body_lines) if case_body_lines else ""
            # 收拢按钮插在 body 最前面
            collapse_btn = (
                '<span class="collapse-btn" onclick="event.stopPropagation();'
                'var c=this.closest(\'.card.case\');c.classList.toggle(\'collapsed\');'
                'setTimeout(syncCollapsedItems,100);return false;" title="收拢/展开">▼</span>'
            )
            case_body = collapse_btn + case_body

            # 收拢按钮（案件标题旁）
            collapse_btn = (
                '<span class="collapse-btn" onclick="event.stopPropagation();'
                'var c=this.closest(\'.card.case\');c.classList.toggle(\'collapsed\');'
                'setTimeout(syncCollapsedItems,50);return false;" title="收拢/展开">▼</span>'
            )

            # 动态案件卡片高度
            case_cpl = self._chars_per_line(270, 13)
            title_lines = max(1, (len(c["title"]) + case_cpl - 1) // case_cpl)
            case_card_h = 38 + title_lines * 18 + 10 + extra_height

            case_color = _pick_case_color(d["id"])
            cards.append(self._card_html(
                "case", c["id"], left=10, top=y, width=270,
                title="🧩 " + c["title"],
                meta=case_meta,
                color=case_color, rotation=rotation,
                extra_class=case_extra,
                body=case_body,
            ))
            y += case_card_h + 10

            case_clues = [cl for cl in self.data.get("clues", []) if cl.get("case") == c["id"]]
            case_tasks = [t for t in self.data.get("tasks", []) if t.get("case") == c["id"]]
            indent_x = 35

            for cl in case_clues:
                cl_prio = PRIORITY_LABELS.get(cl.get("priority", "medium"), "")
                conf_label = CONFIDENCE_LABELS.get(cl.get("confidence", "medium"), "中")
                conf_emoji = CONFIDENCE_EMOJI.get(cl.get("confidence", "medium"), "🟡")
                cl_cpl = self._chars_per_line(235, 12)
                cl_lines = max(1, (len(cl["text"]) + cl_cpl - 1) // cl_cpl)
                cl_h = 28 + cl_lines * 16
                cl_meta = f'置信度:{conf_emoji} {conf_label} | 重要度:{cl_prio}'
                cl_extra = "priority-" + cl.get("priority", "medium")

                cards.append(self._card_html(
                    "clue", cl["id"], left=indent_x, top=y, width=235,
                    title=cl["text"],
                    meta=cl_meta,
                    color="#fff2cc",
                    rotation=_hash_rotation(cl["id"]),
                    extra_class=cl_extra,
                ))
                y += cl_h + 16

            for t in case_tasks:
                status = t.get("status", "todo")
                status_label = STATUS_LABELS.get(status, status)
                t_prio = PRIORITY_LABELS.get(t.get("priority", "medium"), "")
                bg = "#d9ead3" if status == "done" else "#cfe2f3"
                t_cpl = self._chars_per_line(235, 12)
                t_lines = max(1, (len(t["text"]) + t_cpl - 1) // t_cpl)

                # 任务备注
                t_body = ""
                t_extra_h = 0
                notes = t.get("notes", [])
                if notes:
                    latest = notes[-1]["text"]
                    t_body = (
                        f'<div class="task-note">'
                        f'{html.escape(latest[:80])}</div>'
                    )
                    note_cpl = self._chars_per_line(219, 10)
                    note_lines = max(1, (len(latest[:80]) + note_cpl - 1) // note_cpl)
                    t_extra_h = note_lines * 13 + 4

                t_h = 28 + t_lines * 16 + t_extra_h
                t_meta = f'{status_label} | 重要度:{t_prio}'
                t_extra = f'status-{status} priority-{t.get("priority", "medium")}'

                cards.append(self._card_html(
                    "task", t["id"], left=indent_x, top=y, width=235,
                    title=t["text"],
                    meta=t_meta,
                    color=bg,
                    rotation=_hash_rotation(t["id"]),
                    extra_class=t_extra,
                    body=t_body,
                ))
                y += t_h + 16

            y += 24  # 案件间距

        y += 30

        cards_str = "\n".join(cards)
        return (
            f'<div class="domain-column" style="height:{y}px"'
            f' data-domain-id="{html.escape(d["id"])}">\n'
            + cards_str + "\n</div>"
        )

    def _card_html(
        self, card_type: str, card_id: str,
        left: int, top: int, width: int,
        title: str, meta: str, color: str, rotation: int,
        extra_class: str,
        body: str = "",
    ) -> str:
        cls = "card " + card_type
        if extra_class:
            cls += " " + extra_class
        return (
            f'<div class="{cls}" data-id="{html.escape(card_id)}" '
            f'style="left:{left}px;top:{top}px;width:{width}px;'
            f'background:{color};transform:rotate({rotation}deg);" '
            f'title="{html.escape(meta)}">'
            f'<div class="pin"></div>'
            f'<div class="card-title">{html.escape(title)}</div>'
            f'<div class="card-meta">{html.escape(meta)}</div>'
            + body +
            f'</div>'
        )
