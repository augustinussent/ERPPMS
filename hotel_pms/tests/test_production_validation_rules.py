from hotel_pms.production_validation_rules import (
    canonical_source_hash,
    source_fingerprint,
    classify_parallel_row,
    promotion_blockers,
    rehearsal_matches,
    summarize_parallel_rows,
)


def test_source_hash_is_order_independent_and_path_sensitive():
    a = canonical_source_hash([('b.py', b'2'), ('a.py', b'1')])
    b = canonical_source_hash([('a.py', b'1'), ('b.py', b'2')])
    c = canonical_source_hash([('x.py', b'1'), ('b.py', b'2')])
    assert a == b
    assert a != c


def test_parallel_classification_and_summary():
    passed, variance = classify_parallel_row(100, 100.5, 1)
    warning, _ = classify_parallel_row(100, 101.2, 1)
    failed, _ = classify_parallel_row(100, 102, 1)
    assert passed == 'Passed' and float(variance) == 0.5
    assert warning == 'Warning'
    assert failed == 'Failed'
    summary = summarize_parallel_rows([{'status': passed}, {'status': warning}, {'status': failed}])
    assert summary == {'total': 3, 'passed': 1, 'warnings': 1, 'failed': 1, 'status': 'Failed'}


def test_rehearsal_must_match_frozen_artifact():
    row = {'status': 'Passed', 'release_version': '1.0.0rc4', 'source_fingerprint': 'abc', 'image_digest': 'sha256:1'}
    assert rehearsal_matches(row, '1.0.0rc4', 'abc', 'sha256:1')
    assert not rehearsal_matches(row, '1.0.0rc4', 'different', 'sha256:1')


def test_promotion_requires_every_gate():
    blockers = promotion_blockers(
        {'status': 'Approved', 'go_live_decision': 'Go'},
        {'status': 'Frozen'},
        {'Blank Install': True, 'Upgrade': False},
        'Passed',
    )
    assert len(blockers) == 1 and 'Upgrade' in blockers[0]
    assert promotion_blockers(
        {'status': 'Approved', 'go_live_decision': 'Go'},
        {'status': 'Frozen'},
        {'Blank Install': True, 'Upgrade': True},
        'Passed',
    ) == []


def test_normalized_fingerprint_allows_only_version_label_change(tmp_path):
    (tmp_path / "hotel_pms").mkdir()
    (tmp_path / "ci").mkdir()
    version = tmp_path / "hotel_pms/__init__.py"
    logic = tmp_path / "hotel_pms/logic.py"
    version.write_text('__version__ = "1.0.0rc4"\n')
    logic.write_text('VALUE = 1\n')
    first = source_fingerprint(tmp_path)
    version.write_text('__version__ = "1.0.0"\n')
    assert source_fingerprint(tmp_path) == first
    logic.write_text('VALUE = 2\n')
    assert source_fingerprint(tmp_path) != first
