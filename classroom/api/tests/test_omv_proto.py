import pytest

from services import omv_proto
from services.omv_reader import lookup_stat, parse_omv
from tests.omv_pb import analysis, cell, column, element, field, image, note, omv, table


def doc_of(*analyses, index_html=""):
    members = [(a["dir"], a["blob"]) for a in analyses]
    return parse_omv(omv(members, index_html=index_html))


def ttest_entry():
    """``jmv::ttestOneS`` output: a t-table plus its Shapiro-Wilk assumptions box."""
    main = element(
        "ttest", "One Sample T-Test",
        table([
            column("var", "", [cell("score")], type_="text"),
            column("stat", "Statistic", [cell(7.325754)]),
            column("df", "df", [cell(7)]),
            column("p", "p", [cell(0.0001592)], format="zto,pvalue"),
            column("hidden", "Unticked box", [cell(999.0)], visible=1),
        ], notes=[note("1", "H\u2080 \u03bc = 0")]),
    )
    norm = element(
        "norm", "Normality Test (Shapiro-Wilk)",
        table([
            column("name", "", [cell("score")], type_="text"),
            column("w", "W", [cell(0.9876522)]),
            column("p", "p", [cell(0.8612201)], format="zto,pvalue"),
            column("pm", "Error %", [cell(None)]),
        ]),
    )
    root = element("ttestOneS", "One Sample T-Test", elements=[main, norm])
    return {"dir": "ttestOneS",
            "blob": analysis("ttestOneS", root, ns="jmv", title="One Sample T-Test")}


def test_decodes_the_analysis_response_envelope():
    entry = ttest_entry()
    decoded = omv_proto.decode_analysis(entry["blob"])
    assert (decoded["name"], decoded["ns"], decoded["title"]) == (
        "ttestOneS", "jmv", "One Sample T-Test")


def test_placeholder_entries_decode_to_nothing():
    assert omv_proto.decode_analysis(b"") is None
    assert omv_proto.decode_analysis(b"\x10\x01") is None


def test_truncated_blobs_are_rejected_not_guessed():
    entry = ttest_entry()
    assert omv_proto.decode_analysis(entry["blob"][:60]) is None


def test_results_become_gradeable_tables():
    doc = doc_of(ttest_entry())
    assert doc["source"] == "results"
    assert doc["modules"] == ["ttestOneS"]
    main = doc["tables"][0]
    assert main["analysis"] == "One Sample T-Test"
    assert main["module"] == "ttestOneS"
    assert main["title"] == "One Sample T-Test"
    assert main["columns"] == ["", "Statistic", "df", "p"]
    assert main["rows"] == [["score", "7.33", "7.00", "<\u2009.001"]]
    assert main["notes"] == ["H\u2080 \u03bc = 0"]
    assert doc["module_by_analysis"] == {"One Sample T-Test": "ttestOneS"}


def test_a_hidden_statistics_box_is_not_gradeable():
    """What the teacher unticked in jamovi is not on screen, so it is not in the file either."""
    doc = doc_of(ttest_entry())
    assert "Unticked box" not in doc["tables"][0]["columns"]
    assert lookup_stat(doc, table="One Sample T-Test", column="Unticked")[1] == "column"


@pytest.mark.parametrize(
    "value, format_, type_, expected",
    [
        (0.8612201, "zto,pvalue", "number", ".861"),
        (1e-9, "zto,pvalue", "number", "<\u2009.001"),
        (0.0001592, "zto,pvalue", "number", "<\u2009.001"),
        (7.325754, "", "number", "7.33"),
        (0.0156786, "", "number", "0.0157"),
        (219.086, "", "number", "219"),
        (7.0, "", "integer", "7"),
        (0.25, "pc", "number", "25.0\u2009%"),
        (-2.0, "log10", "number", "0.0100"),
        (float("nan"), "", "number", "NaN"),
        (1e7, "", "number", "1.00e+7"),
    ],
)
def test_numbers_print_the_way_the_results_view_prints_them(value, format_, type_, expected):
    fmt = omv_proto.determ_format([value], type_, format_)
    assert omv_proto.format_number(value, fmt) == expected


