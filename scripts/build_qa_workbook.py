"""Build a formula-based QA workbook from real, exported training inputs."""
from pathlib import Path
import csv
import json
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "qa" / "Ankit_Karki_QA_Workbook.xlsx"
NAVY, BLUE, PALE = "17324D", "225C8A", "E8F0F8"
wb = openpyxl.Workbook()
wb.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True)
ws = wb.active
ws.title = "Instructions"
notes = [
    ["ANKIT KARKI | INDEPENDENT QA", "MATH 3315 — Calling the Table"],
    ["Review status", "PENDING personal review — formulas are not a signature"],
    ["Inputs", "Five real fixtures; all goal sums/counts are from dates strictly before each fixture."],
    ["What to do", "Check raw inputs against the exported training data, recalculate formulas, and record your review."],
    ["Formula cells", "Blue/light fill cells calculate rates and a displayed 0–10 score grid independently of Python."],
    ["Tolerance", "Rate differences below 0.0005 agree when rounded to three decimals."],
    ["Grid warning", "The displayed grid is unnormalized and finite. Its tail is shown. The Python engine expands adaptively."],
    ["Outcome order", "Home win (home goals > away goals), draw, away win."],
    ["Software", "Open in Excel or LibreOffice and allow formula recalculation; the grid uses EXP, powers, and FACT."],
    ["Reproducibility", "See data/provenance.json and outputs/source_metadata.json for hashes."],
    ["Privacy", "This workbook contains derived inputs; raw provider CSVs remain private coursework copies."],
    ["Manual external QA", "Official table, group signatures, deadlines and instructor sign-off are still human tasks."],
]
for r in notes:
    ws.append(r)
ws.column_dimensions["A"].width = 27
ws.column_dimensions["B"].width = 110
ws.freeze_panes = "B3"
with (ROOT / "outputs/hand_checks.csv").open(newline="", encoding="utf-8") as f:
    inputs = list(csv.DictReader(f))
