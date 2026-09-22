# 05 — Types and Semantics

*Edition 2026. **[N]** normative, **[I]** informative.*

Coco is statically and strongly typed with complete local inference. A beginner never
writes a type; a library author writes them only in record fields and public signatures.

---

## 5.1 The type lattice **[N]**

```
                      anything            (* only in error recovery; not writable *)
                          │
   ┌──────────┬───────────┼───────────┬──────────────┬────────────┐
 number     text      yes or no     nothing       record        choice
   │                                                 │             │
 ┌─┴─┐                                          list of T    maybe T
whole decimal                                   table of K to V
```

### 5.1.1 Primitive types **[N]**

| Source name | Representation | Notes |
| --- | --- | --- |
| `whole number` | 64-bit two's complement | wrapping is an error, see §5.6 |
| `decimal number` | IEEE-754 binary64 | |
| `text` | UTF-8, immutable, length-prefixed, small-text-optimised | |
| `yes or no` | 1 byte, values `yes` / `no` | |
| `nothing` | zero-sized | the result of a statement |

Fixed-width types exist for interop and are spelled out: `whole number of 8 bits`,
`whole number of 32 bits`, `decimal number of 32 bits`. They are used by the `sys`,
`tensor` and `scene3d` modules and are rarely written by hand.

### 5.1.2 Composite types **[N]**

| Source | Meaning |
| --- | --- |
| `list of T` | growable, contiguous, O(1) index |
| `table of K to V` | hash map, K must be hashable |
| `maybe T` | either a T or `nothing` |
| a declared record | product type, field order = declaration order |
| a declared choice | tagged union, niche-optimised |

## 5.2 Declarations **[N]**

```coco
a player has
  health as a whole number starting at 100
  name as text
  inventory as a list of item

a shape is one of
  circle with radius as a decimal number
  rectangle with width as a decimal number and height as a decimal number
  empty
```

- Record fields with `starting at` get that default in `a player with …` literals that
  omit them.
- A record is **structurally distinct** from every other record: two records with the
  same fields are different types (nominal typing).
- A choice with no payload variants compiles to a single byte; a choice with payloads
  uses niche optimisation when a variant has spare bit patterns.

Constructing and matching:

```coco
let hero be a player with
  name as Ada
  health as 120

let s be a circle with radius as 2.5

if s is a circle
  show text Radius is value of radius of s
```

`if <ref> is a <variant>` is the matching form; inside the body, the variant's fields are
in scope. Exhaustive matching over all variants:

```coco
for the shape s
  when it is a circle
    give 3.14159 times radius of s times radius of s
  when it is a rectangle
    give width of s times height of s
  when it is empty
    give 0
```

`for the <ref>` + `when it is …` is the total-match form; the compiler requires every
variant to be covered (`E-0512`) and rejects duplicate arms (`E-0513`).

## 5.3 Type inference **[N]**

Inference is **Hindley–Milner with rank-1 polymorphism, local to a declaration body**,
extended with:

- **Defaulting.** An unconstrained numeric literal defaults to `whole number` if it has
  no fractional part and `decimal number` otherwise.
- **No implicit widening.** `whole number` does not convert to `decimal number`
  implicitly (`E-0521`). Write `5 as a decimal number`. This is required by the
  Determinism Rule: implicit coercion would make overload resolution depend on a
  preference order.
- **Signature-directed checking.** Because every call site is a signature match, argument
  types are known before the argument is inferred, so inference never needs to solve
  across call boundaries. Bodies are checked in dependency order; recursion requires the
  declaration to state its result type:

```coco
to factorial of a number giving a whole number
  if number is at most 1
    give 1
  give number times factorial of group
    number minus 1
```

- **Generics** come from library signatures only. The core has a small set:

```sig
signature length of
  slot collection of kind value
  gives a whole number
  for any element type

signature add
  slot item of kind value
  particle to
    slot collection of kind ref
  gives nothing
  for any element type
```

Users write generic actions with `for any`:

```coco
to swap the first and second of a pair for any kind
  ...
```

Monomorphisation is the default; see [doc 09 §9.6](09-compiler-pipeline.md).

## 5.4 Subtyping **[N]**

There is **no subtyping** and **no inheritance**. Polymorphism is by:

1. parametric generics (`for any T`);
2. **abilities** — Coco's trait/interface mechanism:

```coco
an ability to draw needs
  to draw the thing into a surface

a circle can draw
  to draw the thing into a surface
    draw a filled circle at position of thing with radius of thing into surface

to render everything in a list of things that can draw into a surface
  for each thing in things
    draw thing into surface
```

Abilities are resolved statically. Dynamic dispatch is available explicitly:

```coco
let shapes be a list of any thing that can draw
```

which compiles to a fat pointer (data pointer + vtable pointer). There is no implicit
boxing (Rule 4).

## 5.5 Mutability **[N]**

| Form | Meaning |
| --- | --- |
| `let x be v` | immutable binding; `x` can never be reassigned, and the value it names can never be mutated through `x` |
| `keep x as v` | mutable binding |
| `set x to v` | assignment; `x` MUST be a `keep` binding or a field of one |

A value reached through an immutable binding is immutable transitively. A `keep` binding
inside a record field is expressed by the field itself — all record fields are mutable if
the record is reached through a mutable path, and immutable otherwise. This is
*path-based mutability*, which is what the borrow inference in
[doc 06](06-memory-and-safety.md) uses.

## 5.6 Arithmetic and overflow **[N]**

