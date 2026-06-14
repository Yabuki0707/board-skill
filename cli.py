#!/usr/bin/env python3
"""OpenClaw Board CLI — 个人侦探线索板管理。

用法：
    board init [--force]
    board show [--format table|summary]
    board add-domain <id> <name> [--emoji] [--situation]
    board add-case <domain> <title> [--goal] [--situation] [--priority] [--urgency] [--status]
    board update-case <case-id> [--title] [--situation] [--goal] [--priority] [--urgency] [--status]
    board add-clue <case> <text> [--confidence]
    board add-task <case> <text> [--priority] [--status] [--due]
    board update-task <task-id> [--text] [--status] [--priority] [--due]
    board move-task <task-id> <status>
    board remove-domain <domain-id>
    board remove-case <case-id>
    board remove-clue <clue-id>
    board remove-task <task-id>
    board link-case <case-id> <obsidian-path>
    board set-situation <text>
    board render [--format md|html] [--output PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .state import BoardState
from .renderer import Renderer, STATUS_LABELS, PRIORITY_LABELS, URGENCY_LABELS, CONFIDENCE_EMOJI, CONFIDENCE_LABELS

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _state_path() -> Path:
    return _workspace_root() / "board-state.json"


def _load_state() -> BoardState:
    return BoardState(_state_path())


# ------------------------------------------------------------------
#  help
# ------------------------------------------------------------------
def cmd_help(args: argparse.Namespace) -> int:
    print("""🕵️ 个人侦探线索板 — 命令速查

查询:
  board show [--format summary|table]    总览（摘要/任务表格）
  board domains                          列出所有领域及简介
  board cases <domain-id>                列出领域下所有案件
  board items <case-id>                  列出案件下所有线索和任务
  board tasks [--status] [--domain] [--priority]   过滤任务列表
  board clues [--confidence] [--domain] [--priority] 过滤线索列表
  board search <query>                   全文搜索（支持中文 Bigram 模糊）
  board stale [--days 3]                 查找超期未更新任务
  board due [--days 7]                    查看未来 N 天到期任务
  board today                             今日变更汇总
  board stats                             全局统计面板
  board validate                          校验数据完整性
  board backup                           备份 board-state.json
  board render [--format md|html] --output PATH   渲染输出
  board version                           查看系统版本与更新记录

创建:
  board init [--force]                   初始化
  board add-domain <id> <name> [--emoji] [--situation]
  board add-case <domain> <title> [--goal] [--situation] [--priority] [--urgency] [--status]
  board add-clue <case> <text> [--confidence] [--priority]
  board add-task <case> <text> [--priority] [--status] [--due]

更新:
  board update-domain <id> [--name] [--emoji] [--situation]
  board update-case <case-id> [--title] [--situation] [--goal] [--priority] [--urgency] [--status]
  board update-clue <clue-id> [--text] [--confidence] [--priority]
  board update-task <task-id> [--text] [--status] [--priority] [--due]
  board move-task <task-id> <status>      快捷改任务状态
  board note <task-id> "备注内容"           给任务追加进度备注
  board archive-case <case-id>            归档案件（灰调显示，不删除）
  board link-case <case-id> <obsidian-path>
  board unlink-case <case-id> <obsidian-path>
  board links <case-id>                   列出案件关联笔记
  board set-situation <text>

删除:
  board remove-domain <id>
  board remove-case <id>
  board remove-clue <id>
  board remove-task <id>

字段值:
  priority/urgency:  critical | high | medium | low
  confidence:        high | medium | low
  status (任务):      todo | doing | blocked | waiting | done | archived
  status (案件):      active | paused | archived

示例:
  board add-domain school "学校" --emoji 🏫
  board add-case school "班主任冲突" --priority high --urgency critical
  board add-clue school-001 "当众批评" --confidence high --priority high
  board add-task school-001 "找年级主任" --priority high
  board move-task task-001 doing
  board search "班主任"
  board archive-case school-001
  board stale --days 7
  board render --format md --output content/board.md

