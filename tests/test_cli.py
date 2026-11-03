"""Tests for the KubeLens Doctor CLI."""

import subprocess


def test_help_command():
    result = subprocess.run(
        ["kubelens", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "KubeLens Doctor" in result.stdout
    assert "--version" in result.stdout


def test_version_command():
    result = subprocess.run(
        ["kubelens", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "KubeLens Doctor 0.1.0" in result.stdout
