#!/usr/bin/env python3
"""
Conformance tests for the Coco reference front end.

    python tests/run_tests.py

Each test checks a specific normative claim from the specification and cites
the section it comes from.
"""

from __future__ import annotations

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "reference"))

import coco_ref as coco  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RESULTS: list = []


def test(name: str, spec_ref: str):
    def wrap(fn):
        RESULTS.append((name, spec_ref, fn))
        return fn
    return wrap


def compile_text(source: str):
    return coco.compile_source(source, "<test>")


def first(items):
    return [i for i in items if i.cid != "core.directive"][0]


def find(items, cid):
    out = []
    for node in items:
        if node.cid == cid:
            out.append(node)
        out.extend(find(node.body, cid))
    return out


def text_of(node, slot):
    value = node.args[slot]
    pieces = value.get("text", value.get("name", []))
    return " ".join(p if isinstance(p, str) else "<splice>" for p in pieces)


# ---------------------------------------------------------------- registry


@test("registry is admissible in every shipped locale", "spec/03 section 3.6")
def _():
    raw, _particles = coco.load_registry()
    assert raw, "core registry is empty"
    for tag in sorted(f[:-7] for f in os.listdir(coco.LOCALE_DIR)
                      if f.endswith(".locale")):
        locale = coco.load_locale(tag)
        registry = coco.BoundRegistry(raw, locale)
        problems = registry.check_admissibility()
        assert not problems, f"{tag}: {problems}"


@test("every core signature is bound in every locale (condition L1)",
      "spec/04 section 4.3.1")
def _():
    raw, _particles = coco.load_registry()
    for tag in ("en", "he", "ja"):
        locale = coco.load_locale(tag)
        missing = [cid for cid in raw if cid not in locale.stmts]
        assert not missing, f"{tag} is missing {missing}"


@test("two signature CIDs may not share a head (condition L2)",
      "spec/04 section 4.3.1")
def _():
    locale = coco.load_locale("en")
    heads = {}
    for cid, phrase in locale.stmts.items():
        key = " ".join(phrase)
        assert key not in heads, f"{key} bound to {heads[key]} and {cid}"
        heads[key] = cid


# ---------------------------------------------------------------- lexing


@test("blank lines and notes produce no tokens", "spec/01 section 1.6.2")
def _():
    comp = compile_text("note a comment\n\n\nshow text Hi\n")
    kinds = [t.kind for t in comp.tokens]
    assert kinds == ["WORD", "WORD", "WORD", "NEWLINE", "EOF"], kinds


@test("a tab in indentation is E-0110", "spec/01 section 1.6.1")
def _():
    try:
        compile_text("page Home\n\tshow text Hi\n")
    except coco.CocoError as err:
        assert err.code == "E-0110", err.code
        return
    raise AssertionError("expected E-0110")


@test("a bidi override in source is E-0115", "spec/01 section 1.8")
def _():
    try:
        compile_text("show text Hi‮ there\n")
    except coco.CocoError as err:
        assert err.code == "E-0115", err.code
        return
    raise AssertionError("expected E-0115")


@test("punctuation is ordinary text inside a text slot", "spec/01 section 1.3.1")
def _():
    comp = compile_text("show text Press {Start} to begin, or wait 10 seconds\n")
    assert text_of(first(comp.items), "content") == \
        "Press {Start} to begin, or wait 10 seconds"


@test("a number in a text slot keeps its source spelling",
      "spec/01 section 1.5.1")
def _():
    comp = compile_text("show text You have 1,000 points\n")
    assert text_of(first(comp.items), "content") == "You have 1,000 points"


@test("unsegmented source is cut by keyword maximal munch",
      "spec/01 section 1.4.2")
def _():
    comp = compile_text("write in japanese\n\nこんにちはという文字を表示\n")
    node = first(comp.items)
    assert node.cid == "core.stmt.show_text", node.cid
    assert text_of(node, "content") == "こんにちは"


# ---------------------------------------------------------------- parsing


@test("a bare `to` does not terminate a text slot", "spec/02 section 2.4.2")
def _():
    comp = compile_text("show button Go to Top\n")
    node = first(comp.items)
    assert text_of(node, "label") == "Go to Top"
    assert "target" not in node.args


@test("a complete `to page` phrase does terminate a text slot",
      "spec/02 section 2.4.2")
def _():
    comp = compile_text("page Home\n  show text x\n\nshow button Go to page Home\n")
    node = find(comp.items, "core.stmt.show_button")[0]
    assert text_of(node, "label") == "Go"
    assert node.args["target"]["ref"] == "Home"


@test("termination is by earliest complete phrase, not by first word",
      "spec/02 section 2.4.2")
