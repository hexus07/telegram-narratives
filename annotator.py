"""Label narratives in narrative_selection.csv with the URW taxonomy.

Each post is printed with its previous labels. Type taxonomy IDs separated by spaces or commas:
the FIRST ID is the dominant narrative, the rest follow in order of appearance in the text.

  F2.3 F1.1             -> narrative = F2.3; F1.1, dominant = F2.3
  F4.3 other <note>     -> "other" takes the rest of the line as its note, so write it last
  none                  -> no narrative
  Enter                 -> accept the suggestion (shown when the old label maps to the taxonomy)
  ?                     -> show the taxonomy
  skip / quit

The file is saved after every answer, so you can stop and continue later.
Posts already labeled with taxonomy IDs are skipped (use --redo to see them again).
"""
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import openpyxl

HERE = Path(__file__).parent
NARR_COL = "narrative"
DOM_COL = "dominat Naratiive"
NEW_ID = re.compile(r"^[FM]\d+\.\d+$", re.IGNORECASE)  # F = war, M = migration
ID_PREFIX = {"war": "f", "migrants": "m"}
OLD_ID = re.compile(r"^(\d+\.\d+|11\.x)\b")


def parse_args():
    p = argparse.ArgumentParser(description="Label narratives with the URW taxonomy.")
    p.add_argument("--csv", default=HERE / "narrative_selection.csv", help="CSV to label")
    p.add_argument("--taxonomy", default=HERE / "narrative_taxonomy_URW_v1_draft.xlsx", help="Taxonomy workbook")
    p.add_argument("--domain", default="war", help="Only posts of this domain: war (F IDs) or migrants (M IDs)")
    p.add_argument("--redo", action="store_true", help="Also show posts that already have taxonomy labels")
    return p.parse_args()


