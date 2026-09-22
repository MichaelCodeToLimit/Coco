# 06 — Memory and Safety

*Edition 2026. **[N]** normative, **[I]** informative.*

Coco's target: **Rust-class memory and data-race safety with zero annotations in
ordinary code, and no tracing garbage collector.** The programmer writes `keep score as 0`
and `damage Hero by 10`; the compiler decides stack vs. arena vs. unique heap vs.
reference counting, proves the absence of use-after-free, and proves the absence of data
races.

---

## 6.1 The guarantee **[N]**

A program that compiles under Coco Edition 2026 has, for all executions:

| Property | Guaranteed |
| --- | --- |
| No use-after-free | ✔ statically |
| No double free | ✔ statically |
| No null dereference | ✔ — there is no null; `maybe T` must be checked (`E-0541`) |
| No out-of-bounds access | ✔ — checked, with checks eliminated where provable |
| No uninitialised read | ✔ statically (definite-assignment analysis) |
| No data race | ✔ statically ([doc 07](07-concurrency-and-simd.md)) |
| No integer overflow surprise | ✔ — traps ([doc 05 §5.6](05-types-and-semantics.md)) |
| No leak | ✖ — leaks are safe and possible via reference cycles (§6.7) |
| No deadlock | ✖ — see [doc 07 §7.7](07-concurrency-and-simd.md) |

Unsafe escape hatches exist but are confined; see §6.9.

## 6.2 The storage ladder **[N]**

Every value is assigned exactly one **storage class** by the compiler. The compiler tries
them in this order and takes the first that is provably correct:

| # | Class | When chosen | Cost |
| --- | --- | --- | --- |
| 1 | **register / stack** | the value does not escape its defining frame and has statically known size | zero |
| 2 | **region (arena)** | the value escapes the frame but its lifetime is bounded by an enclosing *region* (a page render, a request, a frame, a handler invocation) | bump allocate, bulk free |
| 3 | **unique heap** | the value escapes with a single owner, freed at the owner's end of life | `malloc`/`free`, no refcount |
| 4 | **shared** | the value has multiple owners with lifetimes the compiler cannot order | non-atomic refcount if confined to one thread, atomic if shared across threads |
| 5 | **static** | compile-time constant | none |

The chosen class is **observable** to the programmer:

```bash
compose explain storage --in game.coco --for player
```

```
player  (game.coco line 12)
  storage class: region  (frame region, created at `when the world updates`)
  reason:        escapes `spawn a player at position` into `world entities`,
                 but every path that reads it is dominated by the frame region,
                 and no path stores it into anything outliving the region.
  cost:          bump allocation, 0 bytes of per-object metadata
```

This is Principle *Efficient* made inspectable: the programmer never writes the
annotation, but can always ask what was decided and why.

## 6.3 Ownership inference **[N]**

### 6.3.1 The ownership lattice

```
        shared
          │
        unique
       ╱      ╲
  borrowed    moved
```

Each **place** (a binding, a field path, a slot) carries an inferred **capability** at
each program point:

- `owns` — this place is responsible for the value's destruction;
- `borrows(r)` — this place holds a reference valid for region `r`;
- `shares` — this place holds a counted reference;
- `moved` — the value has been transferred away; reading is `E-0611`.

Inference is a **flow-sensitive, path-sensitive dataflow analysis** over the CIR's SSA
form, run per function and then propagated interprocedurally over the call graph in
reverse topological order (SCCs solved to fixpoint).

### 6.3.2 Capability rules **[N]**

For each CIR operation the analysis applies:

| Operation | Effect on capabilities |
| --- | --- |
| `bind x = v` (`let`) | `x` gains `owns` if `v` is a fresh value, otherwise `borrows(r)` where `r` is `v`'s region |
| `set p = v` | `p`'s old value is destroyed; `p` takes `v`'s capability; `v`'s place becomes `moved` if `v` was a place with `owns` and is not used afterwards |
| pass `v` into a slot declared `reads` | `v` is borrowed for the callee's activation region; `v` remains usable |
| pass `v` into a slot declared `takes` | `v` becomes `moved` |
| pass `v` into a slot declared `writes` | `v` is mutably borrowed; no other borrow of `v` may be live |
| `give v` | `v` escapes to the caller's region |
| store `v` into a field of `w` | `v`'s region must outlive `w`'s region; otherwise promote `v` up the ladder |

