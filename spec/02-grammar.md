# 02 — Grammar

*Edition 2026. **[N]** normative, **[I]** informative.*

This document gives the complete syntax of Coco. It is deliberately short: the
grammar is small because the *registry* ([doc 03](03-clause-registry.md)) carries the
variety that other languages put in their grammars.

---

## 2.1 Notation **[N]**

ISO/IEC 14977 EBNF with three extensions:

| Extension | Meaning |
| --- | --- |
| `TOKEN` (upper case) | a terminal produced by the lexer ([doc 01 §1.2](01-lexical-structure.md)) |
| `⟨name⟩` | a *registry-parameterised* production — its right-hand side is supplied by the Clause Signature Registry at parse time |
| `↦ f(x)` | a side condition evaluated by the parser; the production applies only if `f(x)` holds |

The grammar is **LL(k)** where

```
k = 1 + max( longest head phrase, longest terminator phrase )   measured in words
```

For the core registry shipped in this repository, *k* = 7: the longest head is
`fetch these at the same time` (6 words) and the longest terminator is 2 words.
`compose registry check` prints the value for whatever registry is in effect, and it is
bounded because the particle set is closed and heads are finite.

## 2.2 Program structure **[N]**

```ebnf
program        = { NEWLINE } , { top-level } , EOF ;

top-level      = directive
               | declaration
               | statement ;

directive      = use-directive
               | share-directive
               | locale-directive
               | edition-directive ;

use-directive     = "use" , module-path , NEWLINE ;
share-directive   = "share" , name , NEWLINE ;
locale-directive  = "write" , "in" , locale-name , NEWLINE ;
edition-directive = "this" , "is" , "edition" , NUMBER , NEWLINE ;

module-path    = WORD , { WORD } ;
locale-name    = WORD ;
```

A `use` directive makes another module's shared signatures and names visible. A `share`
directive exports a name from the current module. Both are file-scoped and order
independent; an implementation MUST perform a name-collection pass before parsing bodies
so that forward references work.

## 2.3 Declarations **[N]**

```ebnf
declaration    = page-decl
               | record-decl
               | choice-decl
               | action-decl
               | handler-decl
               | binding-decl
               | message-decl ;

page-decl      = "page" , name , NEWLINE , block ;

record-decl    = article , name , "has" , NEWLINE ,
                 INDENT , field , { field } , DEDENT ;
field          = name , "as" , type , [ "starting" , "at" , value ] , NEWLINE ;

choice-decl    = article , name , "is" , "one" , "of" , NEWLINE ,
                 INDENT , variant , { variant } , DEDENT ;
variant        = name , [ "with" , field-list ] , NEWLINE ;
field-list     = name , "as" , type , { "and" , name , "as" , type } ;

action-decl    = "to" , ⟨new-signature⟩ , NEWLINE , block ;

handler-decl   = "when" , ⟨event-signature⟩ , NEWLINE , block ;

binding-decl   = "let" , name , "be" , value , NEWLINE          (* immutable *)
               | "keep" , name , "as" , value , NEWLINE ;       (* mutable   *)

message-decl   = "the" , "message" , name , "says" , NEWLINE ,
                 INDENT , wording , { wording } , DEDENT ;      (* doc 04 §4.12 *)
wording        = "in" , locale-name , text-slot , NEWLINE
               | "in" , locale-name , NEWLINE ,
                 INDENT , plural-case , { plural-case } , DEDENT ;
plural-case    = "when" , plural-category , text-slot , NEWLINE ;
plural-category = "none" | "one" | "two" | "few" | "many" | "other" ;

article        = "a" | "an" | "the" ;
```

### 2.3.1 Examples **[I]**

```coco
a player has
  health as a whole number starting at 100
  name as text
  position as a point

a shape is one of
  circle with radius as a decimal number
  rectangle with width as a decimal number and height as a decimal number
  empty

let maximum health be 100
keep score as 0

the message greeting says
  in english Hi
  in hebrew שלום

to damage a target by an amount
  set health of target to health of target minus amount
```

`to damage a target by an amount` registers the signature
`damage <target: ref> by <amount: value>`; see [doc 03 §3.4](03-clause-registry.md).

## 2.4 Statements **[N]**

```ebnf
statement      = clause , NEWLINE , [ body ]
               | control-statement ;

body           = INDENT , statement , { statement } , DEDENT      (* indented form *)
               | statement                                        (* flush form, §2.6.2 *)
               ↦ signature-of-preceding-clause-ends-in-block-slot ;

clause         = ⟨head⟩ , { segment } ;
segment        = slot
               | ⟨particle-phrase⟩ , slot ;

slot           = text-slot
               | name-slot
               | number-slot
               | ref-slot
               | value-slot
               | text-block ;
```

