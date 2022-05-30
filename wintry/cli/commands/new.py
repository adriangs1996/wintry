from pathlib import Path
import typer
from cookiecutter.main import cookiecutter

new = typer.Typer()
path = Path(__file__).parent.parent
path_to_project_template = path / "templates/project"


@new.command(name="project")
def project(
    project_name: str = typer.Argument(...), output_path: Path = typer.Option(Path("."))
):
    data = {"project_name": project_name}
    cookiecutter(
        str(path_to_project_template),
        extra_context=data,
        no_input=True,
        output_dir=str(output_path.resolve()),
    )
