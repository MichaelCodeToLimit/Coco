# 01 — Lexical Structure

*Edition 2026. **[N]** normative, **[I]** informative.*

The lexer's job in a punctuation-free language is unusual: it must produce a token
stream that a parser can consume without ever guessing where a string "starts". Coco
solves this by making the lexer produce only **word-level** tokens and by deferring all
grouping of words into text to the parser, which knows the clause signature and therefore
knows exactly where each slot ends.

> **The lexer never decides what is a string.** It emits words. The parser, driven by the
> Clause Signature Registry, decides which runs of words form `text` slots.

---

## 1.1 Source files **[N]**

- A source file MUST be valid UTF-8. A byte-order mark, if present, MUST be ignored.
- A source file MUST be normalised to Unicode **NFC** before lexing. An implementation
  MUST normalise on read rather than rejecting non-NFC input.
- File extension: `.coco`. Manifest files use the same grammar and are named `project.coco`.
- Line terminators: `LF` (U+000A), `CRLF`, `CR`, `NEL` (U+0085), `LS` (U+2028), `PS`
  (U+2029). All are normalised to a single `NEWLINE` token.
- The file MUST end with a `NEWLINE`; an implementation MUST synthesise one if absent.
- A file MUST NOT contain unassigned code points, `U+0000`, or characters in the
  Unicode `Cf` category other than `U+200D ZWJ`, `U+200C ZWNJ`, `U+061C ALM`,
  `U+200E LRM`, `U+200F RLM`. The five permitted format characters are handled by
  §1.8.

## 1.2 Token kinds **[N]**

| Token | Produced by |
| --- | --- |
| `WORD` | a maximal run of word characters (§1.4) |
| `NUMBER` | a numeric literal (§1.5) |
| `NEWLINE` | a line terminator, after blank-line suppression (§1.6) |
| `INDENT` | an increase in leading indentation (§1.6) |
| `DEDENT` | a decrease in leading indentation (§1.6) |
| `RAWLINE` | one physical line inside a text block, verbatim (§1.7) |
| `EOF` | end of input |

There are no operator tokens, no delimiter tokens, and no string tokens. Words that act
as operators (`plus`, `is more than`) and words that act as particles (`to`, `with`) are
ordinary `WORD` tokens; their role is decided by the parser.

## 1.3 Character classes **[N]**

Two classes matter, and the distinction between them is where Coco's
"no punctuation" rule actually lives.

```
separator        = U+0020 SPACE | U+3000 IDEOGRAPHIC SPACE | U+00A0 NBSP
                 | U+2000..U+200A | U+205F | U+1680

text-char        = any character that is not a separator, a line terminator,
                   or a forbidden format character (section 1.8)

word-char        = letter | mark | digit | connector | apostrophe-like | script-extender
letter           = <Unicode general category L*>
mark             = <Unicode general category M*>      (* combining marks, matras, nikud *)
digit            = <Unicode general category Nd>
connector        = "_"                                (* Pc; permitted inside words only *)
apostrophe-like  = "'" | U+2019 | U+05F3 GERESH | U+055A ARMENIAN APOSTROPHE
script-extender  = U+30FC KATAKANA-HIRAGANA PROLONGED SOUND MARK
                 | U+05F4 GERSHAYIM
                 | U+0640 ARABIC TATWEEL
```

`apostrophe-like` and `script-extender` characters are word characters only when they
occur **between** two other word characters, so a stray apostrophe at the end of a word
terminates it.

### 1.3.1 Where the punctuation rule is enforced **[N]**

A `WORD` token is a maximal run of `text-char`. The lexer therefore accepts
`100%`, `app,` and `{braces}` — it has to, because a `text` slot may contain any
words at all and the lexer does not know where slots begin.

The restriction is applied by the **parser**, which knows each token's role:

> **Rule P.** A `WORD` that the parser uses as part of a keyword phrase, a particle
> phrase, a declared name, a type name, or a `ref` path MUST consist only of
> `word-char`. Otherwise it is error `E-0101`.

