import typer
import wintry.cli.commands.generate as gen
import wintry.cli.commands.new as new_command

snowman = typer.Typer()
snowman.add_typer(gen.generate, name="g")
snowman.add_typer(gen.generate, name="gen")
snowman.add_typer(gen.generate, name="generate")
snowman.add_typer(new_command.new, name="new")


if __name__ == '__main__':
    snowman()