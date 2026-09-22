# 11 — The Standard Library

*Edition 2026. **[N]** normative, **[I]** informative.*

The standard library is presented as **signatures** ([doc 03](03-clause-registry.md)),
because in Coco an API *is* a set of signatures. Every signature below is part of the
core registry or a module registry and is subject to R1–R6.

Modules: `ui` `events` `net` `store` `draw2d` `scene3d` `physics` `audio` `input`
`tensor` `model` `text` `time` `math` `collections` `sys` `secure` `test`.

`use <module>` brings a module's shared signatures into scope. The prelude
([doc 05 §5.13](05-types-and-semantics.md)) is always available.

---

## 11.1 `ui` — pages, views and layout **[N]**

### 11.1.1 The model

A `page` declares a **view**: a pure function from state to a tree of view nodes. The
runtime diffs successive views and applies the minimum set of platform operations. A
page re-renders when a value it reads changes — dependency tracking is derived from the
effect paths of [doc 07 §7.2](07-concurrency-and-simd.md), so it is exact, not
heuristic.

```coco
page Home
  show text Welcome
  show button Start

  when Start is pressed
    open page Game
```

### 11.1.2 Core view signatures

```sig
signature show text
  slot content of kind text open
  declarative
  gives a view node

signature show button
  slot label of kind text
    terminated by to page
    terminated by with style
    terminated by named
  optional particle to page
    slot target of kind ref
  optional particle with style
    slot style of kind ref
  optional particle named
    slot key of kind name
  declarative
  gives a view node

signature show picture
  slot source of kind value
  optional particle with style
    slot style of kind ref
  declarative
  gives a view node

signature show field
  slot prompt of kind text
    terminated by into
  particle into
    slot binding of kind ref
  declarative
  gives a view node

signature show list of
  slot items of kind value
  particle showing each as
    slot body of kind block
  declarative
  gives a view node

signature show spacer
  declarative
  gives a view node

signature show divider
  declarative
  gives a view node
```

### 11.1.3 Layout

Layout is a small set of block-taking signatures, not a stylesheet language:

```sig
signature in a row
  optional particle spaced
    slot gap of kind value
  slot body of kind block
  declarative
  gives a view node

signature in a column
  optional particle spaced
    slot gap of kind value
  slot body of kind block
  declarative
  gives a view node

signature in a grid of
  slot columns of kind number
  slot body of kind block
  declarative
  gives a view node

signature scrolling
  slot body of kind block
  declarative
  gives a view node

signature centred
  slot body of kind block
  declarative
  gives a view node
```

```coco
page Profile
  in a column spaced 12
    show picture avatar of current user
    show text name of current user
    in a row spaced 8
      show button Follow
      show button Message
```

Layout is **flex-like**: a row/column distributes space by each child's `grow` style,
with a single-pass measure and a single-pass arrange. The algorithm is specified in
`spec/appendix/layout.md` (implementations must match it exactly so that a page renders
identically on every platform).

### 11.1.4 Style

Styles are declarations, not strings:

```coco
a style called heading is
  text size 28
  text weight bold
  text colour deep green
  space below 12

page Home
  show text Welcome with style heading
```

```sig
signature a style called
  slot name of kind name
  particle is
    slot body of kind block
  gives a style

signature text size
  slot value of kind value
  declarative

signature text colour
  slot value of kind value
  declarative

signature background
  slot value of kind value
  declarative

signature padding
  slot value of kind value
  declarative

signature corner radius
  slot value of kind value
  declarative

signature grow
  slot factor of kind value
  declarative
```

Styles compose (`with style heading and emphasis`), are resolved at compile time where
possible, and produce no runtime string parsing.

### 11.1.5 Navigation

```sig
signature open page
  slot target of kind ref
  effects io
  gives nothing

signature go back
  effects io
  gives nothing

signature replace page with
  slot target of kind ref
  effects io
  gives nothing

signature show sheet
  slot target of kind ref
  effects io
  gives nothing
```

