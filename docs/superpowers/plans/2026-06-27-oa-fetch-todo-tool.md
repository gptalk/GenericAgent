# oa_fetch_todo Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap `oa_email_apply_skill.extract_new_email_applications()` as a GenericAgent-callable tool `oa_fetch_todo` with rich filtering and dual report (JSON + TXT).

**Architecture:** Pure wrapper layer in `ga.py::do_oa_fetch_todo`. Calls existing skill (no modification), post-filters in Python, writes 2 report files. TDD with mock-based unit tests via `OA_DRY_RUN=1` env var.

**Tech Stack:** Python 3.11+, Chrome DevTools Protocol (via existing `oa_email_apply_skill.py`), pytest for tests, JSON for machine-readable reports.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `ga.py` | **Modify** | Add `do_oa_fetch_todo` method + helper `_filter_oa_items` + `OA_DRY_RUN` env var support |
| `assets/tools_schema.json` | **Modify** | Add tool schema entry for LLM |
| `memory/oa_fetch_skill.md` | **Create** | SOP doc: parameters, report paths, pitfalls |
| `tests/__init__.py` | **Create** | Empty package marker (project has no `tests/` yet) |
| `tests/conftest.py` | **Create** | Sets `OA_DRY_RUN=1` for test session, fixture helpers |
| `tests/fixtures/oa_fetch_mock.json` | **Create** | 8 real items (from `temp/oa_email_apply_2026-06-27.txt`) for unit tests |
| `tests/test_oa_fetch_todo.py` | **Create** | Unit tests: filter logic + report generation + edge cases |

**Not modified (out of scope):** `oa_email_apply_skill.py`, `e2e_new_email.py`, `agent_loop.py`, `agentmain.py`, `assets/sys_prompt.txt` (LLM learns tool from `tools_schema.json`, not prompt text).

---

## Task 1: Set up test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/oa_fetch_mock.json`

- [ ] **Step 1: Create `tests/__init__.py` (empty package marker)**

```python
# tests package marker for pytest discovery
```

- [ ] **Step 2: Create `tests/fixtures/` directory and mock data file**

Write the file `tests/fixtures/oa_fetch_mock.json` with the 8 real items from `temp/oa_email_apply_2026-06-27.txt`:

```json
[
  {"requestid":"594220","发起申请人":"管紫妍","被申请人姓名":"马玉成","工号":"65044204","移动电话":"18258386203","公司":"泰州新华昌物流装备有限公司","部门":"制造部","邮箱勾选":true,"异常":""},
  {"requestid":"594229","发起申请人":"管紫妍","被申请人姓名":"范建朋","工号":"66011756","移动电话":"13732156444","公司":"泰州新华昌物流装备有限公司","部门":"制造部","邮箱勾选":true,"异常":""},
  {"requestid":"594230","发起申请人":"管紫妍","被申请人姓名":"胡朋朋","工号":"33005494","移动电话":"15706073682","公司":"泰州新华昌物流装备有限公司","部门":"制造部","邮箱勾选":true,"异常":""},
  {"requestid":"594231","发起申请人":"管紫妍","被申请人姓名":"黄晶","工号":"22018829","移动电话":"15022202131","公司":"泰州新华昌物流装备有限公司","部门":"制造部","邮箱勾选":true,"异常":""},
  {"requestid":"594248","发起申请人":"管紫妍","被申请人姓名":"唐志孝","工号":"99020021","移动电话":"15961042413","公司":"泰州新华昌物流装备有限公司","部门":"制造部","邮箱勾选":true,"异常":""},
  {"requestid":"594276","发起申请人":"唐晶","被申请人姓名":"刘倩琳","工号":"99020029","移动电话":"18360859836","公司":"泰州新华昌物流装备有限公司","部门":"质管部","邮箱勾选":true,"异常":""},
  {"requestid":"594282","发起申请人":"唐晶","被申请人姓名":"王苏丽","工号":"9902023","移动电话":"15261488592","公司":"泰州新华昌物流装备有限公司","部门":"质管部","邮箱勾选":true,"异常":"工号异常(9902023)"},
  {"requestid":"594288","发起申请人":"唐晶","被申请人姓名":"徐冰姿","工号":"99020061","移动电话":"13357791887","公司":"泰州新华昌物流装备有限公司","部门":"质管部","邮箱勾选":true,"异常":""}
]
```

