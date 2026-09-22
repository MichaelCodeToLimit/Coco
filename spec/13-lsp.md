# 13 — Language Server Protocol

*Edition 2026. **[N]** normative, **[I]** informative.*

`compose serve` is the Coco language server. It speaks LSP 3.17 plus a small set of
Coco extensions in the `coco/` namespace. The same binary serves VS Code, Neovim,
Zed, Helix, JetBrains (via the LSP plugin), Emacs `eglot` and any other LSP client, so
editor support is one implementation, not one per editor.

---

## 13.1 Server capabilities **[N]**

```jsonc
{
  "textDocumentSync": { "openClose": true, "change": 2, "save": { "includeText": false } },
  "positionEncoding": "utf-16",
  "completionProvider": {
    "triggerCharacters": [" "],
    "resolveProvider": true,
    "completionItem": { "labelDetailsSupport": true }
  },
  "hoverProvider": true,
  "signatureHelpProvider": { "triggerCharacters": [" "], "retriggerCharacters": [" "] },
  "definitionProvider": true,
  "typeDefinitionProvider": true,
  "implementationProvider": true,
  "referencesProvider": true,
  "documentHighlightProvider": true,
  "documentSymbolProvider": { "label": "Coco" },
  "workspaceSymbolProvider": { "resolveProvider": true },
  "codeActionProvider": {
    "codeActionKinds": [
      "quickfix",
      "refactor.rewrite",
      "refactor.extract",
      "source.organizeImports",
      "source.fixAll",
      "coco.explicitForm",
      "coco.translateLocale"
    ],
    "resolveProvider": true
  },
  "codeLensProvider": { "resolveProvider": true },
  "documentFormattingProvider": true,
  "documentRangeFormattingProvider": true,
  "documentOnTypeFormattingProvider": { "firstTriggerCharacter": "\n" },
  "renameProvider": { "prepareProvider": true },
  "foldingRangeProvider": true,
  "selectionRangeProvider": true,
  "semanticTokensProvider": {
    "legend": { "tokenTypes": [ /* §13.3 */ ], "tokenModifiers": [ /* §13.3 */ ] },
    "range": true,
    "full": { "delta": true }
  },
  "inlayHintProvider": { "resolveProvider": true },
  "inlineValueProvider": true,
  "callHierarchyProvider": true,
  "typeHierarchyProvider": true,
  "diagnosticProvider": {
    "identifier": "coco",
    "interFileDependencies": true,
    "workspaceDiagnostics": true
  },
  "executeCommandProvider": {
    "commands": [
      "coco.explainStorage", "coco.explainSchedule",
      "coco.explainVectorisation", "coco.explainParse",
      "coco.switchLocale", "coco.showEIR",
      "coco.canonicalHash", "coco.registryCheck"
    ]
  },
  "experimental": {
    "coco": {
      "signatureRegistry": true,
      "localeSwap": true,
      "bidiColumn": true,
      "parseTrace": true,
      "storageExplain": true,
      "canonicalHash": true,
      "documentDirection": true
    }
  }
}
```

## 13.2 Why completion is unusually good here **[I]**

In most languages, completion after `foo.` is a member lookup. In Coco, completion is
**registry-driven at every word boundary**, which means the editor can always show
exactly what may come next, because the grammar says so:

- At statement start: every signature head reachable from the current trie node.
- Mid-clause: the current signature's next segment — either "type the label here" (a
  `text` slot, with a hint), or a list of names (a `ref` slot, filtered to the slot's
  type), or the set of valid terminator phrases.
- Inside a `when`: only event signatures whose subject type matches.
- Inside a `page`: only `declarative` signatures.

This is the single largest practical benefit of the signature design: the editor never
has to guess, because the parser never has to guess.

### 13.2.1 Completion item shape **[N]**