The navigation stack is runtime state; `go back` is available on every platform,
mapping to the browser history, the Android back gesture, or a window action.

### 11.1.6 Accessibility **[N]**

Every view node carries accessibility information **by construction**: `show button`
produces a node with role *button* and the label from its `label` slot. An implementation
MUST map view nodes to the platform accessibility tree (UIA, AX, AT-SPI, ARIA for the
DOM back end). `show picture` without a `described as` slot produces warning `W-1114`.

```sig
signature described as
  slot description of kind text open
  declarative
```

## 11.2 `events` — the dispatch system **[N]**

The `when [event] → [action]` model.

```sig
signature is pressed of kind event
  subject of kind ref

signature is changed of kind event
  subject of kind ref

signature touches of kind event
  subject of kind ref
  slot other of kind ref

signature reaches of kind event
  subject of kind ref
  slot threshold of kind value

signature the page opens of kind event

signature the page closes of kind event

signature the world updates of kind event
  note fires once per frame, carrying `since last time` in scope

signature every of kind event
  slot interval of kind value

signature a request arrives of kind event
  optional particle at
    slot route of kind text open
```

Declaring your own:

```coco
to notice a user posts something
  give an event

when user posts something
  save post
  show post to followers
```

Emitting:

```sig
signature announce
  slot event of kind ref
  optional particle with
    slot payload of kind value
  effects io
```

### 11.2.1 Handler ordering and conflicts

Specified in [doc 07 §7.3–7.5](07-concurrency-and-simd.md). The user-visible rule:

> Handlers that touch different things run at the same time. Handlers that touch the same
> thing run one after another, in the order they appear in your source.

## 11.3 `text` **[N]**

```sig
signature join
  slot parts of kind block
  gives text

signature length of
  slot value of kind value
  gives a whole number

signature upper case of / lower case of / trimmed
  slot value of kind value
  gives text

signature split
  slot value of kind value
  particle on
    slot separator of kind text open
  gives a list of text

signature replace
  slot needle of kind text
    terminated by with
    terminated by in
  particle with
    slot replacement of kind text
      terminated by in
  particle in
    slot haystack of kind value
  gives text

signature starts with / ends with / contains
  slot haystack of kind value
  particle …
    slot needle of kind value
  gives yes or no

signature format
  slot value of kind value
  optional particle with
    slot options of kind ref
  gives text

signature compare
  slot first of kind value
  particle and
    slot second of kind value
  particle using locale
    slot locale of kind value
  gives a whole number
```

`format` handles numbers, dates and durations with runtime locale rules (CLDR data
shipped with the runtime, ~40 KB for the default set, more downloadable as a package).

### 11.3.1 Messages and the display locale **[N]**

What the application says to its user is declared, not written inline. The declaration
form and its rules are in [doc 04 §4.12](04-multilingual.md); the runtime surface is:

```sig
signature the display locale
  gives text
  effects reads

signature set the display locale to
  slot locale of kind ref
  gives nothing
  effects io writes

signature the wording of
  slot message of kind ref
  particle in
    slot locale of kind ref
  gives text
  effects reads
  note for previewing another locale without changing the process locale

signature the plural category of
  slot count of kind value
  particle in
    slot locale of kind ref
  gives a plural category
  effects reads
```

Messages are resolved against the display locale at the point of use, so a page that
splices a message re-renders when the display locale changes — the dependency is an
ordinary effect path ([doc 07 §7.2](07-concurrency-and-simd.md)), not a special case.

## 11.4 `collections` **[N]**