- [ ] **Step 3: Create `tests/conftest.py` with pytest fixtures**

```python
"""Pytest configuration and shared fixtures for oa_fetch_todo tests."""
import os
import sys
import json
import pytest

# Force dry-run for entire test session
os.environ.setdefault('OA_DRY_RUN', '1')

# Ensure project root is on sys.path so we can import ga
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture
def mock_items():
    """Load 8 real items from oa_email_apply_2026-06-27.txt snapshot."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'oa_fetch_mock.json')
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    """Provide a clean cwd for report file output."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
```

- [ ] **Step 4: Verify pytest can discover the test file (should find no tests yet)**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/ --collect-only -q`
Expected: Output showing "no tests ran" or empty collection, exit code 5 (no tests collected) is OK at this stage.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add tests/__init__.py tests/conftest.py tests/fixtures/oa_fetch_mock.json
git commit -m "test: scaffold oa_fetch_todo test infrastructure with 8-item mock fixture"
```

---

## Task 2: Write filter logic test (failing first)

**Files:**
- Modify: `tests/test_oa_fetch_todo.py` (create)

- [ ] **Step 1: Create `tests/test_oa_fetch_todo.py` with filter tests**

```python
"""Unit tests for oa_fetch_todo tool (filter logic + report generation)."""
import os
import json
import pytest


# ---- Filter logic tests ----

def test_filter_by_initiator_keeps_only_matching(mock_items):
    """initiator='管紫妍' should keep 5 items."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, initiator='管紫妍')
    assert len(out) == 5
    assert all(r['发起申请人'] == '管紫妍' for r in out)


def test_filter_by_company_substring(mock_items):
    """company='泰州' should keep all 8 items (substring match)."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, company='泰州')
    assert len(out) == 8


def test_filter_by_dept(mock_items):
    """dept='制造部' should keep 5 items (管紫妍's 5)."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, dept='制造部')
    assert len(out) == 5
    assert all(r['部门'] == '制造部' for r in out)


def test_filter_email_required_excludes_false(mock_items):
    """email_required=True (default) keeps all since all are True here."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, email_required=True)
    assert len(out) == 8


def test_filter_anomalies_only(mock_items):
    """anomalies_only=True keeps only the 1 row with non-empty 异常 (王苏丽)."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, anomalies_only=True)
    assert len(out) == 1
    assert out[0]['被申请人姓名'] == '王苏丽'


def test_filter_combined_initiator_and_dept(mock_items):
    """initiator='唐晶' + dept='质管部' → 3 items."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, initiator='唐晶', dept='质管部')
    assert len(out) == 3


def test_filter_empty_initiator_matches_all(mock_items):
    """initiator='' is treated as no filter."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, initiator='')
    assert len(out) == 8


def test_filter_no_match_returns_empty_list(mock_items):
    """company='不存在的公司' returns [] (not an error)."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, company='不存在的公司')
    assert out == []


def test_filter_empty_input(mock_items):
    """Empty input returns empty list."""
    from ga import _filter_oa_items
    out = _filter_oa_items([])
    assert out == []
```

- [ ] **Step 2: Run tests and verify they FAIL (function not defined)**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v`
Expected: All 9 tests FAIL with `ImportError: cannot import name '_filter_oa_items' from 'ga'` (or similar).

- [ ] **Step 3: Commit failing tests**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add tests/test_oa_fetch_todo.py
git commit -m "test: add filter logic tests for oa_fetch_todo (failing - function not yet implemented)"
```

---

