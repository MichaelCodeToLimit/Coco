# 04 — Multilingual Lexical Architecture

*Edition 2026. **[N]** normative, **[I]** informative.*

Coco's claim is that the same program can be written in English, Hebrew, Japanese,
Arabic or Spanish and compile to **byte-identical** output. This document specifies the
mechanism that makes that true rather than aspirational.

---

## 4.1 The architecture in one picture **[I]**

```
  English source ─┐
  Hebrew source  ─┤                        ┌─ x86-64
  Japanese source ┼─► Locale Binding ──► Canonical CIR ──►┼─ ARM64
  Arabic source  ─┤     (lexeme → ID)      (opcode IDs)   ├─ WASM
  Spanish source ─┘                        ▲              └─ SPIR-V
                                           │
                                  canonical hash
                                  proves equivalence
```

The only thing a locale supplies is a **bijection between human lexemes and stable
identifiers**. Everything downstream of the parser sees identifiers, never words. This
is why the design is sound: there is no place for a locale to leak into semantics.

## 4.2 Stable identifiers **[N]**

Every keyword phrase, particle phrase, slot, type, and core-library entity has a
**Canonical Identifier (CID)** — an ASCII string in a reserved namespace, fixed forever
once published:

```
core.stmt.show_text
core.stmt.show_button
core.stmt.open_page
core.slot.show_button.label
core.slot.show_button.target
core.particle.to_page
core.op.add
core.op.is_less_than
core.type.whole_number
core.event.is_pressed
```

Normative rules:

1. A CID MUST match `[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+` and MUST be stable across
   editions. A CID may be **deprecated** but never **reassigned**.
2. CIDs are *not* English. They are opaque keys that happen to be spelled with Latin
   letters for the same reason Unicode code point names are: they must be typable
   everywhere. `core.stmt.show_text` has no more claim to being the "real" name of the
   statement than `הצג טקסט` does.
3. Package CIDs are namespaced by package: `plotting.stmt.draw_chart`.
4. User declarations receive **module-local CIDs** derived from their declaration
   position and canonical name, see §4.8.

## 4.3 Locale files **[N]**

A locale file binds CIDs to lexemes for one human language. It lives at
`registry/locales/<tag>.locale` where `<tag>` is a BCP-47 language tag.

```locale
locale he
  name עברית
  direction right to left
  decimal separator .
  group separator ,

  particle to        = ל
  particle to page   = לעמוד
  particle with      = עם
  particle by        = ב
  particle of        = של
  particle from      = מ
  particle as        = בתור
  particle and       = ו

  reserved note when if otherwise while repeat for each let keep set to
  reserved words הערה כאשר אם אחרת כלעוד חזור לכל תן שמור קבע

  word note      = הערה
  word when      = כאשר
  word if        = אם
  word otherwise = אחרת
  word while     = כלעוד
  word repeat    = חזור
  word let       = תן
  word keep      = שמור
  word set       = קבע
  word give      = החזר
  word text      = טקסט
  word value of  = ערך של
  word yes       = כן
  word no        = לא
  word group     = קבוצה

  op plus            = ועוד
  op minus           = פחות
  op times           = כפול
  op over            = חלקי
  op is              = הוא
  op is not          = אינו
  op is more than    = גדול מ
  op is less than    = קטן מ
  op and             = וגם
  op or              = או
  op not             = לא

  stmt core.stmt.show_text   = הצג טקסט
  stmt core.stmt.show_button = הצג כפתור
  stmt core.stmt.open_page   = פתח עמוד
  stmt core.decl.page        = עמוד
  stmt core.event.is_pressed = נלחץ

  slot core.slot.show_button.label  = תווית
  slot core.slot.show_button.target = יעד
```

### 4.3.1 Locale well-formedness **[N]**

A locale MUST satisfy:

