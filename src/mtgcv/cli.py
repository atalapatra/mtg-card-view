"""Command-line interface.

    mtgcv analyze deck.txt                       # grouped by category, sorted by EDHREC rank
    mtgcv analyze deck.txt --group-by type --sort cmc
    mtgcv analyze deck.txt --json report.json    # full data for a UI / other tools
    mtgcv analyze - < deck.txt                   # read from stdin
    mtgcv card "Sol Ring"                        # details + all tags for one card
    mtgcv refresh-tags                           # force re-download of Scryfall oracle tags
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mtgcv.analyze import CardInfo, build_report, card_info, group_cards
from mtgcv.decklist import DeckEntry, parse_decklist
from mtgcv.scryfall import ScryfallClient

GROUP_CHOICES = ["category", "primary", "type", "cmc", "color", "section", "user_tag", "none"]
SORT_CHOICES = ["edhrec", "name", "cmc", "price"]


def _fmt_rank(r: int | None) -> str:
    return f"{r:,}" if r is not None else "—"


def _print_report(report, group_by: str, sort_by: str, show_tags: bool) -> None:
    s = report.to_dict(group_by, sort_by)["summary"]
    print(f"{s['total_cards']} cards ({s['unique_cards']} unique) · {s['lands']} lands · "
          f"avg MV (nonland) {s['average_cmc_nonland']} · identity "
          f"{''.join(s['color_identity']) or 'C'} · median EDHREC rank {_fmt_rank(s['median_edhrec_rank'])}")
    if s["game_changers"]:
        print(f"Game Changers: {', '.join(s['game_changers'])}")
    print()

    width = max((len(c.name) for c in report.cards), default=20) + 2
    cost_w = max((len(c.mana_cost) for c in report.cards), default=10) + 2
    for g in group_cards(report.cards, group_by, sort_by):  # type: ignore[arg-type]
        print(f"== {g.name} ({g.count}) ==")
        for c in g.cards:
            qty = f"{c.quantity}x" if c.quantity > 1 else "  "
            line = f"  {qty} {c.name:<{width}} {c.mana_cost:<{cost_w}} EDHREC {_fmt_rank(c.edhrec_rank):>7}"
            if group_by != "category" and c.categories:
                line += f"   [{', '.join(c.categories)}]"
            print(line)
            if show_tags and c.tags:
                print(f"       tags: {', '.join(c.tags)}")
        print()

    if report.not_found:
        print(f"Not found on Scryfall: {', '.join(report.not_found)}", file=sys.stderr)
    for lineno, text in report.parse_errors:
        print(f"Could not parse line {lineno}: {text!r}", file=sys.stderr)


def cmd_analyze(args: argparse.Namespace) -> int:
    text = sys.stdin.read() if args.decklist == "-" else Path(args.decklist).read_text(encoding="utf-8")
    parsed = parse_decklist(text)
    if not parsed.entries:
        print("No cards found in the deck list.", file=sys.stderr)
        return 1

    client = ScryfallClient()
    try:
        report = build_report(parsed, client)
    finally:
        client.close()

    if args.json:
        data = report.to_dict(args.group_by, args.sort)
        out = json.dumps(data, indent=2, ensure_ascii=False)
        if args.json == "-":
            sys.stdout.write(out + "\n")
        else:
            Path(args.json).write_text(out, encoding="utf-8")
            print(f"Wrote {args.json}", file=sys.stderr)
    else:
        _print_report(report, args.group_by, args.sort, args.tags)
    return 0


def cmd_card(args: argparse.Namespace) -> int:
    client = ScryfallClient()
    try:
        tags = client.load_oracle_tags()
        found, _ = client.get_cards([args.name])
    finally:
        client.close()
    if not found:
        print(f"Card not found: {args.name}", file=sys.stderr)
        return 1
    info: CardInfo = card_info(DeckEntry(name=args.name), found[args.name], tags)
    print(f"{info.name}  {info.mana_cost}")
    print(info.type_line)
    print(info.oracle_text)
    print()
    print(f"EDHREC rank: {_fmt_rank(info.edhrec_rank)}" + ("   (Game Changer)" if info.game_changer else ""))
    print(f"Categories:  {', '.join(info.categories) or '—'}")
    print("Tags:")
    for t in info.tags:
        desc = tags.descriptions.get(t, "")
        print(f"  {t}" + (f" — {desc.splitlines()[0][:100]}" if desc else ""))
    return 0


def cmd_refresh_tags(_: argparse.Namespace) -> int:
    client = ScryfallClient()
    try:
        idx = client.load_oracle_tags(force_refresh=True)
    finally:
        client.close()
    print(f"Loaded tags for {len(idx.by_oracle):,} cards ({len(idx.descriptions):,} described tags).")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # card names / mana symbols on Windows consoles
        sys.stderr.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(prog="mtgcv", description="Analyze MTG card lists with Scryfall data.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyze a deck/card list")
    a.add_argument("decklist", help="Path to a deck list text file, or - for stdin")
    a.add_argument("-g", "--group-by", choices=GROUP_CHOICES, default="category")
    a.add_argument("-s", "--sort", choices=SORT_CHOICES, default="edhrec")
    a.add_argument("-t", "--tags", action="store_true", help="Show raw Scryfall tags for each card")
    a.add_argument("--json", metavar="PATH", help="Write full JSON report to PATH (- for stdout)")
    a.set_defaults(func=cmd_analyze)

    c = sub.add_parser("card", help="Show details and tags for a single card")
    c.add_argument("name")
    c.set_defaults(func=cmd_card)

    r = sub.add_parser("refresh-tags", help="Force re-download of Scryfall oracle tags")
    r.set_defaults(func=cmd_refresh_tags)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
