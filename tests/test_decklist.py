from mtgcv.decklist import parse_decklist


def test_basic_formats():
    text = """
Sol Ring
2 Llanowar Elves
3x Forest
1 Arcane Signet (C21) 263
1 Command Tower (CMR) 350 *F*
1x Cultivate (m21) 177 [Ramp,Land Fetch]
1 Rhystic Study #draw #stax
"""
    r = parse_decklist(text)
    assert not r.errors
    by = {e.name: e for e in r.entries}
    assert by["Sol Ring"].quantity == 1
    assert by["Llanowar Elves"].quantity == 2
    assert by["Forest"].quantity == 3
    assert by["Arcane Signet"].set_code == "c21"
    assert by["Arcane Signet"].collector_number == "263"
    assert by["Command Tower"].set_code == "cmr"
    assert by["Cultivate"].user_tags == ["Ramp", "Land Fetch"]
    assert by["Rhystic Study"].user_tags == ["draw", "stax"]


def test_sections_and_comments():
    text = """// My deck
Commander
1 Atraxa, Praetors' Voice

Deck
1 Sol Ring
# a comment
Sideboard:
1 Lightning Greaves
SB: 1 Swiftfoot Boots
"""
    r = parse_decklist(text)
    sections = {e.name: e.section for e in r.entries}
    assert sections == {
        "Atraxa, Praetors' Voice": "commander",
        "Sol Ring": "main",
        "Lightning Greaves": "sideboard",
        "Swiftfoot Boots": "sideboard",
    }


def test_split_names_normalized():
    r = parse_decklist("1 Fire // Ice\n1 Wear/Tear\n")
    assert [e.name for e in r.entries] == ["Fire // Ice", "Wear // Tear"]


def test_duplicates_merged():
    r = parse_decklist("1 Forest\n2 Forest\n")
    assert len(r.entries) == 1 and r.entries[0].quantity == 3