最佳实践:
  领域划分: 按生活/工作大类分（学校、编程、小说、哲学），4-6个为宜，太多说明粒度太细
  案件粒度: 一个案件 = 一个需要持续关注的问题或项目，不是一次性任务
  独立拆分: 互不相关的内容不要塞进同一个案件——各开各的，线索和任务才能精准归属
  线索 vs 任务: 线索是"已知信息"（发生了什么），任务是"要做什么"（行动项）
  重要度 vs 优先度: 重要度=这件事本身价值多大，优先度=时间上多紧迫
  置信度: 道听途说标 low，亲眼所见标 high，推测标 medium
  归档节奏: 案件完结后 archive，不删除，留着做历史参考
  定期审视: 每次会话结束前 board stale 看看哪些任务太久没动
  保持诚实: 案件 situation 如实写，停滞就是停滞，线索板是镜子不是化妆师
""")
    return 0


# ------------------------------------------------------------------
#  init / show / render
# ------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    path = _state_path()
    if path.exists() and not args.force:
        print("board-state.json 已存在。使用 --force 强制重建。")
        return 1
    bs = BoardState(path)
    if not path.exists():
        bs.save()
    print(f"已初始化: {path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    bs = _load_state()
    if not bs.domains:
        print("线索板为空。使用 board add-domain 添加领域。")
        return 0
    if args.format == "summary":
        print(f"处境: {bs.data.get('situation', '未设置')}")
        print()
        for d in bs.domains:
            cases_count = len(d.get("cases", []))
            case_tasks = sum(len(c.get("tasks", [])) for c in d.get("cases", []))
            case_clues = sum(len(c.get("clues", [])) for c in d.get("cases", []))
            doing = sum(
                1 for t in bs.tasks
                if bs._domain_for_case(t.get("case", ""))
                and bs._domain_for_case(t.get("case", ""))["id"] == d["id"]
                and t["status"] == "doing"
            )
            print(f"{d.get('emoji', '')} {d['name']}  [{d['id']}]")
            print(f"  案件: {cases_count}  线索: {case_clues}  任务: {case_tasks}  进行中: {doing}")
            if d.get("situation"):
                print(f"  处境: {d['situation']}")
            print()
    else:
        tasks = bs.sorted_tasks()
        if tasks:
            print(f"{'状态':<8} {'优先级':<8} {'任务':<40} {'领域':<10} {'案件':<20}")
            print("-" * 90)
            for t in tasks:
                print(f"{t['status']:<8} {t['priority']:<8} {t['text'][:38]:<40} "
                      f"{bs.domain_name(t.get('domain', ''))[:8]:<10} "
                      f"{bs.case_title(t.get('case', ''))[:18]:<20}")
        else:
            print("暂无任务。")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    bs = _load_state()
    r = Renderer(bs.data)
    if args.format == "html":
        output = r.render_html()
    else:
        output = r.render_markdown()
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"已渲染到: {out_path}")
    else:
        print(output)
    return 0


def cmd_set_situation(args: argparse.Namespace) -> int:
    bs = _load_state()
    bs.set_situation(args.text)
    print("已更新总体处境。")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    bs = _load_state()
    results = bs.search(args.query)
    if not results:
        print(f"未找到匹配 '{args.query}' 的内容。")
        return 0
    print(f"搜索 '{args.query}' 找到 {len(results)} 条结果：")
    print()
    for r in results:
        tag = {"clue": "💡线索", "task": "📌任务", "case": "🧩案件", "domain": "📁领域"}.get(r["type"], r["type"])
        loc = f"{r['domain']} › {r['case']}" if r["case"] else r["domain"]
        print(f"  [{r['id']}] {tag}  {r['text']}")
        print(f"          {loc}")
    return 0


def cmd_archive_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        result = bs.archive_case(args.case_id)
        c = result["case"]
        n = result["archived_tasks"]
        print(f"已归档案件 [{c['id']}] {c['title']}，{n} 个任务标记为 archived。")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_stale(args: argparse.Namespace) -> int:
    bs = _load_state()
    tasks = bs.stale_tasks(args.days)
    if not tasks:
        print(f"没有超过 {args.days} 天未更新的活跃任务。")
        return 0
    print(f"{len(tasks)} 个任务超过 {args.days} 天未更新：")
    print()
    for t in tasks:
        domain = bs.domain_name(t.get("domain", ""))
        case = bs.case_title(t.get("case", ""))
        updated = t.get("updatedAt", "")[:10]
        print(f"  [{t['id']}] {t['status']:<8} {t['text'][:40]}")
        print(f"           {domain} › {case}  更新于 {updated}")
    return 0


def cmd_domains(args: argparse.Namespace) -> int:
    bs = _load_state()
    if not bs.domains:
        print("暂无领域。")
        return 0
    for d in bs.domains:
        cases_count = len(d.get("cases", []))
        active = sum(1 for c in d.get("cases", []) if c.get("status") in (None, "active"))
        archived = sum(1 for c in d.get("cases", []) if c.get("status") == "archived")
        print(f"{d.get('emoji', '')} {d['name']}  [{d['id']}]")
        print(f"  案件: {cases_count} (活跃:{active} 归档:{archived})")
        if d.get("situation"):
            print(f"  {d['situation']}")
        print()
    return 0


def cmd_cases(args: argparse.Namespace) -> int:
    bs = _load_state()
    d = bs.domain(args.domain_id)
    if not d:
        print(f"领域不存在: {args.domain_id}")
        return 1
    cases = d.get("cases", [])
    if not cases:
        print(f"领域 [{args.domain_id}] 下暂无案件。")
        return 0
    print(f"{d.get('emoji', '')} {d['name']} — {len(cases)} 个案件：")
    print()
    for c in cases:
        priority = PRIORITY_LABELS.get(c.get("priority", "medium"), c.get("priority", "中"))
        urgency = URGENCY_LABELS.get(c.get("urgency", "medium"), c.get("urgency", "中"))
        clues_n = len(c.get("clues", []))
        tasks_n = len(c.get("tasks", []))
        print(f"  🧩 [{c['id']}] {c['title']}")
        print(f"     {c.get('status', 'active')} | 重要度:{priority} | 优先度:{urgency}")
        print(f"     线索:{clues_n}  任务:{tasks_n}")
        if c.get("goal"):
            print(f"     目标: {c['goal']}")
        print()
    return 0


def cmd_items(args: argparse.Namespace) -> int:
    bs = _load_state()
    c = bs.case(args.case_id)
    if not c:
        print(f"案件不存在: {args.case_id}")
        return 1
    print(f"🧩 {c['title']}  [{c['id']}]")
    print(f"   {c.get('status', 'active')} | 目标: {c.get('goal', '无')}")
    print()

    clues = [cl for cl in bs.clues if cl.get("case") == args.case_id]
    tasks = [t for t in bs.tasks if t.get("case") == args.case_id]

    if clues:
        print(f"  💡 线索 ({len(clues)}条)：")
        for cl in clues:
            conf = CONFIDENCE_LABELS.get(cl.get("confidence", "medium"), "中")
            prio = PRIORITY_LABELS.get(cl.get("priority", "medium"), "")
            print(f"     [{cl['id']}] {cl['text']}")
            print(f"     置信度:{conf}  重要度:{prio}")
        print()

    if tasks:
        print(f"  📌 任务 ({len(tasks)}个)：")
        for t in tasks:
            status = STATUS_LABELS.get(t.get("status", "todo"), t["status"])
            prio = PRIORITY_LABELS.get(t.get("priority", "medium"), "")
            updated = t.get("updatedAt", "")[:10]
            print(f"     [{t['id']}] {t['text']}")
            print(f"     {status}  重要度:{prio}  更新于:{updated}")
        print()

    if not clues and not tasks:
        print("  暂无线索或任务。")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    bs = _load_state()
    tasks = bs.tasks
    if args.status:
        tasks = [t for t in tasks if t.get("status") == args.status]
    if args.domain:
        tasks = [t for t in tasks if t.get("domain") == args.domain]
    if args.priority:
        tasks = [t for t in tasks if t.get("priority") == args.priority]

    if not tasks:
        print("无匹配任务。")
        return 0

    tasks = bs.sorted_tasks(tasks)
    print(f"{'状态':<8} {'重要':<8} {'任务':<42} {'领域':<10} {'案件':<18} {'更新于'}")
    print("-" * 100)
    for t in tasks:
        status = STATUS_LABELS.get(t.get("status", "todo"), t["status"])
        prio = PRIORITY_LABELS.get(t.get("priority", "medium"), "")
        updated = t.get("updatedAt", "")[:10]
        domain = bs.domain_name(t.get("domain", ""))
        case = bs.case_title(t.get("case", ""))
        print(f"{status:<8} {prio:<8} {t['text'][:40]:<42} {domain:<10} {case[:16]:<18} {updated}")
    return 0


def cmd_clues(args: argparse.Namespace) -> int:
    bs = _load_state()
    clues = bs.clues
    if args.confidence:
        clues = [cl for cl in clues if cl.get("confidence") == args.confidence]
    if args.domain:
        clues = [cl for cl in clues if cl.get("domain") == args.domain]
    if args.priority:
        clues = [cl for cl in clues if cl.get("priority") == args.priority]

    if not clues:
        print("无匹配线索。")
        return 0

    print(f"{'置信':<6} {'重要':<8} {'线索':<48} {'领域':<10} {'案件':<18}")
    print("-" * 94)
    for cl in clues:
        conf = CONFIDENCE_LABELS.get(cl.get("confidence", "medium"), "中")
        prio = PRIORITY_LABELS.get(cl.get("priority", "medium"), "")
        domain = bs.domain_name(cl.get("domain", ""))
        case = bs.case_title(cl.get("case", ""))
        print(f"{conf:<6} {prio:<8} {cl['text'][:46]:<48} {domain:<10} {case[:16]:<18}")
    return 0


# ------------------------------------------------------------------
#  add commands
# ------------------------------------------------------------------
def cmd_add_domain(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        d = bs.add_domain(args.name, args.id, emoji=args.emoji, situation=args.situation or "")
        print(f"已添加领域: {d['emoji']} {d['name']} [{d['id']}]")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_add_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        c = bs.add_case(
            args.domain, args.title,
            goal=args.goal or "",
            situation=args.situation or "",
            priority=args.priority,
            urgency=args.urgency,
            status=args.status,
        )
        print(f"已添加案件: [{c['id']}] {c['title']} (重要:{c['priority']} 紧急:{c['urgency']})")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_add_clue(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        cl = bs.add_clue(args.case, args.text, confidence=args.confidence, priority=args.priority)
        print(f"已添加线索: [{cl['id']}] {cl['text']} (置信度: {cl['confidence']}, 重要度: {cl['priority']})")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_add_task(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        t = bs.add_task(
            args.case, args.text,
            priority=args.priority, status=args.status, due=args.due,
        )
        print(f"已添加任务: [{t['id']}] {t['text']} ({t['status']}, {t['priority']})")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    print("🕵️ 个人侦探线索板  v1.3")
    print()
    print("  变更记录:")
    print("    v1.3 — today/stats/backup/validate/due/note/update-domain")
    print("           全部实体 createdAt、任务备注、CJK Bigram 模糊搜索")
    print("           Schema 自动修复时输出 warning")
    print("    v1.2 — task updatedAt 时间戳、board stale 命令、归档灰调显示")
    print("    v1.1 — 多列 Grid 软木板、状态色带、中文标签、SVG 滚动修复")
    print("    v1.0 — 初版：领域-案件-线索-任务四级模型、CLI + HTML 渲染")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        dest = bs.backup()
        print(f"已备份到: {dest}")
    except Exception as e:
        print(f"备份失败: {e}")
        return 1
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    bs = _load_state()
    issues = bs.validate()
    if not issues:
        print("数据完整，无问题。")
    else:
        print(f"发现 {len(issues)} 个问题：")
        for i in issues:
            print(f"  ⚠ {i}")
    return 0


def cmd_due(args: argparse.Namespace) -> int:
    bs = _load_state()
    tasks = bs.due_tasks(args.days)
    if not tasks:
        print(f"未来 {args.days} 天内没有到期的任务。")
        return 0
    print(f"{len(tasks)} 个任务在未来 {args.days} 天内到期：")
    print()
    for t in tasks:
        domain = bs.domain_name(t.get("domain", ""))
        case = bs.case_title(t.get("case", ""))
        print(f"  [{t['id']}] {t['text'][:50]}")
        print(f"  到期: {t.get('due', '')}  状态: {t.get('status', '')}  {domain} › {case}")
    return 0


def cmd_task_note(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        t = bs.add_note(args.task_id, args.note)
        notes_count = len(t.get("notes", []))
        print(f"已添加备注到 [{t['id']}] {t['text'][:40]}  (共 {notes_count} 条)")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    bs = _load_state()
    result = bs.today()
    print(f"📅 今日变更  {result['date']}")
    print()

    new_t = result["new_tasks"]
    new_c = result["new_clues"]
    upd_t = result["updated_tasks"]
    done_t = result["completed_tasks"]
    notes = result["new_notes"]
    upd_c = result["updated_cases"]

    if not any([new_t, new_c, upd_t, done_t, notes, upd_c]):
        print("  今天暂无变更。")
        return 0

    if new_t:
        print(f"  ➕ 新建任务 ({len(new_t)}):")
        for t in new_t:
            print(f"     [{t['id']}] {t['text'][:50]}")
        print()
    if new_c:
        print(f"  ➕ 新建线索 ({len(new_c)}):")
        for cl in new_c:
            print(f"     [{cl['id']}] {cl['text'][:50]}")
        print()
    if upd_t:
        print(f"  ✏️ 更新任务 ({len(upd_t)}):")
        for t in upd_t:
            print(f"     [{t['id']}] {t['text'][:50]}")
        print()
    if done_t:
        print(f"  ✅ 完成任务 ({len(done_t)}):")
        for t in done_t:
            print(f"     [{t['id']}] {t['text'][:50]}")
        print()
    if notes:
        print(f"  📝 新增备注 ({len(notes)}):")
        for n in notes:
            print(f"     [{n['task_id']}] {n['task_text'][:30]}")
            print(f"     → {n['note'][:60]}")
        print()
    if upd_c:
        print(f"  🧩 新建案件 ({len(upd_c)}):")
        for c in upd_c:
            print(f"     [{c['id']}] {c['title']}")
        print()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    bs = _load_state()
    s = bs.stats()

    print("📊 线索板统计")
    print()
    print(f"  领域: {s['domains']}    案件: {s['cases']} (活跃:{s['active_cases']} 归档:{s['archived_cases']})")
    print(f"  线索: {s['clues']}      任务: {s['tasks']} (活跃:{s['active_tasks']})")
    print()

    print("  📋 任务状态分布:")
    st = s["status"]
    bar = lambda n, total: "█" * min(n, 20) if total > 0 else ""
    total_t = s["tasks"] or 1
    print(f"     进行中  {st['doing']:>3}  {bar(st['doing'], total_t)}")
    print(f"     待  办  {st['todo']:>3}  {bar(st['todo'], total_t)}")
    print(f"     阻  塞  {st['blocked']:>3}  {bar(st['blocked'], total_t)}")
    print(f"     已完成  {st['done']:>3}  {bar(st['done'], total_t)}")
    print(f"     已归档  {st['archived']:>3}  {bar(st['archived'], total_t)}")
    print()

    print(f"  🔴 紧急重要: {s['critical']}    🟠 高优先: {s['high']}")
    print(f"  ✅ 完成率: {s['completion']}%")
    print(f"  ⏰ {s['stale_3d']} 个任务超过3天未更新  ({s['stale_7d']} 个超过7天)")
    print(f"  📅 {s['due_soon']} 个任务7天内到期")
    if s["blocked_total"]:
        print(f"  🚫 {s['blocked_total']} 个阻塞任务需要关注")
    print()

    if s["domain_stats"]:
        print("  📁 各领域热度:")
        for ds in s["domain_stats"]:
            flag = " ⚠" if ds["blocked"] > 0 else ""
            bar_len = min(ds["tasks"], 15)
            bar_str = "▓" * bar_len if ds["tasks"] > 0 else "░"
            print(f"     {ds['emoji']} {ds['name']:<8}  {bar_str}  任务:{ds['tasks']}  案件:{ds['cases']}  进行中:{ds['doing']}  阻塞:{ds['blocked']}{flag}")

    if s["latest_activity"]:
        print(f"\n  最近活动: {s['latest_activity']}")
    return 0


# ------------------------------------------------------------------
#  update commands
# ------------------------------------------------------------------
def cmd_update_domain(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        kwargs = {}
        if args.name is not None:
            kwargs["name"] = args.name
        if args.emoji is not None:
            kwargs["emoji"] = args.emoji
        if args.situation is not None:
            kwargs["situation"] = args.situation
        if not kwargs:
            print("未提供任何更新字段。")
            return 1
        d = bs.update_domain(args.domain_id, **kwargs)
        print(f"已更新领域 [{d['id']}]: {d['name']}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_update_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        kwargs = {}
        if args.title is not None:
            kwargs["title"] = args.title
        if args.status is not None:
            kwargs["status"] = args.status
        if args.priority is not None:
            kwargs["priority"] = args.priority
        if args.urgency is not None:
            kwargs["urgency"] = args.urgency
        if args.situation is not None:
            kwargs["situation"] = args.situation
        if args.goal is not None:
            kwargs["goal"] = args.goal
        if not kwargs:
            print("未提供任何更新字段。")
            return 1
        c = bs.update_case(args.case_id, **kwargs)
        print(f"已更新案件 [{c['id']}]: {c['title']}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_update_task(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        kwargs = {}
        if args.text is not None:
            kwargs["text"] = args.text
        if args.status is not None:
            kwargs["status"] = args.status
        if args.priority is not None:
            kwargs["priority"] = args.priority
        if args.due is not None:
            kwargs["due"] = args.due
        if not kwargs:
            print("未提供任何更新字段。")
            return 1
        t = bs.update_task(args.task_id, **kwargs)
        print(f"已更新任务 [{t['id']}]: {t['text']} ({t['status']})")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_move_task(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        t = bs.move_task(args.task_id, args.status)
        print(f"任务 [{t['id']}] 状态更新为: {t['status']}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_link_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        c = bs.link_case(args.case_id, args.obsidian_path)
        print(f"案件 [{c['id']}] 已关联笔记: {args.obsidian_path}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_unlink_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        c = bs.unlink_case(args.case_id, args.obsidian_path)
        print(f"案件 [{c['id']}] 已取消关联: {args.obsidian_path}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    bs = _load_state()
    c = bs.case(args.case_id)
    if not c:
        print(f"案件不存在: {args.case_id}")
        return 1
    links = c.get("links", [])
    if not links:
        print(f"案件 [{args.case_id}] 暂无关联笔记。")
        return 0
    print(f"案件 [{args.case_id}] {c['title']} — {len(links)} 条关联笔记:")
    for l in links:
        print(f"  📎 {l}")
    return 0


def cmd_update_clue(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        kwargs = {}
        if args.text is not None:
            kwargs["text"] = args.text
        if args.confidence is not None:
            kwargs["confidence"] = args.confidence
        if args.priority is not None:
            kwargs["priority"] = args.priority
        if not kwargs:
            print("未提供任何更新字段。")
            return 1
        cl = bs.update_clue(args.clue_id, **kwargs)
        print(f"已更新线索 [{cl['id']}]: {cl['text'][:40]}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


# ------------------------------------------------------------------
#  remove commands
# ------------------------------------------------------------------
def cmd_remove_domain(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        bs.remove_domain(args.domain_id)
        print(f"已删除领域: {args.domain_id}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_remove_case(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        bs.remove_case(args.case_id)
        print(f"已删除案件: {args.case_id}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_remove_clue(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        bs.remove_clue(args.clue_id)
        print(f"已删除线索: {args.clue_id}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


def cmd_remove_task(args: argparse.Namespace) -> int:
    bs = _load_state()
    try:
        bs.remove_task(args.task_id)
        print(f"已删除任务: {args.task_id}")
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    return 0


# ------------------------------------------------------------------
#  main
# ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="board",
        description="OpenClaw Board CLI — 个人侦探线索板管理",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    # help
    p_help = sub.add_parser("help", help="显示帮助信息")
    p_help.set_defaults(func=cmd_help)

    p_init = sub.add_parser("init", help="初始化 board-state.json")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="显示线索板总览")
    p_show.add_argument("--format", choices=["table", "summary"], default="summary")
    p_show.set_defaults(func=cmd_show)

    p_ad = sub.add_parser("add-domain", help="添加领域")
    p_ad.add_argument("id")
    p_ad.add_argument("name")
    p_ad.add_argument("--emoji", default="📌")
    p_ad.add_argument("--situation", default="")
    p_ad.set_defaults(func=cmd_add_domain)

    p_ac = sub.add_parser("add-case", help="添加案件")
    p_ac.add_argument("domain")
    p_ac.add_argument("title")
    p_ac.add_argument("--goal", default="")
    p_ac.add_argument("--situation", default="")
    p_ac.add_argument("--priority", choices=["critical", "high", "medium", "low"], default="medium")
    p_ac.add_argument("--urgency", choices=["critical", "high", "medium", "low"], default="medium")
    p_ac.add_argument("--status", default="active")
    p_ac.set_defaults(func=cmd_add_case)

    p_uc = sub.add_parser("update-case", help="更新案件字段")
    p_uc.add_argument("case_id")
    p_uc.add_argument("--title", default=None)

    p_ud = sub.add_parser("update-domain", help="更新领域字段")
    p_ud.add_argument("domain_id")
    p_ud.add_argument("--name", default=None)
    p_ud.add_argument("--emoji", default=None)
    p_ud.add_argument("--situation", default=None)
    p_ud.set_defaults(func=cmd_update_domain)
    p_uc.add_argument("--situation", default=None)
    p_uc.add_argument("--goal", default=None)
    p_uc.add_argument("--priority", choices=["critical", "high", "medium", "low"], default=None)
    p_uc.add_argument("--urgency", choices=["critical", "high", "medium", "low"], default=None)
    p_uc.add_argument("--status", default=None)
    p_uc.set_defaults(func=cmd_update_case)

    p_acl = sub.add_parser("add-clue", help="添加线索")
    p_acl.add_argument("case")
    p_acl.add_argument("text")
    p_acl.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    p_acl.add_argument("--priority", choices=["critical", "high", "medium", "low"], default="medium")
    p_acl.set_defaults(func=cmd_add_clue)

    p_ucl = sub.add_parser("update-clue", help="更新线索字段")
    p_ucl.add_argument("clue_id")
    p_ucl.add_argument("--text", default=None)
    p_ucl.add_argument("--confidence", choices=["high", "medium", "low"], default=None)
    p_ucl.add_argument("--priority", choices=["critical", "high", "medium", "low"], default=None)
    p_ucl.set_defaults(func=cmd_update_clue)

    p_at = sub.add_parser("add-task", help="添加任务")
    p_at.add_argument("case")
    p_at.add_argument("text")
    p_at.add_argument("--priority", choices=["critical", "high", "medium", "low"], default="medium")
    p_at.add_argument("--status", default="todo")
    p_at.add_argument("--due", default=None)
    p_at.set_defaults(func=cmd_add_task)

    p_ut = sub.add_parser("update-task", help="更新任务字段")
    p_ut.add_argument("task_id")
    p_ut.add_argument("--text", default=None)
    p_ut.add_argument("--status", choices=["todo", "doing", "blocked", "waiting", "done", "archived"], default=None)
    p_ut.add_argument("--priority", choices=["critical", "high", "medium", "low"], default=None)
    p_ut.add_argument("--due", default=None)
    p_ut.set_defaults(func=cmd_update_task)

    p_mt = sub.add_parser("move-task", help="快捷更改任务状态")
    p_mt.add_argument("task_id")
    p_mt.add_argument("status", choices=["todo", "doing", "blocked", "waiting", "done", "archived"])
    p_mt.set_defaults(func=cmd_move_task)

    p_rd = sub.add_parser("remove-domain", help="删除领域及其所有案件/线索/任务")
    p_rd.add_argument("domain_id")
    p_rd.set_defaults(func=cmd_remove_domain)

    p_rc = sub.add_parser("remove-case", help="删除案件及其线索/任务")
    p_rc.add_argument("case_id")
    p_rc.set_defaults(func=cmd_remove_case)

    p_rcl = sub.add_parser("remove-clue", help="删除线索")
    p_rcl.add_argument("clue_id")
    p_rcl.set_defaults(func=cmd_remove_clue)

    p_rt = sub.add_parser("remove-task", help="删除任务")
    p_rt.add_argument("task_id")
    p_rt.set_defaults(func=cmd_remove_task)

    p_lc = sub.add_parser("link-case", help="关联 Obsidian 笔记")
    p_lc.add_argument("case_id")
    p_lc.add_argument("obsidian_path")
    p_lc.set_defaults(func=cmd_link_case)

    p_ulc = sub.add_parser("unlink-case", help="取消关联 Obsidian 笔记")
    p_ulc.add_argument("case_id")
    p_ulc.add_argument("obsidian_path")
    p_ulc.set_defaults(func=cmd_unlink_case)

    p_links = sub.add_parser("links", help="列出案件关联笔记")
    p_links.add_argument("case_id")
    p_links.set_defaults(func=cmd_links)

    p_ss = sub.add_parser("set-situation", help="设置总体处境")
    p_ss.add_argument("text")
    p_ss.set_defaults(func=cmd_set_situation)

    p_search = sub.add_parser("search", help="全文搜索线索/任务/案件")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_archive = sub.add_parser("archive-case", help="归档案件（灰调显示，不删除）")
    p_archive.add_argument("case_id")
    p_archive.set_defaults(func=cmd_archive_case)

    p_stale = sub.add_parser("stale", help="查找超过 N 天未更新的活跃任务")
    p_stale.add_argument("--days", type=int, default=3)
    p_stale.set_defaults(func=cmd_stale)

    p_ver = sub.add_parser("version", help="查看线索板系统版本与更新记录")
    p_ver.set_defaults(func=cmd_version)

    p_backup = sub.add_parser("backup", help="备份 board-state.json")
    p_backup.set_defaults(func=cmd_backup)

    p_val = sub.add_parser("validate", help="校验数据完整性")
    p_val.set_defaults(func=cmd_validate)

    p_due = sub.add_parser("due", help="查看未来 N 天到期的任务")
    p_due.add_argument("--days", type=int, default=7)
    p_due.set_defaults(func=cmd_due)

    p_note = sub.add_parser("note", help="给任务追加进度备注")
    p_note.add_argument("task_id")
    p_note.add_argument("note")
    p_note.set_defaults(func=cmd_task_note)

    p_today = sub.add_parser("today", help="查看今日变更汇总")
    p_today.set_defaults(func=cmd_today)

    p_stats = sub.add_parser("stats", help="全局统计面板")
    p_stats.set_defaults(func=cmd_stats)

    p_doms = sub.add_parser("domains", help="列出所有领域及其简介")
    p_doms.set_defaults(func=cmd_domains)

    p_cases = sub.add_parser("cases", help="列出指定领域下的所有案件")
    p_cases.add_argument("domain_id")
    p_cases.set_defaults(func=cmd_cases)

    p_items = sub.add_parser("items", help="列出指定案件下的所有线索和任务")
    p_items.add_argument("case_id")
    p_items.set_defaults(func=cmd_items)

    p_tasks = sub.add_parser("tasks", help="按状态/领域/优先级过滤任务列表")
    p_tasks.add_argument("--status", choices=["todo", "doing", "blocked", "waiting", "done", "archived"], default=None)
    p_tasks.add_argument("--domain", default=None)
    p_tasks.add_argument("--priority", choices=["critical", "high", "medium", "low"], default=None)
    p_tasks.set_defaults(func=cmd_tasks)

    p_clues = sub.add_parser("clues", help="按置信度/领域/优先级过滤线索列表")
    p_clues.add_argument("--confidence", choices=["high", "medium", "low"], default=None)
    p_clues.add_argument("--domain", default=None)
    p_clues.add_argument("--priority", choices=["critical", "high", "medium", "low"], default=None)
    p_clues.set_defaults(func=cmd_clues)

    p_r = sub.add_parser("render", help="渲染线索板")
    p_r.add_argument("--format", choices=["md", "html"], default="md")
    p_r.add_argument("--output", default=None)
    p_r.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    if not hasattr(args, 'func'):
        cmd_help(args)
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