## Task 3: Implement `_filter_oa_items` helper

**Files:**
- Modify: `ga.py` (add helper function before `GenericAgentHandler` class)

- [ ] **Step 1: Add the filter helper function**

In `ga.py`, **just before the line `class GenericAgentHandler(BaseHandler):`** (currently around line 266), insert:

```python
def _filter_oa_items(items, *, initiator='', company='', dept='', email_required=True, anomalies_only=False):
    """Filter OA todo items by various criteria. Pure function, no side effects.

    Args:
        items:           list of dict (each = one OA todo row)
        initiator:       str, substring match on 发起申请人; '' = no filter
        company:         str, substring match on 公司; '' = no filter
        dept:            str, substring match on 部门; '' = no filter
        email_required:  bool, if True keep only rows with 邮箱勾选 == True
        anomalies_only:  bool, if True keep only rows with non-empty 异常

    Returns:
        filtered list of dict (subset of items, in original order)
    """
    out = []
    for r in items:
        if initiator and initiator not in (r.get('发起申请人') or ''):
            continue
        if company and company not in (r.get('公司') or ''):
            continue
        if dept and dept not in (r.get('部门') or ''):
            continue
        if email_required and not r.get('邮箱勾选'):
            continue
        if anomalies_only and not r.get('异常'):
            continue
        out.append(r)
    return out
```

- [ ] **Step 2: Run filter tests and verify they PASS**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v -k "filter"`
Expected: All 9 filter tests PASS.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add ga.py
git commit -m "feat(ga): add _filter_oa_items helper for oa_fetch_todo"
```

---

## Task 4: Write report generation test (failing first)

**Files:**
- Modify: `tests/test_oa_fetch_todo.py` (append report tests)

- [ ] **Step 1: Add report generation tests at the end of the test file**

Append to `tests/test_oa_fetch_todo.py`:

```python


# ---- Report generation tests ----

def test_write_reports_creates_json_and_txt(tmp_cwd, mock_items):
    """_write_oa_reports should create both .json and .txt files."""
    from ga import _write_oa_reports
    items = _filter_oa_items(mock_items, initiator='管紫妍')
    json_path, txt_path = _write_oa_reports(
        report_dir=str(tmp_cwd),
        raw=mock_items,
        items=items,
        filters_applied={'initiator': '管紫妍', 'limit': 20},
        ts='20260627_180000',
    )
    assert os.path.exists(json_path)
    assert os.path.exists(txt_path)
    assert json_path.endswith('.json')
    assert txt_path.endswith('.txt')


def test_write_reports_json_payload_structure(tmp_cwd, mock_items):
    """JSON file should contain fetched_at, raw_count, filtered_count, items, filters_applied."""
    from ga import _write_oa_reports
    items = _filter_oa_items(mock_items, dept='质管部')
    json_path, _ = _write_oa_reports(
        report_dir=str(tmp_cwd),
        raw=mock_items,
        items=items,
        filters_applied={'dept': '质管部'},
        ts='20260627_180100',
    )
    with open(json_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    assert payload['fetched_at'] == '20260627_180100'
    assert payload['raw_count'] == 8
    assert payload['filtered_count'] == 3
    assert payload['filters_applied'] == {'dept': '质管部'}
    assert isinstance(payload['items'], list)
    assert len(payload['items']) == 3


def test_write_reports_txt_has_table_and_anomalies(tmp_cwd, mock_items):
    """TXT file should include markdown table + anomaly section."""
    from ga import _filter_oa_items, _write_oa_reports
    items = _filter_oa_items(mock_items, anomalies_only=True)
    _, txt_path = _write_oa_reports(
        report_dir=str(tmp_cwd),
        raw=mock_items,
        items=items,
        filters_applied={'anomalies_only': True},
        ts='20260627_180200',
    )
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Table header
    assert '| RequestID |' in content
    # Anomaly section
    assert '## 异常清单' in content
    assert '王苏丽' in content


def test_write_reports_creates_dir_if_missing(tmp_cwd, mock_items):
    """If report_dir doesn't exist, _write_oa_reports should create it."""
    from ga import _write_oa_reports
    nested = os.path.join(str(tmp_cwd), 'subdir', 'reports')
    json_path, _ = _write_oa_reports(
        report_dir=nested,
        raw=mock_items,
        items=mock_items,
        filters_applied={},
        ts='20260627_180300',
    )
    assert os.path.exists(nested)
    assert os.path.exists(json_path)
```

