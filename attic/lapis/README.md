# Lapis — the earlier prototype

This directory holds the **Lapis** prototype, the first attempt at the
punctuation-free language that later became [Coco](../../README.md). It was moved
here unchanged on 2026-09-22 when the specification work began; nothing in it was
edited, and nothing in the Coco toolchain reads from it.

It is kept because it records what the idea looked like before it had a grammar:

| File | What it was |
| --- | --- |
| `app.lp`, `app_page1.lp` | example programs — `page Dashboard`, `show text …`, `show button … to page 1` |
| `commands.lp`, `charts.lp`, `registry.lp` | a hand-written command table: `command show chart (type) with (data)` |
| `engine.ps1` | a PowerShell interpreter that walked the source line by line |
| `template.html` | the HTML shell the interpreter rendered into |
| `lapis.c`, `lapis_core.c` | stub C entry points for a future native engine |
| `lapis-extension/`, `lapis-android/` | an editor extension and an Android shell |
| `test app v1/` | a sample project |

The one idea worth carrying forward was `commands.lp` — the notion that the set of
valid statements is a *declared table* rather than something baked into a parser.
That became the [Clause Signature Registry](../../spec/03-clause-registry.md), with
the addition that the table is now machine-checked for ambiguity before any source
is parsed.

Everything else — the line-by-line interpreter, the HTML target, the untyped command
arguments — was replaced rather than evolved.
