from dataclasses import dataclass
from pathlib import Path
import typer
import jinja2
import importlib.resources
import black
import black.mode as black_mode


class MISSING:
    def __eq__(self, __o: "MISSING") -> bool:
        return isinstance(__o, MISSING)


_none = MISSING()


class InvalidModelField(Exception):
    pass


@dataclass
class ModuleImport:
    module: str
    model: str


@dataclass
class ModelField:
    field_name: str
    field_type: str = "str"
    field_default: str = ""

    @classmethod
    def parse(cls, field: str):
        tokens = field.split(":")
        match len(tokens):
            case 1:
                # Just the field name supplied, assume a required field (default = _none)
                # and field_type str
                return ModelField(tokens[0], "str")
            case 2:
                # assume <field>:<type> shape
                return ModelField(*tokens)
            case 3:
                return ModelField(*tokens)
            case _:
                raise typer.BadParameter(
                    f"must conforms to : <field>[:<type>[:<default>]]"
                )

    @classmethod
    def parse_list(cls, fields: str):
        if not fields:
            return []
        curated_str = fields.split()
        return [cls.parse(f) for f in curated_str]


generate = typer.Typer()


@generate.command(name="model")
def generate_model(
    app: str = typer.Argument(..., help="app where to which this model belongs to."),
    model: str = typer.Argument(..., help="Model name. Use a CamelCase name here please"),
    fields: str = typer.Argument(
        "",
        help='Fields to add to the model. The template is as follows: "<name>[:<type>[:<default>]] ..."',
    ),
    path: Path = typer.Option(
        None,
        help="The path to where create your model. By default it stores on a models folder o your selected app.",
    ),
    dry: bool = typer.Option(
        False, help="Do not do any changes, only print the content to stdin."
    ),
    format: bool = typer.Option(False, help="Format generated code using black."),
):
    if path is None:
        path = Path(f"apps/{app}/models")
    model_fields = ModelField.parse_list(fields)
    imports: list[ModuleImport] = []

    path = path / f"{model.lower()}.py"
    path = path.resolve()

    if not path.exists() and not dry:
        path.parent.mkdir(parents=True, exist_ok=True)

    with importlib.resources.open_text(
        "wintry.cli.templates.generate", "model.py.j2"
    ) as template_file:
        template: jinja2.Template = jinja2.Template(source=template_file.read())
        content = template.render(
            model_name=model, model_fields=model_fields, model_imports=imports
        )
        if format:
            content = black.format_str(content, mode=black_mode.Mode())
        if not dry:
            with path.open(mode="w", encoding="utf-8") as f:
                f.write(content)
        else:
            typer.secho(content, fg=typer.colors.BLUE)


@generate.command(name="m")
def generate_model_alias(
    app: str = typer.Argument(..., help="app where to which this model belongs to."),
    model: str = typer.Argument(..., help="Model name. Use a CamelCase name here please"),
    fields: str = typer.Argument(
        "",
        help='Fields to add to the model. The template is as follows: "<name>[:<type>[:<default>]] ..."',
    ),
    path: Path = typer.Option(
        Path("models"),
        help="The path to where create your model. By default it stores on a models folder.",
    ),
    dry: bool = typer.Option(
        False, help="Do not do any changes, only print the content to stdin."
    ),
    format: bool = typer.Option(False, help="Format generated code using black."),
):
    generate_model(app, model, fields, path, dry, format)


@generate.command(name="controller")
def generate_controller():
    pass


@generate.command(name="c")
def generate_controller_alias():
    generate_controller()