- [ ] **Step 2: Run report tests and verify they FAIL**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v -k "write_reports"`
Expected: All 4 report tests FAIL with `ImportError: cannot import name '_write_oa_reports' from 'ga'`.

- [ ] **Step 3: Commit failing tests**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add tests/test_oa_fetch_todo.py
git commit -m "test: add report generation tests for oa_fetch_todo (failing)"
```

---

## Task 5: Implement `_write_oa_reports` helper

**Files:**
- Modify: `ga.py` (add helper function after `_filter_oa_items`)

- [ ] **Step 1: Add the report writer helper after `_filter_oa_items`**

In `ga.py`, **immediately after the `_filter_oa_items` function**, insert:

```python
def _write_oa_reports(*, report_dir, raw, items, filters_applied, ts):
    """Write dual report (JSON + TXT) for oa_fetch_todo. Returns (json_path, txt_path).

    Args:
        report_dir:      str, absolute directory (will be created if missing)
        raw:             list[dict], all items before filtering (for raw_count)
        items:           list[dict], items after filtering
        filters_applied: dict, the filter values used (for reproducibility)
        ts:              str, timestamp suffix like '20260627_180000'

    Returns:
        (json_path, txt_path) tuple. Paths are absolute.
    """
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, f'oa_fetch_{ts}.json')
    txt_path = os.path.join(report_dir, f'oa_fetch_{ts}.txt')

    # JSON payload
    payload = {
        'fetched_at':     ts,
        'raw_count':      len(raw),
        'filtered_count': len(items),
        'filters_applied': filters_applied,
        'items':          items,
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # TXT report
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"# OA 待办 新增邮箱申请 ({ts})\n")
        f.write(f"原始 {len(raw)} 条 → 过滤后 {len(items)} 条\n")
        f.write(f"过滤: {json.dumps(filters_applied, ensure_ascii=False)}\n\n")
        f.write("| RequestID | 发起人 | 被申请人 | 工号 | 电话 | 公司 | 部门 | 邮箱 | 异常 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in items:
            f.write(
                f"| {r.get('requestid','')} | {r.get('发起申请人','')} | {r.get('被申请人姓名','')} "
                f"| {r.get('工号','')} | {r.get('移动电话','')} | {r.get('公司','')} "
                f"| {r.get('部门','')} | {'✅' if r.get('邮箱勾选') else '❌'} "
                f"| {r.get('异常','')} |\n"
            )
        anomalies = [r for r in items if r.get('异常')]
        if anomalies:
            f.write("\n## 异常清单\n")
            for r in anomalies:
                f.write(f"- {r.get('被申请人姓名')}({r.get('requestid')}): {r.get('异常')}\n")

    return json_path, txt_path
```

