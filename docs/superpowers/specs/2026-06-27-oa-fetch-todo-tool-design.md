# OA Fetch Todo Tool — 设计稿

**日期**: 2026-06-27
**作者**: 黄锦瑜（via GenericAgent brainstorming）
**状态**: 设计已批准 → 待 writing-plans

---

## 1. 目标

让 GenericAgent 主循环里多一个新工具 `oa_fetch_todo`，agent 可以一句话调起"扫 OA 待办 → 定位 IT系统账号管理 分类 → 抓新增邮箱申请明细"，**支持丰富过滤**，**自动写双份报告（JSON + TXT）**。

核心动因：现有 `oa_email_apply_skill.extract_new_email_applications()` 能力完整，但只在 Python 脚本里调，agent 主循环调不到。本设计把它**包装成可被 LLM 选择的 tool**，与 `do_code_run` / `do_file_read` / `do_web_scan` 同级。

---

## 2. 范围

**In scope**:
- `ga.py` 新增 `do_oa_fetch_todo()` 方法
- `assets/tools_schema.json` 新增 `oa_fetch_todo` 工具定义
- `assets/sys_prompt.txt` 工具列表加 1 行
- `memory/oa_fetch_skill.md` 新增 SOP（参数语义 + 报告位置 + 关键坑）
- `tests/test_oa_fetch_todo.py` 新增单测（mock 路径，CI 友好）

**Out of scope**:
- 不修改 `oa_email_apply_skill.py`（避免影响 `e2e_new_email.py`）
- 不重写 CDP 拉数逻辑
- 不做并发 / 限流
- 不做"全公司所有 IT 流程"通用化（只做"IT系统账号管理 → 新增邮箱"这一支）

---

## 3. 设计

### 3.1 Tool 签名

**LLM-facing schema** (`assets/tools_schema.json`):

```json
{
  "name": "oa_fetch_todo",
  "description": "获取OA待办中 IT系统账号管理 分类下的新增邮箱申请明细。支持按发起人/公司/部门/异常过滤，返回结构化数据 + 写报告文件(JSON+TXT)。前置：Chrome 启动 --remote-debugging-port=9222，已在OA listDoing页登录。",
  "parameters": {
    "type": "object",
    "properties": {
      "limit":         {"type":"integer", "default":20,  "description":"最多抓取条数"},
      "initiator":     {"type":"string",  "default":"",  "description":"发起人过滤(子串)"},
      "company":       {"type":"string",  "default":"",  "description":"公司过滤(子串)"},
      "dept":          {"type":"string",  "default":"",  "description":"部门过滤(子串)"},
      "email_required":{"type":"boolean", "default":true, "description":"仅保留邮箱勾选"},
      "anomalies_only":{"type":"boolean", "default":false,"description":"仅保留异常行"},
      "report_dir":    {"type":"string",  "default":"./", "description":"报告目录(相对 cwd)"},
      "cdp_url":       {"type":"string",  "default":"http://localhost:9222","description":"Chrome DevTools 端点"}
    }
  }
}
```

### 3.2 Python 实现（`ga.py` 内的 `do_oa_fetch_todo`）

> **注意**: `oa_email_apply_skill.py` 位于 `memory/`，而 `ga.py` 当前 sys.path 不含 `memory/`。需在 `do_oa_fetch_todo` 内 import 前临时注入，或在 `ga.py` 顶部加 `sys.path.append(os.path.join(script_dir, 'memory'))`（推荐前者，避免改动全局 sys.path）。