So this is fine:

```coco
show text Welcome to my app, 100% of the time — press {Start}
```

and this is not:

```coco
page Home{2}
note E-0101  `Home{2}` cannot be a name: `{` and `}` are not name characters.
```

The practical consequence is exactly the intended one: `{`, `}`, `(`, `)`, `;`, `=`,
`<`, `>` and friends never carry meaning in Coco. They are ordinary text characters
when they appear in text and are rejected everywhere else.

## 1.4 Word segmentation **[N]**

Word segmentation is performed **per script run**. A script run is a maximal sequence of
characters with the same Unicode Script property (with `Common` and `Inherited`
absorbed into the surrounding run).

### 1.4.1 Segmented scripts

For runs in scripts that use inter-word separators — Latin, Cyrillic, Greek, Hebrew,
Arabic, Devanagari, Hangul, and all others not listed in §1.4.2 — a `WORD` is a maximal
run of `word-char`, delimited by `separator`, line terminator, or a script-run boundary.

This is ordinary whitespace tokenisation, and it is what the great majority of the world's
programmers will experience.

### 1.4.2 Unsegmented scripts **[N]**

Han, Hiragana, Katakana, Thai, Lao, Khmer, Myanmar, Tibetan and Javanese runs contain no
inter-word separators. Coco does **not** use a statistical word-breaker for these,
because that would violate the Determinism Rule. It uses **keyword-maximal-munch against
a finite lexicon**:

> **Algorithm LEX-UNSEG.** Let *L* be the set of all keyword phrases, particle phrases
> and declared names currently visible, rendered in the active locale, sorted by
> descending length. Scan the run left to right. At each position *p*:
>
> 1. If some *w* ∈ *L* matches at *p*, emit the longest such *w* as a single `WORD`
>    token carrying the lexeme *w*, and advance by |*w*|.
> 2. Otherwise, let *q* be the least position > *p* at which step 1 would succeed, or the
>    end of the run if none exists. Emit the substring [*p*, *q*) as one `WORD` token.
>
> Ties in step 1 are impossible because the longest match is unique.

This makes segmentation a pure function of (source bytes, locale lexicon, visible name
set) — deterministic, reproducible, and explainable. Its consequences are documented
for users:

- A free-text run in Japanese is emitted as **one** `WORD` token per gap between keyword
  matches. That is exactly what a `text` slot wants.
- A declared name that is a *substring* of a longer keyword will not be recognised where
  the longer keyword matches. The registry conditions ([doc 03 §3.6](03-clause-registry.md),
  condition **R6**) forbid declaring such a name, so the compiler catches it at
  declaration time with `E-0342`, not at use time.
- An optional `U+3000 IDEOGRAPHIC SPACE` may always be inserted by the author to force a
  boundary; it is a `separator` and never appears in a token.

### 1.4.3 Case folding **[N]**

Keyword and particle matching is performed on the **Unicode simple case fold** of the
lexeme. Name matching is performed on the **Unicode case fold with NFKC**. Therefore
`Show Text`, `show text` and `SHOW TEXT` are the same head, and `Game Over`,
`game over` refer to the same page. Text slot contents preserve the author's original
casing exactly.

## 1.5 Numbers **[N]**

```ebnf
NUMBER        = decimal | grouped-decimal ;
decimal       = digits , [ "." , digits ] ;
grouped-decimal
              = digits , { group-sep , digits3 } , [ "." , digits ] ;
group-sep     = "," | U+202F NARROW NBSP ;   (* locale-dependent, see doc 04 §4.6 *)
digits        = Nd , { Nd } ;
digits3       = Nd , Nd , Nd ;
```

- Digits MAY be written in any Unicode decimal digit set (`٠١٢`, `०१२`, `0123`), but a
  single literal MUST NOT mix digit systems (`E-0107`).
- The decimal separator and group separator are **locale properties** declared in the
  locale file ([doc 04 §4.6](04-multilingual.md)), not fixed characters. In the `de`
  locale `1.000,5` is one million and a half; in `en` it is a lexical error. This is the
  only locale-dependent lexical rule besides keyword spelling.
