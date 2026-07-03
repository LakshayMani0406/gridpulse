from gridpulse.docs_util import upsert_section


def test_upsert_creates_with_header(tmp_path):
    p = tmp_path / "E.md"
    upsert_section(p, "Alpha", "## Alpha\n\nbody a\n", doc_header="# DOC")
    txt = p.read_text()
    assert txt.startswith("# DOC")
    assert "## Alpha" in txt and "body a" in txt


def test_upsert_replaces_only_target_section(tmp_path):
    p = tmp_path / "E.md"
    upsert_section(p, "Alpha", "## Alpha\n\nold a\n", doc_header="# DOC")
    upsert_section(p, "Beta", "## Beta\n\nbody b\n")
    # replacing Alpha must NOT drop Beta (order-independence)
    upsert_section(p, "Alpha", "## Alpha\n\nnew a\n")
    txt = p.read_text()
    assert "new a" in txt and "old a" not in txt
    assert "## Beta" in txt and "body b" in txt
    # exactly one Alpha and one Beta section
    assert txt.count("## Alpha") == 1
    assert txt.count("## Beta") == 1


def test_upsert_appends_when_absent(tmp_path):
    p = tmp_path / "E.md"
    p.write_text("# DOC\n\n## Keep\n\nkeep me\n")
    upsert_section(p, "New", "## New\n\nnew body\n")
    txt = p.read_text()
    assert "keep me" in txt and "new body" in txt
