# 00 — Overview and Design Rules

*Edition 2026. Sections marked **[N]** are normative; **[I]** are informative.*

---

## 0.1 What Coco is **[I]**

Coco is a general-purpose, statically typed, ahead-of-time compiled programming
language whose surface syntax is punctuation-free human language, and whose compiler is
a conventional deterministic compiler — a lexer, a parser, a type checker, an optimiser
and a code generator. No machine-learning model is involved at any stage of translating
Coco source into a program.

Coco has:

- its own grammar, defined in this specification;
- its own intermediate representation (**CIR**), defined in [document 08](08-cir.md);
- its own runtime and standard library, defined in [document 11](11-stdlib.md);
- its own build tool, `compose`, defined in [document 12](12-toolchain.md);
- native code generation for x86-64, ARM64, WebAssembly and GPU targets.

Coco is **not** a transpiler to JavaScript, Python, HTML or C++. Those languages may
appear as *optional* interop targets, never as the definition of what an Coco program
means.

## 0.2 The four principles **[I]**

| Principle | Concrete commitment |
| --- | --- |
| **Simple** | One construct per idea. The whole core grammar fits on one page ([doc 02](02-grammar.md)). |
| **Easy** | A reader who has never programmed can state what a line does after reading it once. Zero mandatory annotations — no types, no lifetimes, no ownership markers. |
| **Fast** | Compiles to native machine code. No interpreter, no bytecode dispatch loop, no tracing garbage collector on the hot path. |
| **Efficient** | The compiler, not the programmer, performs allocation elimination, layout optimisation, vectorisation, and device placement. |

These are not slogans; each is cashed out as a testable requirement in
[document 15](15-conformance-and-editions.md).

## 0.3 The five design rules **[N]**

Every part of this specification obeys the following five rules. A proposed language
feature that violates one of them is rejected.

### Rule 1 — The Determinism Rule

> For any byte sequence *S* and any registry state *R*, the compiler either produces
> exactly one parse of *S* under *R*, or reports an error. It never chooses between
> candidate parses by heuristic, probability, frequency, or model inference.

Ambiguity is prevented **by construction**: the Clause Signature Registry is checked for
the ambiguity-freedom conditions R1–R6 ([doc 03 §3.6](03-clause-registry.md)) before any
source is parsed. If the registry is ambiguous, the *registry* fails to build — the
program is never parsed at all.

### Rule 2 — The Sugar Law

> Every punctuation-free convenience form is defined as sugar for an explicit form that
> is unambiguous under all registry states.

So there is always an escape hatch. When the convenient form is ambiguous or means the
wrong thing, the compiler's error message shows the explicit form, and a fix-it applies
it. For example, a button whose label happens to contain a registry particle:

```coco
note the convenient form would mis-parse, because "to page" is a terminator phrase
show button Go to page 2 of the manual

note the explicit form always works
show button
  label
    Go to page 2 of the manual
```

### Rule 3 — The Canonical Meaning Rule

> A program's meaning is a property of its **CIR**, never of its source words.

Two source files in different human languages that lower to the same canonical CIR are
the same program, and are required to produce bit-identical output binaries for the same
target and options ([doc 08 §8.7](08-cir.md)).

### Rule 4 — The No-Hidden-Cost Rule

> A construct that cannot be compiled to predictable machine code is not added to the
> language.

There is no dynamic `eval`, no runtime metaprogramming, no implicit boxing of small
values, no exception unwinding through arbitrary frames on the hot path, and no
stop-the-world tracing collector.

### Rule 5 — The One-Language Rule

> Anything an Coco application needs — layout, styling, interaction, persistence,
> networking, 2D/3D rendering, physics, numeric and GPU compute — is expressible in
> Coco itself, using the same grammar.

There is no embedded second syntax for markup, styling, queries or shaders.

## 0.4 How punctuation-free parsing actually works **[I]**

This is the question the whole design turns on, so here is the short answer before the
formal treatment in [documents 02](02-grammar.md) and [03](03-clause-registry.md).

Coco does not try to *understand English*. It matches against a finite, declared
table of **clause signatures**. A signature is a fixed sequence of keyword phrases,
particle phrases, and typed slots:

```
show button <label: text> [ to page <target: ref> ]
              ↑ slot         ↑ particle phrase   ↑ slot
```

Parsing a statement is three deterministic steps:

1. **Head match.** Walk the registry's keyword trie from the first word, taking the
   longest match. `show button` matches; the parse is now committed to exactly one
   signature family.
2. **Slot fill.** Fill slots left to right. A `text` slot is *greedy*: it consumes words
   until the first position at which a **complete terminator phrase declared for that
   slot** begins, or until end of line.
3. **Block attach.** If the signature ends in a block slot, attach the following
   indented block (or the single following statement, in the flush form).

Because terminator phrases are multi-word, declared per slot, and finite, the lookahead
needed is bounded by the longest terminator phrase in the registry — a small constant.
The grammar is therefore **LL(k)** for small *k*, and a table-driven single-pass parser
suffices. No backtracking, no ambiguity, no guessing.

The trick that makes this scale is that **users extend the registry**, not the grammar.
Defining a function *is* registering a signature:

```coco
to damage a target by an amount
  set health of target to health of target minus amount
```

…which registers `damage <target: ref> by <amount: number>`, callable as:

```coco
damage Hero by 10
```

The registry conditions R1–R6 are re-checked when the definition is added, so
user code can never make the language ambiguous. It can only fail to compile.

## 0.5 Reading a line of Coco **[I]**

Every statement is a **clause**. A clause has:

- a **head** — one or more keywords, e.g. `show text`, `open page`, `create neural network`;
- zero or more **slots** — the varying parts;
- zero or more **particle phrases** — connective words that separate slots, drawn from a
  closed set: `to`, `with`, `from`, `into`, `as`, `at`, `on`, `by`, `for`, `of`, `until`,
  `in`, `over`, `between`, `starting at`.

Four slot kinds carry values:

| Kind | Matches | Example |
| --- | --- | --- |
| `text` | a greedy run of words | `Welcome to my app` |
| `name` | a bounded run of words that names a thing | `Game Over` |
| `number` | a numeric literal | `10`, `3.5` |
| `value` | an expression | `health of player minus 10` |

Plus two structural kinds: `ref` (a reference to something already declared) and
`block` (an indented body).

## 0.6 What Coco deliberately does not have **[N]**

| Absent | Why | Replacement |
| --- | --- | --- |
| Quotation marks | Rule 2 | Greedy `text` slots; indented text blocks for awkward content |
| `()` `{}` `[]` `;` `:` `<>` `=>` | Rule 2 | Signatures, indentation, particle phrases |
| Tracing GC | Rule 4 | Inferred regions + unique ownership + refcounting ([doc 06](06-memory-and-safety.md)) |
| Lifetime annotations | Principle *Easy* | Whole-program region inference; plain-language errors when it fails |
| Operator symbols (`+`, `==`) | Principle *Simple* | Word operators `plus`, `is`, `is more than` ([doc 02 §2.7](02-grammar.md)) |
| `eval` / runtime codegen | Rule 4 | Compile-time evaluation (`compose` const-eval) |
| Implicit numeric coercion | Determinism | Explicit `as a decimal number` |
| Exceptions with unwinding | Rule 4 | `maybe` results and `or stop` / `or use` handling |

## 0.7 Document conventions **[N]**

- Grammar is written in ISO/IEC 14977 EBNF with the extensions noted in
  [doc 02 §2.1](02-grammar.md).
- Coco source appears in fenced blocks tagged `coco`.
- CIR appears in fenced blocks tagged `cir`.
- Registry signature declarations appear in blocks tagged `sig`.
- Diagnostic identifiers have the form `E-CCNN` (see [doc 14](14-diagnostics.md)).
- The key words MUST, MUST NOT, SHOULD, SHOULD NOT, MAY are used as in RFC 2119.

## 0.8 Edition policy **[N]**

The language is versioned by **edition**. This document defines **Edition 2026**. A
project declares its edition in `project.coco`. An implementation MUST be able to compile
every edition it claims to support, and MUST NOT change the meaning of a program within
an edition. New keywords and new core signatures may only be introduced in a new
edition. See [doc 15](15-conformance-and-editions.md).