```jsonc
{
  "label": "show button",
  "labelDetails": { "detail": " <label> to page <target>", "description": "core.ui" },
  "kind": 3,
  "documentation": { "kind": "markdown", "value": "Shows a pressable button…" },
  "insertTextFormat": 2,
  "textEdit": { "range": {...}, "newText": "show button ${1:label} to page ${2:target}" },
  "data": { "cid": "core.stmt.show_button", "locale": "en" }
}
```

`data.cid` lets `completionItem/resolve` fetch documentation, effects, slot modes and
locale aliases without re-parsing.

## 13.3 Semantic tokens **[N]**

Coco's token types map to clause parts, not to C-family categories. Clients that do
not understand the custom types fall back to the standard ones listed in parentheses.

| Token type | Meaning | Fallback |
| --- | --- | --- |
| `cocoHead` | a signature head keyword | `keyword` |
| `cocoParticle` | a particle phrase | `operator` |
| `cocoSlotText` | contents of a `text` slot | `string` |
| `cocoSlotName` | contents of a `name` slot | `variable` |
| `cocoRef` | a resolved reference | `variable` |
| `cocoSplice` | `value of x` inside text | `variable` |
| `cocoEvent` | an event signature | `event` |
| `cocoPage` | a page declaration or reference | `class` |
| `cocoRecord` | a record type | `struct` |
| `cocoChoice` | a choice type | `enum` |
| `cocoNote` | a `note` line | `comment` |
| `cocoNumber` | a numeric literal | `number` |
| `cocoTypeWord` | `whole number`, `text`, … | `type` |

| Modifier | Meaning |
| --- | --- |
| `declaration` | at its declaration site |
| `mutable` | a `keep` binding |
| `shared` | exported |
| `deprecated` | signature deprecated |
| `promoted` | a value the compiler moved up the storage ladder (§6.4) |
| `vectorised` | a loop that vectorised |
| `parallel` | a handler that runs in a parallel group |

The last three turn the editor into a live performance view: a loop that stopped
vectorising after an edit visibly loses its highlight.

## 13.4 Inlay hints **[N]**

Off by default except the first two. All are toggled per category.

| Category | Example |
| --- | --- |
| `types` | `keep score as 0` → `keep score as 0 ⟨whole number⟩` |
| `slotNames` | `damage Hero by 10` → `damage ⟨target⟩ Hero by ⟨amount⟩ 10` |
| `storage` | `let p be a particle …` → `⟨region: this update⟩` |
| `effects` | on an action's declaration line → `⟨writes player.health⟩` |
| `schedule` | on a `when` line → `⟨group 2, serial⟩` |
| `vector` | on a `for each` line → `⟨×8 AVX2⟩` |
| `cid` | on a shared declaration → `⟨app.main.act.damage⟩` |

## 13.5 Incrementality **[N]**

The server MUST keep the registry live:

- On every keystroke it re-runs **collect** (pass 1) for the edited file only.
- If the file's declaration heads changed, it re-checks R1–R6 for the affected trie
  subtrees and publishes registry diagnostics.
- It re-parses and re-type-checks only items whose input hash changed
  ([doc 09 §9.2](09-compiler-pipeline.md)).
- Budget: **p99 ≤ 100 ms** from `didChange` to `publishDiagnostics` for a single-item edit
  in a 100 000-line project on commodity hardware. This is a conformance target, measured
  by the `lsp-latency` suite.

## 13.6 Coco extensions **[N]**

### `coco/signatureRegistry`

```
→ { "uri": "file:///…/main.coco", "position": {…} }
← { "node": "show", "candidates": [
      { "cid": "core.stmt.show_text",   "head": "show text",   "next": "text slot" },
      { "cid": "core.stmt.show_button", "head": "show button", "next": "text slot" }
    ],
    "committed": false }
```

Lets the editor render a live "what can come next" panel.

### `coco/parseTrace`

```
→ { "uri": "…", "line": 12 }
← { "steps": [
      { "action": "head match", "matched": "show button", "lookahead": 2 },
      { "action": "greedy slot", "slot": "label", "stopped at": "to page", "value": "Get Started" },
      { "action": "particle", "matched": "to page" },
      { "action": "ref slot", "slot": "target", "resolved": "app.main.page.level_one" }
    ] }
```