### 2.4.1 Slot productions **[N]**

```ebnf
text-slot      = text-piece , { text-piece }
               ↦ stop at first declared terminator phrase for this slot, or NEWLINE ;
text-piece     = WORD | NUMBER | splice ;
splice         = "value" , "of" , ref-slot ;

name-slot      = WORD , { WORD }
               ↦ stop at first declared terminator phrase for this slot, or NEWLINE ;

number-slot    = NUMBER ;

ref-slot       = ref-path ;
ref-path       = name , { "of" , name } ;

value-slot     = expression ;

text-block     = "text" , NEWLINE , INDENT , RAWLINE , { RAWLINE } , DEDENT ;

name           = WORD , { WORD } ↦ longest match against the visible name set ;
```

### 2.4.2 The greedy-slot rule **[N]**

> **Rule G.** A `text` or `name` slot consumes tokens until the earliest position *p* at
> which a **complete terminator phrase** declared for that slot begins, or until
> `NEWLINE`, whichever comes first. The slot's value is the tokens before *p*; it MUST
> be non-empty (`E-0231`).

"Earliest", not "latest", and "complete phrase", not "first word of a phrase". Both
choices matter:

- *Earliest* makes the parse a single left-to-right scan with no backtracking and gives
  the clearest errors.
- *Complete phrase* means the bare word `to` does not terminate a slot whose terminator
  is the phrase `to page`. So `show button Go to Top` yields the label `Go to Top`,
  while `show button Go to page Home` yields the label `Go` and target `Home`.

When a label genuinely needs to contain a terminator phrase, the Sugar Law applies —
use the explicit form:

```coco
show button
  label
    Go to page 2 of the manual
```

### 2.4.3 Control statements **[N]**

```ebnf
control-statement
               = if-statement
               | while-statement
               | repeat-statement
               | for-each-statement
               | stop-statement
               | skip-statement
               | give-statement
               | try-statement ;

if-statement   = "if" , expression , NEWLINE , body ,
                 { "otherwise" , "if" , expression , NEWLINE , body } ,
                 [ "otherwise" , NEWLINE , body ] ;

while-statement    = "while" , expression , NEWLINE , body ;
repeat-statement   = "repeat" , expression , "times" , NEWLINE , body ;
for-each-statement = "for" , "each" , name , "in" , expression , NEWLINE , body ;

stop-statement = "stop" , NEWLINE ;                    (* break out of nearest loop *)
skip-statement = "skip" , NEWLINE ;                    (* continue nearest loop    *)
give-statement = "give" , expression , NEWLINE ;       (* return a value           *)

try-statement  = "try" , NEWLINE , body ,
                 "or" , "use" , expression , NEWLINE
               | "try" , NEWLINE , body ,
                 "or" , NEWLINE , body ;
```

#### Example **[I]**

```coco
if health of player is less than 1
  open page Game Over
otherwise if health of player is less than 20
  show text Careful
otherwise
  show text You are fine

for each enemy in enemies
  if distance between enemy and player is less than 2
    damage player by 10

repeat 3 times
  play sound beep
```

## 2.5 References and paths **[N]**

`ref-path` uses the particle `of` for member access, read **outermost first**:

```coco
health of player            note the health field of player
name of owner of shop       note ((shop.owner).name)
```

Resolution rules:

1. `name` is resolved by **longest match** against the visible name set. Names may
   contain spaces (`Game Over` is one name), so longest match is required.
2. Resolution is lexically scoped: innermost block, then enclosing blocks, then module,
   then `use`d modules in declaration order, then the core prelude.
3. A name that resolves in more than one `use`d module is ambiguous (`E-0245`); qualify
   it as `chart of plotting module` or rename.
4. Shadowing a name from an outer scope is permitted and MUST produce warning `W-0246`.

## 2.6 Clause layout forms **[N]**

### 2.6.1 Hanging form

If a clause reaches `NEWLINE` with unfilled slots and the next line is indented, the
remaining slots are read from the indented block, one **labelled segment** per line:

```coco
show button
  label
    Start
  to page
    Game
```

Each line of the hanging block begins with the particle phrase (or the slot's declared
label) that introduces the slot it fills. This is the *explicit form* that every
convenience form desugars to, and it is what the compiler shows in fix-its.

### 2.6.2 Flush single-action form

A signature whose final slot is a `block` MAY take its body as the single following
statement at the *same* indentation level:

```coco
when Start is pressed
open page Game
```

