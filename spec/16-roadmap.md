# 16 — Implementation Roadmap

*Edition 2026. **[I]** informative throughout — this is a plan, not a normative rule.*

This document exists because a specification without a credible build order is a wish.
Each stage below is independently useful and independently testable.

---

## 16.1 Stage 0 — Front end in a host language (weeks 1–8)

**Deliverable:** `coco0`, a lexer + registry + parser + CIR-D emitter, written in
Rust (the reference implementation in `reference/` of this repository is a Python sketch
of the same design, deliberately small enough to read in one sitting).

| Milestone | Test |
| --- | --- |
| Lexer with indentation, numbers, notes, text blocks | `conformance/lex` |
| Registry loader and R1–R6 verifier | `conformance/registry` |
| Clause parser with greedy slots | `conformance/parse` |
| Locale binding, `en` + `he` + `ja` | `conformance/locale` |
| CIR-D emitter + canonical hash | locale-equivalence test passes |

**Why first:** everything else depends on the registry and the parser being provably
deterministic. Getting the locale-equivalence test green here validates the entire
multilingual thesis before a single instruction is generated.

## 16.2 Stage 1 — Types, effects, and CIR-C (weeks 6–20)

| Milestone | Test |
| --- | --- |
| Hindley–Milner inference with signature-directed checking | `conformance/types` |
| Abilities and monomorphisation | `conformance/types` |
| Effect inference over the call graph | `conformance/concurrency` (effect parts) |
| CIR-C lowering, SSA construction | `conformance/cir` |
| The 24-invariant verifier | `conformance/cir` |

**Why here:** the verifier is what lets every later stage be developed aggressively
without risking unsoundness. Write it before the optimiser, not after.

## 16.3 Stage 2 — An CIR-C interpreter (weeks 14–22)

A straightforward tree-walking/threaded interpreter over CIR-C.

**Why it matters out of proportion to its size:**

- it makes `compose test` work before any code generation exists;
- it is the const-eval engine ([doc 05 §5.10](05-types-and-semantics.md));
- it is the replay engine ([doc 12 §12.9](12-toolchain.md));
- it is the bootstrap vehicle for stage 6;
- it gives an exact oracle for differential testing of the native back ends: run every
  `conformance/codegen` test on both and compare.

## 16.4 Stage 3 — Memory analysis (weeks 18–34)

Implemented in this order, each shippable:

1. **Escape analysis** → stack promotion and scalar replacement. Immediate, large win.
2. **Ownership/capability dataflow** → the aliasing rule, `E-0615`.
3. **Region inference** → arena allocation, `during` blocks.
4. **Refcounting + elision** for what remains.
5. **Static cycle detection + weak inference**, then the opt-in cycle collector.
6. `compose explain storage`.

Ship 1–2 with everything else refcounted; the language is already safe at that point, and
3–5 are pure performance. This ordering means the project is never blocked on the hardest
analysis.

## 16.5 Stage 4 — Cranelift back end (weeks 26–40)

| Milestone |
| --- |
| MIR lowering |
| Cranelift code generation for x86-64 and aarch64 |
| Runtime `core` layer (traps, regions, refcount, text, list, table) |
| `compose run` producing a real executable |
| Differential testing against the stage 2 interpreter |

At the end of stage 4 Coco is a usable systems language for command-line programs.

## 16.6 Stage 5 — Scheduler, LSP, toolchain (weeks 34–52)

| Track | Deliverable |
| --- | --- |
| Runtime | `sched` layer: work-stealing pool, handler groups, timers |
| Compiler | handler conflict analysis, `compose explain schedule` |
| Tooling | incremental query engine, `compose serve`, VS Code extension |
| Tooling | `project.coco`, lockfile, the Pantry (registry service), `compose add/publish` |
| Tooling | `compose format`, `compose doc`, `compose test` |

Stage 5 is where Coco becomes pleasant rather than merely possible. The LSP is not a
nice-to-have here: because completion is registry-driven
([doc 13 §13.2](13-lsp.md)), the editor is how people discover the language.

## 16.7 Stage 6 — Self-hosting (weeks 44–70)

Rewrite the compiler in Coco, module by module, starting with the lexer (smallest,
most testable) and ending with the back end.

The fixpoint check is unusually strong here:

