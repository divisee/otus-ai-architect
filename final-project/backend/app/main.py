from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

from app.agents.orchestrator import Orchestrator
from app.agents.state import GraphState
from app.ingest.bootstrap import Runtime, load_runtime
from app.schemas import ChatRequest, ChatResponse, VoiceRequest
from app.voice.adapter import voice_to_state

runtime: Runtime | None = None
orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runtime, orchestrator
    if runtime is None:
        runtime = load_runtime()
    if orchestrator is None:
        orchestrator = Orchestrator(runtime)
    yield


app = FastAPI(title="Типовой медицинский центр — ассистент", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat", response_model=ChatResponse)
def chat(body: ChatRequest, x_actor_id: str = Header(..., alias="X-Actor-Id")) -> ChatResponse:
    return _respond(_run_text(x_actor_id, body.text, body.session_id, body.channel))


@app.post("/v1/voice", response_model=ChatResponse)
def voice(body: VoiceRequest, x_actor_id: str = Header(..., alias="X-Actor-Id")) -> ChatResponse:
    actor = _actor(x_actor_id)
    state = voice_to_state(orchestrator, actor, body)
    response = _respond(state)
    response.channel = "voice"
    return response


@app.get("/v1/audit/{request_id}")
def audit(request_id: str) -> dict:
    assert runtime is not None
    event = runtime.audit.get(request_id)
    if event is None:
        raise HTTPException(status_code=404, detail="unknown request")
    return event.__dict__


def _run_text(login: str, text: str, session_id: str | None, channel: str) -> GraphState:
    actor = _actor(login)
    assert orchestrator is not None
    return orchestrator.run(actor, text, session_id, channel)


def _actor(login: str):
    assert runtime is not None
    actor = runtime.crm.actor_from_login(login)
    if actor is None:
        raise HTTPException(status_code=401, detail="unknown actor")
    return actor


def _respond(state: GraphState) -> ChatResponse:
    return ChatResponse(
        request_id=state.request_id,
        session_id=state.session.session_id,
        text=state.answer,
        intent=state.intent,
        subject_id=state.subject_id,
        acl_via=state.acl_via,
        acl_denied=state.acl_denied,
        node_ids=[node.id for node in state.nodes],
        chunk_ids=[chunk.chunk_id for chunk in state.chunks],
        pending_confirm=state.pending_confirm,
        escalate=state.escalate,
        channel=state.channel if state.channel in {"text", "voice"} else "text",
    )