This is `compose registry why` in the editor. It is the answer to "why did my label get
cut off?" and MUST be offered as a code action on any `E-02xx` diagnostic.

### `coco/localeSwap`

```
→ { "uri": "…", "toLocale": "he", "preview": true }
← { "edits": [ … ], "canonicalHashBefore": "b3:9f4c…", "canonicalHashAfter": "b3:9f4c…" }
```

Translates the open document. With `"preview": true` the client shows a diff. The two
hashes MUST be equal; a client SHOULD refuse to apply if they differ and report it as a
toolchain bug.

### `coco/bidiColumn`

```
→ { "uri": "…", "position": { "line": 4, "character": 12 } }
← { "visualColumn": 31, "direction": "rtl", "runs": [ { "start": 0, "end": 18, "dir": "rtl" } ] }
```

For correct caret placement and selection rendering in RTL source
([doc 04 §4.5](04-multilingual.md)).

### `coco/documentDirection` (notification, server → client)

```
← { "uri": "…", "baseDirection": "rtl", "locale": "he" }
```

Sent on open and whenever `write in` changes.

### `coco/storageExplain`

```
→ { "uri": "…", "position": {…} }
← { "name": "player", "class": "region", "region": "this update",
    "reason": "escapes into world entities but never outlives the frame region",
    "cost": "bump allocation, 0 bytes metadata",
    "promotions": [] }
```

### `coco/canonicalHash`

```
→ { "uri": "…" }        (or { "workspace": true })
← { "hash": "b3:9f4c1e…", "edition": 2026, "items": 412 }
```

### `coco/showEIR`

```
→ { "uri": "…", "position": {…}, "level": "d" | "c" }
← { "text": "function app.main.act.damage …", "sourceMap": [ … ] }
```

Opens a synchronised CIR view; selecting a line highlights the source it came from.

## 13.7 Code actions **[N]**

Every diagnostic that has a mechanical fix MUST ship a `quickfix`. The Coco-specific
kinds:

| Kind | Offered when | Does |
| --- | --- | --- |
| `coco.explicitForm` | on any clause | rewrites the clause into the hanging explicit form ([doc 02 §2.6.1](02-grammar.md)) |
| `coco.explicitForm` | on `E-0231`, `E-0233` | fixes a truncated or empty greedy slot |
| `coco.translateLocale` | anywhere | `coco/localeSwap` for the file or selection |
| `refactor.extract` | on a selection of statements | extracts a `to …` action, inferring the signature and slots |
| `refactor.rewrite` | on a `for each` that failed to vectorise | applies the suggested rewrite where one exists |
| `quickfix` | on `E-0615` (aliasing) | inserts the collect-then-modify pattern |
| `quickfix` | on `E-0632` (cycle) | adds `may form cycles` or a weak link |
| `source.organizeImports` | on save | sorts and prunes `use` lines |

## 13.8 Code lenses **[I]**

| Lens | Placement | Action |
| --- | --- | --- |
| `▶ Run test` | above `a test called` | runs that test |
| `n references` | above shared declarations | peek references |
| `group 2 · serial` | above `when` | opens `coco/explainSchedule` |
| `×8 AVX2` | above vectorised `for each` | opens the vectorisation report |
| `open in 日本語` | top of file | `coco/localeSwap` |

## 13.9 Client requirements **[N]**

A conforming Coco editor extension MUST:

1. render `cocoSlotText` distinctly from `cocoHead`, because that distinction is
   what makes quote-free text readable at a glance;
2. honour `coco/documentDirection` for base paragraph direction;
3. use `coco/bidiColumn` for caret and selection in RTL documents;
4. offer `coco/parseTrace` from any `E-02xx` diagnostic;
5. never reformat on save unless `compose format` is the formatter.

A reference VS Code extension implementing all of the above is maintained alongside the
compiler, plus thin configurations for Neovim, Zed and Helix.

---

*Next: [14 — Diagnostics](14-diagnostics.md)*
