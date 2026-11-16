"""An OpenAI-compatible model server of the person's own, used instead of Ollama.

Some people already run a model server on their computer: llama.cpp's server, LM Studio, vLLM, Rapid-MLX, KoboldCpp, or
Ollama's own OpenAI-compatible API. Model > Use your own server (in the app) or SURVIVAL_LLM_ENDPOINT points the app
at it. Nothing here goes on the internet: the address is the person's own machine or their own network, and the
library, their files and the AI's notes stay where they are.

stream() yields the same chunks Ollama streams, so core.py runs one conversation for either engine: the same library
lookups, the same Sources line, the same memory step. capabilities() and models() answer the two other questions
core.py and the app ask of Ollama.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

SETTINGS = "endpoint.json"  # in the app's settings folder, beside settings.json
TIMEOUT = 900               # a big model on a slow computer may take minutes
PROBE_TIMEOUT = 15          # Test, in the Model window: long enough for a busy server, short enough to notice
_folder = [None]
_error = [None]             # why the server last didn't answer, for the Model window (None when it did)


def set_folder(path):
    """The app's settings folder (server.py's APP_DIR), so both find the same endpoint.json."""
    _folder[0] = path


def folder():
    """Where that folder is, for a copy run from the source without the app around it."""
    if _folder[0]:
        return _folder[0]
    if os.environ.get("SURVIVAL_LLM_APP_DIR"):
        return os.environ["SURVIVAL_LLM_APP_DIR"]
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Survival LLM")
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Survival LLM")
    return os.path.join(os.path.expanduser("~"), ".survival-llm")


def settings_path():
    return os.path.join(folder(), SETTINGS)


def config():
    """{"url", "key", "model"} as saved, or {}: the person's own server, and the model to ask it for."""
    if os.environ.get("SURVIVAL_LLM_ENDPOINT"):  # a copy run from the source: point it without the window
        url, _, model = os.environ["SURVIVAL_LLM_ENDPOINT"].partition("=")
        return {"url": clean_url(url), "model": model.strip(), "key": os.environ.get("SURVIVAL_LLM_ENDPOINT_KEY", "")}
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def on():
    """Whether answers come from the person's own server rather than from Ollama."""
    saved = config()
    return bool(saved.get("url") and saved.get("model"))


def url():
    return config().get("url") or ""


def model():
    return config().get("model") or ""


def key():
    return config().get("key") or ""


def last_error():
    return _error[0]


def clean_url(text):
    """"http://127.0.0.1:8080" or ".../v1/" -> the address of its OpenAI API. A whole chat address works too."""
    found = str(text or "").strip().rstrip("/")
    found = re.sub(r"/(chat/)?completions$", "", found)
    if found and "://" not in found:  # people write the address without the http://
        found = "http://" + found
    if found and not re.search(r"/v\d+$", found):
        found += "/v1"
    return found


def save(address, model_name, api_key=""):
    """Keep the server and the model to ask it for. A blank key keeps the one already saved."""
    saved = {"url": clean_url(address), "model": str(model_name or "").strip()}
    if api_key:
        saved["key"] = api_key
    elif os.path.exists(settings_path()):
        old = config().get("key")
        if old:
            saved["key"] = old
    os.makedirs(folder(), exist_ok=True)
    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=1)
    try:
        os.chmod(settings_path(), 0o600)  # it may hold a key: only the person reads it
    except OSError:  # Windows, where the file is already theirs alone
        pass
    _error[0] = None


def forget():
    """Back to Ollama."""
    try:
        os.remove(settings_path())
    except OSError:
        pass
    _error[0] = None


def _open(path, body=None, address=None, api_key=None, timeout=TIMEOUT):
    base = clean_url(address) if address is not None else url()
    if not base:
        raise ValueError("no server address")
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    api_key = key() if api_key is None else api_key  # the saved key, unless a caller says otherwise
    if api_key:
        req.add_header("Authorization", "Bearer " + api_key)
    return urllib.request.urlopen(req, timeout=timeout)


def _names(data):
    """The model names in /v1/models, however the server writes them: {"data": [{"id"}]} is the OpenAI one."""
    items = data.get("data")
    if not isinstance(items, list):
        items = data.get("models") if isinstance(data.get("models"), list) else []
    names = []
    for item in items:
        name = item.get("id") or item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def probe(address=None, api_key=None, timeout=PROBE_TIMEOUT):
    """(model names, error) at this server, without saving anything: what Test in the Model window shows."""
    try:
        with _open("/models", address=address, api_key=api_key, timeout=timeout) as resp:
            names = _names(json.load(resp))
    except urllib.error.HTTPError as exc:
        return [], f"The server answered {exc.code}: {_detail(exc) or exc.reason}."
    except ValueError as exc:  # not JSON, or not an address
        return [], f"That address didn't answer like an OpenAI server ({exc})."
    except OSError as exc:  # nothing there, or too slow
        return [], f"Nothing answered at {clean_url(address or url())} ({reason(exc)})."
    if not names:  # it answered, but with nothing to ask
        _error[0] = "it offers no models"
        return [], None
    _error[0] = None
    return names, None


def models():
    """The model names this server offers, or None when it isn't answering (as core.installed_models does)."""
    names, problem = probe(url(), key(), timeout=3)  # the status page asks often: a hung server mustn't hold it
    _error[0] = problem
    return None if problem else names


def capabilities(model_name):
    """What this app can count on: every OpenAI-compatible server takes tool calls. Reasoning is the server's own
    business here (its thinking still streams through to the person)."""
    return {"tools"}


