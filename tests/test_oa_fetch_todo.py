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