| Condition | Statement |
| --- | --- |
| **L1 — Totality** | Every CID in the core registry has exactly one binding. A locale missing a binding fails to load (`E-0401`) rather than falling back to English. |
| **L2 — Injectivity** | No two CIDs bind to the same lexeme phrase. (`E-0402`) |
| **L3 — Admissibility** | The registry obtained by substituting this locale's lexemes MUST satisfy R1–R6 of [doc 03 §3.6](03-clause-registry.md). (`E-0403`) |
| **L4 — Reserved closure** | Every word appearing in any head or particle phrase is listed in the locale's `reserved words`. (`E-0404`) |
| **L5 — Script consistency** | All lexemes in a locale belong to one script run class (segmented or unsegmented), so §1.4 applies uniformly. Mixed-script locales MUST declare `segmentation mixed` and supply an explicit lexicon order. |

L3 is the important one: **a locale is only valid if it produces an unambiguous
grammar**. A proposed Hebrew binding where `עם` (with) is a prefix of a name used in the
same program is rejected at locale-load time, in *that locale*, without affecting others.

`compose locale check he` runs L1–L5 and prints the proof obligations.

## 4.4 Locale selection **[N]**

The `write in <locale>` directive is the one construct recognised in **every** locale,
including ones it is not written in. It has to be: the locale is not known until the
directive has been read. An implementation MUST accept both the English spelling and the
locale's endonym (`write in hebrew`, `write in עברית`), and MUST treat the line as a
directive wherever it appears in the file. Everything else in the file, including `note`
comments, is in the file's locale.

Resolution order, first hit wins:

1. `write in <locale>` directive anywhere in the file.
2. `locale` field in `project.coco` for the module's directory.
3. The `COCO_LOCALE` environment variable.
4. `en`.

A **file** has exactly one locale. A **project** may mix locales across files freely —
they meet at the CIR level, so a Hebrew module and a Japanese module link without any
bridging code. Names declared in one file and `share`d are visible in another file in a
different locale **by their canonical name** (§4.8).

## 4.5 Right-to-left languages **[N]**

Already specified lexically in [doc 01 §1.8](01-lexical-structure.md). The additional
locale-level requirements are:

1. `direction right to left` in the locale file sets the base paragraph direction used by
   `compose format`, `compose doc`, and diagnostics.
2. Diagnostics rendered for an RTL locale MUST isolate embedded LTR spans (file paths,
   CIDs, numbers) with `U+2066 LRI … U+2069 PDI` so the message renders correctly in a
   terminal. This is the one place Coco emits bidi controls.
3. Column numbers in diagnostics are **logical** code-point offsets. Editors receive an
   additional `visualColumn` via the LSP extension `coco/bidiColumn`
   ([doc 13 §13.6](13-lsp.md)) for caret placement.
4. Indentation is written at the **logical start** of the line, which every RTL-aware
   editor renders on the right. No special handling is needed.

### 4.5.1 Arabic locale sample **[I]**

```locale
locale ar
  name العربية
  direction right to left
  particle to page = إلى صفحة
  particle with    = مع
  stmt core.stmt.show_text   = اعرض نصا
  stmt core.stmt.show_button = اعرض زرا
  stmt core.stmt.open_page   = افتح صفحة
  stmt core.decl.page        = صفحة
  stmt core.event.is_pressed = ضُغط
```

```coco
write in arabic

صفحة الرئيسية
  اعرض نصا مرحبا بك
  اعرض زرا ابدأ

  كاشر ابدأ ضُغط
    افتح صفحة اللعبة
```

## 4.6 Numeric conventions **[N]**

A locale declares `decimal separator` and `group separator`. These affect **only**
numeric literals in source (§1.5) and the compiler's rendering of numbers in
diagnostics. They do **not** affect:

- the CIR, which stores numbers as IEEE-754 binary64 / two's-complement integers;
- runtime formatting, which is controlled by the application's runtime locale via
  `format value with locale` in the `text` module.

An implementation MUST reject a locale whose decimal and group separators are equal
(`E-0405`).

