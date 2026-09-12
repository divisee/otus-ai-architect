import pytest
from fastapi.testclient import TestClient

from app.agents.orchestrator import Orchestrator
from app.ingest.bootstrap import load_runtime
from app.main import app


@pytest.fixture(scope="session")
def runtime():
    return load_runtime()


@pytest.fixture(scope="session")
def orchestrator(runtime):
    return Orchestrator(runtime)


@pytest.fixture
def client(runtime, orchestrator):
    app.dependency_overrides = {}
    import app.main as main

    main.runtime = runtime
    main.orchestrator = orchestrator
    return TestClient(app)