```
hash(  stage0_rust.compile( compiler_source )  )   ==
hash(  stage2_coco.compile( compiler_source )  )
```

Because the canonical hash is locale- and format-invariant
([doc 08 §8.7](08-cir.md)), this equality is exact and independent of how either compiler
formats or orders anything.

## 16.8 Stage 7 — LLVM back end and optimisation (weeks 60–90)

| Milestone |
| --- |
| LLVM MIR lowering, `compose release` |
| Range analysis → bounds-check elimination |
| Loop nest optimiser |
| Auto-vectoriser + `compose explain vectorisation` |
| Layout selection (AoS/SoA) |
| LTO, PGO, `compose extreme` |
| `--verify-reproducible` in CI |

Target: n-body within 1.1× of C `-O2` ([doc 15 §15.5](15-conformance-and-editions.md)).

## 16.9 Stage 8 — The platform layers (weeks 70–120, parallel tracks)

These are independent and can proceed concurrently with separate teams.

| Track | Contents | Depends on |
| --- | --- | --- |
| **UI** | view diffing, layout engine, platform windowing (Win32/AppKit/Wayland), accessibility trees | stage 5 |
| **Draw2D** | GPU 2D renderer, SDF text | stage 4 |
| **Scene3D** | clustered forward+ renderer, glTF pipeline, `compose assets` | Draw2D |
| **Physics** | deterministic fixed-step solver, 2D then 3D | stage 4 |
| **Net** | HTTP/1.1, 2, 3; TLS; sockets; `serve` | stage 5 |
| **Store** | LSM B-tree, MVCC, WAL, compile-time query planning | stage 4 |
| **Device** | SPIR-V and WGSL back ends, transfers, `run on the gpu` | stage 7 |
| **Tensor** | tensor ops, AD on CIR-C, microkernels | Device |
| **WASM** | wasm32 back end, browser runtime, component model | stage 7 |

## 16.10 Sequencing rationale **[I]**

Three principles drove this ordering.

**1. Prove the risky claim first.** The novel part of Coco is punctuation-free
determinism and locale-invariant IR. That risk is fully retired at the end of stage 0,
for eight weeks of work, before anything expensive is built. If the locale-equivalence
test cannot be made green, the design is wrong and should change then — not after a
back end exists.

**2. Safety before speed, verifier before optimiser.** The memory and effect analyses
define what the language *is*. The optimiser only makes it faster. Building the verifier
in stage 1 means every later optimisation is guarded.

**3. Nothing blocks on the hardest thing.** Region inference (stage 4.3) is the most
sophisticated analysis in the compiler. It is deliberately sequenced *after* the language
is already complete and safe with plain refcounting, so a delay there delays performance,
not usability.

## 16.11 Team shape and estimate **[I]**

| Stage | People | Calendar |
| --- | --- | --- |
| 0–2 (front end, types, interpreter) | 2–3 | ~5 months |
| 3–4 (memory, Cranelift, runtime core) | 3–4 | ~4 months, overlapping |
| 5 (scheduler, tooling, LSP) | 3–4 | ~4 months, overlapping |
| 6 (self-host) | 2–3 | ~6 months, overlapping |
| 7 (LLVM, optimiser) | 2–3 | ~7 months, overlapping |
| 8 (platform) | 6–10 across tracks | ~12 months, overlapping |

**Roughly 2.5 years and 10–15 engineers to Edition 2026 Full**, with a usable systems
language at ~10 months (end of stage 4) and a self-hosting one at ~18 months.

For comparison: Rust took about 9 years from first commit to 1.0 with a larger team, but
without the benefit of hindsight on borrow checking. Go took 3 years to 1.0. Coco's
front end is *simpler* than either — the registry does the work a hand-written parser
normally does — and its hard parts (region inference, the optimiser) are well-trodden
ground with published algorithms.

## 16.12 What to build first if you only have one person **[I]**

Stage 0, then stage 2's interpreter, then the VS Code extension from stage 5. That
combination — a deterministic parser, an interpreter that runs programs, and an editor
that teaches the language through completion — is a real, demonstrable Coco that a
beginner can learn from, in roughly four months of focused work, and it is enough to find
out whether the language is actually pleasant to write.

Everything after that is engineering with known techniques.

---

*Back to [00 — Overview](00-overview.md) · [README](../README.md)*
