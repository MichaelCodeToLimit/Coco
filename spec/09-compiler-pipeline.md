# 09 — Compiler Pipeline

*Edition 2026. **[N]** normative, **[I]** informative.*

---

## 9.1 Phases **[N]**

```
 1  read + normalise        bytes → NFC UTF-8
 2  locale bind             resolve `write in`, load locale, build lexicon
 3  registry build          core + stdlib + deps + user; check R1..R6   [doc 03]
 4  lex                     tokens, INDENT/DEDENT                       [doc 01]
 5  collect                 pass 1: declaration heads, names, signatures
 6  parse                   pass 2: bodies → AST                        [doc 02]
 7  resolve                 names → CIDs; `use` graph; prelude
 8  type check              inference, abilities, exhaustiveness        [doc 05]
 9  effect infer            effect sets per action and handler          [doc 07]
10  ownership + region      storage ladder, borrows, escape             [doc 06]
11  lower to CIR-D          declarative + imperative                    [doc 08]
12  monomorphise            generics, abilities → concrete functions
13  lower to CIR-C          SSA, regions materialised
14  verify                  24 invariants                               [doc 08 §8.8]
15  canonicalise            ordering + hash                             [doc 08 §8.6]
16  optimise                CIR-C → CIR-C passes                        §9.5
17  lower to MIR            target-shaped, still portable
18  codegen                 Cranelift | LLVM | SPIR-V | WGSL            [doc 10]
19  link                    native link, or WASM link, or bundle
20  emit                    binary + side tables + `.coco.hash`
```

Phases 1–15 are **target independent** and produce the canonical artefact. Phases 16–20
depend on the target and optimisation level.

## 9.2 Incremental compilation **[N]**

The unit of change tracking is the **item** (an action, handler, page, record, choice or
binding), keyed by CID.

- Each item's inputs are hashed: its AST, the CIDs it references, and the *interface*
  hash of each referenced item (signature + type + effects, not body).
- A body change invalidates only that item's phases 8–18.
- An interface change invalidates dependents transitively.
- The registry is rebuilt incrementally; R1–R6 are re-checked only for the affected trie
  subtrees.
- Query results are stored in `.coco/cache` keyed by input hash, so a rebuild after
  `git checkout` of a previously built revision is a cache hit.

Target: **sub-100 ms** edit-to-diagnostic for a single-item change in a 100 000-line
project, which is what makes the LSP experience in [doc 13](13-lsp.md) possible.

## 9.3 Optimisation levels **[N]**

| Command | Level | Back end | Character |
| --- | --- | --- | --- |
| `compose` | `dev` | Cranelift | fastest build, full checks, full debug info, hot reload |
| `compose release` | `release` | LLVM `-O2`-equivalent + Coco passes | balanced; the default for shipping |
| `compose extreme` | `extreme` | LLVM `-O3` + LTO + PGO + auto-device | longest build, maximum throughput |
| `compose release --small` | `small` | LLVM `-Oz` + section GC | minimum binary size (WASM, embedded) |

Normative: **safety checks are never removed by an optimisation level.** Overflow traps,
bounds checks and `maybe` checks are eliminated only when *proved* redundant. There is no
`--unsafe-fast` flag. This is Rule 4 of [doc 00](00-overview.md).

### 9.3.1 What each level actually does **[N]**

| Pass | dev | release | extreme | small |
| --- | :-: | :-: | :-: | :-: |
| Const-eval + const folding | ✔ | ✔ | ✔ | ✔ |
| Scalar replacement of aggregates | ✔ | ✔ | ✔ | ✔ |
| Region promotion (stack/arena) | ✔ | ✔ | ✔ | ✔ |
| Dead code / dead object elimination | ✔ | ✔ | ✔ | ✔ |
| Inlining (heuristic) | small | full | aggressive + cross-module | size-limited |
| Bounds-check elimination | basic | full range analysis | full + speculative with guard | full |
| Refcount elision | ✔ | ✔ | ✔ | ✔ |
| Struct-of-arrays layout selection | ✖ | ✔ | ✔ | ✖ |
| Loop transforms (unroll, fuse, interchange, tile) | ✖ | ✔ | ✔ | ✖ |
| Auto-vectorisation | ✖ | ✔ | ✔ | limited |
| Link-time optimisation | ✖ | thin | full | full |
| Profile-guided optimisation | ✖ | if profile present | required (auto-collects) | ✖ |
| Automatic device offload | ✖ | ✖ | opt-in `--auto-device` | ✖ |
| Multiversioned vector paths | ✖ | ✖ | ✔ | ✖ |
| Debug info | full | line tables | line tables | none |

## 9.4 Front-end details **[N]**

### 9.4.1 Two-pass parsing

Pass 1 (*collect*) reads only declaration heads. It needs no body parsing and therefore
no user-declared signatures, so it can run with the fixed lexicon
(locale + registry). It produces:

- the visible name set (needed by `ref` slots and by LEX-UNSEG for unsegmented scripts);
- the user signature additions (needed by the registry).

The registry is then re-checked for R1–R6 with the user additions. Only then does pass 2
parse bodies. This is why forward references work and why a program can call an action
declared later in the file.

### 9.4.2 Error recovery **[N]**

The parser recovers at **statement boundaries** using indentation, which is far more
reliable than token-based recovery:

- On error, skip to the next `NEWLINE` at the same or lower indentation level.
- Insert an `error` AST node so later phases still run and still report.
- Never cascade: an item containing a parse error is type-checked in isolation with
  `anything` for the failed sub-expression, and errors caused solely by that are
  suppressed.

A file with *n* independent errors reports *n* diagnostics, not *n*².

## 9.5 Middle-end passes **[N]**

Run on CIR-C, each preserving the verifier invariants (which are re-checked after every
pass in dev builds).

