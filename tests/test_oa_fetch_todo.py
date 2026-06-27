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


def test_filter_email_required_true_keeps_all(mock_items):
    """email_required=True (default) keeps all 8 items since all mock items have 邮箱勾选=True."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, email_required=True)
    assert len(out) == 8


def test_filter_email_required_false_matches_all(mock_items):
    """email_required=False matches all items regardless of 邮箱勾选 field."""
    from ga import _filter_oa_items
    out = _filter_oa_items(mock_items, email_required=False)
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