Slot *modes* (`reads` / `writes` / `takes`) are **inferred** for user-declared actions
and **declared** for library signatures. The inferred modes appear in
`compose registry show` and in LSP hover, so a library author sees them before
publishing.

### 6.3.3 The aliasing rule **[N]**

> At any program point, for any place *p*, either
> (a) there is at most one live `writes` borrow of *p* and no live `reads` borrows, or
> (b) there are any number of live `reads` borrows and no `writes` borrow.

This is the classic readers-writer discipline. Violations are reported as `E-0615` with
a plain-language explanation:

```
E-0615  Two things are changing `inventory of hero` at the same time.

  line 31 │   for each item in inventory of hero
          │                    ─────────────────  this loop is reading the list
  line 32 │     remove item from inventory of hero
          │                      ─────────────────  and this line changes it

  Reading a list while changing it would make the loop skip items.

  Fix: collect what to remove first.
      keep doomed as empty list
      for each item in inventory of hero
        if is broken of item
          add item to doomed
      for each item in doomed
        remove item from inventory of hero
```

Note what is absent: the words "borrow", "lifetime", "mutable reference". The analysis is
Rust's; the vocabulary is not.

## 6.4 Region inference **[N]**

Regions are inferred, not written. The region tree is built from *region introducers*,
which are the only places a new region can begin:

| Introducer | Region name | Freed |
| --- | --- | --- |
| an action body | `activation` | on return |
| a `when` handler body | `handler` | when the handler completes |
| a `page` render | `render` | when the page's next render begins |
| a `for each` body | `iteration` | each iteration, if nothing escapes |
| an explicit `during` block | user-named | at block exit |
| the program | `static` | never |

```coco
during this frame
  keep particles as empty list
  repeat 10000 times
    add a spark at random position to particles
  draw particles
note everything allocated inside the block is freed in one operation here
```

Region inference is a constraint problem:

1. Every allocation site gets a region variable ρ.
2. Each "value v stored into place p" generates `region(v) ⊒ region(p)` (v must outlive p).
3. Each "value v returned from region r" generates `region(v) ⊐ r`.
4. Solve by unification with the region tree's partial order; unsolvable ρ is promoted
   up the storage ladder (region → unique → shared).

This is MLKit-style region inference with the crucial difference that **failure is not an
error, it is a promotion**. Unlike Rust, an Coco program never fails to compile
because a lifetime is too short. It compiles, and pays for a heap allocation or a
refcount, and the compiler tells you:

```
note this is a note, not an error
I-0621  `spark` is reference counted here.
  It is stored into `world particles`, which lives longer than the frame.
  Cost: 8 bytes per spark, plus one increment when copied.
  If sparks do not need to outlive the frame, move `world particles`
  inside `during this frame`.
```

`compose check --show-promotions` lists all of them; a project may set
`deny promotions in <module>` in `project.coco` to turn them into errors for
performance-critical code.

## 6.5 Escape analysis **[N]**

Escape analysis is the first pass of region inference and also drives stack promotion.
A value *escapes* if it is:

- stored into a place whose region is not a descendant of the value's defining region;
- returned (`give`);
- captured by a closure or handler that outlives the defining region;
- passed to a slot whose mode is `takes` and whose callee stores it;
- passed across a device boundary ([doc 07 §7.6](07-concurrency-and-simd.md)).

Non-escaping values of statically known size are stack-allocated. Non-escaping
*collections* whose maximum size is provable (e.g. a `list of` with a proven bound) are
stack-allocated with a fixed capacity; otherwise they use the nearest region.

**Scalar replacement**: a non-escaping record whose fields are all independently used is
decomposed into separate SSA values and never materialised. This is why

```coco
let p be a point with
  x as 3
  y as 4
show text value of x of p
```

allocates nothing at all.

## 6.6 Destruction **[N]**

- Destruction is **deterministic**, at the end of the owning scope or region, in reverse
  declaration order.
- A record with a `to finish` action is destroyed by calling it, then destroying fields.
- Regions are destroyed by running finishers for any value in the region that has one,
  then releasing the arena in one operation. If no value in a region has a finisher —
  the common case — the region's teardown is a single pointer reset.
- `to finish` must not fail and must not block.

```coco
a file handle has
  raw as a whole number of 32 bits

to finish a file handle
  close the raw handle of the file handle
```

## 6.7 Reference cycles **[N]**

Values in the `shared` class are reference counted. Reference counting leaks cycles. The
compiler's response, in order:

1. **Static cycle detection on the type graph.** If the type graph containing a `shared`
   type has no cycle, no cycle can exist at runtime. This covers the large majority of
   programs and is reported as "cycle-free" by `compose check --memory`.
2. **Automatic weak inference.** If the type graph has a cycle and one of the edges is a
   *back edge* in the declaration's ownership direction (e.g. `child.parent`), the
   compiler makes it `weak` and reports it:

```
I-0631  `parent of node` is a weak link.
  Nodes own their children; a child pointing back at its parent would keep
  the parent alive forever. Reading it gives `maybe a node`.
```

3. **Explicit opt-in cycle collector.** If neither applies, the compiler emits `E-0632`
   and offers two fixes: make a link weak explicitly (`a weak link to`), or enable the
   optional cycle collector for that type:

```coco
a graph node may form cycles
  neighbours as a list of graph node
```

`may form cycles` opts a type into a **local, incremental trial-deletion collector**
(Bacon–Rajan) that runs only over values of opted-in types, only when their refcount is
decremented to a non-zero value, and never stops the world. This is the *only* garbage
collection in Coco, it is opt-in per type, and its cost is visible in
`compose explain storage`.

## 6.8 Bounds and definite assignment **[N]**

- Every indexed access is bounds-checked. The optimiser removes checks it can prove
  redundant via the range analysis in [doc 09 §9.5](09-compiler-pipeline.md); `compose
  explain bounds` lists which checks survived and why.
- `for each x in c` never bounds-checks.
- Definite assignment: a `keep` binding without an initialiser must be assigned on every
  path before use (`E-0641`). In practice `keep x as v` always initialises, so this
  applies only to `keep x` inside conditional initialisation, which `compose format`
  discourages.

## 6.9 The unsafe boundary **[N]**

Some things cannot be proven. They are confined to modules that opt in:

```coco
this module is trusted because it wraps the platform audio device
```

Inside a trusted module:

- `raw memory` operations from `sys` become visible;
- foreign function declarations are permitted;
- the compiler still performs all analyses and still reports promotions, but
  `assume` statements may discharge obligations:

```coco
assume buffer holds at least count samples
```

Rules:

1. Only a module with the `trusted because` declaration may use these.
2. The reason string is mandatory and appears in `compose audit`.
3. `compose audit` lists every trusted module, every `assume`, and every foreign
   declaration in the dependency graph, with a total count. A project may set
   `maximum trusted modules 0` in `project.coco` to forbid them, including in
   dependencies.
4. Trusted code is still bounds-checked and still type-checked. `assume` discharges only
   the specific named obligation.

## 6.10 Interaction with the storage ladder — worked example **[I]**

```coco
a particle has
  position as a point
  velocity as a point
  life as a decimal number

keep world particles as empty list

to spawn a burst at a place
  repeat 200 times
    add a particle with
      position as place
      velocity as random direction times 4
      life as 1
    to world particles

when the world updates
  during this update
    keep visible as empty list
    for each p in world particles
      set position of p to position of p plus velocity of p
      set life of p to life of p minus 0.016
      if life of p is more than 0
        add p to visible
    draw visible
  remove dead particles from world particles
```

What the compiler decides:

| Value | Class | Reason |
| --- | --- | --- |
| `place` | register | scalar pair, does not escape `spawn a burst` |
| the `a particle with …` literal | unique heap | escapes into `world particles`, single owner (the list) |
| `world particles` backing store | unique heap | module-level `keep`, single owner |
| `visible` backing store | region (`this update`) | never escapes the `during` block |
| the borrows of `p` in the loop | borrowed(`this update`) | mutation is through a single `writes` borrow at a time |
| `random direction times 4` | register | scalar-replaced, never materialised |

Net allocation per frame: **zero**, apart from the `visible` arena, which is a bump
pointer reset. No refcounts anywhere. No GC. The programmer wrote no annotations.

`compose explain storage --in particles.coco` prints exactly this table.

## 6.11 Why not just use a GC **[I]**

Because Principle *Efficient* names battery, startup time and data movement as
first-class concerns, and because Rule 4 forbids unpredictable pauses. The ladder above
gives:

- Zero-cost for the majority of values (classes 1, 2, 5).
- Predictable, deterministic destruction, which the `page` render model depends on.
- A cost model the programmer can query and act on.

The price is that cyclic data needs one extra declaration (`may form cycles`), which is
a small, well-signposted cost paid by a small fraction of programs.

---

*Next: [07 — Concurrency and SIMD](07-concurrency-and-simd.md)*
