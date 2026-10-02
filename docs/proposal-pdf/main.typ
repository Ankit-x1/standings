// Portable Markdown proposal using the skill-owned report theme.
#import "@preview/cmarker:0.1.10"
#import "@preview/mitex:0.2.7": mitex
#import "report-theme.typ": report-theme
#show: report-theme.with(
  title: "Calling the Table — MATH 3315 Proposal",
  author: "Group proposal; Ankit Karki, Quality Assurance Lead",
  body-size: 10.5pt,
  first-line-indent: none,
  running-header: false,
)
#set text(lang: "en", region: "us")
#set heading(numbering: none)
#show table: it => {
  let n = it.columns.len()
  let widths = if n == 3 {
    if repr(it.children).contains("Accountable role") { (1.1fr, 3.2fr, 1.2fr) }
    else { (1.1fr, 1.3fr, 3.1fr) }
  } else if n == 2 { (1.25fr, 3.75fr) } else { (1fr,) * n }
  set par(justify: false)
  set text(size: 10pt)
  if it.columns == widths { it } else { table(
    columns: widths,
    align: left + top,
    stroke: none,
    inset: (x: 7pt, y: 6pt),
    fill: (_, y) => if y == 0 { rgb("#e9eff7") } else if calc.even(y) { luma(248) } else { none },
    table.hline(stroke: 0.7pt + rgb("#1a5fb4")),
    ..it.children.filter(child => child.func() != table.hline and child.func() != table.vline),
    table.hline(stroke: 0.7pt + rgb("#1a5fb4")),
  ) }
}
#show table.cell.where(y: 0): set text(weight: "bold")
#cmarker.render(read("source.md"), math: mitex)
