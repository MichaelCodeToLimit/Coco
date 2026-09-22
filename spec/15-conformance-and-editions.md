# 15 — Conformance and Editions

*Edition 2026. **[N]** normative, **[I]** informative.*

---

## 15.1 What "an Coco implementation" means **[N]**

An implementation may claim conformance with **Coco Edition 2026** if and only if it
satisfies every requirement in §15.2 and passes the suites in §15.3–§15.9.

Partial claims are permitted and must be stated precisely:

| Claim | Requires |
| --- | --- |
| **Coco 2026 Core** | §15.2 A–F, suites `lex`, `parse`, `registry`, `types`, `cir` |
| **Coco 2026 Native** | Core + §15.2 G–J, suites `memory`, `concurrency`, `codegen`, `repro` |
| **Coco 2026 Full** | Native + §15.2 K–M, suites `stdlib`, `tooling`, `lsp` |
| **Coco 2026 Multilingual** | any of the above + suite `locale` for each claimed locale |

An implementation MUST report its claim from `compose version --conformance`.

## 15.2 Requirements **[N]**

**A — Lexing.** Implements [doc 01](01-lexical-structure.md) exactly, including NFC
normalisation, script-run segmentation, LEX-UNSEG for unsegmented scripts, the
indentation rules, and the bidi restrictions.

**B — Registry.** Builds the registry per [doc 03](03-clause-registry.md) and **verifies
R1–R6 before parsing**. An implementation that parses against an unverified registry is
non-conforming, because Rule 1 of [doc 00](00-overview.md) then does not hold.

**C — Parsing.** Implements [doc 02](02-grammar.md), including the greedy-slot rule G,
the hanging form and the flush single-action form. Given an admissible registry, the
parser MUST be a function: same bytes, same registry ⇒ same AST.

**D — Types.** Implements [doc 05](05-types-and-semantics.md), including no implicit
numeric widening, exhaustive choice matching, and mandatory failure handling.

**E — CIR.** Produces CIR-C per [doc 08](08-cir.md), runs the 24 verifier invariants in
dev builds, and computes the canonical hash per §8.7.

**F — Diagnostics.** Implements the taxonomy and style rules of
[doc 14](14-diagnostics.md), and provides a long form for every code it can emit.

**G — Memory.** Implements the storage ladder of
[doc 06](06-memory-and-safety.md) with at least: stack promotion via escape analysis,
region inference with promotion-not-failure, unique ownership, refcounting with the
elision pass, deterministic destruction, and static cycle detection with automatic weak
inference.

**H — Safety.** No conforming program exhibits use-after-free, double free, out-of-bounds
access, uninitialised read, or a data race, except through `trusted` modules.

**I — Concurrency.** Implements handler scheduling per
[doc 07](07-concurrency-and-simd.md), including the conflict relation, deterministic
group order and thread-count-independent reductions.

**J — Code generation.** Emits native code for at least one Tier 1 target. Builds are
reproducible per [doc 09 §9.9](09-compiler-pipeline.md).

**K — Vectorisation.** Meets the obligation of [doc 07 §7.9.1](07-concurrency-and-simd.md)
and provides `compose explain vectorisation`.

**L — Standard library.** Provides every `stable` signature of
[doc 11](11-stdlib.md) with the specified semantics and effects.

**M — Toolchain.** Provides the commands of [doc 12](12-toolchain.md), a formatter that
preserves the canonical hash, and a language server meeting
[doc 13 §13.5](13-lsp.md)'s latency budget.

## 15.3 The conformance suite **[N]**

The suite lives at `conformance/` in the reference repository and is versioned with the
edition. Each test is a directory:

```
conformance/parse/0231-empty-label/
  input.coco
  registry.signatures        (optional; defaults to core)
  expected.diagnostics.json
  expected.ast.json          (optional)
  expected.cir               (optional)
  expected.hash              (optional)
```

Runner:

```bash
compose conformance run                      # all
compose conformance run parse
compose conformance run --claim "2026 Core"
compose conformance report --format json
```

## 15.4 Suite contents **[N]**

| Suite | Tests (Edition 2026) | Checks |
| --- | ---: | --- |
| `lex` | 412 | tokens, INDENT/DEDENT, NFC, segmentation, digits, bidi rejection |
| `parse` | 1 186 | AST shape, greedy slots, hanging/flush forms, precedence, error recovery |
| `registry` | 298 | R1–R6 acceptance and rejection, overload families, user extension |
| `locale` | 240 per locale | L1–L5, translation round-trip, **hash equality across locales** |
| `types` | 903 | inference, defaulting, exhaustiveness, abilities, failure handling |
| `memory` | 517 | storage class decisions, promotion reports, aliasing rejection, cycle handling |
| `concurrency` | 344 | conflict groups, determinism, reduction reproducibility, race rejection |
| `cir` | 276 | verifier invariants, canonical ordering, encoding round-trip |
| `codegen` | 688 | semantics of every opcode on every claimed target |
| `repro` | 44 | double-build equality, path/time/env independence, format invariance |
| `stdlib` | 1 940 | every stable signature |
| `tooling` | 210 | manifest, lockfile, resolution, format, doc, assets |
| `lsp` | 168 | capabilities, extension messages, latency budget |

