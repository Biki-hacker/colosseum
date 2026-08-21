"""Full local integration test: a real uvicorn server is spawned (same
entrypoint as production), then exercised over REST and WebSocket, plus unit
checks for topics/judge/storage.

The TestClient (in-process ASGI) approach is deliberately avoided: the
scheduler's asyncio.to_thread calls hang under the TestClient portal loop,
while the real uvicorn server completes debates reliably (verified in the
Phase 8 smoke test).
"""

import concurrent.futures
import os
import subprocess
import sys
import tempfile
import time
import uuid

import pytest
import httpx
from websockets.sync.client import connect as ws_connect

import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="colosseum_it_")
PORT = "8011"
BASE = f"http://127.0.0.1:{PORT}"
WS_URL = f"ws://127.0.0.1:{PORT}/ws/debates"

VALID_WINNERS = {"optimist", "pessimist"}


@pytest.fixture(scope="session")
def server():
    env = dict(os.environ)
    env.update(
        {
            "STORAGE_MODE": "local",
            "DATA_DIR": TMP,
            "DEBATE_INTERVAL_SECONDS": "1",
            "TURN_DELAY_SECONDS": "0",
            "PORT": PORT,
            "LLM_API_KEY": "",
            "LLM_BASE_URL": "",
        }
    )


    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", PORT],
        cwd=ROOT,
        env=env,
        stdout=open(os.path.join(TMP, "server_out.log"), "w"),
        stderr=open(os.path.join(TMP, "server_err.log"), "w"),
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                r = httpx.get(f"{BASE}/api/health", timeout=2)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(1.0)
        else:
            pytest.fail("server did not become healthy within 60s")
        yield BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def wait_debates(status=None, timeout=120):
    deadline = time.time() + timeout
    last = []
    while time.time() < deadline:
        last = httpx.get(f"{BASE}/api/debates?limit=20", timeout=5).json()
        if status is None and last:
            return last
        if status and any(d["status"] == status for d in last):
            return last
        time.sleep(1.0)
    pytest.fail(f"no debate with status={status} within {timeout}s; saw {len(last)} debates")


def recv_with_timeout(conn, timeout=30):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(conn.recv)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            pytest.fail(f"timed out after {timeout}s waiting for WS event")


def test_health(server):
    h = httpx.get(f"{server}/api/health", timeout=5).json()
    assert h["status"] == "ok"
    assert h["llm"] == "mock"
    assert h["storage"] == "local"
    assert h["interval_s"] == 1


def test_debate_completes_end_to_end(server):
    debates = wait_debates(status="completed")
    done = [d for d in debates if d["status"] == "completed"]
    assert done, "expected at least one completed debate"
    d = done[0]
    assert d["topic"]
    assert d["winner"] in VALID_WINNERS
    assert d["ended_at"]
    detail = httpx.get(f"{server}/api/debates/{d['id']}", timeout=5).json()
    assert detail["id"] == d["id"]
    turns = detail["turns"]
    assert len(turns) >= 1
    assert turns[0]["speaker"] == "optimist"
    speakers = [t["speaker"] for t in turns]
    for i, t in enumerate(turns):
        assert t["speaker"] in ("optimist", "pessimist")
        assert isinstance(t["text"], str) and t["text"]
        assert t["position"] == i
        assert speakers[i] == ("optimist" if i % 2 == 0 else "pessimist")


def test_ws_streams_full_debate(server):
    seen = {"recent": False, "debate_started": False, "turn": 0, "debate_completed": False}
    with ws_connect(WS_URL, open_timeout=10) as conn:
        deadline = time.time() + 150
        while time.time() < deadline and not seen["debate_completed"]:
            ev = json.loads(recv_with_timeout(conn))
            t = ev["type"]
            if t == "recent":
                seen["recent"] = True
                assert isinstance(ev["debates"], list)
            elif t == "debate_started":
                seen["debate_started"] = True
                assert ev["topic"]
            elif t == "turn":
                seen["turn"] += 1
                assert ev["speaker"] in ("optimist", "pessimist")
                assert isinstance(ev["text"], str)
            elif t == "debate_completed":
                seen["debate_completed"] = True
                assert ev["winner"] in VALID_WINNERS
                assert 1 <= ev["optimist_score"] <= 10
                assert 1 <= ev["pessimist_score"] <= 10
            elif t == "debate_failed":
                pytest.fail(f"debate failed: {ev.get('error')}")
    assert seen["recent"], "expected 'recent' snapshot on connect"
    assert seen["debate_started"], "expected debate_started event"
    assert seen["turn"] >= 2, f"expected >=2 turns, saw {seen['turn']}"


def test_unknown_debate_404(server):
    r = httpx.get(f"{server}/api/debates/{uuid.uuid4()}", timeout=5)
    assert r.status_code == 404


def test_topic_provider_mock():
    sys.path.insert(0, ROOT)
    from app.llm import LLMClient
    from app.topics import TopicProvider

    tp = TopicProvider(LLMClient(mock=True))
    for _ in range(5):
        topic = tp.next()
        assert topic, "expected a topic"
        assert 3 <= len(topic) <= 120


def test_heuristic_judge():
    sys.path.insert(0, ROOT)
    from app.judge import heuristic_judge

    lean_text = " ".join(
        ["opportunity", "hope", "growth", "positive", "better", "together", "learn", "good", "love", "possibility",
         "future", "encourage", "strength", "solution", "confidence", "believe", "wonderful", "excited", "bright",
         "gain", "build", "change"] * 20
    )
    pes_text = "risk danger fail harm worse mistake"
    assert heuristic_judge([("optimist", lean_text)] + [("pessimist", pes_text)])["winner"] == "optimist"
    assert heuristic_judge([("optimist", "good good")] + [("pessimist", "risk risk")])["winner"] in ("optimist", "pessimist")



def test_llm_mock_chat_schema():
    sys.path.insert(0, ROOT)
    from app.llm import LLMClient

    c = LLMClient(mock=True)
    assert c.mock
    out = c.chat("sys", "user", json_schema={"type": "object", "properties": {"a": {"type": "string"}}})
    assert isinstance(out, dict) and "a" in out


def test_localstorage_cleanup():
    sys.path.insert(0, ROOT)
    from app.storage import LocalStorage

    data = tempfile.mkdtemp(prefix="colosseum_cleanup_")
    s = LocalStorage(data)
    old_id = s.create_debate("old topic")
    path = os.path.join(data, "debates", f"{old_id}.json")
    rec = json.load(open(path, encoding="utf-8"))
    rec["created_at"] = "2020-01-01T00:00:00+00:00"
    json.dump(rec, open(path, "w", encoding="utf-8"))
    s.create_debate("new topic")
    assert s.delete_older_than(48) == 1
    assert s.get_debate(old_id) is None