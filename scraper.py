import argparse
import asyncio
import csv
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

# Keywords per domain (the "domain" value in channels.json).
KEYWORDS = {
    "war": None,
    "migrants": [
        "migra", "immigra", "emigra", "remigra", "refugee", "asylum", "deport", "illegals", "illegal alien",
        "undocumented", "border control", "border crossing", "border patrol", "open borders",
        "small boat", "channel crossing", "people smuggl", "human smuggl",
        "ice raid", "ice agent", "ice officer", "ice detention",
        "visa", "residence permit", "work permit", "citizenship", "naturaliz",
        "foreign-born", "foreigners", "displaced", "frontex", "lampedusa", "schengen",
        "great replacement", "invasion", "multicultural", "sanctuary city",
    ],
    "crypto": {'crypto', 'token', 'airdrop', 'presale', 'altcoin', 'blockchain', 'NFT', 'ICO', 'cryptocurrency', 'defi', 'staking', 'yield farming', 'pump and dump', 'rug pull', 'moonshot', 'giveaway', 'airdrops', 'airdropped', 'airdropping', 'airdrops are free', 'airdrops are legit', 'airdrops are scam', 'airdrops are safe', 'airdrops are risky', 'airdrops are profitable', 'airdrops are worth it', 'airdrops are a scam', 'airdrops are a risk', 'airdrops are a gamble', 'airdrops are a lottery', 'airdrops are a pyramid scheme', 'airdrops are a ponzi scheme', 'airdrops are a scammy scheme', 'airdrops are a scammy project', 'airdrops are a scammy token', 'airdrops are a scammy coin', 'airdrops are a scammy NFT', 'airdrops are a scammy project token', 'airdrops are a scammy project coin', 'airdrops are a scammy project NFT'},
}

COLUMNS = [
    "message_id", "channel", "date", "domain", "language", "url", "text",
    "role_A", "is_narrative?", "stance", "ad_repost?"
]


def excel_separator():
    """Excel splits CSV columns by the Windows 'list separator' (',' or ';' depending on locale)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as key:
            return winreg.QueryValueEx(key, "sList")[0] or ","
    except (ImportError, OSError):
        return ","


def excel_safe(text):
    # Excel treats cells starting with = + - @ as formulas (e.g. "- item" -> #NAME?)
    return " " + text if text[:1] in ("=", "+", "-", "@") else text


def parse_args():
    p = argparse.ArgumentParser(description="Collect, filter and review messages from Telegram channels.")
    p.add_argument("-c", "--config", default="channels.json", help="JSON list of {channel, language, domain}")
    p.add_argument("-n", "--num", type=int, default=100, help="Last N messages per channel to check (default 100)")
    p.add_argument("-o", "--out", default="data/scraped_messages.csv", help="Output CSV file")
    p.add_argument("--sep", default=None, help="CSV separator (default: this computer's Excel separator)")
    p.add_argument("--session", default="collector_session", help="Telethon session file name")
    return p.parse_args()


def load_channels(path):
    with open(path, encoding="utf-8") as f:
        channels = json.load(f)
    for ch in channels:
        missing = {"channel", "language", "domain"} - ch.keys()
        if missing:
            raise ValueError(f"{ch} is missing {missing}")
        ch["channel"] = ch["channel"].strip().lstrip("@")
        if ch["domain"] not in KEYWORDS:
            print(f"Warning: domain '{ch['domain']}' (@{ch['channel']}) is not in KEYWORDS - no filtering.")
    return channels


def matched_keywords(text, keywords):
    """Keywords found in text ([] = none found, message is dropped).
    With no keywords, every message passes (returns None)."""
    if not keywords:
        return None
    # match at the start of a word: "deport" finds "deportation", but "ice" does not find "police"
    return [k for k in keywords if re.search(r"\b" + re.escape(k), text, re.IGNORECASE)]


def load_saved_channels(path, sep):
    """Channels already in the output file (lowercase), so they are skipped."""
    if not path.exists() or path.stat().st_size == 0:
        return set()
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return {r["channel"].casefold() for r in csv.DictReader(f, delimiter=sep)}
    except (UnicodeDecodeError, KeyError):
        sys.exit(f"Can't read {path} (re-saved by Excel or a different separator?). "
                 f"Rename it or pass --out to write to a new file.")


async def fetch_candidates(client, cfg, num):
    """Last `num` messages of a channel that have text and match the domain's keywords, oldest first."""
    entity = await client.get_entity(cfg["channel"])
    username = getattr(entity, "username", None) or cfg["channel"]
    keywords = KEYWORDS.get(cfg["domain"])

    found = []
    async for msg in client.iter_messages(entity, limit=num):
        text = msg.message or ""
        if msg.action is not None or not text.strip():
            continue  # service messages and media without a caption
        hits = matched_keywords(text, keywords)
        if hits == []:
            continue
        found.append((username, msg, hits))
    found.reverse()
    return found


