import io
import zipfile

import pytest

from services.omv_reader import lookup_stat, parse_number, parse_omv


def find_stat(doc, **kwargs):
    """The value a grading rule points at, or None when the rule cannot be read."""
    return lookup_stat(doc, **kwargs)[0]


_INDEX_HTML = """
<html><body>
<h1>Linear Regression</h1>
<table aria-labelledby="label-3">
  <tr><th scope="colgroup" colspan="3"><span id="label-3">Model Fit Measures</span></th></tr>
  <tr><th scope="col">Model</th><th scope="col">R</th><th scope="col">R&#178;</th></tr>
  <tr><td><span>1</span></td><td><span>0.156</span></td><td><span>0.0242</span></td></tr>
  <tr><td colspan="3"><span>Note. N=1047</span></td></tr>
</table>
<table>
  <tr><th scope="colgroup" colspan="5">Model Coefficients - outcome</th></tr>
  <tr><th scope="col">Predictor</th><th scope="col">Estimate</th><th scope="col">SE</th><th scope="col">t</th><th scope="col">p</th></tr>
  <tr><td>Intercept</td><td>14.302</td><td>4.2330</td><td>3.38</td><td>&lt;.001</td></tr>
  <tr><td>predictor1</td><td>0.320</td><td>0.0629</td><td>5.09</td><td>&lt;.001</td></tr>
</table>
<h1>One-Way ANOVA</h1>
<table>
  <tr><th scope="colgroup" colspan="4">One-Way ANOVA (Welch's)</th></tr>
  <tr><th scope="col">Statistic</th><th scope="col">df1</th><th scope="col">df2</th><th scope="col">p</th></tr>
  <tr><td>3.4821</td><td>2</td><td>58.6</td><td>0.038</td></tr>
</table>
<p>Some free-text note about the analysis.</p>
<img src="04%20anovaOneW/resources/abc.png">
</body></html>
"""


def make_omv(index_html: str = _INDEX_HTML, modules=("linReg", "empty", "anovaOneW")) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("meta", "Manifest-Version: 1.0\njamovi-Archive-Version: 11.0\n")
        archive.writestr("index.html", index_html)
        archive.writestr("metadata.json", '{"document":{},"dataSet":{}}')
        for i, module in enumerate(modules, start=1):
            archive.writestr(f"{i:02d} {module}/analysis", b"")
        archive.writestr("04 anovaOneW/resources/abc.png", b"\x89PNG")
    return buf.getvalue()


def test_reads_tables_columns_and_rows():
    doc = parse_omv(make_omv())
    fit = doc["tables"][0]
    assert fit["analysis"] == "Linear Regression"
    assert fit["title"] == "Model Fit Measures"
    assert fit["columns"] == ["Model", "R", "R²"]
    assert fit["rows"][0] == ["1", "0.156", "0.0242"]
    # the trailing "Note." row is a real cell row and stays available for lookups
    assert [r[0] for r in fit["rows"]] == ["1", "Note. N=1047"]


def test_skips_placeholder_entries_when_listing_modules():
    doc = parse_omv(make_omv())
    assert doc["modules"] == ["linReg", "anovaOneW"]


def test_tables_grouped_by_analysis():
    doc = parse_omv(make_omv())
    assert [(a["name"], len(a["tables"])) for a in doc["analyses"]] == [
        ("Linear Regression", 2),
        ("One-Way ANOVA", 1),
    ]


def test_notes_and_images_captured():
    doc = parse_omv(make_omv())
    assert "Some free-text note about the analysis." in doc["notes"]
    assert doc["images"] == ["04%20anovaOneW/resources/abc.png"]


def test_find_stat_prefers_exact_column_over_substring():
    doc = parse_omv(make_omv())
    assert find_stat(doc, table="Model Fit", column="R") == 0.156
    assert find_stat(doc, table="Model Fit", column="R²") == 0.0242
    # "p" must not accidentally land on the "Predictor" column
    assert find_stat(doc, table="Model Coefficients", column="p", row="predictor1") == 0.0005


def test_find_stat_scopes_by_analysis():
    doc = parse_omv(make_omv())
    assert find_stat(doc, analysis="One-Way ANOVA", column="p") == 0.038
    assert find_stat(doc, analysis="nonexistent", column="p") is None


def test_find_stat_reports_missing_values_as_none():
    doc = parse_omv(make_omv())
    assert find_stat(doc, table="Model Fit", column="df_error") is None
    assert find_stat(doc, table="Model Fit", column="R", row="no such row") is None