## 4.7 Unsegmented scripts in depth **[N]**

Algorithm LEX-UNSEG ([doc 01 §1.4.2](01-lexical-structure.md)) requires a lexicon. The
lexicon for a file is:

```
Lexicon(file) = lexemes(locale)                    (* keywords, particles, operators *)
              ∪ lexemes(visible signature heads)    (* from the registry, in this locale *)
              ∪ visible declared names
```

Because the visible name set grows as the parser proceeds, LEX-UNSEG is run
**incrementally, line by line**, after name collection for the current scope. This is
still deterministic: the lexicon at any line is a pure function of the preceding
declarations, which are themselves lexed with the lexicon available at their own lines.
Implementations MUST perform a **two-pass** collection (declaration heads first, bodies
second) so that forward references work; the first pass uses only
`lexemes(locale) ∪ lexemes(registry)`, which is fixed.

### 4.7.1 Japanese locale sample **[I]**

```locale
locale ja
  name 日本語
  direction left to right
  segmentation unsegmented
  particle to page = のページへ
  particle with    = とともに
  particle by      = だけ
  word when        = のとき
  word if          = もし
  word text        = テキスト
  stmt core.stmt.show_text   = という文字を表示
  stmt core.stmt.show_button = というボタンを表示
  stmt core.stmt.open_page   = ページを開く
  stmt core.decl.page        = ページ
  stmt core.event.is_pressed = が押された
```

Japanese word order puts the object before the verb, which the signature system handles
naturally because a signature's segments may begin with a slot:

```sig
signature core.stmt.show_text
  in locale ja
    slot content of kind text open
    head という文字を表示
```

Source:

```coco
write in japanese

ページ ホーム
  こんにちはという文字を表示
  スタートというボタンを表示

  スタートが押されたのとき
    ゲームページを開く
```

Trace of line 3 (`こんにちはという文字を表示`):

| Position | Longest lexicon match | Emitted |
| --- | --- | --- |
| 0 | none of `という文字を表示`, `というボタンを表示`, … matches at 0 | scan forward |
| 5 | `という文字を表示` matches | `WORD("こんにちは")`, then `WORD("という文字を表示")` |

The parser sees a slot-first signature: `content` = `こんにちは`, head =
`という文字を表示`. Identical CIR to `show text Hi`.

### 4.7.2 Slot-first signatures **[N]**

A locale MAY reorder a signature's segments, including placing the head after a slot,
by declaring an `in locale` override:

```sig
signature core.stmt.show_button
  slot label of kind text
    terminated by to page
  optional particle to page
    slot target of kind ref

  in locale ja
    slot label of kind text
      terminated by のページへ
    head というボタンを表示
    optional particle のページへ
      slot target of kind ref
```

Constraints:

- The override MUST bind exactly the same slot CIDs, with the same kinds and the same
  optionality. Reordering is permitted; adding, removing or retyping slots is not
  (`E-0406`).
- The overridden form MUST independently satisfy R1–R6 in that locale (condition L3).

### 4.7.3 Heads terminate the slots that precede them **[N]**

> **Rule H.** When a locale's segment order places a greedy slot *before* the head, the
> head phrase is automatically added to that slot's terminator set.

Without this rule a slot-first ordering would be unparseable: an `open` slot placed
first would swallow its own head. With it, `Game started という文字を表示` terminates
the content slot at `という文字を表示` and yields content = `Game started`, which is
the same value the English `show text Game started` produces.

Rule H is what makes condition R2 hold for reordered signatures, and it is why an
`open` slot may legally be non-final in a slot-first locale: it is no longer open there,
because the head closes it.

### 4.7.4 Splice order **[N]**

The value splice of [doc 01 §1.7.1](01-lexical-structure.md) is written
`value of score` in English, but Japanese puts the possessor first: `score の値`. A
locale declares which, with

