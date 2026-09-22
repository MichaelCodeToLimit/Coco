# 03 — The Clause Signature Registry

*Edition 2026. **[N]** normative, **[I]** informative.*

This is the mechanism that makes a punctuation-free language deterministic. It replaces
what other languages express with parentheses, commas and quotes: an explicit, finite,
machine-checked table of what a statement can look like.

---

## 3.1 Definitions **[N]**

A **signature** is a tuple

```
σ = ( head, segments, result, effects, visibility )
```

where

- **head** is a non-empty sequence of *keyword lexemes* (`show button`, `create neural network`);
- **segments** is a sequence of *segment descriptors*, each being either
  - a **slot** `(name, kind, terminators, optionality)` with
    `kind ∈ { text, name, number, ref, value, block }`, or
  - a **particle phrase** `(lexemes, optionality)` drawn from the closed particle set;
- **result** is a type or `nothing`;
- **effects** is a set drawn from `{ reads, writes, io, device, allocates, blocks }`
  ([doc 07 §7.4](07-concurrency-and-simd.md));
- **visibility** is `module` or `shared`.

A **registry** *R* is a finite set of signatures together with a **head trie** and, for
each signature, a **terminator automaton** per greedy slot.

## 3.2 Registry sources **[N]**

A registry is assembled, in this order, from:

1. the **core registry** shipped with the compiler (`registry/core.signatures`);
2. the **standard library** signatures of modules brought in by `use`;
3. **package** signatures of dependencies declared in `project.coco`;
4. **user declarations** in the current module (`to …`, `page …`, records, choices).

Later sources may not silently override earlier ones; see condition **R5**.

## 3.3 Declaration syntax **[N]**

The registry file format (`.signatures`) is itself punctuation-free Coco:

```sig
signature show text
  slot content of kind text
  gives nothing
  effects io

signature show button
  slot label of kind text
    terminated by to page
    terminated by with style
  optional particle to page
    slot target of kind ref
  optional particle with style
    slot style of kind ref
  gives nothing
  effects io

signature open page
  slot target of kind ref
  gives nothing
  effects io

signature damage
  slot target of kind ref
  particle by
    slot amount of kind value
  gives nothing
  effects writes

signature distance between
  slot first of kind ref
  particle and
    slot second of kind ref
  gives a decimal number
  effects reads
```

### 3.3.1 Field reference **[N]**

| Field | Meaning |
| --- | --- |
| `signature <head words>` | begins a signature; the head is everything up to `NEWLINE` |
| `slot <name> of kind <kind>` | a positional slot |
| `terminated by <phrase>` | adds a terminator phrase for the *preceding* greedy slot |
| `particle <phrase>` | a required particle phrase |
| `optional particle <phrase>` | a particle phrase that may be omitted with everything nested under it |
| `repeated particle <phrase>` | a particle phrase that may appear 0..n times |
| `gives <type>` | result type; the signature may then be used in a `value` slot |
| `effects <set>` | effect annotation |
| `device <name>` | restricts the signature to a device target (`cpu`, `gpu`) |
| `since edition <n>` | edition gate |
| `label <slot> as <phrase>` | the hanging-form label for a slot without a particle |

## 3.4 User declarations become signatures **[N]**

An `action-decl` head is translated to a signature by the following rules. Scanning the
head left to right:

| Head token | Becomes |
| --- | --- |
| `a` / `an` / `the` + WORD | a slot of kind `ref` (or `value` if the next word is `as` + type) named by the WORD |
| a word in the closed particle set | a particle phrase, greedily extended to the longest particle phrase that matches |
| any other word | a keyword lexeme, appended to the head if no slot has yet been seen, otherwise error `E-0311` |

So:

```coco
to damage a target by an amount
```

→ head `damage`; slot `target` kind `ref`; particle `by`; slot `amount` kind `value`.

```coco
to show a chart of a kind with some data
```

→ head `show chart`? **No** — `a chart` produces a slot immediately after head `show`,
so the head is just `show`, which collides with the core `show text` family. This is
caught by condition **R1** and reported as `E-0312` with the fix-it "rename to
`to draw a chart …`". The rule *"keywords must all precede the first slot"* keeps heads
trie-matchable.

Explicit slot kinds may be given for clarity or to force `text`:

```coco
to announce the message as text
  show text value of message
```

## 3.5 The closed particle set **[N]**

```
to     with    from    into    as      at      on      by     for
of     until   in      over    between starting at     through
and                                    (* only inside a signature, never as an operator there *)
```