```sig
signature add            slot item … particle to … slot collection of kind ref
signature remove         slot item … particle from … slot collection of kind ref
signature insert         slot item … particle at … slot index … particle into … slot collection
signature count of       slot collection of kind value            gives a whole number
signature is empty       slot collection of kind value            gives yes or no
signature first in       slot collection of kind value            gives maybe element
signature last in        slot collection of kind value            gives maybe element
signature first in … where
                         slot collection … particle where … slot condition of kind block
                                                                  gives maybe element
signature every … in … where
                         gives a list of element
signature sorted by      slot collection … particle by … slot key of kind block
                                                                  gives a list of element
signature sum of / product of / minimum of / maximum of
                         slot collection of kind value            gives element
signature reversed       slot collection of kind value            gives a list of element
signature grouped by     slot collection … particle by … slot key of kind block
                                                                  gives a table
```

All of these are ordinary generic Coco actions; there is no special-cased "builtin"
behaviour. They vectorise under the rules of [doc 07 §7.9](07-concurrency-and-simd.md).

## 11.5 `net` — lightweight async networking **[N]**

```sig
signature get from
  slot url of kind text open
  gives text
  may fail with a network problem
  effects io blocks

signature get json from
  slot url of kind text open
  gives a json value
  may fail with a network problem
  effects io blocks

signature post
  slot body of kind value
    terminated by to
  particle to
    slot url of kind text open
  optional particle as
    slot format of kind ref
  gives text
  may fail with a network problem
  effects io blocks

signature download
  slot url of kind text
    terminated by into
  particle into
    slot path of kind text open
  gives nothing
  may fail with a network problem
  effects io blocks

signature open a socket to
  slot url of kind text open
  gives a socket
  may fail with a network problem
  effects io blocks

signature send
  slot message of kind value
  particle over
    slot socket of kind ref
  effects io blocks

signature serve
  optional particle on port
    slot port of kind number
  slot body of kind block
  effects io blocks
```

Concurrency:

```coco
when the page opens
  fetch these at the same time
    let profile be get json from https example com api me
    let feed be get json from https example com api feed
  show profile and feed
```

Server:

```coco
use net

serve on port 8080
  when a request arrives at /health isolated
    reply with text
      ok

  when a request arrives at /users isolated
    let users be every row in people
    reply with json users
```

Transport details: HTTP/1.1 + HTTP/2 + HTTP/3 client, TLS 1.3 via the platform store,
connection pooling, automatic retry with jitter for idempotent methods, and a hard
deadline on every operation ([doc 07 §7.7.1](07-concurrency-and-simd.md)).

## 11.6 `store` — embedded persistent storage **[N]**

An embedded, transactional, single-file store. Not a SQL dialect — Rule 5 forbids a
second query language — but a set of Coco signatures over typed collections.

```coco
use store

a person has
  name as text
  age as a whole number
  city as text

the collection people holds person
  indexed by city
  indexed by name unique

when a user signs up
  put a person with
    name as given name
    age as given age
    city as given city
  into people
```

```sig
signature the collection
  slot name of kind name
  particle holds
    slot type of kind ref
  optional repeated particle indexed by
    slot field of kind name
  gives nothing

signature put
  slot value of kind value
    terminated by into
  particle into
    slot collection of kind ref
  effects io writes

signature every row in
  slot collection of kind ref
  optional particle where
    slot condition of kind block
  optional particle sorted by
    slot key of kind block
  optional particle limited to
    slot limit of kind number
  gives a list
  effects reads

signature the row in
  slot collection of kind ref
  particle where
    slot condition of kind block
  gives maybe a row
  effects reads

signature change every row in
  slot collection of kind ref
  particle where
    slot condition of kind block
  particle to
    slot body of kind block
  effects io writes

signature delete every row in
  slot collection of kind ref
  particle where
    slot condition of kind block
  effects io writes

signature all at once
  slot body of kind block
  effects io writes
  note a transaction: everything inside commits together or not at all
```

Implementation: a log-structured B-tree with MVCC snapshots, WAL, full ACID,
crash-safe, with a file format versioned and forward compatible. Queries compile to
index plans at **compile time**, because the condition block is ordinary Coco that the
compiler can analyse — so there is no query planner at runtime and no string
interpolation, which means **SQL injection is not expressible**.