| Pass | Purpose | Enables |
| --- | --- | --- |
| **const-eval** | evaluate `pure` module bindings and calls with constant args | folding, table generation |
| **SROA** | split non-escaping records into SSA values | register allocation |
| **mem2reg-equivalent** | promote region slots with no address taken | everything |
| **GVN + PRE** | remove redundant computation | bounds checks |
| **range analysis** | derive integer ranges from branches, loop bounds, list lengths | bounds-check elimination, overflow-check hoisting |
| **bounds elision** | remove `list.get` checks proved in range | vectorisation |
| **refcount elision** | remove `retain`/`release` pairs where the value provably outlives the use (ownership-based, not runtime) | allocation-free loops |
| **region promotion** | move allocations down the storage ladder when escape facts allow | zero-alloc frames |
| **layout selection** | choose AoS vs SoA per collection from field access patterns | SIMD |
| **loop nest optimiser** | unroll, fuse, interchange, tile, distribute | cache behaviour |
| **vectoriser** | emit `vec<T,n>` operations | SIMD ([doc 07 §7.9](07-concurrency-and-simd.md)) |
| **inliner** | cross-item and cross-module under LTO | everything |
| **device splitter** | extract `run on the gpu` regions into device functions | SPIR-V/WGSL |
| **handler scheduler** | compute conflict groups, emit the schedule table | parallel dispatch |
| **shrink** | dead-object, dead-field, dead-variant elimination | size |

### 9.5.1 Why refcount elision works so well here **[I]**

In most reference-counted languages, elision is limited because the compiler cannot prove
that a value is not also held elsewhere. Coco's ownership analysis
([doc 06 §6.3](06-memory-and-safety.md)) has already partitioned every place into
`owns` / `borrows(r)` / `shares`. A `retain`/`release` pair around a `borrows(r)` use
whose region `r` is nested inside the owner's region is *provably* redundant. The pass
is therefore a simple traversal, not a heuristic — and most values never enter the
`shared` class at all.

## 9.6 Monomorphisation **[N]**

- Generic actions and generic library signatures are monomorphised per distinct type
  argument tuple.
- Ability dispatch is resolved statically at monomorphisation time; `any thing that can
  draw` produces a vtable and a dynamic call, everything else is direct.
- **Instantiation explosion control**: the compiler tracks instantiation count per
  generic; above `maximum instantiations` (default 4 096 per generic) it switches that
  generic to dynamic dispatch and reports `I-0961` with the count. This bounds compile
  time and binary size without changing semantics.
- Monomorphised CIDs are `base-cid#type-cid,type-cid`, which keeps them stable across
  builds and therefore keeps the canonical hash stable.

## 9.7 Profile-guided optimisation **[N]**

```bash
compose extreme --profile-from profiles/       # use recorded profiles
compose run --record-profile profiles/         # collect
```

- Profiles record block execution counts, branch outcomes, indirect call targets and
  allocation sizes per site, keyed by CID — **not** by source position, so profiles stay
  valid across formatting and translation.
- A profile from an English build is valid for the Hebrew translation of the same
  program, because the CIDs are identical. This is a direct dividend of
  [doc 08 §8.7](08-cir.md).
- `compose extreme` without a profile performs a two-stage build: instrument, run the
  project's `to profile` action (if declared), then rebuild. Projects without one fall
  back to static heuristics and report `I-0971`.

## 9.8 Compile-time budgets **[N]**

An implementation MUST enforce and report:

| Budget | Default | Flag |
| --- | --- | --- |
| Const-eval steps | 10⁸ | `--const-eval-budget` |
| Monomorph instances per generic | 4 096 | `--max-instantiations` |
| Inliner growth factor | 3× per item (release) | `--inline-growth` |
| Total compile wall time | none | `--time-budget` (reports, does not fail) |
| Peak compiler memory | none | `--memory-budget` (fails cleanly if exceeded) |

Exceeding a budget produces a diagnostic naming the item responsible, never a hang.

## 9.9 Determinism of the compiler itself **[N]**

The compiler MUST be deterministic:

- identical inputs (source, deps, target, flags, toolchain version) ⇒ byte-identical
  output;
- no timestamps, absolute paths, hostnames, or environment leakage in the output
  (paths are stored relative to the project root; `--remap-path` handles external deps);
- parallel compilation MUST NOT affect output — each phase's output is sorted
  canonically before the next phase consumes it;
- hash-map iteration MUST NOT influence output; all compiler maps used for code emission
  are ordered.

`compose build --verify-reproducible` builds twice in separate directories and compares.
This is a conformance requirement ([doc 15](15-conformance-and-editions.md)).

## 9.10 Diagnostics as a first-class output **[N]**

Every phase emits structured diagnostics ([doc 14](14-diagnostics.md)) carrying:

```
code, severity, primary span, secondary spans with labels,
explanation, fix-its (each a set of text edits), related CIDs
```

The same structure serves the terminal renderer, the LSP, `compose explain`, and the JSON
output consumed by CI (`--message-format json`).

## 9.11 Bootstrap **[I]**

See [doc 16](16-roadmap.md) for the full plan. In outline:

1. **Stage 0** — a front end in a host language (the reference implementation in this
   repository) that produces CIR-C.
2. **Stage 1** — an CIR-C interpreter, enough to run the Coco-written parts of the
   compiler.
3. **Stage 2** — the Coco compiler written in Coco, compiled by stage 0 + stage 1.
4. **Stage 3** — stage 2 compiles itself; the fixpoint is checked by comparing canonical
   hashes of stage 2's and stage 3's output. Because the hash is locale- and
   format-invariant, this check is exact.

---

*Next: [10 — Backends, targets and ABI](10-backends-targets-abi.md)*