Locales define their own particle sets ([doc 04 §4.3](04-multilingual.md)). The set is
closed per edition: user code cannot introduce new particles, which is what bounds *k* in
the LL(k) property.

## 3.6 Ambiguity-freedom conditions **[N]**

A registry *R* is **admissible** if and only if it satisfies R1–R6. An implementation
MUST verify admissibility when the registry is built, and MUST refuse to compile
anything against an inadmissible registry.

---

### R1 — Head prefix-freeness up to the first slot

> For any two distinct signatures σ₁, σ₂ ∈ *R*: `head(σ₁)` MUST NOT be a proper prefix of
> `head(σ₂)` **unless** at the point where they diverge, σ₁ requires a slot whose kind is
> `number`, `ref` or `value` and σ₂ continues with a keyword that is not a valid start of
> that slot kind.

*Why.* Head matching is longest-match on a trie. If `show` and `show button` both exist
and `show`'s first slot is `text`, the word `button` could begin the text slot or extend
the head. R1 forbids that configuration outright.

*Diagnostic.* `E-0312` — "`show` and `show button` cannot both exist; the shorter one's
first slot could start with `button`."

---

### R2 — Greedy slots must be terminator-closed

> For every slot *s* of kind `text` or `name` in σ, if *s* is not the last segment of σ,
> then the immediately following segment MUST be a particle phrase *p*, and *p* MUST be
> declared as a terminator of *s*.

*Why.* Rule G ([doc 02 §2.4.2](02-grammar.md)) needs a terminator to stop at. Without
R2 a greedy slot followed by another slot has no boundary.

*Corollary.* Two greedy slots can never be adjacent.

---

### R3 — At most one block slot, and it is last

> A signature contains at most one slot of kind `block`, and if present it is the final
> segment.

*Why.* A block is delimited by INDENT/DEDENT; two blocks in one clause would need a
separator, which would be punctuation.

---

### R4 — Terminator phrases must be distinguishable from slot content

> For every greedy slot *s* with terminator set *T(s)*, and every *t* ∈ *T(s)*: *t* MUST
> have length ≥ 1 and, if |*t*| = 1, the single word of *t* MUST be a member of the closed
> particle set, and *s* MUST NOT be declared `open` (see §3.8).

*Why.* A single-word terminator that is an ordinary word would silently truncate text.
`to`, `with`, `by` etc. are rare enough inside short labels and, crucially, the
*complete phrase* rule means `to page` does not fire on a bare `to`.

*Practical effect.* Library authors are pushed towards two-word terminators (`to page`,
`with style`, `into table`), which is what makes labels like `Go to Top` parse
correctly.

---

### R5 — No silent override

> If a signature in a later registry source has the same head and the same segment kinds
> as one from an earlier source, the later one MUST either
> (a) be declared `replacing`, or (b) be rejected with `E-0315`.

```sig
signature show text replacing core
  slot content of kind text
  gives nothing
  effects io
```

*Why.* A dependency must not be able to silently change what `show text` means in your
program.

---

### R6 — Names must not shadow keyword or particle phrases

> A declared name *n* MUST NOT be equal to, nor have as a prefix, any head lexeme
> sequence or particle phrase visible at the point of declaration, under locale case
> folding.

*Why.* In unsegmented scripts ([doc 01 §1.4.2](01-lexical-structure.md)) the lexer
matches the lexicon by maximal munch; a name that is a prefix of a keyword would be
unreachable. In segmented scripts it would make `ref` slots ambiguous with head
continuation.

*Diagnostic.* `E-0342` — "`open` cannot be a name here; it begins the phrase `open page`."

---

## 3.7 The admissibility algorithm **[N]**

```
function build_registry(sources):
    R ← ∅
    for src in sources in order:
        for σ in src:
            check_R5(σ, R)
            R ← R ∪ {σ}
    T ← build_head_trie(R)
    check_R1(T, R)
    for σ in R:
        check_R3(σ)
        for slot s in greedy_slots(σ):
            check_R2(σ, s)
            for t in terminators(s):
                check_R4(s, t)
    return (R, T)

function check_R1(T, R):
    for each trie node n that is both terminal and internal:
        σ_short ← signature at n
        for each child edge (n, w, n'):
            if first_slot_kind(σ_short) ∈ {text, name}:
                report E-0312 (σ_short, w)
            if first_slot_kind(σ_short) = number and w is a NUMBER-shaped lexeme:
                report E-0312
```

