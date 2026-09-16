from pathlib import Path

from src.cli import main


def test_validate_combined_example(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    assert main(["validate-data", str(root / "examples" / "combined")]) == 0
    assert '"status": "valid"' in capsys.readouterr().out


def test_validate_split_example(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    assert main(["validate-data", str(root / "examples" / "split")]) == 0
    assert '"representation": "split"' in capsys.readouterr().out
