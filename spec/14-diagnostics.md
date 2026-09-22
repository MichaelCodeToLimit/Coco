# 14 — Diagnostics

*Edition 2026. **[N]** normative, **[I]** informative.*

Coco's audience includes people who have never programmed. The error messages are part
of the language design, not an afterthought, and this document is normative about them.

---

## 14.1 Code taxonomy **[N]**

```
E-CCNN   error       compilation fails
W-CCNN   warning     compilation succeeds
I-CCNN   information  something the compiler decided that you may want to know
```

| `CC` | Phase |
| --- | --- |
| `01` | lexical |
| `02` | parsing |
| `03` | registry |
| `04` | locale, messages |
| `05` | types and semantics |
| `06` | memory, ownership, regions |
| `07` | concurrency, effects, vectorisation |
| `08` | CIR / verifier (internal) |
| `09` | pipeline, budgets |
| `10` | targets, ABI, devices |
| `11` | standard library |
| `12` | toolchain, packages |
| `13` | language server |
| `15` | conformance |

Codes are permanent. A code is never reused for a different condition.

## 14.2 Message style rules **[N]**

Every diagnostic MUST follow these rules. They are checked by a lint over the compiler's
own message table.

1. **Say what happened, in words a non-programmer uses.** Not "type mismatch"; "this
   needs a number, but `name` is text".
2. **Never use a term the language does not have.** The words *pointer*, *lifetime*,
   *borrow*, *monad*, *nullable*, *undefined behaviour* MUST NOT appear in a user-facing
   message. The corresponding concepts are described concretely.
3. **Point at the cause, not only the symptom.** The primary span is where the fix goes;
   secondary spans explain why.
4. **Offer a fix when a mechanical one exists.** Every fix-it must be applicable without
   further questions.
5. **One diagnostic per root cause.** Cascades are suppressed
   ([doc 09 §9.4.2](09-compiler-pipeline.md)).
6. **No blame.** No "you forgot", no "invalid", no exclamation marks.
7. **Localised.** Messages are translated per locale; the code and the CIDs are not.
8. **Isolated LTR spans in RTL locales** ([doc 04 §4.5](04-multilingual.md)).

## 14.3 Anatomy **[N]**

```
E-0231  This button has no label.

   ┌─ src/main.coco:7:3
   │
 7 │   show button to page Game
   │   ─────────── ↑ the label would go here
   │               │
   │               `to page` starts the next part of the line,
   │               so nothing is left to use as the label.
   │
   help: give the button something to say
   fix:  show button Play to page Game
   more: compose explain E-0231
```

Required elements: code, one-sentence summary, primary span with a caret label, zero or
more secondary spans with labels, `help` (what to do), `fix` (the edit, if mechanical),
`more` (how to read the long form).

## 14.4 The long form **[N]**

`compose explain E-0231` prints a page with: what the rule is, why it exists, two or
three worked examples including the explicit form, and links to the relevant
specification section. Every code MUST have a long form. The LSP surfaces it in hover and
in the diagnostic's `codeDescription.href`.

## 14.5 Selected diagnostics **[N]**

The complete table lives in `spec/appendix/diagnostics.md`. These are the ones that
define the character of the language.

### E-0231 — greedy slot is empty

Shown above.

### E-0233 — greedy slot was cut short

```
W-0233  Part of this text was read as an instruction.

  10 │   show button Go to page 2 of the manual
     │               ── ────────
     │               │  └ `to page` is how a button says where to go,
     │               │    so the label stopped before it.
     │               └ the label is just `Go`

  If you meant the whole sentence as the label, write it out in full:

  fix:  show button
          label
            Go to page 2 of the manual
```

This is the Sugar Law ([doc 00 §0.3](00-overview.md)) doing its job. It is a **warning**,
not an error, because the clipped parse is well-formed — but the warning is on by default
and the fix is one keystroke.

### E-0312 — the registry would become ambiguous

```
E-0312  Two instructions could start the same way.

   ┌─ src/charts.coco:3:1
   │
 3 │ to show a chart of a kind with some data
   │    ──── ↑ this would create an instruction called `show`
   │
   note: `show text` already exists, and its first part is free text,
         so `show chart …` could be read as showing the text "chart …".

  help: give it a distinct first word
  fix:  to draw a chart of a kind with some data
```

### E-0615 — two things changing at once

Shown in [doc 06 §6.3.3](06-memory-and-safety.md).

### E-0721 — steps cannot happen at the same time

Shown in [doc 07 §7.6](07-concurrency-and-simd.md).

### E-0541 — a possible failure is unhandled

```
E-0541  Reading this file might not work.

  4 │   let data be read file scores.txt
    │               ──────────────────── this can fail if the file is missing

  help: say what to do if it fails
  fix:  try
          let data be read file scores.txt
        or
          let data be text
            0
```

### E-0521 — numbers of different kinds