This is exactly one statement, never more. It exists so the prose style of the original
Coco concept remains valid. `compose format` rewrites it to the indented form.
Implementations MUST accept it and MUST NOT treat a second flush line as part of the
body.

### 2.6.3 Grouped expressions

There are no parentheses. Sub-expressions that need explicit grouping are indented under
the word `group`:

```coco
set total to
  group
    base plus bonus
  times multiplier
```

`group` is only valid where a `value` slot is expected.

## 2.7 Expressions **[N]**

```ebnf
expression     = or-expr ;
or-expr        = and-expr , { "or" , and-expr } ;
and-expr       = not-expr , { "and" , not-expr } ;
not-expr       = [ "not" ] , compare-expr ;
compare-expr   = add-expr , [ comparator , add-expr ] ;
add-expr       = mul-expr , { ( "plus" | "minus" ) , mul-expr } ;
mul-expr       = unary-expr , { ( "times" | "over" | "remainder" , "of" ) , unary-expr } ;
unary-expr     = [ "minus" ] , primary ;
primary        = NUMBER
               | "yes" | "no" | "nothing"
               | ref-path
               | list-literal
               | record-literal
               | call-expr
               | group-expr ;

comparator     = "is" | "is" , "not"
               | "is" , "more" , "than" | "is" , "less" , "than"
               | "is" , "at" , "least" | "is" , "at" , "most" ;

group-expr     = "group" , NEWLINE , INDENT , expression , DEDENT ;

list-literal   = "list" , "of" , NEWLINE , INDENT , ( expression , NEWLINE ) + , DEDENT
               | "empty" , "list" ;

record-literal = "a" , name , "with" , NEWLINE ,
                 INDENT , ( name , "as" , expression , NEWLINE ) + , DEDENT ;

call-expr      = ⟨value-signature⟩ ;     (* an action used for its result *)
```

### 2.7.1 Precedence **[N]**

Tightest first. All binary operators are left-associative. Comparison is
**non-associative** — `a is less than b is less than c` is error `E-0252`; write
`a is less than b and b is less than c`.

| Level | Operators |
| --- | --- |
| 1 | `of` (member access), `value of` |
| 2 | prefix `minus` |
| 3 | `times`, `over`, `remainder of` |
| 4 | `plus`, `minus` |
| 5 | `is`, `is not`, `is more than`, `is less than`, `is at least`, `is at most` |
| 6 | `not` |
| 7 | `and` |
| 8 | `or` |

`and` and `or` **short-circuit**. Evaluation order everywhere else is strictly left to
right, including argument slots ([doc 05 §5.9](05-types-and-semantics.md)).

### 2.7.2 Why word operators **[I]**

`a plus b times c` is 4 levels deep in the table above and evaluates as `a plus (b times c)`,
matching arithmetic convention and the reader's expectation. Using words rather than
symbols keeps Rule 1 of [doc 00](00-overview.md) intact: `+` is not in the character set,
so there is no lexical special-casing at all.

## 2.8 Types in source **[N]**

```ebnf
type           = [ article ] , type-name
               | "list" , "of" , type
               | "table" , "of" , type , "to" , type
               | "maybe" , type ;

type-name      = "whole" , "number"
               | "decimal" , "number"
               | "text"
               | "yes" , "or" , "no"
               | "nothing"
               | name ;                 (* a declared record or choice *)
```

Type annotations are **never required** in bodies. They appear only in record fields and
optionally in action parameters for documentation:

```coco
to move a player by an amount as a decimal number
  ...
```

## 2.9 Complete grammar, collected **[N]**

