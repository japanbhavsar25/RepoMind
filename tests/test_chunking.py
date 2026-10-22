# tests/test_chunking.py
from repomind.chunking import build_symbol_chunks, chunk_source


def test_single_short_source_one_chunk():
    chunks = chunk_source("def a():\n    pass\n", 10)
    assert len(chunks) == 1
    text, cs, ce = chunks[0]
    assert cs == 10
    assert ce == 12


def test_long_source_splits_with_overlap_and_lines():
    src = "line %s padding xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n" * 0  # placeholder
    src = "".join(f"value_{i} = '{'x'*80}'  # pad\n" for i in range(100))
    assert len(src) > 3000
    chunks = chunk_source(src, 1, max_chars=3000, overlap_chars=300)
    assert len(chunks) >= 2
    # overlap: tail of first == head of second
    assert chunks[0][0][-300:] == chunks[1][0][:300]
    # lines monotonic and overlapping
    assert chunks[0][1] == 1
    assert chunks[1][1] <= chunks[0][2]
    assert chunks[-1][2] >= 90


def test_build_symbol_chunks_ids_and_metadata():
    src = "def a():\n" + "    x = 1\n" * 200  # long enough to split
    out = build_symbol_chunks("func", 7, "a", "pkg.a", "Doc.", src, "pkg/a.py", 5, 300)
    assert len(out) >= 1
    assert out[0]["id"].startswith("func_7")
    assert out[0]["metadata"]["file"] == "pkg/a.py"
    assert "start" in out[0]["metadata"] and "end" in out[0]["metadata"]
    if len(out) > 1:
        assert out[0]["id"] == "func_7#0"
        assert out[0]["metadata"]["total"] == len(out)