def test_missing_and_not_a_number_cells_are_blank():
    column_bytes = column("x", "X", [cell(None), cell(True), cell(4.0)])
    decoded = omv_proto._decode_column(column_bytes)
    assert [c["value"] for c in decoded["cells"]] == [None, "NaN", 4.0]
    assert [c["missing"] for c in decoded["cells"]] == [True, False, False]


def test_footnotes_number_their_marker():
    entry = {
        "dir": "linReg",
        "blob": analysis("linReg", element(
            "fit", "Model Fit Measures",
            table([
                column("r2", "R\u00b2", [cell(0.0242, footnotes=["1", "2"])]),
            ], notes=[note("1", "A note"), note("2", "Another note")]))),
    }
    doc = doc_of(entry)
    assert doc["tables"][0]["rows"] == [["0.0242^{1}^{2}"]]
    assert doc["tables"][0]["notes"] == ["A note", "Another note"]


def test_lookup_uses_the_stored_number_not_the_rounded_text():
    doc = doc_of(ttest_entry())
    value, reason = lookup_stat(doc, analysis="ttestOneS", table="One Sample T-Test", column="Statistic")
    assert reason == ""
    assert value == pytest.approx(7.325754)


def test_row_wildcard_and_labels():
    doc = doc_of(ttest_entry())
    assert lookup_stat(doc, table="Normality", column="W", row="*")[0] == pytest.approx(0.9876522)
    assert lookup_stat(doc, table="Normality", column="p", row="score")[0] == pytest.approx(0.8612201)


def test_lookup_reasons_distinguish_a_bad_key_from_an_unrun_analysis():
    doc = doc_of(ttest_entry())
    assert lookup_stat(doc, analysis="anovaOneW")[1] == "analysis"
    assert lookup_stat(doc, table="Kruskal-Wallis")[1] == "table"
    assert lookup_stat(doc, table="Normality", column="df")[1] == "column"
    assert lookup_stat(doc, table="Normality", column="p", row="no such group")[1] == "row"


def test_a_blank_cell_is_not_a_value():
    """A statistics box the analysis left empty must not read as zero."""
    doc = doc_of(ttest_entry())
    value, reason = lookup_stat(doc, table="Normality", column="Error %")
    assert value is None
    assert reason == "value"


def test_images_and_notices_travel_with_the_analysis():
    notice = field(1, "insufficient data") + field(2, 2)   # ResultsNotice{content, type}
    entry = {
        "dir": "linReg",
        "blob": analysis("linReg", element("root", "Linear Regression", elements=[
            element("plot", "Plot", image("01 linReg/resources/plots-1.png"), kind=7),
            element("m", "Message", notice, kind=24),
        ])),
    }
    doc = doc_of(entry)
    assert doc["analyses"][0]["images"][0]["path"] == "01 linReg/resources/plots-1.png"
    assert doc["analyses"][0]["notices"][0]["content"] == "insufficient data"
    assert doc["images"] == ["01 linReg/resources/plots-1.png"]


def test_results_win_over_the_report_the_browser_sent():
    """The HTML arrives from the student's own page and only ever rounds; the file
    holds what jamovi computed, so a submission is graded from the file."""
    entry = ttest_entry()
    doc = doc_of(entry, index_html=(
        "<html><body><h1>Linear Regression</h1>"
        "<table><tr><th scope='colgroup' colspan='2'>Model Fit Measures</th></tr>"
        "<tr><th scope='col'>R\u00b2</th></tr><tr><td>0.99</td></tr></table>"
        "</body></html>"))
    assert doc["source"] == "results"
    assert [t["title"] for t in doc["tables"]] == ["One Sample T-Test", "Normality Test (Shapiro-Wilk)"]
    assert lookup_stat(doc, table="Model Fit", column="R2")[1] == "table"


def test_tables_from_results_skips_an_analysis_that_rendered_nothing():
    entry = {"dir": "empty", "blob": analysis("empty", element("Results", "Results", b"", kind=8))}
    doc = doc_of(entry)
    assert doc["source"] == "html"
    assert doc["tables"] == []
    assert doc["modules"] == []