def show(i, total, username, cfg, msg, hits):
    print("\n" + "=" * 70)
    print(f"[{i}/{total}]  @{username}   ({cfg['domain']}, {cfg['language']})")
    print(f"{msg.date:%Y-%m-%d %H:%M} UTC   https://t.me/{username}/{msg.id}")
    if hits:
        print("Keywords:", ", ".join(hits))
    print("-" * 70)
    print(msg.message)
    print("-" * 70)


async def ask():
    # input() runs in a thread so the Telegram connection stays alive while you read
    while True:
        answer = (await asyncio.to_thread(input, "Add? [y]es / [n]o / skip / quit: ")).strip().lower()
        if answer in ("y", "yes", "n", "no", "skip", "quit"):
            return answer[0] if answer in ("yes", "no") else answer
        print("Please type y, n, skip or quit.")


async def main():
    args = parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # show emoji / Cyrillic correctly in the console
    channels = load_channels(args.config)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sep = args.sep or excel_separator()

    saved_channels = load_saved_channels(out_path, sep)
    if saved_channels:
        print(f"{out_path} already has channels: {', '.join(sorted(saved_channels))} - they will be skipped.")

    try:
        f = open(out_path, "a", encoding="utf-8-sig", newline="")
    except PermissionError:
        sys.exit(f"{out_path} is open in another program (Excel?). Close it and try again.")

    api_id = int(os.getenv("TG_API_ID"))
    api_hash = os.getenv("TG_API_HASH")
    added, failed = 0, []

    async with TelegramClient(args.session, api_id, api_hash, flood_sleep_threshold=60) as client:
        # utf-8-sig writes the BOM (so Excel shows Cyrillic) only when the file is new
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=sep, restval="")
        if f.tell() == 0:
            writer.writeheader()

        for cfg in channels:
            if cfg["channel"].casefold() in saved_channels:
                print(f"\n[skip] @{cfg['channel']}: already in {out_path}")
                continue
            try:
                found = await fetch_candidates(client, cfg, args.num)
            except Exception as e:  # one bad channel should not stop the rest
                print(f"\n[skip] @{cfg['channel']}: {e}")
                failed.append(cfg["channel"])
                continue

            print(f"\n### @{cfg['channel']}: {len(found)} messages to review")

            answer = None
            for i, (username, msg, hits) in enumerate(found, 1):
                show(i, len(found), username, cfg, msg, hits)
                answer = await ask()
                if answer == "y":
                    writer.writerow({
                        "message_id": msg.id,
                        "channel": username,
                        "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                        "domain": cfg["domain"],
                        "language": cfg["language"],
                        "url": f"https://t.me/{username}/{msg.id}",
                        "text": excel_safe(msg.message),
                    })
                    f.flush()  # saved immediately, nothing is lost if you stop
                    added += 1
                elif answer in ("skip", "quit"):
                    break
            if answer == "quit":
                break

    f.close()
    print(f"\nAdded {added} messages to {out_path}")
    if failed:
        print("Failed channels:", ", ".join(failed))


if __name__ == "__main__":
    asyncio.run(main())