```
E-0521  These are different kinds of number.

  6 │   set total to count plus average
    │                ─────      ─────── a decimal number
    │                └ a whole number
    │
    Whole numbers and decimal numbers are kept apart on purpose,
    so that a rounding never happens without you asking for it.

  fix:  set total to count as a decimal number plus average
```

### E-0512 — a choice is not fully covered

```
E-0512  One kind of shape has no answer here.

  12 │   for the shape s
     │       ───────────
  13 │     when it is a circle
  14 │     when it is a rectangle
     │
     `empty` is also a shape, and nothing here says what to do with it.

  fix:  add
          when it is empty
            give 0
```

### W-0412 — a message has no wording for a language

```
W-0412  `greeting` has nothing to say in Japanese.

   6 │ the message greeting says
     │             ──────── this message
   7 │   in english Hi
   8 │   in hebrew  שלום
     │
     Your project says it supports Japanese, and this message has no
     Japanese wording, so Japanese users will see the English one.

  help: add a wording, or remove japanese from the project's languages
  fix:  in japanese こんにちは
```

### E-0413 — a wording dropped a placeholder

```
E-0413  These wordings do not use the same values.

  12 │   in english value of name scored value of points
     │              ─────────────        ───────────────
  13 │   in hebrew ערך של name צבר
     │             ────────────  `points` is missing here

  Every wording of a message must use the same set of values, or the
  text will be wrong for some readers.

  fix:  in hebrew ערך של name צבר ערך של points
```

### W-0246 — a name is hidden

```
W-0246  This `score` hides the `score` from outside.

   3 │ keep score as 0
     │      ───── the outer one
  ...
  19 │     keep score as 0
     │          ───── this one is used for the rest of the block

  help: rename one of them if that was not intended
```

### I-0621 — a value is reference counted

Shown in [doc 06 §6.4](06-memory-and-safety.md). Informational by default; a project
may raise it to an error in named modules with `deny promotions in <module>`.

### I-0791 — layout chosen for speed

Shown in [doc 07 §7.9.2](07-concurrency-and-simd.md).

## 14.6 Severity policy **[N]**

| Situation | Severity |
| --- | --- |
| The program has no single meaning | error |
| The program has a meaning that is almost certainly not intended | warning, on by default |
| The compiler made a performance-relevant choice | information |
| A deprecated signature is used | warning with fix-it |
| A signature is `preview` | warning |
| An unused `keep` binding, `use`, or parameter | warning |
| Missing accessibility description | warning |
| A trusted module or foreign call was added | information, error under `--deny-new-trusted` |

Warnings MUST be individually controllable:

```coco
allow hidden names in this block
  ...
```

```coco
note in project.coco
warnings
  hidden names off
  missing descriptions as errors
```

There is no global `-Werror`; `compose --frozen check --deny warnings` is the CI form.

## 14.7 Machine-readable output **[N]**

```bash
compose check --message-format json
```

```jsonc
{
  "code": "E-0231",
  "severity": "error",
  "summary": "This button has no label.",
  "primary": { "file": "src/main.coco", "line": 7, "column": 3, "endColumn": 14,
               "byteStart": 118, "byteEnd": 129, "label": "the label would go here" },
  "secondary": [ { "file": "src/main.coco", "line": 7, "column": 15, "endColumn": 22,
                   "label": "`to page` starts the next part of the line" } ],
  "help": "give the button something to say",
  "fixes": [ { "title": "Add a label",
               "edits": [ { "file": "src/main.coco", "byteStart": 129, "byteEnd": 129,
                            "newText": " Play" } ] } ],
  "cids": [ "core.stmt.show_button", "core.slot.show_button.label" ],
  "explainUrl": "https://coco-lang.org/e/E-0231"
}
```

Columns are **logical code-point offsets**; byte offsets are also given so tools need not
re-decode. For RTL files, `visualColumn` is present.

## 14.8 Internal compiler errors **[N]**

A verifier failure ([doc 08 §8.8](08-cir.md)) or any unexpected state produces:

```
E-0801  The compiler found a problem in its own work.

  This is a bug in Coco, not in your program.

  Please report it at https://coco-lang.org/bug with this file:
    .coco/reports/2026-09-22-141203.embug

  The report contains: your source (unless you pass --no-source),
  the canonical hash b3:9f4c1e…, the toolchain version, and the
  failing invariant (V11: value escapes its region).
```

The compiler MUST NOT emit a binary after an internal error, and MUST write a
self-contained reproduction bundle.

## 14.9 Beginner mode **[N]**

```bash
compose --explain-everything
```

- Every diagnostic prints its long form inline.
- Every `I-` information message is shown.
- Every clause that parsed in a non-obvious way (any greedy slot that stopped at a
  terminator) prints its parse trace.

This mode is the default for `compose new` projects for their first ten builds, then
switches off with a one-line note explaining how to bring it back. New programmers get
the explanations while they need them, and stop being interrupted once they do not.

---

*Next: [15 — Conformance and editions](15-conformance-and-editions.md)*
