#!/usr/bin/env python3

import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8081"


def get(path: str, timeout: int = 10) -> tuple[int, bytes]:
    req = urllib.request.Request(BASE_URL + path)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def post_json(path: str, payload: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)



PULSE_SCHEMA = {
    "type": "object",
    "required": [
        "procedures",
        "signals_used",
        "confidence",
        "escalate",
        "none_needed",
        "rationale_fr",
    ],
    "properties": {
        "procedures": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["code", "urgency"],
                "properties": {
                    "code": {"type": "string"},
                    "urgency": {"enum": ["now", "today", "this_week"]},
                    "inputs": {"type": "object"},
                },
            },
        },
        "signals_used": {"type": "array", "items": {"type": "string"}},
        "confidence": {"enum": ["high", "medium", "low"]},
        "escalate": {"type": "boolean"},
        "none_needed": {"type": "boolean"},
        "rationale_fr": {"type": "string", "maxLength": 400},
    },
}


def pulse_mode_a() -> None:
    payload = {
        "model": "local_executor",
        "temperature": 0,
        "max_tokens": 512,
        "thinking_budget_tokens": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es l'interprète Pulse. "
                    "Réponds uniquement selon le schéma JSON fourni."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Signaux: fatigue=élevée (yellow), sommeil=5h30 (yellow). "
                    "Catalogue actif: recovery_day — récupération; "
                    "sleep_recovery — récupération sommeil. "
                    "Choisis les procédures pertinentes."
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "interpreter_output",
                "strict": True,
                "schema": PULSE_SCHEMA,
            },
        },
    }

    body = post_json("/v1/chat/completions", payload)
    choice = body["choices"][0]
    content = choice["message"].get("content", "")
    reasoning = choice["message"].get("reasoning_content", "")

    assert choice["finish_reason"] == "stop"
    assert reasoning in ("", None)
    parsed = json.loads(content)

    assert set(PULSE_SCHEMA["required"]).issubset(parsed)
    assert parsed["confidence"] in {"high", "medium", "low"}
    assert isinstance(parsed["escalate"], bool)
    assert isinstance(parsed["none_needed"], bool)
    assert len(parsed["rationale_fr"]) <= 400

    print("H3.5_PULSE_MODE_A_SINGLE=PASS")



def pulse_mode_b() -> tuple[bytes, bytes]:
    payload = {
        "model": "local_executor",
        "temperature": 0,
        "max_tokens": 2200,
        "thinking_budget_tokens": 1000,
        "chat_template_kwargs": {"enable_thinking": True},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es l'interprète Pulse. "
                    "Réponds uniquement selon le schéma JSON fourni."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Signaux: fatigue=élevée (yellow), sommeil=5h30 (yellow). "
                    "Catalogue actif: recovery_day — récupération; "
                    "sleep_recovery — récupération sommeil. "
                    "Choisis les procédures pertinentes."
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "interpreter_output",
                "strict": True,
                "schema": PULSE_SCHEMA,
            },
        },
    }

    body = post_json("/v1/chat/completions", payload)
    choice = body["choices"][0]
    msg = choice["message"]
    content = msg.get("content", "")
    reasoning = msg.get("reasoning_content", "")

    assert choice["finish_reason"] == "stop"
    assert content
    assert reasoning

    parsed = json.loads(content)
    assert set(PULSE_SCHEMA["required"]).issubset(parsed)
    assert parsed["confidence"] in {"high", "medium", "low"}
    assert isinstance(parsed["escalate"], bool)
    assert isinstance(parsed["none_needed"], bool)
    assert len(parsed["rationale_fr"]) <= 400

    usage = body.get("usage", {})
    print(
        "H3.5_MODE_B_SINGLE=PASS "
        f"completion_tokens={usage.get('completion_tokens')} "
        f"content_bytes={len(content.encode())} "
        f"reasoning_bytes={len(reasoning.encode())}"
    )

    return content.encode(), reasoning.encode()

WR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "mechanism_fr", "confidence"],
    "properties": {
        "verdict": {
            "type": "string",
            "enum": [
                "direct_cause",
                "favoring_condition",
                "correlation",
                "no_link",
            ],
        },
        "mechanism_fr": {"type": "string", "maxLength": 200},
        "confidence": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
    },
}


def wr_mode_a() -> None:
    payload = {
        "model": "local_executor",
        "temperature": 0,
        "max_tokens": 300,
        "thinking_budget_tokens": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu juges une paire d'événements pour le moteur causal WR. "
                    "Retourne uniquement le verdict structuré demandé."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Événement candidat antérieur : vibration inhabituelle du véhicule "
                    "signalée mais non traitée. "
                    "Événement cible deux jours plus tard : usure asymétrique sévère "
                    "constatée sur le pneu avant droit. "
                    "Juge le lien causal."
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "wr_pair_verdict",
                "strict": True,
                "schema": WR_SCHEMA,
            },
        },
    }

    body = post_json("/v1/chat/completions", payload)
    choice = body["choices"][0]
    msg = choice["message"]
    content = msg.get("content", "")
    reasoning = msg.get("reasoning_content", "")
    obj = json.loads(content)

    assert choice["finish_reason"] == "stop"
    assert reasoning in ("", None)
    assert set(obj) == {"verdict", "mechanism_fr", "confidence"}
    assert obj["verdict"] in {
        "direct_cause",
        "favoring_condition",
        "correlation",
        "no_link",
    }
    assert isinstance(obj["confidence"], int)
    assert 0 <= obj["confidence"] <= 100
    assert len(obj["mechanism_fr"]) <= 200

    print("H3.5_WR_MODE_A_SINGLE=PASS")



def test_mode_b_determinism() -> None:
    results = []

    for run in range(1, 4):
        content, reasoning = pulse_mode_b()
        results.append((content, reasoning))
        print(
            f"H3.6_RUN_{run}: "
            f"content_bytes={len(content)} "
            f"reasoning_bytes={len(reasoning)}"
        )

    content_identical = all(
        result[0] == results[0][0] for result in results[1:]
    )
    reasoning_identical = all(
        result[1] == results[0][1] for result in results[1:]
    )

    print(f"CONTENT_BYTE_IDENTICAL={content_identical}")
    print(f"REASONING_BYTE_IDENTICAL={reasoning_identical}")

    assert content_identical
    assert reasoning_identical

    print("H3.6_DETERMINISM=PASS")


def repeat_test(name: str, test_func, runs: int = 10) -> None:
    for run in range(1, runs + 1):
        test_func()
        print(f"{name}_RUN_{run:02d}=PASS")
    print(f"{name}_RESULTS={runs}/{runs}")

def main() -> None:
    health_status, health_body = get("/health")
    assert health_status == 200, (
        f"/health attendu 200, obtenu {health_status}: "
        f"{health_body.decode(errors='replace')}"
    )
    print("H3.2_HEALTH=PASS")

    metrics_status, metrics_body = get("/metrics")
    assert metrics_status == 200, f"/metrics attendu 200, obtenu {metrics_status}"
    assert metrics_body.strip(), "/metrics est vide"
    print("H3.2_METRICS=PASS")

    test_mode_b_determinism()
    repeat_test("H3.5_PULSE_MODE_A", pulse_mode_a)
    repeat_test("H3.5_WR_MODE_A", wr_mode_a)

    print("LOCAL_EXECUTOR_SMOKE=PASS")


if __name__ == "__main__":
    main()
