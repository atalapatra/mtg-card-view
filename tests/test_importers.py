from pathlib import Path

import pytest

from mtgcv.decklist import parse_decklist
from mtgcv.importers import looks_like_manabox, manabox_to_decklist

SAMPLE = (Path(__file__).parent / "fixtures" / "manabox_sample.csv").read_text(encoding="utf-8")


def test_detects_manabox():
    assert looks_like_manabox(SAMPLE)
    assert looks_like_manabox("﻿" + SAMPLE)  # BOM from Excel/Windows
    assert not looks_like_manabox("1 Sol Ring\n1 Arcane Signet\n")
    assert not looks_like_manabox("Name,Quantity\nSol Ring,1\n")  # generic CSV


def test_defaults_skip_tokens_and_lists_and_combine_printings():
    r = manabox_to_decklist(SAMPLE)
    lines = r.text.splitlines()
    assert "4 Island (FDN) 274" in lines             # 1 + 3 across printings, first printing kept
    assert "2 Sol Ring (TDC) 106" in lines           # same name in binder + deck
    assert "8 Plains (40K) 306" in lines             # quoted set name with comma
    assert "1 Lord of the Nazgûl (LTC) 60" in lines  # non-ASCII
    assert "1 Murderous Rider // Swift End (DRC) 45" in lines
    assert "1 Arcane Signet (PLST) OTC-252" in lines
    assert not any("Zombie" in l or "Copy" in l or "Rhystic" in l for l in lines)
    assert (r.skipped_tokens, r.skipped_lists) == (7, 3)
    assert r.unique == len(lines) == 9 and r.cards == 20 and r.rows == 15


def test_include_options():
    r = manabox_to_decklist(SAMPLE, include_tokens=True, include_lists=True)
    assert "6 Copy (TBLC) 1" in r.text and "2 Life Finds a Way (REX) 5" in r.text
    assert r.skipped_tokens == r.skipped_lists == 0


def test_output_parses_like_a_pasted_list():
    parsed = parse_decklist(manabox_to_decklist(SAMPLE).text)
    assert not parsed.errors
    by = {e.name: e for e in parsed.entries}
    assert by["Island"].quantity == 4 and by["Island"].set_code == "fdn"
    assert by["Arcane Signet"].collector_number == "OTC-252"
    assert by["Akawalli, the Seething Tower"].quantity == 1


def test_rejects_other_csv():
    with pytest.raises(ValueError):
        manabox_to_decklist("Card,Count\nSol Ring,1\n")