def _detail(exc):
    try:
        body = exc.read().decode("utf-8", "replace")
    except OSError:
        return ""
    try:
        found = json.loads(body)
    except ValueError:
        return body.strip()[:200]
    if isinstance(found, dict):
        error = found.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or "")[:200]
        return str(error or found.get("message") or "")[:200]
    return ""


def reason(exc):
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ConnectionRefusedError) or "refused" in str(reason).lower():
        return "nothing is listening there"
    if "timed out" in str(reason).lower():
        return "it didn't answer in time"
    return str(reason)


def _args(value):
    """A tool call's arguments as the JSON text OpenAI sends them (this app keeps them as a dict)."""
    if isinstance(value, str):
        return value or "{}"
    try:
        return json.dumps(value or {})
    except (TypeError, ValueError):
        return "{}"


def _messages(messages):
    """The chat in OpenAI's shape. A tool result there names the call it answers; this app's chat keeps the Ollama
    shape, where it doesn't, so ids are made here and paired with the results in order."""
    out, pending, count = [], [], 0
    for message in messages:
        role = message.get("role")
        if role == "assistant":
            entry = {"role": "assistant", "content": message.get("content") or ""}
            if message.get("tool_calls"):
                entry["tool_calls"] = []
                for call in message["tool_calls"]:
                    function = call.get("function") or {}
                    count += 1
                    call_id = call.get("id") or f"call_{count}"  # the server's own id, when this app kept it
                    entry["tool_calls"].append({"id": call_id, "type": "function",
                                                "function": {"name": function.get("name") or "",
                                                             "arguments": _args(function.get("arguments"))}})
                    pending.append(call_id)
            out.append(entry)
        elif role == "tool":  # the result of the call before it, in the order it was asked
            if pending:
                call_id = pending.pop(0)
            else:  # its call was trimmed out of a long chat: it still needs an id of its own
                count += 1
                call_id = f"call_{count}"
            out.append({"role": "tool", "tool_call_id": call_id, "content": message.get("content") or ""})
        else:
            out.append({"role": role, "content": message.get("content") or ""})
    return out


def _call(function, call_id=None) -> dict:
    """One tool call the server streamed, in the shape core.py runs (and Ollama's). Its id comes along, so the result
    can answer that exact call in the next request."""
    call = {"function": {"name": function.get("name") or "", "arguments": function.get("arguments") or "{}"}}
    if call_id:
        call["id"] = call_id
    return call


def _done(finish, usage, started) -> dict:
    """Ollama's last chunk, from OpenAI's finish_reason and usage."""
    return {"done": True, "done_reason": "length" if finish == "length" else "stop",
            "eval_count": (usage or {}).get("completion_tokens") or 0,
            "eval_duration": int((time.monotonic() - started) * 1e9)}


def stream(model_name, messages, tools, options):
    """One answer, as Ollama's /api/chat streams it. options are the app's Ollama options; what OpenAI has no place
    for (num_ctx, top_k) is left out, and num_predict becomes max_tokens."""
    body = {"model": model_name, "messages": _messages(messages), "stream": True,
            "temperature": options.get("temperature", 0.7),
            # The token count at the end of an answer, which OpenAI servers only send when asked.
            "stream_options": {"include_usage": True}}
    if options.get("top_p") is not None:
        body["top_p"] = options["top_p"]
    limit = options.get("num_predict", -1)
    if limit and limit > 0:
        body["max_tokens"] = limit
    if tools:
        body["tools"] = tools
    started, resp = time.monotonic(), None
    try:
        try:
            resp = _open("/chat/completions", body)
        except urllib.error.HTTPError as exc:
            if exc.code != 400 or "stream_options" not in body:
                raise
            # A server that doesn't know stream_options refuses the whole request: ask again for a plain stream,
            # without the token count.
            body.pop("stream_options")
            resp = _open("/chat/completions", body)
        if "event-stream" not in (resp.headers.get("Content-Type") or "").lower():
            yield from _whole(resp, started)  # a server that answered in one piece, stream asked for or not
            return
        calls, usage, finish = {}, {}, None
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            usage = chunk.get("usage") or usage
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            finish = choice.get("finish_reason") or finish
            delta = choice.get("delta") or {}
            # Reasoning: vLLM and Rapid-MLX send reasoning_content, some servers send reasoning.
            thought = delta.get("reasoning_content") or delta.get("reasoning")
            part = {"thinking": thought} if thought else {}
            if delta.get("content"):
                part["content"] = delta["content"]
            for piece in delta.get("tool_calls") or []:  # streamed in bits: the name, then the arguments
                slot = calls.setdefault(piece.get("index", 0), {"name": "", "arguments": "", "id": ""})
                slot["id"] = piece.get("id") or slot["id"]
                function = piece.get("function") or {}
                slot["name"] += function.get("name") or ""
                slot["arguments"] += function.get("arguments") or ""
            yield {"message": part}  # an empty one is the app's heartbeat, as from Ollama
        if calls:
            yield {"message": {"content": "", "tool_calls": [_call(calls[i], calls[i]["id"]) for i in sorted(calls)]}}
        yield _done(finish, usage, started)
    finally:
        if resp is not None:
            resp.close()  # Stop closes this generator, which closes the request and stops the server generating


def _whole(resp, started):
    """An answer that came in one piece instead of as a stream."""
    data = json.load(resp)
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    thought = message.get("reasoning_content") or message.get("reasoning")
    if thought:
        yield {"message": {"thinking": thought}}
    calls = [_call(call.get("function") or {}) for call in message.get("tool_calls") or []]
    if calls:
        yield {"message": {"content": message.get("content") or "", "tool_calls": calls}}
    elif message.get("content"):
        yield {"message": {"content": message["content"]}}
    yield _done(choice.get("finish_reason"), data.get("usage"), started)
