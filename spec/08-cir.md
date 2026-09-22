# 08 — Coco IR (CIR)

*Edition 2026. **[N]** normative, **[I]** informative.*

CIR is Coco's own intermediate representation. It is the point at which human language
stops and machine semantics begin, and it is the artefact whose identity proves the
multilingual claim of [doc 04](04-multilingual.md).

---

## 8.1 Position in the pipeline **[I]**

```
source ─► tokens ─► AST ─► CIR-D ─► CIR-C ─► MIR ─► Cranelift / LLVM / SPIR-V
                            │         │
                    declarative   canonical
                    + imperative   (lowered, typed, SSA)
```

- **CIR-D** (*declarative*) preserves pages, handlers, records, choices and effects. It
  is what the LSP, the doc generator, the hot-reload engine and the translator consume.
- **CIR-C** (*canonical*) is fully lowered, monomorphised, typed, SSA, region-annotated.
  It is what the optimiser and the back ends consume, and what the canonical hash is
  computed over.

## 8.2 Design constraints **[N]**

| Constraint | Consequence |
| --- | --- |
| Locale-free | every node references a CID, never a source lexeme |
| Order-canonical | declaration order is normalised to a defined total order (§8.6) |
| Self-describing | every node carries its type and effect set |
| Round-trippable | CIR-D → source is exact modulo formatting; this is how `compose translate` works |
| Verifiable | a standalone verifier checks 24 invariants (§8.8) |
| Stable | the binary encoding is versioned and forward-compatible |

## 8.3 CIR-D: the declarative layer **[N]**

### 8.3.1 Node vocabulary

```
Module      ( cid, edition, uses, items )
Page        ( cid, name, state, view, handlers )
Record      ( cid, name, fields, layout-hint )
Choice      ( cid, name, variants )
Action      ( cid, signature, params, body, effects, result )
Handler     ( cid, event, subject, body, effects )
Ability     ( cid, requirements )
Impl        ( cid, type, ability, members )
Binding     ( cid, name, mutability, type, init )
View        ( node-tree of ViewNode )
ViewNode    ( cid, props, children, key )
```

### 8.3.2 Textual form **[I]**

`compose build --emit cir-d` produces:

```cir
module app.main edition 2026
  uses core.prelude, core.ui

  page app.main.page.home
    name "Home"
    view
      node core.ui.text
        prop content = const text "Welcome"
      node core.ui.button
        prop label = const text "Start"
        key "Start"
    handler app.main.page.home.h0
      event core.event.is_pressed subject = view-key "Start"
      effects io
      body
        call core.stmt.open_page
          arg target = ref app.main.page.game
```

Note every identifier is a CID or a quoted *datum*. The word `Welcome` appears only
inside `const text`, where it is application data, and the word `Start` appears only as
data and as a view key. No Coco keyword survives into CIR.

## 8.4 CIR-C: the canonical layer **[N]**

### 8.4.1 Structure

CIR-C is a set of **functions**, each a control-flow graph of **basic blocks** in SSA
form with block parameters (no phi nodes).

```
Function  ( cid, params, result, effects, regions, blocks, entry )
Block     ( id, params, instructions, terminator )
Value     ( id, type, region )
```

### 8.4.2 Instruction set **[N]**

CIR-C has 41 opcodes. They are deliberately few; everything else is a `call` into the
runtime or a library, which the optimiser may inline.

**Constants and moves**

```
const.int    t, imm                 const.dec  t, imm
const.text   t, datum-id            const.bool t, imm
const.nothing t
copy         t, v
```

**Arithmetic** (all trapping variants are explicit)

```
add.int  t, a, b        add.int.wrap  t, a, b     add.dec t, a, b
sub.int  t, a, b        sub.int.wrap  t, a, b     sub.dec t, a, b
mul.int  t, a, b        mul.int.wrap  t, a, b     mul.dec t, a, b
div.int  t, a, b        rem.int       t, a, b     div.dec t, a, b
neg      t, a
```

**Comparison and logic**

```
cmp.eq t, a, b     cmp.lt t, a, b     cmp.le t, a, b
and    t, a, b     or     t, a, b     not    t, a
```

**Aggregates**

```
record.new    t, type, f0..fn
field.get     t, r, index
field.set     r, index, v
choice.new    t, type, variant, payload
choice.tag    t, c
choice.payload t, c, variant
```

**Collections**

```
list.new      t, elem-type, capacity
list.get      t, l, i          (* bounds-checked unless proven *)
list.set      l, i, v
list.push     l, v
list.len      t, l
table.get     t, m, k
table.set     m, k, v
```

**Memory and regions**