```locale
splice order = marker first     (* the default: `value of score` *)
splice order = ref first        (* `score の値` *)
```

Both forms lower to the identical splice node, so a text slot containing a splice has
the same canonical form in every locale. A locale MUST NOT introduce any other splice
syntax.

This is the feature that makes Coco genuinely multilingual rather than
"English with a translated dictionary": SOV languages get SOV signatures, VSO languages
get VSO signatures, and all of them produce the same CIR.

## 4.8 Names across locales **[N]**

Declared names are author-chosen words, not keywords, so they are **not** translated.
A Hebrew module that declares `עמוד ראשי` and shares it is referenced from an English
module as `עמוד ראשי`.

To allow cross-locale libraries, a declaration may carry an explicit CID and per-locale
names:

```coco
note doc The main landing page.
page Home
  also known as עמוד ראשי in hebrew
  also known as ホーム in japanese
  ...
```

Rules:

- `also known as <name> in <locale>` adds an alias visible only when that locale is
  active.
- All aliases of a declaration share one CID, so they are the same entity in CIR.
- Aliases participate in R6 and L2 checks in their own locale.
- `compose doc` lists all aliases.

## 4.9 Lossless source translation **[N]**

Because the locale binding is a bijection (L2) and the parse is deterministic (R1–R6),
translating a source file between locales is a **total, information-preserving,
mechanical** operation:

```bash
compose translate app.coco --to hebrew --out app.he.coco
```

Normative requirements for `compose translate`:

1. `translate(translate(S, A→B), B→A)` MUST be identical to `S` modulo whitespace
   normalisation performed by `compose format`.
2. `canonical_hash(compile(S)) == canonical_hash(compile(translate(S, A→B)))` MUST hold
   for every well-formed *S*.
3. Content of `text` slots and text blocks is **never** translated — it is application
   data, not code. The tool emits a report listing every text slot so a human translator
   can localise the application separately. §4.12 is the language's answer to that
   problem, and the report names every text slot that should become a message.
4. `note` comments are preserved verbatim and marked in the report.
5. If a name would violate R6 in the target locale, translation fails with `E-0407` and
   names the offending identifier. It does not silently rename.

Requirement 2 is checked by the conformance suite ([doc 15 §15.4](15-conformance-and-editions.md))
and by `compose translate --verify`, which compiles both and compares hashes.

## 4.10 Adding a locale **[I]**

```bash
compose locale new pt            # scaffold registry/locales/pt.locale with every CID unbound
compose locale check pt          # L1..L5
compose locale coverage pt       # percentage of core + stdlib CIDs bound
compose translate examples/hello.coco --to pt --verify
```

A locale is complete when `compose locale coverage` reports 100% for `core`, and is
publishable as a package when it reaches 100% for the standard library. Locale packages
are versioned and pinned like any dependency, so a locale update cannot silently change
how an existing project parses.

## 4.11 What locales may never do **[N]**

To keep Rule 3 of [doc 00](00-overview.md) intact:

- A locale MUST NOT introduce a new CID. It binds existing ones.
- A locale MUST NOT change a signature's slot kinds, count, optionality, result type or
  effects.
- A locale MUST NOT change operator precedence.
- A locale MUST NOT change evaluation order.
- A locale MUST NOT affect the CIR in any way other than through the source that
  produced it.

An implementation MUST be able to demonstrate this: `compose build --emit cir` output is
required to be byte-identical across locales for translated sources, and this is a
conformance test.

---

*Next: [05 — Types and semantics](05-types-and-semantics.md)*

## 4.12 Localising what the application says **[N]**

Everything above is about the language the **programmer** writes in. This section is
about the language the **user** reads. They are separate problems and Coco keeps them
separate, because conflating them is the single most common mistake in this area.

### 4.12.1 The distinction **[I]**

```coco
show text Hi
```