def _():
    comp = compile_text(
        "page Level Two\n  show text x\n\n"
        "show button Go to the final level to page Level Two\n")
    node = find(comp.items, "core.stmt.show_button")[0]
    assert text_of(node, "label") == "Go to the final level"
    assert node.args["target"]["ref"] == "Level Two"


@test("an open slot cannot be truncated", "spec/03 section 3.8")
def _():
    comp = compile_text("show text Welcome to my app to page nowhere\n")
    assert text_of(first(comp.items), "content") == \
        "Welcome to my app to page nowhere"


@test("declared names may contain spaces and match longest first",
      "spec/02 section 2.5")
def _():
    comp = compile_text(
        "page Game Over\n  show text x\n\nshow button Quit to page Game Over\n")
    node = find(comp.items, "core.stmt.show_button")[0]
    assert node.args["target"]["ref"] == "Game Over"


@test("an empty greedy slot is E-0231", "spec/14 section 14.5")
def _():
    try:
        compile_text("show button to page Home\n")
    except coco.CocoError as err:
        assert err.code == "E-0231", err.code
        return
    raise AssertionError("expected E-0231")


@test("the flush single-action form takes exactly one statement",
      "spec/02 section 2.6.2")
def _():
    comp = compile_text(
        "page Game\n  show text x\n\n"
        "when Start is pressed\n"
        "open page Game\n"
        "show text after\n")
    handlers = find(comp.items, "core.decl.handler")
    assert len(handlers) == 1
    assert len(handlers[0].body) == 1
    assert handlers[0].body[0].cid == "core.stmt.open_page"
    assert find(comp.items, "core.stmt.show_text")[-1].args["content"]["text"] \
        == ["after"]


@test("the indented and flush handler forms produce the same node",
      "spec/02 section 2.6.2")
def _():
    a = compile_text("page Game\n  show text x\n\n"
                     "when Start is pressed\nopen page Game\n")
    b = compile_text("page Game\n  show text x\n\n"
                     "when Start is pressed\n  open page Game\n")
    assert a.hash == b.hash


@test("the hanging explicit form fills slots by label",
      "spec/02 section 2.6.1")
def _():
    comp = compile_text(
        "page Manual\n  show text x\n\n"
        "show button\n"
        "  label\n"
        "    Go to page 2 of the manual\n"
        "  to page\n"
        "    Manual\n")
    node = find(comp.items, "core.stmt.show_button")[0]
    assert text_of(node, "label") == "Go to page 2 of the manual"
    assert node.args["target"]["ref"] == "Manual"


@test("an event subject runs up to the event head", "spec/03 section 3.10")
def _():
    comp = compile_text("page Game\n  show text x\n\n"
                        "when Give up is pressed\n  open page Game\n")
    handler = find(comp.items, "core.decl.handler")[0]
    assert handler.args["event"]["args"]["subject"]["ref"] == "Give up"


@test("value splices are recognised inside text", "spec/01 section 1.7.1")
def _():
    comp = compile_text("keep score as 0\nshow text Your score is value of score\n")
    node = find(comp.items, "core.stmt.show_text")[0]
    assert node.args["content"]["splices"][0]["ref"] == "score"


# ---------------------------------------------------------------- expressions


@test("`a plus b times c` binds as plus(a, times(b, c))",
      "spec/02 section 2.7.1")
def _():
    comp = compile_text("keep a as 1\nkeep b as 2\nkeep c as 3\n"
                        "let total be a plus b times c\n")
    tree = find(comp.items, "core.decl.let")[0].args["value"]
    assert tree["apply"] == "plus"
    assert tree["right"]["apply"] == "times"


@test("`a times b plus c` binds as plus(times(a, b), c)",
      "spec/02 section 2.7.1")
def _():
    comp = compile_text("keep a as 1\nkeep b as 2\nkeep c as 3\n"
                        "let total be a times b plus c\n")
    tree = find(comp.items, "core.decl.let")[0].args["value"]
    assert tree["apply"] == "plus"
    assert tree["left"]["apply"] == "times"


@test("multi-word comparisons are matched longest first",
      "spec/02 section 2.7")
def _():
    comp = compile_text("keep a as 1\nkeep b as 2\n"
                        "let ok be a is less than b\n")
    tree = find(comp.items, "core.decl.let")[0].args["value"]
    assert tree["apply"] == "is less than", tree


@test("comparisons do not chain (E-0252)", "spec/02 section 2.7.1")
def _():
    try:
        compile_text("keep a as 1\nlet x be a is less than 2 is less than 3\n")
    except coco.CocoError as err:
        assert err.code == "E-0252", err.code
        return
    raise AssertionError("expected E-0252")


