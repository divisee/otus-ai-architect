def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_chat_unknown_actor(client):
    response = client.post(
        "/v1/chat",
        headers={"X-Actor-Id": "patient:ghost"},
        json={"text": "привет"},
    )
    assert response.status_code == 401


def test_chat_and_voice_same_policy(client):
    chat = client.post(
        "/v1/chat",
        headers={"X-Actor-Id": "patient:boris"},
        json={"text": "Какое направление у Анны Соколовой?"},
    ).json()
    voice = client.post(
        "/v1/voice",
        headers={"X-Actor-Id": "patient:boris"},
        json={"transcript": "Какое направление у Анны Соколовой?", "speakers": ["SPEAKER_00"]},
    ).json()
    assert chat["acl_denied"] is True
    assert voice["acl_denied"] is True
    assert voice["channel"] == "voice"
    assert "K80.1" not in chat["text"]


def test_audit_endpoint(client):
    payload = client.post(
        "/v1/chat",
        headers={"X-Actor-Id": "patient:anna"},
        json={"text": "Что означает код N28.1 у сына?"},
    ).json()
    audit = client.get(f"/v1/audit/{payload['request_id']}").json()
    assert audit["via"] == "guardian"
    assert audit["acl_denied"] is False