- A `NUMBER` immediately followed by a `word-char` with no separator is a lexical error
  `E-0108`; write `10 times` not `10times`.
- There are no hexadecimal, octal or binary literals in the core language. Use
  `the number written in base 16 as 1f4` from the `math` module, which is const-folded.

### 1.5.1 Numbers inside `text` slots **[N]**

A `NUMBER` token appearing inside a `text` slot contributes its **original source
spelling** to the text, not its numeric value. `show text You have 1,000 points`
displays `You have 1,000 points`.

## 1.6 Lines, indentation and blocks **[N]**

### 1.6.1 Indentation unit

- Indentation MUST be composed of `U+0020 SPACE` only. A leading `TAB` is error `E-0110`
  with fix-it "replace tabs with spaces".
- The file's **indentation unit** *u* is the leading-space count of the first line in the
  file whose indentation is greater than zero. *u* MUST be between 1 and 8.
- Every line's leading-space count MUST be an exact multiple of *u* (`E-0111`).
- Consequently the indentation state is an integer *level* = spaces / *u*.

### 1.6.2 Blank lines and comments

A line that is empty or contains only separators produces **no tokens at all** — no
`NEWLINE`, no `INDENT`, no `DEDENT`. Blank lines are therefore free to use anywhere for
readability and can never change a program's meaning.

A **note** is a comment:

```coco
note this whole line is ignored by the compiler
```

`note` at the start of a line (after indentation) causes the remainder of the physical
line to be discarded. A note line produces no tokens. Notes cannot appear at the end of
a code line — this is deliberate, because a trailing comment marker would be
punctuation. Notes may be indented to any level; their indentation is ignored.

A **doc note** is a note used for documentation extraction:

```coco
note doc Damages a target and returns the remaining health.
to damage a target by an amount
  ...
```

Consecutive `note doc` lines immediately preceding a declaration are attached to it and
surfaced by `compose doc` and by the LSP hover provider.

### 1.6.3 INDENT / DEDENT

Let *prev* be the level of the previous token-producing line and *cur* the level of the
current one.

- If *cur* = *prev* + 1, emit one `INDENT`.
- If *cur* > *prev* + 1, error `E-0112` ("indented by more than one step").
- If *cur* < *prev*, emit (*prev* − *cur*) `DEDENT` tokens.
- At `EOF`, emit `DEDENT` tokens down to level 0, then `EOF`.

`INDENT`/`DEDENT` are emitted **after** the `NEWLINE` of the preceding line.

### 1.6.4 Statement termination

A statement ends at `NEWLINE`. There is no statement separator and no line-continuation
character. A clause whose signature still has unfilled slots when `NEWLINE` is reached
takes its remaining slots from the following **indented** lines (the *hanging form*,
[doc 02 §2.6](02-grammar.md)); otherwise `NEWLINE` completes it.

## 1.7 Text blocks **[N]**

A text block is the universal escape hatch required by the Sugar Law. It is introduced
by a bare `text` keyword occupying the whole of a slot, followed by an indented body:

```coco
set banner to text
  Welcome! You have 100% of your health.
  Press "Start" — or go to page 2 of the manual.
```

Rules:

- Every physical line of the indented body is emitted as one `RAWLINE` token containing
  the line's bytes **after removing exactly the block's indentation prefix**, with no
  further interpretation.
- The block ends at the first line whose indentation is less than the block's level, or
  at `EOF`.
- Inside a `RAWLINE`, **no** character is illegal, no keyword is recognised, no splice is
  performed, and no case folding occurs. This is the only place in Coco where
  arbitrary bytes may appear.
- Lines are joined with a single `U+000A`. A trailing newline is not added.
- Blank lines inside the block are preserved as empty `RAWLINE`s.

### 1.7.1 Splices in text **[N]**

Values are inserted into ordinary (non-block) `text` slots by the reserved two-word
splice phrase `value of`:

```coco
show text Your score is value of score
show text Hello value of name and welcome back
```