```
region.enter  r
region.exit   r
alloc         t, type, region
retain        v                  (* shared class only *)
release       v
drop          v                  (* run finisher, release storage *)
```

**Control**

```
br            block(args)
br.if         cond, then-block(args), else-block(args)
switch        tag, [case → block(args)], default → block(args)
call          t, callee-cid, args
call.indirect t, fnptr, args
return        v
trap          reason-code
```

**Concurrency / device**

```
par.for       loop-cid, range, body-fn, reduction?
device.enter  device, transfers
device.exit   device
handler.park  continuation-id
```

### 8.4.3 Types in CIR-C **[N]**

```
i8 i16 i32 i64   f32 f64   bool   unit
text
ptr<T, region>            (* borrowed *)
own<T>                    (* unique heap *)
rc<T>                     (* shared *)
arr<T, n>                 (* fixed *)
slice<T>                  (* ptr + len *)
rec<cid>                  (* record, layout resolved *)
var<cid>                  (* choice, tag + payload *)
fn(T…) -> T
vec<T, n>                 (* SIMD *)
```

Generics are gone by CIR-C: monomorphisation happens during AST → CIR-C lowering
([doc 09 §9.6](09-compiler-pipeline.md)).

### 8.4.4 Example **[I]**

Source:

```coco
to damage a target by an amount
  set health of target to health of target minus amount
```

CIR-C:

```cir
function app.main.act.damage
  params  %target : ptr<rec<app.main.rec.player>, %r_act>
          %amount : i64
  result  unit
  effects writes app.main.rec.player.health
  regions %r_act : activation

  block entry(%target, %amount):
    %0 = field.get %target, 0           ; health
    %1 = sub.int   %0, %amount          ; traps on overflow
    field.set %target, 0, %1
    return unit
```

## 8.5 Region annotations **[N]**

Every `Value` carries the region it lives in, and every `Function` declares its region
parameters. Region well-formedness is invariant **V11** of §8.8: no value may be stored
into a place whose region strictly outlives it. This is the machine-checkable residue of
[doc 06 §6.4](06-memory-and-safety.md) — the inference happens on the AST, but the
*result* is re-verified on CIR-C, so a bug in inference is caught by the verifier rather
than producing an unsound binary.

## 8.6 Canonical ordering **[N]**

For a canonical hash to be meaningful, CIR-C must be ordered by a rule that depends only
on the program's meaning. The canonicalisation pass applies, in order:

1. **Module order** — by module CID, byte-lexicographic.
2. **Item order** — within a module, by item CID.
3. **Block order** — reverse post-order of the CFG from the entry block; ties (which
   cannot occur in RPO of a reducible graph) broken by instruction count then by the
   canonical hash of the block body.
4. **Value numbering** — values are renumbered in the order they are defined under the
   block order above, starting at 0 per function.
5. **Commutative operand order** — for `add`, `mul`, `and`, `or`, `cmp.eq`, operands are
   sorted by (value number, type CID).
6. **Datum pool** — text and numeric data are interned into a pool sorted by byte value;
   `const.text` references pool indices.
7. **Effect sets** — sorted by path, then by effect kind.
8. **Region names** — renumbered by first use under the block order.

Source coordinates, comments, locale, and original identifier spellings are **excluded**
from CIR-C; they live in a side-table (§8.9) that does not participate in the hash.

## 8.7 The canonical hash **[N]**

```
canonical_hash(program) = BLAKE3-256( canonical_encoding(CIR-C) )
```

Normative requirements:

1. `canonical_encoding` is the binary encoding of §8.10 applied to the canonically
   ordered CIR-C.
2. Two programs with the same canonical hash MUST compile to identical output for the
   same target, options and toolchain version.
3. **Locale invariance**: for any well-formed source *S* and any locales *A*, *B*,
   `canonical_hash(compile(S, A)) = canonical_hash(compile(translate(S, A→B), B))`.
