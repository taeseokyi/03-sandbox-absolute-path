"""Doc Generator - Generates Markdown API docs for a tool class."""

import inspect
from pathlib import Path
from ..base_tool import BaseTool


class DocGenerator(BaseTool):
    """Generate a Markdown reference doc for a BaseTool subclass.

    Usage:
        gen = DocGenerator()
        md = gen.run(CSVConverter)
        gen.run(CSVConverter, dst="docs/generated/csv_converter.md")
    """

    name = "doc_generator"
    description = "Generate Markdown API docs for a tool class"

    def run(self, tool_cls: type, dst: str | Path | None = None) -> str:
        name = tool_cls.name if hasattr(tool_cls, "name") else tool_cls.__name__
        desc = tool_cls.description if hasattr(tool_cls, "description") else ""
        docstring = inspect.getdoc(tool_cls) or ""
        run_sig = inspect.signature(tool_cls.run)
        run_doc = inspect.getdoc(tool_cls.run) or ""

        lines = [
            f"# {name}",
            "",
            f"> {desc}",
            "",
            "## Description",
            "",
            docstring,
            "",
            "## Interface",
            "",
            f"```python",
            f"def run{run_sig}",
            f"```",
            "",
        ]
        if run_doc:
            lines += ["### Parameters", "", run_doc, ""]

        md = "\n".join(lines)
        if dst:
            Path(dst).write_text(md, encoding="utf-8")
        return md
