"""Join the classifiers' answers back onto the documents, and run the roll call in code.

Usage:
    python3 collect_classifications.py <session_dir> [--floor 0.7]

Reads every <session_dir>/BATCHES*.json — the authority on which readings were sent, one per round —
the batch outputs each names, and WORKFLOW.json for what the app allows.

Writes <session_dir>/CLASSIFICATIONS.json: one entry per document, carrying its item, sha, document
template with the app's own id, derived section, confidence and evidence. Writes
<session_dir>/REREAD.json naming the readings a second opinion would settle. Prints the roll call, the
confidence spread, and every document a person still has to settle.

An answer is joined on its reading id, fanned out to every copy of that content, and checked three ways
before it counts: the template must be one the app allows on that table, the quoted evidence must
actually appear in what the classifier was given to read, and the classifier must say the document
reached it.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import item_index

SAMPLE = 10
BUCKETS = ((0.9, "0.9-1.0  one clear fit"), (0.7, "0.7-0.9  a fit, with a distant second"),
           (0.5, "0.5-0.7  two plausible fits"))

# What a quotation has to survive to count as found: a classifier re-wraps lines and tidies spacing,
# and none of that changes whether it read the document.
WHITESPACE = re.compile(r"\s+")
PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
# Below this a quotation is too short to be evidence of anything — "SDS" appears everywhere.
QUOTE_FLOOR = 12


def load(path, what):
    if not path.is_file():
        raise SystemExit(f"missing {what}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def folded(text):
    """Case and spacing flattened, so a re-wrapped quotation still matches the text it came from."""
    return WHITESPACE.sub(" ", (text or "").casefold()).strip()


def folded_hard(text):
    """Folded further, for grouping names a person will act on once: `Vegan-Statement` is `vegan statement`."""
    return WHITESPACE.sub(" ", PUNCTUATION.sub(" ", (text or "").casefold())).strip()


def display_name(group):
    """The spelling to put in front of the user for names that folded together.

    `Vegan Statement` and `vegan-statement` are one template to create, and which of the two is shown
    matters far less than it being the same one on every run.
    """
    return sorted({name for name, _ in group})[0]


def manifests_in(session_dir):
    """Every round's batch manifest, in round order. Round one is BATCHES.json, later ones BATCHES_rN.json."""
    found = []
    for path in sorted(session_dir.glob("BATCHES*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        found.append((manifest.get("round") or 1, path, manifest))
    if not found:
        raise SystemExit(f"no BATCHES.json in {session_dir} — the batching step has not run")
    return [(r, p, m) for r, p, m in sorted(found, key=lambda f: f[0])]


def read_answers(entries):
    """({reading id: answer}, batch numbers that did not answer) for one round."""
    answers, silent = {}, []
    for entry in entries:
        output = Path(entry["output"])
        if not output.is_file():
            silent.append(entry["batch"])
            continue
        try:
            results = json.loads(output.read_text(encoding="utf-8")).get("results") or []
        except json.JSONDecodeError as error:
            print(f"  batch {entry['batch']}: unreadable output ({error})")
            silent.append(entry["batch"])
            continue
        wanted = set(entry["readingIds"])
        kept = [r for r in results if isinstance(r, dict) and r.get("readingId") in wanted]
        for result in kept:
            answers.setdefault(result["readingId"], result)
        if len(kept) < len(wanted):
            silent.append(entry["batch"])
    return answers, silent


def confidence_of(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def text_given_to(reading):
    """What the classifier was shown, for checking a quotation against. Empty for a reading of images."""
    parts = []
    for path in reading.get("readFrom") or []:
        if not str(path).lower().endswith(".md"):
            continue
        try:
            parts.append(Path(path).read_text(encoding="utf-8"))
        except OSError:
            continue
    return folded("\n".join(parts))


def quote_missing(quote, haystack):
    """Why this quotation does not count, or None. A reading of images has nothing to check against."""
    if not haystack:
        return None
    if not quote:
        return "quoted nothing from the document"
    if len(folded(quote)) < QUOTE_FLOOR:
        return f"quoted only {folded(quote)!r}, too little to show the document was read"
    if folded(quote) not in haystack:
        return f"quoted {folded(quote)[:60]!r}, which is not in what it was given to read"
    return None


def sections_holding(app, item_template, template_id):
    """The sections on this item template that render this template, in the app's own order."""
    entry = app.item_templates.get(item_template or "")
    if not entry or not template_id:
        return []
    return [s for s in sorted(entry["sections"], key=lambda s: s["sortOrder"])
            if template_id in s["documentTemplates"]]


def why_not_read(answer, given):
    """Why this answer does not show the document was read, or None.

    Two ways to fail and they are different admissions: the classifier saying the document never
    reached it, and the classifier quoting something that is not in what it was given. Neither was
    detectable before, because the answer had no field either could be said in.
    """
    if answer.get("received") is False:
        return "the classifier says this document never reached it"
    return quote_missing((answer.get("quote") or "").strip(), given)


def settle(answered, given):
    """(the answer to use, why no reading held up, the two ids that disagreed, whether they agreed).

    The two failures are kept apart because they are different outcomes: `failure` is set when nothing
    could be shown to have read the document, `contest` when two readings both held up and named
    different templates. At most one of them is ever set.

    An answer that cannot be shown to have read the document is set aside rather than settled with, so
    a second reading replaces a fabricated first one instead of arguing with it. Where two readings
    that both hold up name the same template, that agreement is the evidence a thin margin was missing;
    where they differ, neither attaches on its own and both go to a person.
    """
    checked = [(answer, why_not_read(answer, given)) for answer in answered]
    held_up = [answer for answer, why in checked if not why]
    if not held_up:
        return checked[0][0], checked[0][1], None, False
    if len(held_up) == 1:
        return held_up[0], None, None, False

    chosen = item_index.normalise(held_up[0].get("documentTemplateId"))
    for other in held_up[1:]:
        against = item_index.normalise(other.get("documentTemplateId"))
        if against != chosen:
            return held_up[0], None, (chosen, against), False
    return held_up[0], None, None, True


def report(heading, rows):
    if not rows:
        return
    print(f"\n{heading} ({len(rows)}):")
    for row in rows[:SAMPLE]:
        print(f"  {row}")
    if len(rows) > SAMPLE:
        print(f"  ... and {len(rows) - SAMPLE} more in CLASSIFICATIONS.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--floor", type=float, default=0.7,
                        help="confidence below this is two templates fitting, so it needs a second look (default: 0.7)")
    options = parser.parse_args()

    # Windows consoles default to a codepage that cannot print this summary's punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    rounds = manifests_in(session_dir)
    first_round = rounds[0][2]
    documents = first_round.get("documents") or []
    readings = {r["readingId"]: r for r in first_round.get("readings") or []}

    try:
        app = item_index.load(session_dir / "WORKFLOW.json", session_dir / "ITEMS.csv")
    except item_index.ExportError as error:
        raise SystemExit(f"the export cannot be used: {error}")

    allowed_by_table = {table: {t["id"] for t in app.templates_for(table)} for table in app.tables}

    by_reading, silent = {}, []
    for number, _, manifest in rounds:
        answers, quiet = read_answers(manifest.get("batches") or [])
        for reading_id, answer in answers.items():
            by_reading.setdefault(reading_id, []).append(answer)
        if quiet:
            silent.append((number, quiet))

    # Checked once per reading rather than once per copy: every copy of one content was answered by one
    # agent, so a fabricated answer is one fact about that reading, not a fact about forty files.
    verdicts = {}
    for reading_id, reading in readings.items():
        given = text_given_to(reading)
        answered = by_reading.get(reading_id) or []
        if not answered:
            verdicts[reading_id] = {
                "unread": True, "review": "unread — no classifier answered for this reading"
            }
            continue

        answer, note, contest, agreed = settle(answered, given)
        if contest:
            note = "read twice and settled differently: " + " then ".join(
                (app.document_templates.get(i) or {}).get("name") or (i or "nothing") for i in contest
            )
        confidence = confidence_of(answer.get("confidence"))
        if agreed:
            # The better of the two scores stands. Clearing the floor is not left to that score, though:
            # two readings that independently picked the same template out of the same list have already
            # answered the question the floor asks, even where both of them found it a close call.
            confidence = max(
                [c for c in (confidence_of(a.get("confidence")) for a in answered) if c is not None]
                or [confidence]
            )
        unverified = bool(note)
        verdict = {
            "unread": False,
            "evidence": (answer.get("evidence") or "").strip() or None,
            "quote": (answer.get("quote") or "").strip() or None,
            "confidence": confidence,
            "runnerUp": item_index.normalise(answer.get("runnerUpTemplateId")) or None,
            "templateId": item_index.normalise(answer.get("documentTemplateId")),
            "proposedTemplate": item_index.normalise(answer.get("proposedTemplate")),
            "rounds": len(answered),
            "agreed": agreed,
            "contested": bool(contest),
            "unverified": unverified,
            "review": note,
        }
        # A contest keeps its first reading, so the row still shows what was read. A reading that could
        # not be shown to have happened keeps nothing at all — not the template and not the proposal,
        # since a name proposed off a document nobody can show was read is the same fabrication.
        if unverified:
            verdict["templateId"] = None
            verdict["proposedTemplate"] = None
        verdicts[reading_id] = verdict

    results, unanswered, no_template, low, rejected, unarranged, unquoted, contested = (
        [], [], [], [], [], [], [], []
    )
    proposed_templates, unarranged_on = {}, {}
    listed_paths = set()
    reread = {}
    for document in documents:
        verdict = verdicts.get(document["readingId"], {"review": "unread — this reading was never batched"})
        entry = {
            **{
                k: document[k]
                for k in (
                    "path", "relativePath", "name", "sha", "readingId",
                    "table", "identifier", "itemId", "itemName", "itemTemplate",
                )
            },
            "documentTemplate": None,
            "documentTemplateId": None,
            "proposedTemplate": None,
            "section": None,
            "sectionSortOrder": None,
            "confidence": verdict.get("confidence"),
            "evidence": verdict.get("evidence"),
            "quote": verdict.get("quote"),
            "review": verdict.get("review"),
        }
        relative_path = document["relativePath"]

        if verdict.get("unread"):
            listed_paths.add(relative_path)
            unanswered.append(relative_path)
            results.append(entry)
            continue
        if verdict.get("unverified"):
            # Rejected on receipt or on the quotation, so there is no reading to carry forward.
            listed_paths.add(relative_path)
            unquoted.append(f"{relative_path} — {entry['review']}")
            reread.setdefault(document["readingId"], entry["review"])
            results.append(entry)
            continue

        template_id = verdict.get("templateId")
        proposed_template = verdict.get("proposedTemplate")
        known = app.document_templates.get(template_id)
        allowed = allowed_by_table.get(document["table"], set())
        if template_id and not known:
            entry["review"] = f"template id {template_id!r} is not in the app's list"
            listed_paths.add(relative_path)
            rejected.append(f"{relative_path} — answered with id {template_id!r}")
        elif template_id and template_id not in allowed:
            entry["review"] = f"template {known['name']!r} is not allowed on {document['table']}"
            listed_paths.add(relative_path)
            rejected.append(f"{relative_path} — {known['name']!r} is not for {document['table']}")
        elif template_id:
            entry["documentTemplateId"] = template_id
            entry["documentTemplate"] = known["name"]
        elif proposed_template:
            # A read the app has no word for yet. The reading is kept and the name goes to the user,
            # since creating the template is the action that makes this document attachable.
            entry["proposedTemplate"] = proposed_template
            entry["review"] = f"proposes a template the app does not have: {proposed_template!r}"
            listed_paths.add(relative_path)
            proposed_templates.setdefault(folded_hard(proposed_template), []).append(
                (proposed_template, relative_path)
            )
        else:
            entry["review"] = "no template fitted what the classifier read"
            listed_paths.add(relative_path)
            no_template.append(f"{relative_path} — {entry['evidence'] or 'no evidence given'}")

        # The section is a lookup, not an answer: whichever section of this copy's own item template
        # renders the chosen template. One reading can cover copies on several item templates, so this
        # is settled per copy rather than once. See docs/adr/0002.
        blueprint = document["itemTemplate"] or ""
        where = blueprint or "no item template"
        holders = sections_holding(app, blueprint, entry["documentTemplateId"])
        if holders:
            entry["section"] = holders[0]["label"]
            entry["sectionSortOrder"] = holders[0]["sortOrder"]
        elif entry["documentTemplateId"]:
            # Which sections that blueprint does have goes with it, because the action is arranging the
            # template into one of them in the app, and the user cannot pick from a list they cannot see.
            elsewhere = [s["label"] for s in sorted(
                app.item_templates.get(blueprint, {}).get("sections") or [],
                key=lambda s: s["sortOrder"],
            )]
            note = f"{entry['documentTemplate']!r} sits in no section on {where}"
            entry["review"] = f"{entry['review']} | {note}" if entry["review"] else note
            listed_paths.add(relative_path)
            unarranged.append(
                f"{relative_path} — {note}"
                + (f"; it has {', '.join(repr(s) for s in elsewhere)}" if elsewhere else "")
            )
            unarranged_on.setdefault((blueprint, entry["documentTemplate"]), set()).update(elsewhere)

        # Two readings that agreed have already settled what the floor asks about, so the floor is not
        # applied to them however close a call each of them found it on its own.
        thin = (
            entry["documentTemplate"]
            and not verdict.get("agreed")
            and (entry["confidence"] is None or entry["confidence"] < options.floor)
        )
        if verdict.get("contested"):
            listed_paths.add(relative_path)
            contested.append(f"{relative_path} — {verdict['review']}")
        elif thin:
            shown = "unscored" if entry["confidence"] is None else f"{entry['confidence']:.2f}"
            # A runner-up that is the pick is not a runner-up. Printing it reads as a contradiction and
            # tells the user nothing about what the score is a margin over.
            runner_id = verdict.get("runnerUp")
            runner = app.document_templates.get(runner_id or "") if runner_id != entry["documentTemplateId"] else None
            against = f", against {runner['name']!r}" if runner else ""
            note = f"confidence {shown}{against}, below the {options.floor:.2f} floor"
            entry["review"] = entry["review"] or note
            listed_paths.add(relative_path)
            low.append(f"{relative_path} — {entry['documentTemplate']} — {shown}{against}")
            reread.setdefault(document["readingId"], note)

        results.append(entry)

    usable = [r for r in results if r["documentTemplate"] and not r["review"]]
    # A reading two rounds already disagreed about is not sent a third time: the contest is the answer,
    # and it belongs to a person now.
    already_read = {rid for rid, v in verdicts.items() if v.get("rounds", 0) > 1}
    reread = {k: v for k, v in reread.items() if k not in already_read}

    (session_dir / "CLASSIFICATIONS.json").write_text(
        json.dumps({
            "floor": options.floor,
            "rounds": [n for n, _, _ in rounds],
            "counts": {
                "expected": len(documents),
                "answered": len(documents) - len(unanswered),
                "usable": len(usable),
                "needsReview": len(results) - len(usable),
                "readings": len(readings),
            },
            "silentBatches": {f"round {n}": sorted(set(q)) for n, q in silent},
            "proposedTemplates": {
                display_name(p): len(p) for p in proposed_templates.values()
            },
            "unarrangedTemplates": {
                f"{blueprint}:{name}": sorted(labels)
                for (blueprint, name), labels in sorted(unarranged_on.items())
            },
            "results": results,
        }, indent=2),
        encoding="utf-8",
    )
    (session_dir / "REREAD.json").write_text(
        json.dumps({"readingIds": sorted(reread), "why": reread}, indent=2), encoding="utf-8"
    )

    print(
        f"{len(documents) - len(unanswered)}/{len(documents)} documents answered "
        f"from {len(readings)} reading(s), {len(usable)} usable as-is"
    )
    for number, quiet in silent:
        print(f"\nSEND THESE ROUND-{number} BATCHES AGAIN ({len(quiet)}): "
              + ", ".join(str(b) for b in sorted(set(quiet))))

    scored = [r["confidence"] for r in results if r["confidence"] is not None]
    if scored:
        print("\nconfidence — the gap between the best fit and the runner-up:")
        remaining = sorted(scored, reverse=True)
        for edge, label in BUCKETS:
            count = len([c for c in remaining if c >= edge])
            print(f"  {label}: {count}")
            remaining = [c for c in remaining if c < edge]
        print(f"  below 0.5 a coin toss:        {len(remaining)}")

    report("UNREAD — no classifier answered, so these are not classified", unanswered)
    report("NOT SHOWN TO HAVE BEEN READ — the receipt or the quotation did not hold up", unquoted)
    report("NO TEMPLATE — nothing in the app's list fitted", no_template)
    report("TEMPLATE THE APP CANNOT TAKE — wrong id, or not allowed on that table", rejected)
    report("NO SECTION RENDERS IT — the app allows the template but arranges it nowhere here", unarranged)
    report(
        "TEMPLATES TO CREATE — proposed because nothing in the app fitted",
        [f"{display_name(p)!r} — {len(p)} document(s), e.g. {p[0][1]}"
         for p in proposed_templates.values()],
    )
    report(
        "SECTIONS TO ARRANGE — add the template to a section on that item template, in the app",
        [f"{name!r} on {blueprint or 'no item template'} — it has "
         + (", ".join(repr(s) for s in sorted(labels)) if labels else "no sections at all")
         for (blueprint, name), labels in sorted(unarranged_on.items())],
    )
    report("READ TWICE, SETTLED DIFFERENTLY — a person picks between the two", contested)
    report(f"BELOW THE {options.floor:.2f} FLOOR — two templates fitted, so worth a second reading", low)

    if reread:
        print(
            f"\nA SECOND READING WOULD SETTLE {len(reread)} READING(S). Nothing has been sent: run\n"
            f"  python3 plan_batches.py {session_dir} --round 2\n"
            "and fan those batches out as before, then run this again."
        )

    # Every document is either usable or listed above — a gap here means a review reason nothing
    # reports. Counted over distinct documents, since one can fail on its template and its section both.
    needing = {r["relativePath"] for r in results if r["review"]}
    silent_failures = sorted(needing - listed_paths)
    if silent_failures:
        print(
            f"\nACCOUNTING GAP: {len(silent_failures)} document(s) carry a review reason nothing above "
            f"reports — read `review` in CLASSIFICATIONS.json: {', '.join(silent_failures[:SAMPLE])}"
        )

    print(f"\n-> {session_dir / 'CLASSIFICATIONS.json'}")


if __name__ == "__main__":
    main()
