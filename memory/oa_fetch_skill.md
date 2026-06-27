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
# 15 个测试, 全过
```

## 典型调用示例
```python
# agent 调 (LLM 自主选择 args)
oa_fetch_todo(initiator="管紫妍")               # 5 条
oa_fetch_todo(dept="制造部", anomalies_only=True) # 工号/电话异常的制造部
oa_fetch_todo(company="泰州", report_dir="./reports")  # 写报告到指定目录
```