```sig
signature connect to postgres at
  slot url of kind text open
  gives a database
  effects io blocks
```

External databases are a package, using the same signature shapes, so switching from the
embedded store to Postgres changes the connection line and nothing else.

## 11.7 `draw2d`, `scene3d`, `physics`, `audio`, `input` **[N]**

### 11.7.1 `draw2d`

```sig
signature draw a rectangle
  particle at        slot position of kind value
  particle sized     slot size of kind value
  optional particle filled with  slot paint of kind value
  optional particle outlined with slot paint of kind value
  effects device cpu

signature draw a circle
  particle at slot centre of kind value
  particle with radius slot radius of kind value
  optional particle filled with slot paint of kind value

signature draw a line
  particle from slot start of kind value
  particle to   slot finish of kind value
  optional particle thick slot width of kind value

signature draw text
  slot content of kind text
    terminated by at
  particle at slot position of kind value
  optional particle with style slot style of kind ref

signature draw
  slot sprite of kind value
  particle at slot position of kind value
  optional particle rotated slot angle of kind value
  optional particle scaled slot scale of kind value
```

Backed by a GPU-accelerated 2D renderer (tessellation + signed-distance-field text),
falling back to CPU rasterisation where no GPU exists.

### 11.7.2 `scene3d`

```sig
signature a scene called
  slot name of kind name
  slot body of kind block

signature add a model
  slot source of kind value
  particle at slot position of kind value
  optional particle rotated slot rotation of kind value
  optional particle scaled slot scale of kind value
  gives an entity

signature add a light
  slot kind of kind ref
  particle at slot position of kind value
  optional particle coloured slot colour of kind value
  optional particle strength slot strength of kind value

signature the camera
  particle at slot position of kind value
  particle looking at slot target of kind value
  optional particle field of view slot fov of kind value

signature a material called
  slot name of kind name
  particle is slot body of kind block
  note base colour, roughness, metalness, normal map, emission
```

Renderer: clustered forward+ with physically based shading, cascaded shadow maps,
GPU-driven culling, and an optional deferred path. Assets: glTF 2.0 in, with an
Coco-native packed format produced at build time by `compose assets`.

### 11.7.3 `physics`

```sig
signature give
  slot entity of kind ref
  particle a body that is
    slot kind of kind ref          note solid, moving, or trigger
  optional particle shaped like
    slot shape of kind value
  optional particle with mass
    slot mass of kind value

signature push
  slot entity of kind ref
  particle with force
    slot force of kind value

signature when … touches … of kind event
  note the collision event of doc 11 §11.2
```

2D and 3D rigid bodies, continuous collision detection, a deterministic fixed-step
solver (so [doc 07 §7.5](07-concurrency-and-simd.md) determinism holds for replays and
for lockstep multiplayer).

### 11.7.4 `audio`

```sig
signature play sound
  slot which of kind ref
  optional particle at volume slot volume of kind value
  optional particle from position slot position of kind value
  effects io

signature play music
  slot which of kind ref
  optional particle looping
  effects io

signature stop sound
  slot which of kind ref
  effects io
```

Mixing graph with 3D spatialisation, streaming decode, sample-accurate scheduling.

### 11.7.5 `input`

```sig
signature when … is held of kind event
signature when … is released of kind event
signature the pointer position         gives a point
signature the direction from           slot stick of kind ref   gives a point
signature vibrate
  slot controller of kind ref
  particle for slot duration of kind value
```

## 11.8 `tensor` and `model` — GPU-accelerated numerics **[N]**

```sig
signature a tensor of
  slot shape of kind value
  optional particle holding slot kind of kind ref      note decimal 32, decimal 16, whole 8
  optional particle filled with slot value of kind value
  gives a tensor
  effects allocates

signature the shape of / the size of
  slot tensor of kind value
  gives a list of whole numbers

signature matrix product of
  slot first of kind value
  particle and slot second of kind value
  gives a tensor
  effects device any

signature elementwise
  slot operation of kind ref
  particle over slot tensors of kind value
  gives a tensor
  effects device any

signature reduce
  slot tensor of kind value
  particle by slot operation of kind ref
  optional particle over axis slot axis of kind number
  gives a tensor
  effects device any

signature reshape / transpose / slice / concatenate
  ...
```