| Situation | Behaviour |
| --- | --- |
| `whole number` overflow in `compose` (dev) | trap, with a diagnostic naming the operation |
| `whole number` overflow in `compose release` | trap (same) |
| `whole number` overflow in `compose extreme` | trap; the check is hoisted/eliminated where the optimiser can prove it cannot fire, never simply disabled |
| Division by zero | trap |
| `decimal number` overflow | IEEE-754 infinities; no trap |
| Explicit wrapping | `wrapping sum of a and b` from `math` |
| Explicit saturation | `saturating sum of a and b` from `math` |

Overflow is **never** undefined behaviour and is **never** silently wrapped. Rule 4
forbids a construct with unpredictable machine behaviour; Principle *Easy* forbids
surprising a beginner with `2147483647 plus 1` being negative.

## 5.7 Text semantics **[N]**

- `text` is a sequence of Unicode **scalar values**, stored as UTF-8.
- `length of t` is the number of **extended grapheme clusters** (UAX #29), because that
  is what a non-programmer means by "how long is this". `scalar count of t` and
  `byte count of t` are available in the `text` module.
- Indexing is by grapheme cluster and is O(n); the compiler warns (`W-0533`) when a loop
  indexes text repeatedly and suggests `for each character in t`.
- Comparison `is` on text is by **canonical equivalence** (NFC-normalised code point
  sequence). Locale-sensitive collation is explicit: `compare a and b using locale l`.
- Concatenation is `join`; there is no `plus` on text (`E-0534` with a fix-it), because
  overloading `plus` across numbers and text is a classic beginner trap.

## 5.8 `maybe` and failure **[N]**

There are no exceptions with unwinding. Operations that can fail return `maybe T` or a
`result`:

```coco
let found be first item in list where price of item is less than 10

if found is nothing
  show text No cheap items
otherwise
  show text Found value of name of found
```

For operations that fail with a reason:

```coco
try
  let data be read file scores.txt
  show text value of data
or
  show text Could not read the file
```

`try … or …` catches **recoverable failures** only — declared by a signature's
`may fail with <type>` clause. It does not catch traps (overflow, division by zero,
assertion failure); those abort the process in dev and release, and are configurable to
abort-or-unwind at the process boundary for server targets
([doc 10 §10.7](10-backends-targets-abi.md)).

```sig
signature read file
  slot path of kind text open
  gives text
  may fail with a file problem
  effects io blocks
```

Ignoring a possible failure is an error (`E-0541`), so failure handling is not
optional — but it is one line.

## 5.9 Evaluation order **[N]**

1. Statements execute in source order.
2. Within a clause, slots are evaluated **left to right in source order**, which for a
   locale with reordered segments ([doc 04 §4.7.2](04-multilingual.md)) means *the order
   the slots appear in that locale's source*.
3. **Therefore**: a signature whose slots have side effects could evaluate them in a
   different order in a different locale. To prevent this from breaking Rule 3, the
   compiler enforces: **at most one slot of a signature may have `io` or `writes`
   effects, unless the signature is declared `order sensitive`** (`E-0552`). Pure slots
   may be reordered freely without observable difference.
4. `and` / `or` short-circuit.
5. `if` evaluates its condition exactly once.
6. Handler bodies (`when …`) are scheduled by the runtime per
   [doc 07](07-concurrency-and-simd.md); ordering between handlers is specified there.

Rule 3 of this section is the single place where multilingual source ordering interacts
with semantics, and it is resolved by restriction rather than by convention. `compose
check` reports it before it can ever matter.

## 5.10 Constants and compile-time evaluation **[N]**

`let` bindings at module level whose initialiser is composed only of literals and
`pure`-effect signatures are **compile-time evaluated**. The compiler runs them in a
deterministic const-eval interpreter with:

- no I/O, no clock, no randomness, no device access;
- a step budget (default 10⁸ steps, `compose` flag `--const-eval-budget`);
- exact same arithmetic semantics as runtime, including traps.

This gives the same benefit as `constexpr` without a second language, and it is how
`the number written in base 16 as 1f4` and lookup tables are handled.

## 5.11 Pages and the declarative layer **[N]**

A `page` is a **declaration**, not a procedure. Its body is a sequence of clauses whose
signatures are marked `declarative`, which means:

- they are evaluated to build a **UI description tree**, not executed for effect;
- they may be re-evaluated by the runtime whenever their inputs change;
- they MUST be free of `io` and `writes` effects other than through the declared
  `state` mechanism.

```coco
page Profile
  show picture avatar of current user
  show text name of current user
  show button Follow

  when Follow is pressed
    follow current user
    change button Follow to Following
```

The `when` blocks inside a page are **imperative** and may have effects. The separation
is enforced by the effect system, and it is what allows the runtime to diff and re-render
a page without re-running the user's logic. See [doc 11 §11.1](11-stdlib.md).

## 5.12 Modules and visibility **[N]**

- One file = one module. The module's name is its path relative to the project's `source`
  directory, with separators becoming spaces: `ui/panels/side.coco` → `ui panels side`.
- `use ui panels side` imports it.
- Only `share`d names and signatures are visible to importers.
- Cyclic `use` between modules is permitted for types and signatures; cyclic *value*
  initialisation is an error (`E-0561`).
- `use <package> <module>` imports from a dependency declared in `project.coco`.

## 5.13 The prelude **[N]**

The following are visible in every module without `use`:

`show text`, `show`, `join`, `length of`, `add … to`, `remove … from`, `first … in … where`,
`count of`, `is empty`, `as a decimal number`, `as a whole number`, `as text`,
`minimum of`, `maximum of`, `absolute value of`, `random number between … and …` (seeded,
see [doc 11 §11.9](11-stdlib.md)), `now`, `wait for`, plus the control-flow keywords.

A project may disable the prelude with `no prelude` in `project.coco` for embedded targets.

---

*Next: [06 — Memory and safety](06-memory-and-safety.md)*