```ebnf
(* ============ Coco Edition 2026 — collected grammar ============ *)

program            = { NEWLINE } , { top-level } , EOF ;
top-level          = directive | declaration | statement ;

directive          = "use" , module-path , NEWLINE
                   | "share" , name , NEWLINE
                   | "write" , "in" , locale-name , NEWLINE
                   | "this" , "is" , "edition" , NUMBER , NEWLINE ;

declaration        = "page" , name , NEWLINE , body
                   | article , name , "has" , NEWLINE , INDENT , field+ , DEDENT
                   | article , name , "is" , "one" , "of" , NEWLINE , INDENT , variant+ , DEDENT
                   | "to" , ⟨new-signature⟩ , NEWLINE , body
                   | "when" , ⟨event-signature⟩ , NEWLINE , body
                   | "let" , name , "be" , expression , NEWLINE
                   | "keep" , name , "as" , expression , NEWLINE
                   | "the" , "message" , name , "says" , NEWLINE ,
                     INDENT , wording+ , DEDENT ;

wording            = "in" , locale-name , text-slot , NEWLINE
                   | "in" , locale-name , NEWLINE , INDENT , plural-case+ , DEDENT ;
plural-case        = "when" , plural-category , text-slot , NEWLINE ;
plural-category    = "none" | "one" | "two" | "few" | "many" | "other" ;

field              = name , "as" , type , [ "starting" , "at" , expression ] , NEWLINE ;
variant            = name , [ "with" , field-list ] , NEWLINE ;
field-list         = name , "as" , type , { "and" , name , "as" , type } ;

statement          = clause , NEWLINE , [ body ] | control-statement ;
body               = INDENT , statement+ , DEDENT | statement ;

clause             = ⟨head⟩ , { slot | ⟨particle-phrase⟩ , slot } ;
slot               = text-slot | name-slot | number-slot | ref-slot
                   | value-slot | text-block ;
text-slot          = ( WORD | NUMBER | splice )+ ;
name-slot          = WORD+ ;
number-slot        = NUMBER ;
ref-slot           = name , { "of" , name } ;
value-slot         = expression ;
text-block         = "text" , NEWLINE , INDENT , RAWLINE+ , DEDENT ;
splice             = "value" , "of" , ref-slot ;
name               = WORD+ ;

control-statement  = "if" , expression , NEWLINE , body ,
                     { "otherwise" , "if" , expression , NEWLINE , body } ,
                     [ "otherwise" , NEWLINE , body ]
                   | "while" , expression , NEWLINE , body
                   | "repeat" , expression , "times" , NEWLINE , body
                   | "for" , "each" , name , "in" , expression , NEWLINE , body
                   | "try" , NEWLINE , body , "or" , [ "use" , expression , NEWLINE | NEWLINE , body ]
                   | "stop" , NEWLINE
                   | "skip" , NEWLINE
                   | "give" , expression , NEWLINE ;

expression         = or-expr ;
or-expr            = and-expr , { "or" , and-expr } ;
and-expr           = not-expr , { "and" , not-expr } ;
not-expr           = [ "not" ] , compare-expr ;
compare-expr       = add-expr , [ comparator , add-expr ] ;
add-expr           = mul-expr , { ( "plus" | "minus" ) , mul-expr } ;
mul-expr           = unary-expr , { ( "times" | "over" | "remainder" , "of" ) , unary-expr } ;
unary-expr         = [ "minus" ] , primary ;
primary            = NUMBER | "yes" | "no" | "nothing" | ref-slot
                   | list-literal | record-literal | call-expr | group-expr ;
comparator         = "is" | "is" , "not" | "is" , "more" , "than"
                   | "is" , "less" , "than" | "is" , "at" , "least" | "is" , "at" , "most" ;
group-expr         = "group" , NEWLINE , INDENT , expression , DEDENT ;
list-literal       = "list" , "of" , NEWLINE , INDENT , ( expression , NEWLINE )+ , DEDENT
                   | "empty" , "list" ;
record-literal     = "a" , name , "with" , NEWLINE ,
                     INDENT , ( name , "as" , expression , NEWLINE )+ , DEDENT ;
call-expr          = ⟨value-signature⟩ ;

type               = [ article ] , type-name | "list" , "of" , type
                   | "table" , "of" , type , "to" , type | "maybe" , type ;
type-name          = "whole" , "number" | "decimal" , "number" | "text"
                   | "yes" , "or" , "no" | "nothing" | name ;
article            = "a" | "an" | "the" ;
module-path        = WORD+ ;
locale-name        = WORD ;
```

## 2.10 Worked parse **[I]**

Source:

```coco
show button Get Started to page Level One
```

Registry entry:

```sig
signature show button
  slot label of kind text
    terminated by to page
    terminated by with style
  optional particle to page
    slot target of kind ref
```

Parse trace:

| Step | Action | State |
| --- | --- | --- |
| 1 | Head trie: `show` → `show button` (longest match) | committed to signature `show button` |
| 2 | Slot `label` is `text`, greedy. Scan words. | `Get` |
| 3 | `Started` — is `to page` starting here? No. | `Get Started` |
| 4 | `to` — is `to page` starting here? Peek `page`. Yes → stop. | label = `Get Started` |
| 5 | Consume particle `to page` | |
| 6 | Slot `target` is `ref`, longest name match → `Level One` | target = `Level One` |
| 7 | `NEWLINE` → clause complete | ✔ |

Lookahead used: 2 tokens. No backtracking. Exactly one parse exists.

---

*Next: [03 — Clause Signature Registry](03-clause-registry.md)*