```python
def do_oa_fetch_todo(self, args, response):
    """获取OA待办中 IT系统账号管理 分类下的新增邮箱申请明细 ..."""
    import time as _t, sys as _sys
    # 临时把 memory/ 加进 sys.path, 使 oa_email_apply_skill 可被 import
    _mem_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory')
    if _mem_dir not in _sys.path:
        _sys.path.insert(0, _mem_dir)
    limit          = int(args.get('limit', 20))
    initiator      = (args.get('initiator') or '').strip()
    company        = (args.get('company') or '').strip()
    dept           = (args.get('dept') or '').strip()
    email_required = bool(args.get('email_required', True))
    anomalies_only = bool(args.get('anomalies_only', False))
    report_dir     = self._get_abs_path(args.get('report_dir', './'))
    cdp_url        = args.get('cdp_url', 'http://localhost:9222')
    os.makedirs(report_dir, exist_ok=True)
    t0 = _t.time()

    # 1. 调现有 skill(不写报告, 自己控制)
    try:
        from oa_email_apply_skill import extract_new_email_applications
        raw, _ = extract_new_email_applications(limit=limit, report=False, cdp_url=cdp_url)
    except ImportError:
        err = "oa_email_apply_skill 未找到,请确认 memory/ 已在 sys.path"
        yield f"[Error] {err}\n"
        return StepOutcome({'err': err}, next_prompt="\n")
    except Exception as e:
        err = f"OA 抓取失败: {e}"
        yield f"[Error] {err}\n"
        return StepOutcome({'err': err, 'hint': '检查 Chrome CDP / OA 登录态 / listDoing 页'},
                            next_prompt="\n")

    # 2. Python 端后置过滤
    items = []
    for r in raw:
        if initiator and initiator not in (r.get('发起申请人') or ''): continue
        if company   and company   not in (r.get('公司') or ''):       continue
        if dept      and dept      not in (r.get('部门') or ''):       continue
        if email_required and not r.get('邮箱勾选'):                   continue
        if anomalies_only and not r.get('异常'):                       continue
        items.append(r)

    # 3. 双份报告
    ts = _t.strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(report_dir, f'oa_fetch_{ts}.json')
    txt_path  = os.path.join(report_dir, f'oa_fetch_{ts}.txt')
    payload = {
        'fetched_at':     ts,
        'raw_count':      len(raw),
        'filtered_count': len(items),
        'filters_applied': {
            'limit': limit, 'initiator': initiator, 'company': company,
            'dept': dept, 'email_required': email_required,
            'anomalies_only': anomalies_only,
        },
        'items': items,
    }
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# OA 待办 新增邮箱申请 ({ts})\n")
            f.write(f"原始 {len(raw)} 条 → 过滤后 {len(items)} 条\n")
            f.write(f"过滤: {payload['filters_applied']}\n\n")
            f.write("| RequestID | 发起人 | 被申请人 | 工号 | 电话 | 公司 | 部门 | 邮箱 | 异常 |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            for r in items:
                f.write(f"| {r.get('requestid','')} | {r.get('发起申请人','')} | {r.get('被申请人姓名','')} "
                        f"| {r.get('工号','')} | {r.get('移动电话','')} | {r.get('公司','')} "
                        f"| {r.get('部门','')} | {'✅' if r.get('邮箱勾选') else '❌'} "
                        f"| {r.get('异常','')} |\n")
            anomalies = [r for r in items if r.get('异常')]
            if anomalies:
                f.write(f"\n## 异常清单\n")
                for r in anomalies:
                    f.write(f"- {r.get('被申请人姓名')}({r.get('requestid')}): {r.get('异常')}\n")
    except OSError as e:
        yield f"[Warn] 报告写入失败: {e}, 但内存 items 仍可用\n"
        json_path = txt_path = None

    elapsed = round(_t.time() - t0, 1)
    yield f"[Info] 抓到 {len(raw)} 条, 过滤后 {len(items)} 条, 报告 → {json_path}\n"
    return StepOutcome({
        'count': len(items),
        'items': items,
        'json_path': json_path,
        'txt_path': txt_path,
        'filters_applied': payload['filters_applied'],
        'elapsed_sec': elapsed,
    }, next_prompt=self._get_anchor_prompt(skip=args.get('_index', 0) > 0))
```

### 3.3 数据流

```
[Agent 主循环]
  └─ args = {limit:20, initiator:"管紫妍", email_required:True, ...}
     │
     ▼
[do_oa_fetch_todo]
     │
     │ (1) 参数校验 + 路径解析
     │ (2) extract_new_email_applications(limit, report=False)
     │ (3) Python 端过滤
     │ (4) 写双份报告
     │ (5) yield 进度 + return StepOutcome
     │
     └─ 主循环把 dict 作为 tool_result 注入 LLM
```

