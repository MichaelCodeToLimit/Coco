# 07 — Concurrency, Parallelism and SIMD

*Edition 2026. **[N]** normative, **[I]** informative.*

Coco's concurrency story follows the same shape as its memory story: the programmer
describes *what may happen*, the compiler decides *how it runs*, and the result is
statically race-free.

There is no `thread` keyword, no mutex, no `async`/`await`, and no colouring of
functions. There are handlers, effects, and a scheduler.

---

## 7.1 The execution model **[N]**

An Coco program is:

```
  a set of declared state      (module-level `keep` bindings, pages, records)
+ a set of handlers            (`when …` blocks)
+ a set of actions             (`to …` definitions)
```

The runtime repeatedly:

1. collects **pending events** (input, timers, network completions, device completions,
   page invalidations);
2. computes, for each event, the set of handlers that match;
3. partitions the matched handlers into **non-conflicting groups** using the static
   conflict relation of §7.3;
4. runs each group's handlers **in parallel** on a work-stealing pool;
5. runs groups in a **deterministic order** (§7.5).

This is an ECS/actor hybrid. It is how "when player touches enemy → remove 10 health
from player" can safely become 16-way-parallel collision handling without the programmer
knowing threads exist.

## 7.2 Effects **[N]**

Every signature carries an effect set. Effects are **inferred** for user code and
**declared** for library signatures; the inferred set appears in hover and in
`compose registry show`.

| Effect | Meaning |
| --- | --- |
| `reads S` | reads the state paths in *S* |
| `writes S` | writes the state paths in *S* |
| `io` | observable interaction with the outside world (screen, file, socket) |
| `blocks` | may suspend waiting on the outside world |
| `device D` | executes on device *D* (`cpu`, `gpu`, `npu`) |
| `allocates` | may allocate outside the current region |
| `random` | consumes the deterministic entropy stream (§7.8) |
| `time` | reads the clock |

*S* is a set of **state paths** — rooted at a module-level `keep` binding, a page's
state, or a parameter, and refined by field and index:

```
world particles
world particles [*] . position          (* every element's position field *)
current user . name
```

Path refinement is what makes the conflict relation precise enough to be useful: two
handlers that both touch `world particles` but one only reads `.position` and the other
only writes `.life` do **not** conflict.

## 7.3 The conflict relation **[N]**

Two handlers *h₁*, *h₂* **conflict** iff

```
writes(h₁) ∩ (reads(h₂) ∪ writes(h₂)) ≠ ∅
  ∨ writes(h₂) ∩ reads(h₁) ≠ ∅
  ∨ (io ∈ effects(h₁) ∧ io ∈ effects(h₂) ∧ same io channel)
```

where path intersection is computed with the prefix-and-wildcard algebra of §7.2.

Non-conflicting handlers run in parallel. Conflicting handlers are **serialised in the
deterministic order of §7.5**.

Because the relation is static, the schedule shape is known at compile time and can be
inspected:

```bash
compose explain schedule --for the world updates
```

```
the world updates  →  3 groups

  group 1  (parallel, 4 handlers)
    physics step            writes world particles[*].position
    decay particles         writes world particles[*].life
    spin turrets            writes world turrets[*].angle
    advance animations      writes world sprites[*].frame
      ↳ no pairwise conflicts: disjoint field paths

  group 2  (serial, 2 handlers)
    collide player          reads world particles[*].position, writes player.health
    collide enemies         reads world particles[*].position, writes enemies[*].health
      ↳ serialised: both read a path group 1 writes

  group 3  (serial, 1 handler)
    draw frame              io screen
```

## 7.4 Data-race freedom theorem **[I]**

> **Theorem.** If every handler's effect set soundly over-approximates the state paths it
> touches, and handlers are scheduled per §7.3, then no two concurrently executing
> operations access the same memory location with at least one write.

*Sketch.* Two operations run concurrently only if their handlers are in the same group.
Handlers in a group are pairwise non-conflicting, so their write sets are disjoint from
each other's read and write sets. Path soundness is guaranteed by the effect inference
being a conservative dataflow over the ownership analysis of
[doc 06 §6.3](06-memory-and-safety.md): any write through a place *p* contributes the
path of *p*'s root, widened to `[*]` wherever the index is not a compile-time constant.
Borrows across handler boundaries are impossible because a handler body is a region
introducer and borrows cannot escape their region. ∎