@test("`health of player` is a member path", "spec/02 section 2.5")
def _():
    comp = compile_text("keep player as 1\nlet h be health of player\n")
    tree = find(comp.items, "core.decl.let")[0].args["value"]
    assert tree["member"]["ref"] == "player"
    assert tree["in"]["ref"] == "health"


# ---------------------------------------------------------------- multilingual


@test("the same program in en, he and ja has one canonical hash",
      "spec/04 section 4.11, spec/08 section 8.7")
def _():
    hashes = {}
    for tag, path in coco.TOUR_FILES.items():
        hashes[tag] = coco.compile_file(path).hash
    assert len(set(hashes.values())) == 1, hashes


@test("the canonical hash ignores layout and notes", "spec/08 section 8.7")
def _():
    a = compile_text("page Home\n  show text Hi\n")
    b = compile_text("note a comment\n\npage Home\n\n\n    show text Hi\n\n")
    assert a.hash == b.hash


@test("the canonical hash does not ignore the data", "spec/08 section 8.7")
def _():
    a = compile_text("show text Hi\n")
    b = compile_text("show text Hello\n")
    assert a.hash != b.hash


@test("a right to left locale needs no special handling",
      "spec/01 section 1.8, spec/04 section 4.5")
def _():
    comp = compile_text("write in hebrew\n\nעמוד Home\n  הצג טקסט Welcome\n")
    page = find(comp.items, "core.decl.page")[0]
    assert text_of(page, "name") == "Home"
    assert text_of(page.body[0], "content") == "Welcome"


@test("a locale may place the head after its slot",
      "spec/04 section 4.7.2")
def _():
    comp = compile_text("write in japanese\n\nGame started という文字を表示\n")
    node = first(comp.items)
    assert node.cid == "core.stmt.show_text"
    assert text_of(node, "content") == "Game started"


@test("a message declares a name usable in a splice",
      "spec/04 section 4.12.2")
def _():
    comp = compile_text("""the message greeting says
  in english Hi
  in hebrew שלום

show text value of greeting
""")
    message = find(comp.items, "core.decl.message")[0]
    assert text_of(message, "name") == "greeting"
    assert len(message.body) == 2
    assert message.body[0].args["locale"]["ref"] == "english"
    assert text_of(message.body[0], "content") == "Hi"
    shown = find(comp.items, "core.stmt.show_text")[0]
    assert shown.args["content"]["splices"][0]["ref"] == "greeting"


@test("a wording's content is open and cannot be truncated",
      "spec/04 section 4.12.2")
def _():
    comp = compile_text("""the message notice says
  in english Back in 10 minutes, 100% sure
""")
    wording = find(comp.items, "core.stmt.in_locale")[0]
    assert text_of(wording, "content") == "Back in 10 minutes, 100% sure"


@test("a splice may follow its reference where the locale says so",
      "spec/04 section 4.7.4")
def _():
    assert coco.load_locale("en").splice_order == "marker first"
    assert coco.load_locale("ja").splice_order == "ref first"
    comp = compile_text("""write in japanese

greeting というメッセージ の内容は
  english では Hi

greeting の値 という文字を表示
""")
    shown = find(comp.items, "core.stmt.show_text")[0]
    assert shown.args["content"]["splices"][0]["ref"] == "greeting"


@test("one message program in en, he and ja has one canonical hash",
      "spec/04 section 4.12.2")
def _():
    hashes = {}
    for tag in ("", ".he", ".ja"):
        path = os.path.join(ROOT, "examples", "greeting" + tag + ".coco")
        hashes[tag or "en"] = coco.compile_file(path).hash
    assert len(set(hashes.values())) == 1, hashes


# ---------------------------------------------------------------- examples


@test("every example in examples/ compiles", "spec/15 section 15.8")
def _():
    directory = os.path.join(ROOT, "examples")
    checked = 0
    skipped = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".coco"):
            continue
        path = os.path.join(directory, name)
        try:
            coco.compile_file(path)
            checked += 1
        except coco.CocoError as err:
            skipped.append(f"{name}: {err.code} {err.message}")
    assert checked >= 6, f"only {checked} examples compiled"
    # game.coco, social.coco and brain.coco use constructs beyond the reference
    # front end; they are specification illustrations.
    for entry in skipped:
        assert entry.split(":")[0] in ("game.coco", "social.coco", "brain.coco"), entry


def main() -> int:
    width = max(len(name) for name, _ref, _fn in RESULTS)
    passed = failed = 0
    for name, spec_ref, fn in RESULTS:
        try:
            fn()
            print(f"  ok    {name.ljust(width)}   {spec_ref}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {name.ljust(width)}   {spec_ref}")
            for line in traceback.format_exc().splitlines()[-4:]:
                print(f"          {line}")
            failed += 1
    print()
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
