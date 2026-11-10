"""Tool for faster annotating posts with narratives and entity roles """
import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import openpyxl

HERE = Path(__file__).parent
CSV_PATH = HERE / "data" / "annotation" / "message_annotation.csv"
TAXONOMY_PATH = HERE / "data" / "annotation" / "narrative_taxonomy.xlsx"
NARR_COL = "narrative"
DOM_COL = "dominat Naratiive"
ROLE_COL = "Entity roles"
ID_PREFIX = {"war": "F", "migrants": "M"}
ROLES = {"a": "Protagonist", "b": "Antagonist", "c": "Innocent"}


class Skip(Exception):
    pass


class Quit(Exception):
    pass


def prompt(text):
    answer = input(text).strip()
    if answer.lower() == "skip":
        raise Skip
    if answer.lower() == "quit":
        raise Quit
    return answer


def confirm():
    return prompt("Save? [y]/n: ").lower() in ("", "y", "yes")


def load_taxonomy(path):
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)["taxonomy"]
    taxonomy = {}  # lower-case ID -> {id, sub, full}
    for row in list(sheet.iter_rows(values_only=True))[1:]:
        if row[0]:
            tid = str(row[0]).strip()
            taxonomy.setdefault(tid.lower(), {"id": tid, "sub": str(row[2] or "").strip(), "full": str(row[3] or "").strip()})
    return taxonomy


def show_taxonomy(taxonomy, prefix):
    print("\nTaxonomy:")
    for t in taxonomy.values():
        if t["id"].startswith(prefix) or t["id"].lower() in ("other", "none"):
            print(f"  {t['id']:<6} {t['sub']}")


def ids_of(value):
    """'F2.3 Discrediting...; F1.1 Responsibility...' -> ['F2.3', 'F1.1']"""
    # Split only before an ID
    parts = [p.strip() for p in re.split(r";\s*(?=[FM]\d+\.\d+\b|none\b|Other\b)", value) if p.strip()]
    return [p if p.startswith("Other") else p.split()[0] for p in parts]


def narratives_done(row):
    ids = ids_of(row[NARR_COL])
    return bool(ids and row[DOM_COL].strip()) and all(
        re.fullmatch(r"[FM]\d+\.\d+", i) or i == "none" or i.startswith("Other") for i in ids)


def roles_done(row):
    value = row[ROLE_COL].strip()
    if value.lower() == "none":
        return True
    pairs = [p.rpartition(":") for p in value.split(";")]
    return bool(value) and all(sep and role.strip() in ROLES.values() for _, sep, role in pairs)


def show(i, total, row):
    print("\n" + "=" * 70)
    print(f"[{i}/{total}]  @{row['channel']}   ({row['domain']}, {row['language']}, side: {row['side']})")
    print(f"{row['date']}   {row['url']}")
    print("-" * 70)
    print(row["text"].strip())
    print("-" * 70)
    dominant = ids_of(row[DOM_COL])
    print("Narratives:", " ".join(ids_of(row[NARR_COL])) or "-", f"  (dominant: {dominant[0]})" if dominant else "")
    print("Roles:     ", row[ROLE_COL] or "-")


def parse_narratives(answer, taxonomy, prefix):
    """Return the list of full labels (first = dominant), or an error message."""
    match = re.search(r"\bother\b[:\s]*(.*)$", answer, re.IGNORECASE)
    head = answer[:match.start()] if match else answer
    labels = []
    for t in re.split(r"[\s,;]+", head):
        if not t:
            continue
        if t.lower() == "none":
            labels.append("none")
        elif t.lower() in taxonomy and t.upper().startswith(prefix):
            labels.append(taxonomy[t.lower()]["full"])
        else:
            return f"Unknown ID for this domain: {t}"
    if match:
        note = match.group(1).strip()
        labels.append(f"Other ({note})" if note else "Other")
    if not labels:
        return "Type at least one ID."
    if "none" in labels and len(labels) > 1:
        return "'none' cannot be combined with other labels."
    return list(dict.fromkeys(labels))


def ask_narratives(row, taxonomy):
    """Return the new labels, or None to keep the current ones."""
    prefix = ID_PREFIX.get(row["domain"], "")
    while True:
        answer = prompt("Narratives (first = dominant), Enter = keep, ? = taxonomy: ")
        if answer == "?":
            show_taxonomy(taxonomy, prefix)
            continue
        if not answer:
            if narratives_done(row):
                return None
            print("This post has no labels yet - type the IDs.")
            continue
        labels = parse_narratives(answer, taxonomy, prefix)
        if isinstance(labels, str):
            print(labels)
            continue
        print("  ->", " ".join(ids_of("; ".join(labels))), f"  (dominant: {ids_of(labels[0])[0]})")
        if confirm():
            return labels


def ask_roles():
    """Ask for entities first, then a role for each one. Return the value for ROLE_COL."""
    while True:
        print("Entities: type one and press Enter, empty line = done.")
        entities = []
        while name := prompt(f"  entity {len(entities) + 1}: "):
            name = " ".join(re.sub(r"[:;]", " ", name).split())  # ":" and ";" separate the stored value
            if name not in entities:
                entities.append(name)
        pairs = []
        for name in entities:
            while (key := prompt(f"  {name}:  a) Protagonist  b) Antagonist  c) Innocent: ").lower()) not in ROLES:
                print("  Type a, b or c.")
            pairs.append(f"{name}:{ROLES[key]}")
        value = "; ".join(pairs) or "none"
        print("  ->", value)
        if confirm():
            return value


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
                time.sleep(1)  # answers come from a pipe: don't read a line, or they shift
    sys.exit(f"Could not save {path}: the file stays locked.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Annotate narratives or entity roles.")
    p.add_argument("mode", nargs="?", choices=["narratives", "roles"], default="narratives")
    p.add_argument("--domain", choices=list(ID_PREFIX), help="Only this domain (default: both)")
    p.add_argument("--redo", action="store_true", help="Also show posts that are already annotated")
    p.add_argument("--csv", type=Path, default=CSV_PATH)
    p.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH)
    args = p.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)
    with open(args.csv, encoding="utf-8-sig") as f:
        header = f.readline()
        sep = ";" if header.count(";") > header.count(",") else ","
        f.seek(0)
        reader = csv.DictReader(f, delimiter=sep)
        fieldnames, rows = reader.fieldnames, list(reader)

    done = narratives_done if args.mode == "narratives" else roles_done
    posts = [r for r in rows if not args.domain or r["domain"] == args.domain]
    todo = [r for r in posts if args.redo or not done(r)]
    print(f"{args.mode}: {len(todo)} posts to show, {sum(map(done, posts))} of {len(posts)} already done.")

    saved = 0
    try:
        for i, row in enumerate(todo, 1):
            show(i, len(todo), row)
            try:
                if args.mode == "narratives":
                    labels = ask_narratives(row, taxonomy)
                    if labels is None:
                        continue
                    row[NARR_COL] = "; ".join(labels)
                    row[DOM_COL] = labels[0]
                else:
                    row[ROLE_COL] = ask_roles()
            except Skip:
                continue
            save(args.csv, fieldnames, rows, sep)
            saved += 1
    except (Quit, KeyboardInterrupt, EOFError):
        pass
    print(f"\nSaved {saved} posts to {args.csv}")


if __name__ == "__main__":
    main()
