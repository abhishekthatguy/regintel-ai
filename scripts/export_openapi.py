"""Export the OpenAPI schema for handoff (Postman/insomnia import).

    .venv/bin/python scripts/export_openapi.py > regintel.openapi.json
"""

import json

from app.main import create_app

print(json.dumps(create_app().openapi(), indent=2))
