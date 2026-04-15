from pulsecommerce.cli import build_parser


def test_parser_has_all_commands():
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"
    )
    cmds = set(subparsers_action.choices.keys())
    assert {"generate", "warehouse", "pipeline", "all", "version"} <= cmds


def test_version_command(capsys):
    from pulsecommerce.cli import main

    rc = main(["version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "pulsecommerce" in captured.out