def load_taxonomy(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    taxonomy = {}  # lower-case ID -> row
    for row in list(wb["taxonomy"].iter_rows(values_only=True))[1:]:
        if row[0]:
            tid, _, sub, full, definition, direction = (str(c or "").strip() for c in row[:6])
            taxonomy[tid.lower()] = {"id": tid, "sub": sub, "full": full, "definition": definition, "direction": direction}
    mapping = {}  # old SemEval ID -> (new ID, status)
    for row in list(wb["semeval_mapping"].iter_rows(values_only=True))[1:]:
        if row[0] and row[2]:
            mapping[str(row[0]).strip()] = (str(row[2]).strip(), str(row[3] or "").strip())
    return taxonomy, mapping


def show_taxonomy(taxonomy):
    print("\nTaxonomy:")
    for t in taxonomy.values():
        print(f"  {t['id']:<6} {t['sub']}  [{t['direction']}]")


def labels_of(value):
    # Split only before an ID: some full labels contain ";" themselves (e.g. F5.1)
    parts = re.split(r";\s*(?=[FM]\d+\.\d+\b|none\b|Other\b|\d+\.\d+\b|11\.x\b)", value)
    return [p.strip() for p in parts if p.strip()]


def is_done(row):
    # Done = a dominant label is set and every stored label is a taxonomy ID, Other or none
    parts = labels_of(row[NARR_COL])
    return bool(parts and row[DOM_COL].strip()) and all(
        NEW_ID.match(p.split()[0]) or p.lower() == "none" or p.startswith("Other") for p in parts
    )


def suggest(row, mapping):
    """Translate the old labels to taxonomy IDs where the mapping sheet allows it."""
    ids, notes = [], []
    for part in labels_of(row[DOM_COL]) + labels_of(row[NARR_COL]):  # dominant first
        first = part.split()[0]
        if NEW_ID.match(first):
            new = first.upper()
        elif OLD_ID.match(part):
            old = OLD_ID.match(part).group(1)
            if old not in mapping:
                continue
            new, status = mapping[old]
            note = f"{old} -> {new} ({status})"
            if note not in notes:
                notes.append(note)
        elif part.lower() in ("none", "no"):
            new = "none"
        else:
            continue
        if new not in ids:
            ids.append(new)
    return ids, notes


def show(i, total, row, suggestion, notes):
    print("\n" + "=" * 70)
    print(f"[{i}/{total}]  @{row['channel']}   ({row['domain']}, {row['language']}, side: {row['side']})")
    print(f"{row['date']}   {row['url']}")
    print("-" * 70)
    print(row["text"].strip())
    print("-" * 70)
    print("Previous narrative:", row[NARR_COL] or "-")
    print("Previous dominant: ", row[DOM_COL] or "-")
    if suggestion:
        print("Suggestion:        ", " ".join(suggestion), f"  ({'; '.join(notes)})" if notes else "")


def parse_answer(answer, taxonomy):
    """Return the list of full labels (first = dominant), or an error message."""
    match = re.search(r"\bother\b[:\s]*(.*)$", answer, re.IGNORECASE)
    head = answer[:match.start()] if match else answer
    tokens = [t for t in re.split(r"[\s,;]+", head) if t]
    labels = []
    for t in tokens:
        if t.lower() == "none":
            labels.append("none")
        elif t.lower() in taxonomy:
            labels.append(taxonomy[t.lower()]["full"])
        else:
            return f"Unknown ID: {t}"
    if match:
        note = match.group(1).strip()
        labels.append(f"Other ({note})" if note else "Other")
    if "none" in labels and len(labels) > 1:
        return "'none' cannot be combined with other labels."
    if not labels:
        return "Type at least one ID."
    return list(dict.fromkeys(labels))


def ask(taxonomy, suggestion):
    while True:
        answer = input("Narratives (first = dominant), Enter = suggestion, ? / skip / quit: ").strip()
        if answer == "?":
            show_taxonomy(taxonomy)
            continue
        if answer.lower() in ("skip", "quit"):
            return answer.lower()
        if not answer:
            if not suggestion:
                print("No suggestion for this post - type the IDs.")
                continue
            answer = " ".join(suggestion)
        result = parse_answer(answer, taxonomy)
        if isinstance(result, str):
            print(result)
            continue
        print("  narrative:", "; ".join(result))
        print("  dominant: ", result[0])
        if input("Save? [y]/n: ").strip().lower() in ("", "y", "yes"):
            return result


def save(path, fieldnames, rows, sep):
    tmp = Path(path).with_suffix(".tmp")
    for _ in range(30):
        try:
            with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=sep)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(tmp, path)
            return
        except PermissionError:
            if sys.stdin.isatty():
                input(f"{path} is open in another program (Excel?). Close it and press Enter to retry.")
            else:
                # Answers come from a pipe: wait instead of reading a line, so they don't shift
                time.sleep(1)
    sys.exit(f"Could not save {path}: the file stays locked.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    taxonomy, mapping = load_taxonomy(args.taxonomy)
    # Keep only this domain's IDs (F for war, M for migration) plus Other and none
    prefix = ID_PREFIX.get(args.domain)
    if prefix:
        taxonomy = {k: v for k, v in taxonomy.items() if k.startswith(prefix) or k in ("other", "none")}

    with open(args.csv, encoding="utf-8-sig") as f:
        header = f.readline()
        sep = ";" if header.count(";") > header.count(",") else ","
        f.seek(0)
        reader = csv.DictReader(f, delimiter=sep)
        fieldnames, rows = reader.fieldnames, list(reader)

    todo = [r for r in rows if r["domain"] == args.domain and (args.redo or not is_done(r))]
    done_before = sum(1 for r in rows if r["domain"] == args.domain and is_done(r))
    print(f"{args.csv}: {len(todo)} {args.domain} posts to label ({done_before} already labeled).")
    show_taxonomy(taxonomy)

    labeled = 0
    for i, row in enumerate(todo, 1):
        suggestion, notes = suggest(row, mapping)
        show(i, len(todo), row, suggestion, notes)
        result = ask(taxonomy, suggestion)
        if result == "quit":
            break
        if result == "skip":
            continue
        row[NARR_COL] = "; ".join(result)
        row[DOM_COL] = result[0]
        save(args.csv, fieldnames, rows, sep)
        labeled += 1

    print(f"\nLabeled {labeled} posts in {args.csv}")


if __name__ == "__main__":
    main()
