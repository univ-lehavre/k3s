from pathlib import Path

from pilotremote.executor import expand_identity_file


def test_expand_identity_file_expands_home() -> None:
    assert expand_identity_file("~/.ssh/id_ed25519") == str(Path("~/.ssh/id_ed25519").expanduser())