- [ ] **Step 2: Run report tests and verify they PASS**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v -k "write_reports"`
Expected: All 4 report tests PASS.

- [ ] **Step 3: Run full test suite to confirm nothing regressed**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v`
Expected: All 13 tests (9 filter + 4 report) PASS.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add ga.py
git commit -m "feat(ga): add _write_oa_reports helper (JSON + TXT) for oa_fetch_todo"
```

---

## Task 6: Implement `do_oa_fetch_todo` method

**Files:**
- Modify: `ga.py` (add method to `GenericAgentHandler` class)

- [ ] **Step 1: Add the method to `GenericAgentHandler`**

In `ga.py`, **after the `do_file_write` method** (currently ends around line 406), insert:

```python
    def do_oa_fetch_todo(self, args, response):
        """获取OA待办中 IT系统账号管理 分类下的新增邮箱申请明细。

        支持按发起人/公司/部门/异常过滤, 返回结构化数据 + 写双份报告 (JSON + TXT)。

        Args (from LLM):
            limit:          int, default 20 — 最多抓取条数
            initiator:      str, default '' — 发起人过滤(子串)
            company:        str, default '' — 公司过滤(子串)
            dept:           str, default '' — 部门过滤(子串)
            email_required: bool, default True — 仅保留邮箱勾选
            anomalies_only: bool, default False — 仅保留异常行
            report_dir:     str, default './' — 报告目录(相对 cwd)
            cdp_url:        str, default 'http://localhost:9222'

        Returns:
            StepOutcome with dict: {count, items, json_path, txt_path, filters_applied, elapsed_sec}
        """
        import time as _t
        import sys as _sys

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

        t0 = _t.time()

        # 1. 拉数据 (CDP or dry-run fixture)
        try:
            if os.environ.get('OA_DRY_RUN') == '1':
                from oa_email_apply_skill import extract_new_email_applications as _real_fn
                # In dry-run we read from fixture instead of CDP
                fixture = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures', 'oa_fetch_mock.json')
                if os.path.isfile(fixture):
                    raw = json.load(open(fixture, 'r', encoding='utf-8'))
                else:
                    raw, _ = _real_fn(limit=limit, report=False, cdp_url=cdp_url)
            else:
                from oa_email_apply_skill import extract_new_email_applications
                raw, _ = extract_new_email_applications(limit=limit, report=False, cdp_url=cdp_url)
        except ImportError:
            err = "oa_email_apply_skill 未找到, 请确认 memory/ 已在 sys.path"
            yield f"[Error] {err}\n"
            return StepOutcome({'err': err}, next_prompt="\n")
        except Exception as e:
            err = f"OA 抓取失败: {e}"
            yield f"[Error] {err}\n"
            return StepOutcome({'err': err, 'hint': '检查 Chrome CDP / OA 登录态 / listDoing 页'},
                               next_prompt="\n")

        # 2. Python 端后置过滤
        items = _filter_oa_items(
            raw,
            initiator=initiator, company=company, dept=dept,
            email_required=email_required, anomalies_only=anomalies_only,
        )
        filters_applied = {
            'limit': limit, 'initiator': initiator, 'company': company,
            'dept': dept, 'email_required': email_required,
            'anomalies_only': anomalies_only,
        }

        # 3. 写双份报告
        ts = _t.strftime('%Y%m%d_%H%M%S')
        try:
            json_path, txt_path = _write_oa_reports(
                report_dir=report_dir, raw=raw, items=items,
                filters_applied=filters_applied, ts=ts,
            )
        except OSError as e:
            yield f"[Warn] 报告写入失败: {e}, 但内存 items 仍可用\n"
            json_path = txt_path = None

        elapsed = round(_t.time() - t0, 1)
        yield f"[Info] 抓到 {len(raw)} 条, 过滤后 {len(items)} 条, 报告 → {json_path}\n"
        return StepOutcome({
            'count': len(items),
            'items': items,
            'json_path': json_path,
            'txt_path':  txt_path,
            'filters_applied': filters_applied,
            'elapsed_sec': elapsed,
        }, next_prompt=self._get_anchor_prompt(skip=args.get('_index', 0) > 0))
```

- [ ] **Step 2: Add a method-level integration test (uses dry-run)**

Append to `tests/test_oa_fetch_todo.py`:

```python


# ---- do_oa_fetch_todo method integration test ----