4. **Formatting invariance**: reformatting, re-indenting, adding/removing notes and blank
   lines, and renaming a *local* binding MUST NOT change the hash. (Renaming a *shared*
   name does change it, because the name is part of the module's interface.)
5. The hash is printed by `compose build --print-hash` and embedded in the output binary's
   `.coco.hash` section, so a shipped binary can be matched to its source.

### 8.7.1 The equivalence proof in practice **[I]**

```bash
$ compose build examples/hello.coco --print-hash
b3:9f4c1e...7a20

$ compose translate examples/hello.coco --to hebrew --out /tmp/hello.he.coco
$ compose build /tmp/hello.he.coco --print-hash
b3:9f4c1e...7a20

$ compose translate examples/hello.coco --to japanese --out /tmp/hello.ja.coco
$ compose build /tmp/hello.ja.coco --print-hash
b3:9f4c1e...7a20
```

The reference implementation in this repository demonstrates this for the subset it
covers:

```bash
python reference/coco_ref.py --prove-locale-equivalence
```

## 8.8 Verifier invariants **[N]**

An implementation MUST include an CIR-C verifier, MUST run it on every build in
`compose` (dev) mode, and SHOULD run it in release mode behind a flag. It checks:

| # | Invariant |
| --- | --- |
| V1 | Every value is defined exactly once (SSA) |
| V2 | Every use is dominated by its definition |
| V3 | Every block ends in exactly one terminator |
| V4 | Branch targets exist and arities match block parameters |
| V5 | Operand types match opcode signatures |
| V6 | `field.get`/`field.set` indices are within the record's field count |
| V7 | `choice.payload` variant matches a preceding `switch` on `choice.tag` |
| V8 | `list.get`/`list.set` are preceded by a bounds check or carry a `proven` flag |
| V9 | Every `region.enter` has a matching `region.exit` on every path |
| V10 | No value escapes its region (see §8.5) |
| V11 | `ptr<T, r>` uses are dominated by `region.enter r` and dominate `region.exit r` |
| V12 | `retain`/`release` are applied only to `rc<T>` |
| V13 | Reference counts balance on every path (net zero at function exit for borrowed params) |
| V14 | `drop` is not applied twice on any path |
| V15 | Every path to `return` has initialised the result |
| V16 | Effect set of a function ⊇ union of effect sets of its calls |
| V17 | `par.for` bodies have no loop-carried dependency except a declared reduction |
| V18 | `device.enter`/`device.exit` nest correctly and transfers cover all crossing values |
| V19 | Calls reference existing function CIDs with matching arity and types |
| V20 | Monomorphised instances are fully concrete (no type variables remain) |
| V21 | The datum pool contains no unreferenced entries |
| V22 | Canonical ordering (§8.6) holds |
| V23 | `trap` reason codes are from the defined enumeration |
| V24 | The module's declared edition is supported |

Verifier failure is an **internal compiler error**, never a user error. It is reported
with a reproduction bundle and the canonical hash.

## 8.9 Side tables **[N]**

CIR-C carries, outside the hashed region:

| Table | Contents |
| --- | --- |
| `source map` | value/instruction → (file, logical line, logical column, byte span) |
| `names` | CID → original spelling, per locale |
| `docs` | CID → `note doc` text |
| `storage` | value → storage class and reason string (for `compose explain storage`) |
| `schedule` | handler → group assignment (for `compose explain schedule`) |
| `vectorisation` | loop → outcome and reason |

These drive every `compose explain` command and the LSP. They are stripped from release
binaries unless `keep debug information` is set.

## 8.10 Binary encoding **[N]**

```
cir-file    = magic , version , section+ ;
magic       = "CIRC" ;                          (* 0x43 49 52 43 *)
version     = u16 major , u16 minor ;
section     = kind:u8 , length:u32 , payload:bytes ;
```

| Kind | Section |
| --- | --- |
| `0x01` | module header (CID, edition, dependency hashes) |
| `0x02` | type table |
| `0x03` | datum pool |
| `0x04` | function table |
| `0x05` | instruction stream (varint-coded) |
| `0x06` | region table |
| `0x07` | effect table |
| `0x10`–`0x1F` | side tables (§8.9), not hashed |

Instruction encoding is `opcode:u8 , operands:varint*`. Values, blocks, types and CIDs
are all varint indices into their tables, so the encoding is compact and position
independent.

Forward compatibility: an unknown section kind ≥ `0x40` MUST be skipped; an unknown
opcode is an error.

## 8.11 Why an own IR rather than emitting LLVM directly **[I]**

1. **Locale invariance needs a canonical form** that is *ours*, with our ordering rules.
   LLVM IR's ordering is not stable enough to hash for this purpose.
2. **The declarative layer has no LLVM analogue.** Pages, views, handlers and effect sets
   must survive to the runtime and the tooling.
3. **Region and effect information is first class** in CIR and would be lost in LLVM
   metadata, which optimisation passes may legally drop.
4. **Multiple back ends.** Cranelift for dev, LLVM for release, SPIR-V/WGSL for devices,
   and a portable CIR interpreter for bootstrapping. A neutral IR is the only sane way to
   feed all four.
5. **Hot reload** ([doc 12 §12.7](12-toolchain.md)) diffs CIR-D between builds to decide
   what can be swapped live.

---

*Next: [09 — Compiler pipeline](09-compiler-pipeline.md)*
