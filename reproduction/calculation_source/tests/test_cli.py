from econtypes import cli


def test_help(capsys):
    try:
        cli.main(["--help"])
    except SystemExit:
        pass
    assert "econtypes" in capsys.readouterr().out