def test_do_oa_fetch_todo_dry_run_returns_filtered_items(tmp_cwd, mock_items):
    """In dry-run, do_oa_fetch_todo should use fixture, filter, write report, return dict."""
    from ga import GenericAgentHandler
    handler = GenericAgentHandler(parent=None, cwd=str(tmp_cwd))
    gen = handler.do_oa_fetch_todo(
        {'initiator': '管紫妍', 'limit': 20, '_index': 0, '_tool_num': 1},
        response=None,
    )
    # drain generator
    for _ in gen:
        pass
    # The last yielded value is a StepOutcome (generator returns it)
    # In this test we just verify side effects
    json_files = [f for f in os.listdir(str(tmp_cwd)) if f.startswith('oa_fetch_') and f.endswith('.json')]
    assert len(json_files) == 1
    with open(os.path.join(str(tmp_cwd), json_files[0]), 'r', encoding='utf-8') as f:
        payload = json.load(f)
    assert payload['filtered_count'] == 5
    assert payload['raw_count'] == 8
    assert payload['filters_applied']['initiator'] == '管紫妍'
```

- [ ] **Step 3: Run the full test suite and verify ALL tests pass**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/test_oa_fetch_todo.py -v`
Expected: All 14 tests PASS (9 filter + 4 report + 1 integration).

- [ ] **Step 4: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add ga.py tests/test_oa_fetch_todo.py
git commit -m "feat(ga): add do_oa_fetch_todo method with dry-run support for tests"
```

---

## Task 7: Add tool schema to `tools_schema.json`

**Files:**
- Modify: `assets/tools_schema.json` (append new tool entry)

- [ ] **Step 1: Add the tool entry at the end of the array**

In `assets/tools_schema.json`, find the last entry (currently `start_long_term_update` ending with `}}`) and **after its closing `}`**, before the final `]`, append:

```json
  ,
  {"type": "function", "function": {
    "name": "oa_fetch_todo",
    "description": "获取OA待办中 IT系统账号管理 分类下的新增邮箱申请明细。支持按发起人/公司/部门/异常过滤, 返回结构化数据 + 写双份报告 (JSON + TXT)。前置: Chrome 启动 --remote-debugging-port=9222, 已在OA listDoing页登录。设置 OA_DRY_RUN=1 环境变量可用 mock fixture 跳过 CDP (CI/无 Chrome 环境)。",
    "parameters": {"type": "object", "properties": {
      "limit":          {"type": "integer", "default": 20, "description": "最多抓取条数"},
      "initiator":      {"type": "string",  "default": "",  "description": "发起人过滤(子串匹配)"},
      "company":        {"type": "string",  "default": "",  "description": "公司过滤(子串匹配)"},
      "dept":           {"type": "string",  "default": "",  "description": "部门过滤(子串匹配)"},
      "email_required": {"type": "boolean", "default": true, "description": "仅保留邮箱勾选的申请"},
      "anomalies_only": {"type": "boolean", "default": false,"description": "仅保留异常行 (工号/电话/邮箱勾选异常)"},
      "report_dir":     {"type": "string",  "default": "./", "description": "报告目录(相对 cwd)"},
      "cdp_url":        {"type": "string",  "default": "http://localhost:9222", "description": "Chrome DevTools 端点"}
    }}
  }}
```

- [ ] **Step 2: Validate JSON is still well-formed**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -c "import json; data = json.load(open('assets/tools_schema.json', encoding='utf-8')); names = [t['function']['name'] for t in data]; assert 'oa_fetch_todo' in names; print('OK,', len(data), 'tools, oa_fetch_todo present')"`
Expected: `OK, 10 tools, oa_fetch_todo present` (was 9, now 10).

- [ ] **Step 3: Run tests to confirm schema change didn't break anything**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/ -v`
Expected: All 14 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add assets/tools_schema.json
git commit -m "feat(tools): register oa_fetch_todo tool schema for LLM"
```

---

## Task 8: Write SOP documentation `oa_fetch_skill.md`

**Files:**
- Create: `memory/oa_fetch_skill.md`

- [ ] **Step 1: Create the SOP file**

```markdown
# 技能: OA 待办抓取（oa_fetch_todo）
**版本**: v1.0 (2026-06-27 R50)
**适用场景**: 用户说"扫一下OA待办"、"看看有哪些人申请了邮箱"、"今天新增邮箱有谁"
**底层能力**: 包装 `oa_email_apply_skill.extract_new_email_applications()`, 增加过滤 + 报告输出