The remaining hole is `trusted` modules (§6.9), which the theorem excludes and
`compose audit` enumerates.

## 7.5 Determinism of scheduling **[N]**

Parallel execution must not make program output depend on thread timing. Coco
guarantees:

1. **Deterministic group order.** Groups run in the order produced by a topological sort
   of the conflict graph, with ties broken by a total order on handlers:
   (module path, declaration line, declaration column). This order is a property of the
   source, not of the machine.
2. **Deterministic intra-group results.** Handlers in a group have disjoint write sets,
   so their interleaving is unobservable.
3. **Deterministic reductions.** Parallel reductions over floating point use a
   **fixed tree shape** determined by the input length, not by the number of worker
   threads, so `sum of a list of decimal numbers` is bit-reproducible regardless of core
   count. Implementations MUST NOT use a thread-count-dependent reduction tree.
4. **Deterministic collection order.** `for each` over a `table` iterates in insertion
   order. Hash iteration order is never exposed.
5. **Deterministic entropy** — §7.8.

Consequence: a program's output is a function of its inputs, not of the machine it runs
on. `compose test` relies on this; so does replay debugging
([doc 12 §12.9](12-toolchain.md)).

## 7.6 Explicit parallelism and devices **[N]**

The handler model covers event-driven parallelism. Data parallelism is expressed with
`for each … at the same time`:

```coco
for each pixel in image at the same time
  set colour of pixel to brighten colour of pixel by 0.2
```

The compiler must **prove independence** to accept this (`E-0721` if it cannot):
iteration *i* must not read a location written by iteration *j*. The proof uses the same
path algebra plus affine index analysis. When the proof fails, the diagnostic names the
dependency:

```
E-0721  These steps cannot happen at the same time.
  line 8 │     set colour of pixel to blend of pixel and previous pixel
         │                                              ──────────────
         │  each step reads the pixel the step before it wrote.
  Fix: remove `at the same time`, or compute into a second image.
```

Device placement:

```coco
run on the gpu
  for each pixel in image at the same time
    set colour of pixel to brighten colour of pixel by 0.2
```

`run on the gpu` is a region introducer that:

- requires every signature used inside to carry `device gpu` or be `device any`;
- makes values crossing the boundary **explicitly transferred** — the compiler inserts
  the copy and reports its size in `compose explain transfers`;
- lowers the body to SPIR-V or WGSL ([doc 10 §10.5](10-backends-targets-abi.md)).

If `run on the gpu` is omitted, the compiler MAY still place a proven-independent,
sufficiently large loop on an available device when compiling with
`compose extreme --auto-device`, but MUST report every such placement, and MUST NOT do so
when it would change floating-point results (per §7.5.3).

## 7.7 Blocking, waiting and async **[N]**

There is no `async` keyword and no function colouring. Instead:

- A signature with effect `blocks` may suspend. Calling it from a handler suspends the
  **handler**, not the thread: the runtime parks the handler's continuation and runs
  other groups.
- The compiler knows `blocks` transitively, so it knows which handlers can suspend and
  allocates them segmented/growable stacks; non-blocking handlers run on the worker's
  own stack with zero overhead.
- Concurrency inside a handler:

```coco
when the page opens
  fetch these at the same time
    let profile be get from https example com api me
    let feed be get from https example com api feed
  show profile and feed
```

`fetch these at the same time` starts each binding's blocking operation, then resumes
when all complete. It is the only "await" the language has, and it reads as English.

Timeouts and cancellation:

```coco
try
  wait at most 3 seconds for
    let data be get from https example com api slow
or
  show text The server is slow
```

Cancellation is **structured**: cancelling a `wait at most` block cancels everything
started inside it, and the region's finishers run.

### 7.7.1 Deadlock **[N]**

Coco does not statically prevent deadlock; a handler can wait on something that never
completes. It mitigates it:

- there are no user-visible locks to take in the wrong order;
- every `blocks` operation in the standard library takes a deadline, defaulting to the
  project's `default deadline` (30 seconds) rather than infinity;
- the runtime's watchdog reports a handler that has been parked longer than its deadline,
  with the full parked-handler graph, under `compose` (dev) builds.

## 7.8 Determinism of randomness and time **[N]**

- `random number between a and b` has effect `random` and draws from a per-handler
  deterministic stream seeded from `(project seed, handler CID, invocation index)`.