Cost is O(|R| · L) where L is the longest head, plus O(|R| · |T|) for terminator checks.
For the core registry (≈ 380 signatures) this is well under a millisecond, and it is
recomputed incrementally as the user types — see [doc 13 §13.5](13-lsp.md).

### 3.7.1 Determinism theorem **[I]**

> **Theorem.** If *R* is admissible then for every token sequence *S* and every parser
> state, at most one signature can be selected, and each greedy slot has exactly one
> extent.

*Sketch.* Head selection is longest match on a trie, which is a function; R1 removes the
only configuration in which the longest match could be wrong (a shorter head whose first
slot could absorb the next keyword). Given the signature, segments are consumed left to
right; particle phrases are matched literally; non-greedy slots have fixed extents
(`number` = one token, `ref` = longest name match, which is a function of the visible
name set, `value` = the expression grammar, which is LL(1) by §2.7.1's precedence table
and non-associative comparison). Greedy slot extents are determined by "earliest complete
terminator phrase", which is a function of the token sequence and *T(s)*; R2 guarantees
*T(s)* is non-empty whenever a greedy slot is non-final. ∎

Lookahead is bounded by the longest phrase the parser must see whole before it can
commit: a head or a terminator. So *k* = 1 + max(longest head, longest terminator),
measured in words. For the core registry in this repository that is 7. Both quantities
are finite and known when the registry is built, so *k* is a compile-time constant that
`compose registry check` reports.

## 3.8 Open slots **[N]**

A slot may be declared `open`, meaning it has **no** terminators and therefore runs to
`NEWLINE`:

```sig
signature show text
  slot content of kind text open
```

An `open` slot MUST be the final segment (this is R2 with an empty terminator set). It
is what makes `show text Welcome to my app, 100% guaranteed` work: nothing can truncate
it. Most single-slot display signatures use `open`.

## 3.9 Overload families **[N]**

Signatures sharing a head form an **overload family**. Within a family, disambiguation is
by *segment shape*, checked at registry build time:

```sig
signature play sound
  slot which of kind ref
  gives nothing

signature play sound
  slot which of kind ref
  particle at volume
    slot volume of kind value
  gives nothing
```

These are distinguishable because the second has a required particle the first lacks.
Two members of a family whose required segments have identical kinds in identical
positions violate R1 and are rejected (`E-0313`).

## 3.10 Event signatures **[N]**

`when` takes an **event signature**, which is a signature with `kind event`:

```sig
signature is pressed of kind event
  subject of kind ref
  gives nothing

signature touches of kind event
  subject of kind ref
  slot other of kind ref
  gives nothing

signature health reaches of kind event
  subject of kind ref
  slot threshold of kind number
  gives nothing
```

Event signatures are *subject-first*: the clause begins with a `ref`, then the head. So
`when player touches enemy` parses as subject `player`, head `touches`, slot `enemy`.
The parser knows to expect subject-first form because it is inside `when`.

Users declare events with `to notice`:

```coco
to notice a user posts something
  ...

when user posts something
  save post
  show post to followers
```

## 3.11 Worked registry extension **[I]**

Adding a charting library. The package ships:

```sig
signature draw chart
  slot kind of kind ref
    terminated by with data
    terminated by into area
  particle with data
    slot data of kind value
  optional particle into area
    slot area of kind ref
  gives nothing
  effects io device cpu
```

Admissibility:

- **R1**: no existing signature has head `draw` or a head for which `draw chart` is a
  prefix. ✔
- **R2**: slot `kind` is `ref`, not greedy — R2 does not apply. `data` is `value`,
  terminated by the optional particle `into area`. ✔
- **R3**: no block slot. ✔
- **R4**: terminators `with data` and `into area` both have length 2 and start with
  particles. ✔
- **R5**: no clash. ✔
- **R6**: the library declares no names that prefix `draw chart`. ✔

Usage:

```coco
use plotting

draw chart bar with data monthly sales into area main panel
```

Parse: head `draw chart`; `kind` = longest name match → `bar`; particle `with data`;
`data` = expression `monthly sales`; particle `into area`; `area` = `main panel`.

## 3.12 Inspecting the registry **[N]**

```bash
compose registry list                  # all visible signatures
compose registry show "show button"    # one signature, expanded, with terminators
compose registry check                 # re-run R1..R6 and print the proof obligations
compose registry why "Go to page Home" # explain how a line parses, step by step
```

`compose registry why` prints exactly the table in [doc 02 §2.10](02-grammar.md). It is
the primary teaching tool and the primary debugging tool for "why did my label get cut
off".

---

*Next: [04 — Multilingual architecture](04-multilingual.md)*
