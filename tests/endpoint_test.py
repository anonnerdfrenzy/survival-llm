"""An OpenAI-compatible server of the person's own, instead of Ollama: endpoint.py, and core.py handing it a whole
conversation. A real HTTP server on this computer answers the way such servers do (streamed deltas, tool calls in
pieces, usage at the end), so the test covers the bytes on the wire, not a stand-in for them.

No Ollama, no model, no library on disk: a fake library and a server that replays what each round should say.

Usage: .venv/bin/python tests/endpoint_test.py"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import endpoint  # noqa: E402

FAILS = []
REQUESTS = []      # every request body the server got, in order
REPLIES = []       # what to answer each POST with, in order: (content type, chunks or a JSON body)


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


def sse(*chunks):
    """An answer streamed the way OpenAI-compatible servers stream it."""
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]
    return "text/event-stream", "".join(lines).encode()


def delta(**part):
    return {"choices": [{"index": 0, "delta": part, "finish_reason": None}]}


def tool_call(index, name=None, arguments=None, call_id=None):
    piece = {"index": index}
    if call_id:
        piece["id"] = call_id
    function = {}
    if name:
        function["name"] = name
    if arguments:
        function["arguments"] = arguments
    if function:
        piece["function"] = function
    return delta(tool_calls=[piece])


def finish(reason="stop", completion_tokens=7):
    return [{"choices": [{"index": 0, "delta": {}, "finish_reason": reason}],
             "usage": {"prompt_tokens": 100, "completion_tokens": completion_tokens, "total_tokens": 107}}]


def text_reply(answer, completion_tokens=7):
    """The answer in a few deltas, as a model writes it."""
    steps = [answer[i:i + 11] for i in range(0, len(answer), 11)]
    return sse(*[delta(content=step) for step in steps], *finish("stop", completion_tokens))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet: the test prints its own lines
        pass

    def _send(self, ctype, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/models"):
            return self._send("application/json", json.dumps({"data": [
                {"id": "qwen3.5-9b-4bit", "object": "model"},
                {"id": "granite-4.2-8b-4bit", "object": "model"}]}).encode())
        self._send("application/json", b"{}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        REQUESTS.append({"path": self.path, "body": json.loads(self.rfile.read(length) or b"{}"),
                         "auth": self.headers.get("Authorization")})
        reply = REPLIES.pop(0)
        if len(reply) == 3:  # (status, content type, body)
            status, ctype, body = reply
        else:
            status, (ctype, body) = 200, reply
        self._send(ctype, body, status)


SERVER = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
PORT = SERVER.server_address[1]

FOLDER = tempfile.mkdtemp(prefix="survival-endpoint-test-")
endpoint.set_folder(FOLDER)


class Lib:
    """The library, the way core.py uses it."""
    has_personal = False

    def labels(self):
        return ["Ready.gov", "CDC"]

    def search(self, query, topic="any", limit=8):
        return [{"id": 1403312, "title": "Generator safety", "source": "Ready.gov", "official": True,
                 "snippet": "Never run a generator in a garage."}]

    def read(self, pid, max_chars=5000):
        return {"title": "Generator safety", "source": "Ready.gov", "official": True, "url": "",
                "text": "Never run a generator in a garage, even with the door open.", "next_id": None}


# ---------- nothing is set yet: the app is on Ollama, exactly as before ----------
check("nothing saved: not on", not endpoint.on())
check("clean_url leaves a /v1 address alone", endpoint.clean_url("http://127.0.0.1:8080/v1/") == "http://127.0.0.1:8080/v1",
      endpoint.clean_url("http://127.0.0.1:8080/v1/"))
check("clean_url adds /v1 to a bare address", endpoint.clean_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080/v1",
      endpoint.clean_url("http://127.0.0.1:8080"))
check("clean_url adds http:// when the scheme is left out", endpoint.clean_url("127.0.0.1:8080") == "http://127.0.0.1:8080/v1",
      endpoint.clean_url("127.0.0.1:8080"))
check("clean_url takes a whole chat address", endpoint.clean_url("http://h:9/v1/chat/completions") == "http://h:9/v1",
      endpoint.clean_url("http://h:9/v1/chat/completions"))

# ---------- Test: what the server offers, before anything is saved ----------
names, problem = endpoint.probe(f"http://127.0.0.1:{PORT}", "")
check("probe lists the server's models", names == ["qwen3.5-9b-4bit", "granite-4.2-8b-4bit"] and not problem, (names, problem))
check("probe never saves anything", not endpoint.on() and not os.path.exists(endpoint.settings_path()))

names, problem = endpoint.probe("http://127.0.0.1:9", "")  # nothing listens there
check("probe explains a server that isn't there", names == [] and "nothing is listening" in problem, problem)

# ---------- Save, with a key, and ask a question ----------
endpoint.save(f"http://127.0.0.1:{PORT}", "qwen3.5-9b-4bit", "sk-test")
check("saved: on, with its address, model and key",
      endpoint.on() and endpoint.url() == f"http://127.0.0.1:{PORT}/v1" and endpoint.model() == "qwen3.5-9b-4bit"
      and endpoint.key() == "sk-test", endpoint.config())
check("capabilities count on tool calls", endpoint.capabilities("anything") == {"tools"},
      endpoint.capabilities("anything"))
check("installed_models() asks the server", core.installed_models() == ["qwen3.5-9b-4bit", "granite-4.2-8b-4bit"],
      core.installed_models())

ANSWER = "No. Never run a generator in a garage.\n\nSources: Generator safety (Ready.gov)"
REPLIES[:] = [
    sse(delta(role="assistant"), delta(content="Let me look. "),
        tool_call(0, name="search_library", arguments='{"query": "generator'),
        tool_call(0, arguments=' garage"}', call_id="call_a"), *finish("tool_calls", 9)),
    sse(delta(reasoning_content="It found the Ready.gov page. "),
        tool_call(0, name="read_article", arguments='{"id": 1403312}', call_id="call_b"), *finish("tool_calls", 11)),
    sse(delta(reasoning_content="Now answer from it. "), *[delta(content=step) for step in [ANSWER[i:i + 9]
                                                                                          for i in range(0, len(ANSWER), 9)]],
        *finish("stop", 40)),
]
REQUESTS.clear()
messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "Can I run a generator in the garage?"}]
events = list(core.chat_events("qwen3.5-9b-4bit", Lib(), messages, reasoning="off"))
kinds = [e["type"] for e in events if e["type"] not in ("tick", "token")]
check("one turn: search, thinking, read, thinking, done",
      kinds == ["search", "thinking", "read", "thinking", "done"], kinds)
check("the search ran from the tool call the model streamed in pieces",
      next(e for e in events if e["type"] == "search")["query"] == "generator garage",
      next(e for e in events if e["type"] == "search"))
done = next(e for e in events if e["type"] == "done")
check("the answer is the model's text", done["answer"].startswith("No. Never run a generator"), done["answer"])
check("the app adds its own Sources line", done["answer"].endswith("Sources: Generator safety (Ready.gov)"), done["answer"])
check("its reasoning came through, and isn't in the answer",
      [e["text"] for e in events if e["type"] == "thinking"] == ["It found the Ready.gov page. ", "Now answer from it. "]
      and "Ready.gov page" not in done["answer"], [e.get("text") for e in events if e["type"] == "thinking"])
check("the server's usage became the token count", done["tokens"] == 9 + 11 + 40, done["tokens"])

# What went to the server: OpenAI's shape, with the app's chat in it
body = REQUESTS[0]["body"]
check("the key went as a bearer token", REQUESTS[0]["auth"] == "Bearer sk-test", REQUESTS[0]["auth"])
check("the model, stream, and a temperature were asked for",
      body["model"] == "qwen3.5-9b-4bit" and body["stream"] is True and "temperature" in body, body)
check("the library tools went along", [t["function"]["name"] for t in body.get("tools", [])]
      == ["search_library", "read_article", "show_article"], body.get("tools"))
check("Ollama-only options stayed behind", "options" not in body and "num_ctx" not in body and "think" not in body, body)
check("a length limit becomes max_tokens", body.get("max_tokens", 0) > 0, body.get("max_tokens"))
second = REQUESTS[1]["body"]["messages"]
assistant = [m for m in second if m["role"] == "assistant"][-1]
check("the model's tool call went back with an id", assistant["tool_calls"][0]["id"] == "call_a",
      assistant.get("tool_calls"))
check("its arguments are JSON text, as OpenAI sends them",
      json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"query": "generator garage"},
      assistant["tool_calls"][0]["function"]["arguments"])
result = [m for m in second if m["role"] == "tool"][-1]
check("the tool's result answers that id", result["tool_call_id"] == "call_a" and "Generator safety" in result["content"],
      result)
check("no tool markup reached the person", "<tool_call" not in done["answer"] and "<function" not in done["answer"],
      done["answer"])

# ---------- A server that answers without streaming, and one that calls nobody ----------
REPLIES[:] = [("application/json", json.dumps({"choices": [{"index": 0, "message": {
    "role": "assistant", "content": "Boil it for one minute."}, "finish_reason": "stop"}],
    "usage": {"completion_tokens": 6}}).encode())]
events = list(core.chat_events("qwen3.5-9b-4bit", None, [{"role": "system", "content": "s"},
                                                        {"role": "user", "content": "Water?"}]))
check("an answer in one piece works too", next(e for e in events if e["type"] == "done")["answer"].startswith("Boil it"),
      events)

# ---------- A server that refuses stream_options: asked again without it ----------
REPLIES[:] = [(400, "application/json", b'{"error": {"message": "unknown field: stream_options"}}'),
              text_reply("Plain stream worked.")]
events = list(core.chat_events("qwen3.5-9b-4bit", None, [{"role": "system", "content": "s"},
                                                        {"role": "user", "content": "Water?"}]))
check("a server that refuses stream_options still answers",
      next(e for e in events if e["type"] == "done")["answer"].startswith("Plain stream worked"), events)
check("the second try left stream_options out", "stream_options" not in REQUESTS[-1]["body"], REQUESTS[-1]["body"])
check("and kept the question", REQUESTS[-1]["body"]["messages"][-1]["content"] == "Water?", REQUESTS[-1]["body"])

# ---------- Stop: closing the generator closes the request ----------
REPLIES[:] = [sse(delta(content="One "), delta(content="two "), delta(content="three "), *finish())]
stream = core._stream("qwen3.5-9b-4bit", [{"role": "user", "content": "Hi"}], None, False, {"temperature": 0.7})
next(stream)
stream.close()  # what the app does when Stop is pressed
check("closing the stream is enough", True)

# ---------- Back to Ollama: the saved file goes, and nothing follows it ----------
endpoint.forget()
check("forget: off again", not endpoint.on())
check("forget: the file is gone", not os.path.exists(endpoint.settings_path()))
check("no model saved: on only with both an address and a model",
      endpoint.save(f"http://127.0.0.1:{PORT}", "") is None and not endpoint.on())

# A blank key keeps the one saved: the window never shows the key back
endpoint.save(f"http://127.0.0.1:{PORT}", "qwen3.5-9b-4bit", "sk-test")
endpoint.save(f"http://127.0.0.1:{PORT}", "granite-4.2-8b-4bit", "")
check("saving again with no key keeps the saved one", endpoint.key() == "sk-test", endpoint.config())
check("and takes the new model", endpoint.model() == "granite-4.2-8b-4bit", endpoint.config())
endpoint.forget()

SERVER.shutdown()
print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
sys.exit(1 if FAILS else 0)
