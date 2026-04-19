from tools.sie_autoppt.quality.ruff_incremental import RuffEntry, aggregate_diagnostics, compare_entries


def test_aggregate_diagnostics_groups_by_path_and_code():
    diagnostics = [
        {"filename": "tools/a.py", "code": "E501"},
        {"filename": "tools/a.py", "code": "E501"},
        {"filename": "tools/a.py", "code": "I001"},
        {"filename": "tools/b.py", "code": "E501"},
    ]

    entries = aggregate_diagnostics(diagnostics)

    assert entries == [
        RuffEntry(path="tools/a.py", code="E501", count=2),
        RuffEntry(path="tools/a.py", code="I001", count=1),
        RuffEntry(path="tools/b.py", code="E501", count=1),
    ]


def test_compare_entries_allows_reduced_or_equal_counts():
    baseline = [
        RuffEntry(path="tools/a.py", code="E501", count=3),
        RuffEntry(path="tools/a.py", code="I001", count=1),
    ]
    current = [
        RuffEntry(path="tools/a.py", code="E501", count=2),
        RuffEntry(path="tools/a.py", code="I001", count=1),
    ]

    assert compare_entries(current, baseline) == []


def test_compare_entries_blocks_new_or_increased_counts():
    baseline = [RuffEntry(path="tools/a.py", code="E501", count=1)]
    current = [
        RuffEntry(path="tools/a.py", code="E501", count=2),
        RuffEntry(path="tools/new.py", code="I001", count=1),
    ]

    regressions = compare_entries(current, baseline)

    assert len(regressions) == 2
    assert "tools/a.py [E501] increased from 1 to 2" in regressions
    assert "tools/new.py [I001] increased from 0 to 1" in regressions
