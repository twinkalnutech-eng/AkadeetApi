from pathlib import Path
from jinja2 import Template

# Points to /akadit/app
BASE_DIR = Path(__file__).resolve().parent.parent


def render_html_template(template_path: str, context: dict) -> str:
    """
    template_path example:
    'templates/ticket_mail.html'
    """
    full_path = BASE_DIR / template_path

    if not full_path.exists():
        raise FileNotFoundError(f"Template not found: {full_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.render(**context)