puts the *word* `Hi` into the program. It is data, like `42`. Translating the source to
Hebrew translates the instruction, not the word — so the Hebrew source still shows `Hi`,
and that is correct. A program that greets a Hebrew-speaking user with `שלום` has to say
so, in the program, in every language it supports.

### 4.12.2 Messages **[N]**

A **message** is one idea with a wording per human language:

```coco
the message greeting says
  in english Hi
  in hebrew שלום
  in japanese こんにちは

show text value of greeting
```

```ebnf
message-decl   = "the" , "message" , name , "says" , NEWLINE ,
                 INDENT , wording , { wording } , DEDENT ;
wording        = "in" , locale-name , text-run , NEWLINE ;
```

Normative rules:

1. A message has type `text`. It is used like any other `text` value — spliced into a
   slot, passed to an action, stored.
2. Each wording's content is an **open** text slot, so nothing can truncate it. Commas,
   percent signs and the word `in` are all ordinary text.
3. Resolution happens at **run time**, against the application's *display locale*
   (§4.12.4), not at compile time. All wordings are present in the binary.
4. A message MUST have a wording for the project's `default locale`; missing that is
   error `E-0411`.
5. A message with no wording for a locale the project claims to support produces warning
   `W-0412`, naming the message and the locale.
6. Wordings are **not** deduplicated across messages and are **not** ordered by the
   source's locale. The canonical form sorts wordings by locale tag, so the same message
   written in an English source file and in its Japanese translation have the identical
   canonical hash.

### 4.12.3 Placeholders and plurals **[N]**

A wording may splice, and different languages may use a different order:

```coco
the message score line says
  in english value of name scored value of points
  in hebrew ערך של name צבר ערך של points
```

The splice names refer to whatever is in scope where the message is *used*, checked at
the use site. A message whose wordings do not all splice the same set of names is error
`E-0413` — this catches the classic bug where a translator drops a placeholder.

Plural and gender selection is by wording variants:

```coco
the message item count says
  in english
    when none        No items
    when one         One item
    when many        value of count items
  in hebrew
    when none        אין פריטים
    when one         פריט אחד
    when two         שני פריטים
    when many        ערך של count פריטים
```

The categories are CLDR's (`none`, `one`, `two`, `few`, `many`, `other`) and which ones
a locale needs is a property of the locale, so a Hebrew wording that omits `two` is
`W-0412` and an English one that includes it is `W-0414`.

### 4.12.4 The display locale **[N]**

```coco
use text

show text the display locale
set the display locale to hebrew
```

- The display locale defaults to the platform's user locale, not to the source locale.
- It is per-process, and reading it has effect `reads`, so a page that reads it
  re-renders when it changes ([doc 11 §11.1.1](11-stdlib.md)).
- Number, date, duration and collation formatting follow the display locale
  ([doc 11 §11.3](11-stdlib.md)), independently of any message.

### 4.12.5 Tooling **[N]**

| Command | Does |
| --- | --- |
| `compose locale coverage --messages` | percentage of messages covered per display locale |
| `compose locale extract` | writes every message to an interchange file for translators |
| `compose locale merge <file>` | reads translations back, preserving splice checks |
| `compose check --deny missing wordings` | turns `W-0412` into an error for release builds |

`compose locale extract` emits XLIFF 2.1 so existing translation tooling works
unchanged. This is deliberately the one place Coco speaks someone else's format: the
people doing the translating are not programmers and should not have to learn Coco.

### 4.12.6 Why this is a language feature and not a library **[I]**

It could have been a library that reads a catalogue file at startup. It is not, for
three reasons:

- **The compiler can check it.** Missing wordings, dropped placeholders and wrong plural
  categories are compile-time errors here and runtime surprises everywhere else.
- **Rule 5** ([doc 00 §0.3](00-overview.md)) says an application needs no second syntax.
  A `.po` or `.json` catalogue would be exactly that.
- **It closes the multilingual story honestly.** A language that lets you write source in
  your own language but cannot ship an application in your user's language has solved the
  smaller half of the problem.