- `value of` is recognised **only** inside a `text` slot, and **only** when followed by a
  resolvable `ref`.
- The splice consumes `value of` plus exactly one `ref` ([doc 02 §2.5](02-grammar.md)),
  which may itself be a member path such as `health of player`.
- To place the literal words "value of" in text, use a text block (§1.7). This is the
  Sugar Law working as designed.
- Splices are **not** performed inside `RAWLINE`s. To build text from a block plus a
  value, use `join`:

```coco
set message to join
  text
    Final score:
  value of score
```

Formatting of the spliced value is by the value's `to text` conversion
([doc 11 §11.3](11-stdlib.md)), which is locale-sensitive at runtime and never at
compile time.

## 1.8 Bidirectional text **[N]**

Coco source in Hebrew, Arabic, Persian, Urdu, Syriac and Thaana is written
right-to-left. This has **no effect on the language**, because Coco is defined over
*logical* character order, exactly as every other programming language is.

Normative rules:

1. Lexing, parsing and all semantics operate on **logical order** — the order of code
   points in the file — never on visual order.
2. **Indentation is measured in leading code points of the logical string**, which is
   what every editor produces when you press space at the start of a line, in both
   directions. Implementations MUST NOT attempt to measure visual indentation.
3. The explicit bidi *embedding* and *override* controls `U+202A`–`U+202E` and
   `U+2066`–`U+2069` are **forbidden** in source outside text blocks (`E-0115`). They
   allow a line's visual rendering to differ arbitrarily from its logical meaning, which
   is a security hazard (the "Trojan Source" class of attack) and a readability hazard.
4. The *marks* `U+200E LRM`, `U+200F RLM` and `U+061C ALM` are permitted, are treated as
   `separator`-equivalent for segmentation, and are stripped before any lexeme
   comparison. They let an author fix rendering of mixed-direction lines without
   affecting meaning.
5. A source file MAY declare a base direction for tooling:
   ```coco
   write in hebrew
   ```
   This sets both the locale ([doc 04](04-multilingual.md)) and the base paragraph
   direction used by `compose format` and by editors via the LSP
   `coco/documentDirection` notification. It does not affect compilation.
6. `compose format` emits an `U+2066 LRI … U+2069 PDI` pair **only inside comments and
   only in its own diagnostic output**, never in source.

### 1.8.1 Worked example **[I]**

```coco
write in hebrew

עמוד ראשי
  הצג טקסט שלום
  הצג כפתור התחל

  כאשר התחל נלחץ
    פתח עמוד משחק
```

Logical reading order of line 3 is: `עמוד` (page), `ראשי` (Home). The leading-space count
of line 4 is 2. Both facts are visible to the lexer without any bidi processing.

## 1.9 Reserved words **[N]**

The following words are reserved in the `en` locale at all positions where a head is
expected, and MUST NOT be used as the first word of a user-declared name:

```
note  to  when  if  otherwise  while  repeat  for  each  let  keep  set  a  an  the
text  value  of  and  or  not  yes  no  use  share  stop  skip  give  page  try
```

Each locale declares its own reserved set ([doc 04 §4.3](04-multilingual.md)). The
reserved set is intentionally small; all other keywords (`show`, `button`, `create`)
are ordinary registry entries and may be shadowed by user declarations subject to
condition **R5**.

## 1.10 Lexical error summary **[N]**

| Code | Condition |
| --- | --- |
| `E-0101` | Character not permitted outside a text block |
| `E-0107` | Mixed digit systems in one numeric literal |
| `E-0108` | Number immediately followed by a letter |
| `E-0110` | Tab character in indentation |
| `E-0111` | Indentation is not a multiple of the file's indentation unit |
| `E-0112` | Indentation increased by more than one step |
| `E-0115` | Bidirectional embedding or override control in source |
| `E-0117` | Unterminated text block at end of file (informational; block simply ends) |
| `E-0118` | File is not valid UTF-8 |

---

*Next: [02 — Grammar](02-grammar.md)*
