import typer
import wintry.cli.commands.generate as gen

app = typer.Typer()
app.add_typer(gen.generate, name="g")
app.add_typer(gen.generate, name="gen")
app.add_typer(gen.generate, name="generate")

def cli():
    app()


if __name__ == '__main__':
    cli()