- `compose test` and `compose run --record` fix the project seed, so runs reproduce.
- `compose run --release` seeds from the OS entropy pool unless `fixed seed` is set.
- `now` has effect `time`. Under `--record`, clock reads are recorded; under `--replay`
  they are served from the recording. This makes replay debugging exact.

## 7.9 Automatic vectorisation (SIMD) **[N]**

Vectorisation is **not** a user-visible feature; it is an obligation on the compiler.

### 7.9.1 Requirement

> An implementation claiming Edition 2026 conformance MUST vectorise a `for each` loop
> over a contiguous collection of a primitive or scalar-replaceable record type when:
> (a) the loop body is free of `io`, `blocks` and `allocates` effects;
> (b) loop-carried dependencies are absent, or are a recognised reduction
>     (`sum`, `product`, `minimum`, `maximum`, `count where`);
> (c) all memory accesses are affine in the loop index;
> (d) the target has a vector unit of width ≥ 128 bits.

### 7.9.2 How the earlier analyses make this easy **[I]**

Auto-vectorisation is hard in C because aliasing is unknown. In Coco it is
straightforward because the ownership analysis has already proved the aliasing facts:

- **No aliasing between distinct owned collections** is a *theorem* from §6.3.3, not a
  guess. There is no `restrict` to forget to write.
- **Element type layout is chosen by the compiler**, so a `list of particle` may be
  stored **struct-of-arrays** when the compiler sees that loops touch fields
  independently. This is the single largest SIMD win and is impossible in languages where
  the programmer fixes the layout. The decision is reported:

```
I-0791  `list of particle` is stored as separate arrays per field.
  Loops in `physics step` and `decay particles` touch `position` and `life`
  independently. Field order in memory: position.x, position.y, velocity.x,
  velocity.y, life.
  If you need the fields adjacent (for a C interface), write
    a particle is laid out together
```

- **Regions give alignment for free.** A region allocator can align every collection to
  the target's vector width at zero cost, so no unaligned prologue is needed.
- **Overflow traps are hoisted, not disabled.** For `whole number` loops the compiler
  computes the range of the accumulator from the loop bound and hoists a single check
  before the loop when the range is provable, keeping §5.6's guarantee inside vectorised
  code.

### 7.9.3 Vector width and portability **[N]**

The compiler emits **width-agnostic vector IR** (LLVM scalable vectors / Cranelift vector
types) and specialises per target:

| Target | Widths used |
| --- | --- |
| x86-64 baseline | SSE2 128-bit |
| x86-64-v3 | AVX2 256-bit |
| x86-64-v4 | AVX-512 512-bit, with a 256-bit fallback path |
| aarch64 | NEON 128-bit |
| aarch64+sve | SVE/SVE2 scalable |
| wasm32 | `simd128` when enabled |

`compose release --cpu native` specialises for the build machine. For distributed
binaries, `compose release --multiversion` emits several code paths for the hottest
vectorised loops with a one-time CPU-feature dispatch at startup; `compose explain
vectorisation` lists which loops were multiversioned and why.

### 7.9.4 Reporting **[N]**

An implementation MUST provide `compose explain vectorisation`, listing for every
candidate loop: whether it vectorised, at what width, and if not, the precise reason
(dependency, non-affine access, effect, unknown trip count). A missed vectorisation is a
diagnostic with a fix-it wherever a mechanical rewrite would enable it.

```
game.coco line 44  `for each p in world particles`
  ✔ vectorised, width 8 (AVX2), struct-of-arrays layout
  reduction: none
  bounds checks: hoisted (1 check before the loop)

image.coco line 12 `for each pixel in image`
  ✖ not vectorised
  reason: `blend of pixel and previous pixel` reads the previous iteration's write
  fix-it: compute into a second image (press . to apply)
```

## 7.10 Memory ordering **[N]**

Programmers never write atomics. The runtime uses them in three places, all specified:

1. Reference counts for `shared` values touched by more than one worker: relaxed
   increment, release decrement with acquire fence before destruction.
2. The work-stealing deque: standard Chase–Lev with the published orderings.
3. Handler group completion: release/acquire on the group barrier.

Because group boundaries are barriers and groups have disjoint write sets, a handler
always observes the complete effects of all groups that preceded it and never observes a
partial effect of a concurrent handler. This is **sequential consistency at the handler
level**, which is the only level the programmer can observe.

---

*Next: [08 — Coco IR](08-cir.md)*