Models:

```sig
signature create neural network
  slot name of kind name
  slot body of kind block
  gives a model

signature a dense layer of
  slot units of kind number
  optional particle activated by slot activation of kind ref
  declarative

signature an attention layer with
  slot heads of kind number
  particle and width slot width of kind number
  declarative

signature train
  slot model of kind ref
  particle on slot data of kind value
  optional particle for slot epochs of kind number
  optional particle using slot optimiser of kind ref
  effects device any io blocks

signature ask
  slot model of kind ref
  particle about slot input of kind value
  gives a tensor
  effects device any
```

Faithful to the original concept:

```coco
create neural network Brain
  an embedding layer of 512
  repeat 12 times
    an attention layer with 8 heads and width 512
    a dense layer of 2048 activated by gelu
  a dense layer of vocabulary size

give Brain training data from corpus
train Brain for 3 epochs using adam

when Brain receives text
  generate an answer
```

Gradients come from **reverse-mode automatic differentiation on CIR-C**: `train`
differentiates the model's forward CIR, so a user-written layer is differentiable
without any registration step. The AD transform is a middle-end pass
([doc 09 §9.5](09-compiler-pipeline.md)) and is subject to the verifier.

## 11.9 `math`, `time`, `sys`, `secure` **[N]**

```sig
signature random number between
  slot low of kind value
  particle and slot high of kind value
  gives a number
  effects random

signature now                       gives a moment           effects time
signature wait for
  slot duration of kind value       effects blocks
signature since
  slot moment of kind value         gives a duration         effects time

signature the number of processors  gives a whole number     effects reads
signature the amount of memory used gives a whole number     effects reads
signature read file
  slot path of kind text open       gives text
  may fail with a file problem      effects io blocks
signature write
  slot content of kind value
  particle into slot path of kind text open
  may fail with a file problem      effects io blocks

signature hash of
  slot value of kind value
  optional particle using slot algorithm of kind ref
  gives text

signature encrypt / decrypt
  slot value of kind value
  particle with key slot key of kind ref
  gives a sealed value

signature a secret called
  slot name of kind name
  gives text
  effects io
  note read from the platform keychain or the environment; never from source
```

`secure` deliberately has **no** signature that takes a key as inline text, so a
hard-coded key is not expressible; `compose audit` reports any `a secret called` whose
value is absent at build time.

## 11.10 `test` **[N]**

```sig
signature a test called
  slot name of kind text
    terminated by checks
  particle checks
    slot body of kind block

signature expect
  slot actual of kind value
  particle to be
    slot expected of kind value

signature expect
  slot actual of kind value
  particle to be near
    slot expected of kind value
  optional particle within
    slot tolerance of kind value

signature expect this to fail
  slot body of kind block
```

```coco
use test

a test called damage reduces health checks
  let hero be a player with health as 100
  damage hero by 30
  expect health of hero to be 70
```

`compose test` discovers every `a test called` in the project, runs them in parallel
(they are handlers with disjoint state by construction), and reports. Property testing:

```coco
a test called sums are commutative checks
  for any whole numbers a and b
    expect a plus b to be b plus a
```

`for any` generates values with a seeded, reproducible generator and shrinks failures.

## 11.11 Stability policy **[N]**

| Tier | Meaning |
| --- | --- |
| **stable** | Will not change within an edition. |
| **preview** | May change; must be enabled with `use preview <module>`; produces `W-1191`. |
| **deprecated** | Still works; produces `W-1192` with the replacement signature and a fix-it. |

A signature is never removed within an edition. An edition boundary may remove
signatures deprecated for at least one full edition.

---

*Next: [12 — Toolchain](12-toolchain.md)*