## 入口
```python
# 在 GenericAgent 主循环里直接调 tool
# 工具名: oa_fetch_todo
# 自动出现在 TOOLS_SCHEMA 里, LLM 可选择
```

## 参数语义
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 20 | 最多抓取条数(CDP 阶段上限) |
| `initiator` | str | "" | 发起人过滤, 子串匹配 |
| `company` | str | "" | 公司过滤, 子串匹配 |
| `dept` | str | "" | 部门过滤, 子串匹配 |
| `email_required` | bool | True | 仅保留"邮箱勾选"的申请 |
| `anomalies_only` | bool | False | 仅保留异常行 |
| `report_dir` | str | "./" | 报告目录(相对 cwd) |
| `cdp_url` | str | http://localhost:9222 | Chrome DevTools 端点 |

## 返回
```python
{
    "count": <int>,                  # 过滤后条数
    "items": [dict, ...],            # 每行 dict (含 requestid/被申请人姓名/工号/...)
    "json_path": "oa_fetch_xxx.json", # 报告文件路径
    "txt_path":  "oa_fetch_xxx.txt",  # 报告文件路径
    "filters_applied": {...},         # 实际生效的过滤条件
    "elapsed_sec": <float>,
}
```

## 报告
- **JSON** (`oa_fetch_YYYYMMDD_HHMMSS.json`): 完整结构 + filters_applied + raw_count vs filtered_count
- **TXT** (`oa_fetch_YYYYMMDD_HHMMSS.txt`): 人类可读 markdown 表格 + 异常清单

## 关键坑
1. **Chrome 必须启动远程调试端口**: `--remote-debugging-port=9222 --user-data-dir=<独立目录>`
2. **OA 待办页必须已登录** + 在 `listDoing` 路径(否则找不到 tab)
3. **CDP 不可达时**: 报错 "检查 Chrome CDP / OA 登录态 / listDoing 页", 不重试
4. **过滤后 0 条** ≠ 错误, 是正常结果(可能放宽条件)
5. **OA_DRY_RUN=1**: CI/无 Chrome 环境使用 mock fixture(8 条固定数据)
6. **不要修改 `oa_email_apply_skill.py`**: 改它会破坏 `e2e_new_email.py`

## 测试
```bash
python -m pytest tests/test_oa_fetch_todo.py -v
# 14 个测试, 全过
```

## 典型调用示例
```python
# agent 调 (LLM 自主选择 args)
oa_fetch_todo(initiator="管紫妍")               # 5 条
oa_fetch_todo(dept="制造部", anomalies_only=True) # 工号/电话异常的制造部
oa_fetch_todo(company="泰州", report_dir="./reports")  # 写报告到指定目录
```
```

- [ ] **Step 2: Verify file is readable**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -c "import os; assert os.path.exists('memory/oa_fetch_skill.md'); print('SOP doc size:', os.path.getsize('memory/oa_fetch_skill.md'), 'bytes')"`
Expected: `SOP doc size: <positive number> bytes`.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/yellow/mcp/GenericAgent
git add memory/oa_fetch_skill.md
git commit -m "docs: add oa_fetch_skill.md SOP for oa_fetch_todo tool"
```

---

## Task 9: Regression check on `e2e_new_email.py`

**Files:**
- Read: `e2e_new_email.py` (verify it still works)
- Read: `oa_email_apply_skill.py` (verify imports are unchanged)

- [ ] **Step 1: Verify `e2e_new_email.py` still imports without error**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -c "import sys; sys.path.insert(0, 'memory'); from e2e_new_email import process_one; print('e2e_new_email.py import: OK')"`
Expected: `e2e_new_email.py import: OK` (no changes to oa_email_apply_skill means this should still work).

