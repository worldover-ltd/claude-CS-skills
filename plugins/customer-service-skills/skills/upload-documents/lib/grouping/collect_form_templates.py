"""Take the form-level answers back, and hold each one to the list it was offered.

Usage:
    python3 collect_form_templates.py <session_dir>

Reads `FORM_CLASSIFICATION.json` and the answer files it names; writes `FORM_TEMPLATES.json` and prints
the roll call.

Two checks, and they are the same two the per-document collector runs, moved up a level:

- the template must be one the app allows on that form's tables, because an id outside the list is an
  answer to a question nobody asked;
- the quotation must appear in one of the samples the agent was shown, because a form answered without
  reading anything is exactly what a single answer standing for a thousand documents must not be.

The second check is *weaker here than per document, on purpose*, and it is the price of ADR-0005. One
answer covers every member of the form, and only the sampled members were read. What holds the rest is
the grouping — the claim that they are the same stationery — not a reading of each. `FORM_TEMPLATES.json`
records `standsFor` so a workbook row can say where its answer came from rather than implying somebody
looked at that document.
"""

import argparse
import json
import re
import sys
from pathlib import Path

WHITESPACE = re.compile(r"\s+")
QUOTE_FLOOR = 12
SAMPLE = 10


def folded(text):
    return WHITESPACE.sub(" ", (text or "").casefold()).strip()


def load(session_dir, name):
    path = session_dir / name
    if not path.is_file():
        raise SystemExit(f"missing {name} in {session_dir} — the step that writes it has not run")
    return json.loads(path.read_text(encoding="utf-8"))


def offered(payload):
    """{id: name} for every template this form's agent was allowed to pick."""
    out = {}
    for templates in ((payload.get("vocabulary") or {}).get("documentTemplates") or {}).values():
        for template in templates:
            out[template["id"]] = template["name"]
    return out


def shown_text(payload):
    """Everything the agent was actually shown, folded, for the quotation to be found in."""
    parts = []
    for sample in payload.get("samples") or []:
        parts.extend(sample.get("structure") or [])
    return folded("\n".join(parts))


def why_not_usable(answer, names, haystack):
    if answer.get("received") is False:
        return "the agent said the samples did not reach it"
    template_id = answer.get("documentTemplateId")
    proposed = (answer.get("proposedTemplate") or "").strip()
    if not template_id and not proposed:
        return "neither a template nor a proposal"
    if template_id and template_id not in names:
        return f"named a template the app does not allow on this form's table(s): {template_id!r}"
    quote = folded(answer.get("quote"))
    if len(quote) < QUOTE_FLOOR:
        return f"quoted only {quote!r}, too little to show anything was read"
    if quote not in haystack:
        return f"quoted {quote[:60]!r}, which is not in the samples it was given"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    options = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session_dir = options.session_dir
    planned = load(session_dir, "FORM_CLASSIFICATION.json")
    tasks = planned.get("tasks") or []

    settled, missing, rejected, proposals = [], [], [], []
    for task in tasks:
        output = Path(task["output"])
        if not output.is_file():
            missing.append((task["formId"], "no answer on disk"))
            continue
        try:
            answer = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            missing.append((task["formId"], f"unreadable answer: {error}"))
            continue
        # An answer naming another form is not an answer to this task; keeping it would let one agent
        # overwrite a form it never saw.
        if answer.get("formId") not in (None, task["formId"]):
            missing.append((task["formId"], f"answered for {answer.get('formId')!r}"))
            continue

        payload = json.loads(Path(task["input"]).read_text(encoding="utf-8"))
        names = offered(payload)
        why = why_not_usable(answer, names, shown_text(payload))
        if why:
            rejected.append((task["formId"], why))
            missing.append((task["formId"], why))
            continue

        template_id = answer.get("documentTemplateId")
        entry = {
            "formId": task["formId"],
            "documents": task["documents"],
            "standsFor": task["documents"],
            "sampled": len(payload.get("samples") or []),
            "title": payload.get("title"),
            "documentTemplateId": template_id,
            "documentTemplateName": names.get(template_id),
            "proposedTemplate": (answer.get("proposedTemplate") or "").strip() or None,
            "runnerUpTemplateId": answer.get("runnerUpTemplateId"),
            "confidence": answer.get("confidence"),
            "quote": " ".join((answer.get("quote") or "").split()),
            "evidence": " ".join((answer.get("evidence") or "").split()),
        }
        settled.append(entry)
        if entry["proposedTemplate"]:
            proposals.append(entry)

    written = {"forms": settled,
               "missing": [{"formId": f, "why": w} for f, w in missing],
               "rejected": [{"formId": f, "why": w} for f, w in rejected],
               "documentsSettled": sum(f["documents"] for f in settled)}
    (session_dir / "FORM_TEMPLATES.json").write_text(json.dumps(written, indent=2), encoding="utf-8")

    print(f"{len(settled)}/{len(tasks)} form(s) answered, standing for "
          f"{written['documentsSettled']} document(s)")
    for form in settled[:SAMPLE]:
        called = form["documentTemplateName"] or f"proposed: {form['proposedTemplate']}"
        print(f"  {form['formId']}  {form['documents']:5d} documents  {(form['title'] or '')[:38]:38s} "
              f"-> {called}")
    if len(settled) > SAMPLE:
        print(f"  ... and {len(settled) - SAMPLE} more in FORM_TEMPLATES.json")

    if proposals:
        print(f"\nPROPOSED, NOT PICKED ({len(proposals)} form(s), "
              f"{sum(p['documents'] for p in proposals)} document(s)):")
        for form in proposals:
            print(f"  {form['formId']}  {form['proposedTemplate']}")
        print("  the app has no template for these; somebody creates them before those documents attach")

    if missing:
        print(f"\nSEND THESE AGAIN ({len(missing)}):")
        for form_id, why in missing[:SAMPLE]:
            print(f"  {form_id} — {why}")

    print(f"\n-> {session_dir / 'FORM_TEMPLATES.json'}")


if __name__ == "__main__":
    main()