### 15.4.1 The locale-equivalence test **[N]**

For every program *P* in the `parse` and `types` suites and every claimed locale *L*:

```
assert canonical_hash(compile(P, en))
    == canonical_hash(compile(translate(P, en→L), L))
assert translate(translate(P, en→L), L→en) == format(P)
```

This is the mechanical proof of the multilingual claim, and it is why
[doc 04 §4.11](04-multilingual.md) forbids locales from touching anything but lexemes.

### 15.4.2 The determinism fuzz test **[N]**

`compose conformance fuzz` generates random admissible registries and random token
sequences and asserts that parsing is a function and that no input causes the parser to
consider two candidate parses. Implementations MUST pass 10⁷ iterations with no failures
before a release.

## 15.5 Performance expectations **[I]**

Not conformance requirements, but published targets against which the reference
implementation is tracked. Measured on a 2024-class 8-core laptop.

| Benchmark | Target |
| --- | --- |
| Cold build, 10 000 lines, dev | ≤ 1.5 s |
| Incremental rebuild, one body change | ≤ 120 ms |
| LSP `didChange` → diagnostics, p99 | ≤ 100 ms |
| Numeric loop (n-body, 1 024 bodies) | within 1.1× of C `-O2` |
| Text processing (word count, 1 GB) | within 1.2× of C |
| Allocation-free frame (particle demo, 200 000 particles) | 0 heap allocations per frame |
| Hello-world binary, release, stripped, x86-64 | ≤ 80 KB |
| Hello-world binary, `--small`, wasm32 brotli | ≤ 30 KB |
| Startup to first frame, UI app | ≤ 25 ms |

## 15.6 Editions **[N]**

```coco
this is edition 2026
```

- A file without an edition directive uses the project's edition; a project without one
  uses the oldest edition the toolchain supports, and warns.
- An implementation MUST compile every edition it claims, and MUST allow modules of
  different editions in one program — editions meet at CIR, which is edition-tagged per
  module.
- Within an edition, a program's meaning MUST NOT change. Bug fixes that would change
  meaning are gated behind the next edition and reported as `W-1501` until then.

### 15.6.1 What an edition may change **[N]**

| May change | May not change |
| --- | --- |
| Add reserved words | Remove a stable signature deprecated for < 1 edition |
| Add core signatures | Change the meaning of an existing signature |
| Change defaults (e.g. warning levels) | Change operator precedence |
| Remove long-deprecated signatures | Change the canonical hash algorithm without a new hash version tag |
| Tighten a check that previously warned | Change CIR opcode semantics |
| Add slot kinds | Reassign a CID |

### 15.6.2 Migration **[N]**

```bash
compose migrate --to 2029
```

MUST be mechanical for every change an edition makes, or the change is not permitted.
The tool reports any item it cannot migrate and leaves it on the old edition.

## 15.7 Versioning of the specification **[N]**

- This document set is the normative specification; its version is the edition year plus
  a revision (`2026.3`).
- Revisions may clarify, fix errata and add tests. A revision MUST NOT change what a
  conforming implementation accepts or what it means.
- Errata are tracked publicly with a test added to the suite for each.

## 15.8 Reference implementation status **[I]**

The implementation in `reference/` of this repository covers:

| Area | Status |
| --- | --- |
| Lexer: indentation, numbers, notes, separators, bidi rejection | ✔ |
| Lexer: LEX-UNSEG for unsegmented scripts (Japanese) | ✔ |
| Registry load and R1–R6 admissibility verification | ✔ |
| Head-anchored clause parsing with greedy slots and terminators | ✔ |
| The hanging explicit form and the flush single-action form | ✔ |
| Expressions with the full precedence table and non-associative comparison | ✔ |
| Member paths (`health of player`) and value splices (`value of score`) | ✔ |
| Declarations: `page`, `when`, `let`, `keep`, `the message`, layout blocks | ✔ |
| Locale binding, three locales (en, he, ja), slot-first reordering, splice order | ✔ |
| CIR-D emission, canonical ordering, canonical hash | ✔ |
| Message plural categories and placeholder checking | ✖ |
| Records, choices, abilities, `to` definitions, control flow | ✖ |
| Type checking, ownership and region inference | ✖ |
| CIR-C, the verifier, the optimiser, code generation | ✖ — see [doc 16](16-roadmap.md) |

The hash uses BLAKE2b rather than the specified BLAKE3, because BLAKE2b is in the Python
standard library and the reference has no dependencies; the tag on the hash records
which was used.

It exists to make the determinism and multilingual claims **executable** rather than
merely asserted. Its own test suite (`tests/run_tests.py`, 31 tests) checks one
normative claim per test and cites the section it comes from.

## 15.9 Trademark and naming **[N]**

An implementation that does not pass the suites it claims may not be called "Coco"
without qualification. "Coco-compatible" requires passing `lex`, `parse`, `registry`
and `cir`. This mirrors the practice of other language ecosystems and exists to keep the
Determinism Rule meaningful — a dialect that guesses is not Coco.

---

*Next: [16 — Implementation roadmap](16-roadmap.md)*
