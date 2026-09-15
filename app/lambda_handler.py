"""Lambda entry point (Phase 3 deploy): Mangum adapts the FastAPI app to
API Gateway + Lambda. The app is stateless — SQLite paths are only for the
local profile; cloud deploys set REGINTEL_STORE_BACKEND=dynamodb."""

try:
    from mangum import Mangum

    from app.main import app

    handler = Mangum(app, lifespan="off")
except ImportError:  # mangum only needed in the deployment package
    handler = None