for d in inputs:
    s = wb.create_sheet(f"Fixture_{d['Check']}")
    s["A1"] = f"FIXTURE {d['Check']} | {d['HomeTeam']} vs {d['AwayTeam']}"
    s.merge_cells("A1:L1")
    s["A2"] = "Independent formulas from historical sums/counts; Ankit's manual verification remains pending."
    s.merge_cells("A2:L2")
    rows = {
        5: ("Prediction date", d["Date"]), 6: ("Home team", d["HomeTeam"]),
        7: ("Away team", d["AwayTeam"]), 8: ("Training matches", int(d["TrainingRows"])),
        9: ("Latest training date", d["LatestTrainingDate"]),
        11: ("League home goals sum", int(d["LeagueHomeGoalsSum"])),
        12: ("League home matches", int(d["LeagueHomeMatches"])),
        13: ("League away goals sum", int(d["LeagueAwayGoalsSum"])),
        14: ("League away matches", int(d["LeagueAwayMatches"])),
        16: ("Home team's home goals", int(d["HomeHomeGoalsScoredSum"])),
        17: ("Home team's home matches", int(d["HomeHomeMatches"])),
        18: ("Away team's away conceded", int(d["AwayAwayGoalsConcededSum"])),
        19: ("Away team's away matches", int(d["AwayAwayMatches"])),
        20: ("Away team's away goals", int(d["AwayAwayGoalsScoredSum"])),
        21: ("Home team's home conceded", int(d["HomeHomeGoalsConcededSum"])),
        23: ("League home mean", "=B11/B12"), 24: ("League away mean", "=B13/B14"),
        25: ("Home scoring rate", "=B16/B17"), 26: ("Away conceding rate", "=B18/B19"),
        27: ("Away scoring rate", "=B20/B19"), 28: ("Home conceding rate", "=B21/B17"),
        30: ("Excel lambda HOME", "=B25*B26/B23"),
        31: ("Excel lambda AWAY", "=B27*B28/B24"),
        32: ("Python lambda HOME", float(d["M1_HomeLambda"])),
        33: ("Python lambda AWAY", float(d["M1_AwayLambda"])),
        34: ("Absolute difference HOME", "=ABS(B30-B32)"),
        35: ("Absolute difference AWAY", "=ABS(B31-B33)"),
        36: ("Calculation comparison", '=IF(AND(B34<0.0005,B35<0.0005),"AGREES TO 3 DECIMALS","INVESTIGATE")'),
        52: ("Displayed grid mass", "=SUM(B40:L50)"),
        53: ("Omitted 0–10 tail", "=1-B52"),
        57: ("Outcome raw sum", "=SUM(B54:B56)"),
        59: ("Manual reviewer", "Ankit Karki — pending personal review"),
        60: ("Review date", ""), 61: ("Manual decision", "PENDING"),
    }
    for r, (label, value) in rows.items():
        s.cell(r, 1, label)
        s.cell(r, 2, value)
    s["A38"] = "Score grid: rows = home goals; columns = away goals"
    s.merge_cells("A38:L38")
    home_cells, draw_cells, away_cells = [], [], []
    for j in range(11):
        s.cell(39, j + 2, j)
    for i in range(11):
        s.cell(40 + i, 1, i)
        for j in range(11):
            c = s.cell(40 + i, j + 2)
            c.value = f"=(EXP(-$B$30)*$B$30^$A{40+i}/FACT($A{40+i}))*(EXP(-$B$31)*$B$31^{get_column_letter(j+2)}$39/FACT({get_column_letter(j+2)}$39))"
            c.number_format = "0.0000%"
            (home_cells if i > j else draw_cells if i == j else away_cells).append(c.coordinate)
    for rownum, label, cells in [(54, "HOME win raw mass", home_cells), (55, "DRAW raw mass", draw_cells), (56, "AWAY win raw mass", away_cells)]:
        s.cell(rownum, 1, label)
        s.cell(rownum, 2, "=SUM(" + ",".join(cells) + ")")
    s.column_dimensions["A"].width = 31
    s.column_dimensions["B"].width = 25
    for col in range(3, 13):
        s.column_dimensions[get_column_letter(col)].width = 12
    for r in list(range(23, 36)) + list(range(52, 58)):
        s.cell(r, 2).number_format = "0.000000"
    s.freeze_panes = "B10"
    s.print_options.horizontalCentered = True
    s.sheet_properties.pageSetUpPr.fitToPage = True
    s.page_setup.orientation = "landscape"
    s.page_setup.paperSize = s.PAPERSIZE_A4
    s.page_setup.fitToWidth = 1
    s.page_setup.fitToHeight = 2
    s.print_area = "A1:L61"
log = wb.create_sheet("Issue_Log")
with (ROOT / "qa/Issue_Log.csv").open(newline="", encoding="utf-8") as f:
    for row in csv.reader(f):
        log.append(row)
for col in range(1, 9):
    log.column_dimensions[get_column_letter(col)].width = [12, 14, 12, 60, 60, 35, 22, 55][col - 1]
log.freeze_panes = "D2"
log.auto_filter.ref = log.dimensions
for s in wb:
    for cell in s[1]:
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(name="Calibri", color="FFFFFF", bold=True, size=12)
    s.row_dimensions[1].height = 30
    for row in s.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name="Calibri", size=11, color="17324D")
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(c.value, str) and c.value.startswith("="):
                c.fill = PatternFill("solid", fgColor=PALE)
                c.font = Font(name="Calibri", size=11, color=BLUE)
    if s.title == "Instructions":
        for r in range(2, s.max_row + 1):
            s.row_dimensions[r].height = 34
    elif s.title == "Issue_Log":
        for r in range(2, s.max_row + 1):
            s.row_dimensions[r].height = 65
    else:
        s.row_dimensions[2].height = 32
        s.row_dimensions[36].height = 34
        for r in range(40, 51):
            s.row_dimensions[r].height = 23
wb.save(OUT)
print(f"Workbook written: {OUT} ({len(wb.worksheets)} sheets)")
