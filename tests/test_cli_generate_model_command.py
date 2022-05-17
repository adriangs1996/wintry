from typer.testing import CliRunner
from wintry.cli.cli import app
from wintry.models import Model


class Address(Model):
    name: str


cli_runner = CliRunner()


def test_generate_model_command_produces_model():
    result = cli_runner.invoke(
        app, ["g", "model", "User", '"age:int:0 name:str"', "--dry"]
    )
    assert result.exit_code == 0
    assert "from wintry.models import Model" in result.stdout
    assert "from dataclasses import field" in result.stdout
    assert "class User(Model):" in result.stdout
    assert "age: int = 0" in result.stdout
    assert "name: str" in result.stdout


def test_generate_model_command_make_one_to_one_relation():
    result = cli_runner.invoke(
        app, ["g", "model", "User", '"name:str address:Address:None"', "--dry"]
    )
    assert result.exit_code == 0
    assert "from wintry.models import Model" in result.stdout
    assert "from tests.test_cli_generate_model_command import Address"
    assert "class User(Model):" in result.stdout
    assert "name: str" in result.stdout
    assert "address: Address = None" in result.stdout


def test_generate_user_with_list_of_addresses():
    result = cli_runner.invoke(
        app,
        [
            "g",
            "model",
            "User",
            '"name:str addresses:list[Address]:field(default_factory=list)"',
            "--dry",
        ],
    )
    assert result.exit_code == 0
    assert "from wintry.models import Model" in result.stdout
    assert "from tests.test_cli_generate_model_command import Address"
    assert "class User(Model):" in result.stdout
    assert "name: str" in result.stdout
    assert "addresses: list[Address] = field(default_factory=list)" in result.stdout
