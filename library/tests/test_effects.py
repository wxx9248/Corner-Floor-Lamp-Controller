"""Effect/scene table integrity (counts verified against arrays.xml)."""
from duoco_stripx.effects import (
    ANIMATION_MODES,
    ANIMATION_NAME_TO_ID,
    SCENE_NAME_TO_ID,
    SCENES,
)


def test_counts() -> None:
    assert len(ANIMATION_MODES) == 213
    assert len(SCENES) == 28


def test_id_ranges_contiguous() -> None:
    assert sorted(ANIMATION_MODES) == list(range(213))
    assert sorted(SCENES) == list(range(1, 29))


def test_spot_checks() -> None:
    assert ANIMATION_MODES[0] == "Auto Play"
    assert ANIMATION_MODES[193] == "7-Color Jump"
    assert SCENES[1] == "Sunrise"
    assert SCENES[26] == "Valentine's Day"  # arrays.xml escapes this as \'
    assert SCENES[28] == "Warning"  # arrays.xml has the vendor typo "Warnning"


def test_reverse_maps_total() -> None:
    # duplicated app names must have been disambiguated
    assert len(ANIMATION_NAME_TO_ID) == 213
    assert len(SCENE_NAME_TO_ID) == 28
    for i, name in ANIMATION_MODES.items():
        assert ANIMATION_NAME_TO_ID[name] == i
    for i, name in SCENES.items():
        assert SCENE_NAME_TO_ID[name] == i


def test_known_duplicates_disambiguated() -> None:
    # the 4 names the app duplicates (groups 6/7) carry an " (id)" suffix
    for a, b in ((115, 169), (121, 173), (116, 170), (122, 174)):
        assert ANIMATION_MODES[a] != ANIMATION_MODES[b]
        assert ANIMATION_MODES[a].endswith(f"({a})")
        assert ANIMATION_MODES[b].endswith(f"({b})")
