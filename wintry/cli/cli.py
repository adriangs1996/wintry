import typer
import wintry.cli.commands.generate as gen

snowman = typer.Typer()
snowman.add_typer(gen.generate, name="g")
snowman.add_typer(gen.generate, name="gen")
snowman.add_typer(gen.generate, name="generate")


if __name__ == '__main__':
    snowman()