@pytest.mark.parametrize(
    "cell, expected",
    [
        (".023", 0.023),
        ("<.001", 0.0005),
        ("1,234.5", 1234.5),
        ("\u2212.02", -0.02),
        ("0.00", 0.0),
        ("95%", 95.0),
        ("0.156", 0.156),
        ("—", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_number(cell, expected):
    assert parse_number(cell) == expected


_AMBIGUOUS_HTML = """
<html><body>
<h1>One-Way ANOVA (Non-parametric)</h1>
<table>
  <tr><th scope="colgroup" colspan="3">Kruskal-Wallis</th></tr>
  <tr><th scope="col">Statistic</th><th scope="col">df</th><th scope="col">p</th></tr>
  <tr><td>12.30</td><td>3</td><td>0.001</td></tr>
</table>
<h1>One-Way ANOVA</h1>
<table>
  <tr><th scope="colgroup" colspan="4">One-Way ANOVA (Welch's)</th></tr>
  <tr><th scope="col">Statistic</th><th scope="col">df1</th><th scope="col">df2</th><th scope="col">p</th></tr>
  <tr><td>3.4821</td><td>2</td><td>58.6</td><td>0.038</td></tr>
</table>
</body></html>
"""


def test_find_stat_prefers_the_exact_analysis_name():
    """"One-Way ANOVA" is also a substring of "One-Way ANOVA (Non-parametric)".

    Picking the first substring hit would grade the Welch p-value out of the
    Kruskal-Wallis table and silently report a wrong number to the student.
    """
    doc = parse_omv(make_omv(_AMBIGUOUS_HTML, modules=("anovaNP", "anovaOneW")))
    assert find_stat(doc, analysis="One-Way ANOVA", column="p") == 0.038
    assert find_stat(doc, analysis="Non-parametric", column="p") == 0.001


def test_find_stat_accepts_the_jamovi_module_key():
    """Teachers see module keys in the archive, so linReg == Linear Regression."""
    doc = parse_omv(make_omv())
    assert doc["module_by_analysis"] == {"Linear Regression": "linReg", "One-Way ANOVA": "anovaOneW"}
    assert find_stat(doc, analysis="linReg", table="Model Fit", column="R2") == 0.0242
    assert find_stat(doc, analysis="anovaOneW", column="p") == 0.038


def test_grading_schema_lists_everything_a_teacher_can_check():
    from services.omv_reader import grading_schema

    doc = parse_omv(make_omv())
    schema = grading_schema(doc)
    assert [a["name"] for a in schema] == ["Linear Regression", "One-Way ANOVA"]
    assert schema[0]["module"] == "linReg"
    fit = schema[0]["tables"][0]
    assert fit["title"] == "Model Fit Measures"
    assert fit["columns"] == ["Model", "R", "R²"]
    assert "1" in fit["row_labels"]


_LIVE_RESULTS_HTML = """
<h1>Linear Regression</h1>
<div class="jmv-results-table-table-wrap">
<table aria-labelledby="label-7">
  <caption class="jmv-results-table-title-cell" scope="colgroup" colspan="2"><span id="label-7">Model Fit Measures</span></caption>
  <tbody>
    <tr><th scope="col">Model</th><th scope="col">R&#178;</th></tr>
    <tr><td><span>1</span></td><td><span>0.0242</span></td></tr>
  </tbody>
</table>
</div>
<h1>One-Way ANOVA</h1>
<table>
  <caption class="jmv-results-table-title-cell" scope="colgroup">ANOVA</caption>
  <tr><th scope="col">Statistic</th><th scope="col">p</th></tr>
  <tr><td>3.4821</td><td>0.038</td></tr>
</table>
"""


def test_the_browser_report_makes_an_empty_omv_gradeable():
    """A .omv saved before any analysis ran carries no results, only the report the
    browser rendered. That markup titles tables with <caption> rather than the
    full-width <th scope="colgroup"> an exported report uses, and it is the fallback
    the file-based reader drops to when the archive holds nothing.
    """
    doc = parse_omv(make_omv("<html><body>nothing rendered here</body></html>"), html=_LIVE_RESULTS_HTML)
    fit = doc["tables"][0]
    assert fit["analysis"] == "Linear Regression"
    assert fit["title"] == "Model Fit Measures"
    assert fit["columns"] == ["Model", "R²"]
    assert fit["rows"] == [["1", "0.0242"]]
    assert find_stat(doc, analysis="linReg", table="Model Fit", column="R2") == 0.0242
    assert find_stat(doc, analysis="anovaOneW", column="p") == 0.038


def test_an_omv_with_no_report_at_all_yields_no_tables():
    doc = parse_omv(make_omv(""))
    assert doc["tables"] == []