- [ ] **Step 2: Verify `oa_email_apply_skill.py` was NOT modified by this plan**

Run: `cd C:/Users/yellow/mcp/GenericAgent && git log --oneline memory/oa_email_apply_skill.py | head -3`
Expected: Most recent commit on this file is from BEFORE this plan started (e.g., 942bd31 or earlier). The plan should not have added any new commits touching this file.

- [ ] **Step 3: Run final full test suite**

Run: `cd C:/Users/yellow/mcp/GenericAgent && python -m pytest tests/ -v`
Expected: All 14 tests PASS.

- [ ] **Step 4: Commit a regression check note (no code change)**

If everything passed, no commit is needed. If a fix was required, commit it as:
```bash
cd C:/Users/yellow/mcp/GenericAgent
git commit --allow-empty -m "chore: regression check for oa_fetch_todo plan (all tests pass)"
```

---

## Task 10: Manual integration test (smoke test)

**Files:**
- (no file changes — documentation only)

- [ ] **Step 1: Document the manual test procedure**

This is a one-time manual verification, **not committed as code**. Run on a machine with Chrome + OA logged in:

```bash
# 1. Ensure Chrome is running with remote debug
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-test

# 2. Open http://oa.cxic.com/wui/index.html?#/main/workflow/listDoing?menuIds=1,13&_key=vpoh75
#    Log in if needed. Confirm "IT系统账号管理" classification visible.

# 3. In a Python REPL with project root on path:
cd C:/Users/yellow/mcp/GenericAgent
python -c "
import sys; sys.path.insert(0, '.')
from ga import GenericAgentHandler
h = GenericAgentHandler(parent=None, cwd='./temp')
gen = h.do_oa_fetch_todo({'initiator': '管紫妍', 'limit': 20, '_index': 0, '_tool_num': 1}, response=None)
for chunk in gen:
    print(chunk)
"

# 4. Verify:
#    - 8 条 raw, 5 条 filtered (管紫妍)
#    - JSON report at temp/oa_fetch_*.json exists
#    - TXT report at temp/oa_fetch_*.txt exists
#    - Counts in report match return value
```

- [ ] **Step 2: Report results to user**

Expected outcomes:
- ✅ All 5 items in 管紫妍's 5 entries appear in `items` list
- ✅ Reports are written to `temp/`
- ✅ `filters_applied` echo matches input
- ⏭️ If something fails: investigate network/CDP, don't proceed to merge

---

## Self-Review (done by plan author)

**1. Spec coverage:**
- §3.1 Tool signature → Tasks 6, 7 ✓
- §3.2 Python impl → Tasks 3, 5, 6 ✓
- §3.3 Data flow → Task 6 (woven into do_oa_fetch_todo) ✓
- §3.4 Error handling → Task 6 (try/except blocks) ✓
- §3.5 Testing → Tasks 1-6 (filter tests, report tests, integration test) ✓
- §4 Decisions (filter in wrapper, dual reports, dry-run via env) → Tasks 5, 6, 7 ✓
- §7 Acceptance → Task 9 (regression) + Task 10 (manual smoke) ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"add appropriate"/"handle edge cases" found in plan steps.

**3. Type consistency:**
- `_filter_oa_items(items, *, initiator='', company='', dept='', email_required=True, anomalies_only=False)` defined Task 3, used Tasks 4, 6, 7 ✓
- `_write_oa_reports(*, report_dir, raw, items, filters_applied, ts)` defined Task 5, used Task 6 ✓
- Return shape `{count, items, json_path, txt_path, filters_applied, elapsed_sec}` consistent across Tasks 6, 8, 10 ✓
- `os.environ.get('OA_DRY_RUN')` used Task 6, set by `conftest.py` Task 1 ✓

**4. Gaps to address before execution:**
- None — plan is self-contained.