### 3.4 错误处理

| 错误场景 | 行为 | 消息 |
|---|---|---|
| `oa_email_apply_skill` 不可导入 | 抛出 + 友好错误 | "oa_email_apply_skill 未找到,请确认 memory/ 已在 sys.path" |
| CDP 不可达 | 抛出 + 提示 | "OA 抓取失败: ..., 提示: 检查 Chrome CDP / OA 登录态 / listDoing 页" |
| 过滤后 0 条 | 正常返回 | "抓到 N 条, 过滤后 0 条" (不强报错) |
| 写报告 IO 失败 | 不阻塞, warn | "报告写入失败, 但内存 items 仍可用" |
| 部分详情 tab 拉失败 | 保留行 + `异常`字段标记 | (沿用 skill 既有行为) |

### 3.5 测试

**单测 (`tests/test_oa_fetch_todo.py`, 不依赖 Chrome)**:
> 项目当前无 `tests/` 目录, 本次实现时新建。
- 准备 mock 数据：8 条已抓好的 list（包含马玉成等真实数据）
- 通过 monkey-patch 替换 `extract_new_email_applications` 为 mock 版本
- 测过滤逻辑（每个参数组合）
- 测报告生成（JSON 完整 + TXT 表格行数）
- 测边界：raw 空、过滤后 0 条

**集成测（手动）**:
- Chrome + OA 已登录 + listDoing 打开
- 跑一次完整流程
- 验证报告文件 + dict 返回

**Dry-run 兜底**:
- `OA_DRY_RUN=1` 环境变量 → 用 mock 数据代替 CDP 调用（CI/无 Chrome 环境友好）
- mock 数据从 `tests/fixtures/oa_fetch_mock.json` 读

---

## 4. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 包装 vs 重构 | **包装** | 不破坏 `e2e_new_email.py` 现有调用方 |
| 过滤位置 | **wrapper 后置** | 简单、快、不重跑 CDP |
| 报告格式 | **JSON + TXT 双份** | JSON 给 agent / 程序用，TXT 给人看 |
| Skill 是否改 | **不改** | 减少回归风险 |
| Tool 名 | **`oa_fetch_todo`** | 沿用现有动词-名词风格 (file_read / web_scan / code_run) |
| 默认 limit | **20** | 平衡"覆盖全"和"CDP 流量"；当前 8 条待办够用 |
| 默认 email_required | **True** | 本工具主要服务于"邮箱申请"任务 |
| 报告路径 | **相对 cwd** (GenericAgentHandler.cwd) | 与现有 `do_file_read` 行为一致 |

---

## 5. 不在本次范围

- 不实现"通用 OA 流程抓取"（只做 IT系统账号管理 → 新增邮箱）
- 不做并发 / 限流
- 不做 OA 后台"创建邮箱"动作（那是另一个 tool: `oa_create_email_account`，留给后续）
- 不做"已办/已审批"扫描（只做待办）

---

## 6. 风险

| 风险 | 缓解 |
|---|---|
| `oa_email_apply_skill` 路径不在 sys.path | wrapper 内 import; 失败给清晰错误 |
| CDP 偶发抖动 | skill 已有 time.sleep 缓冲; 失败不阻塞 |
| mock 数据与真实数据漂移 | 单测覆盖关键字段; 集成测验证 |
| agent 误把"邮箱未勾选"当成"无邮箱申请" | `email_required` 默认 True 已暗示; 异常字段保留 |
| Chrome 端口被其他实例占用 | `cdp_url` 可参数化; 默认 9222 与现有 SOP 一致 |

---

## 7. 验收

- [ ] 工具 `oa_fetch_todo` 出现在 `assets/tools_schema.json`
- [ ] LLM 能正确调起（用一个简单 prompt 验证）
- [ ] 报告文件 `oa_fetch_*.json` + `oa_fetch_*.txt` 在指定目录生成
- [ ] 8 条真实待办场景下, 各项过滤组合返回正确条数
- [ ] 现有 `oa_email_apply_skill.extract_new_email_applications` 调用方 (`e2e_new_email.py`) 不受影响
- [ ] 单测 100% 通过
