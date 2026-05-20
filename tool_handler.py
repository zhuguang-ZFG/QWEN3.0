"""tool_handler.py — Tool call forwarding via OpenRouter (DeepSeek R1). Extracted from server.py. Converts Anthropic<->OpenAI tool formats, forwards to DeepSeek, streams responses."""
import json, os, time, uuid, asyncio
import httpx

MODEL_ID = "lima-1.3"
TOOL_BACKEND_URL = "https://openrouter.ai/api/v1/chat/completions"
TOOL_BACKEND_MODEL = "deepseek/deepseek-v4-flash:free"
TOOL_BACKEND_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# No-op stub — override with server._record_request for real stats tracking
def _record_request(query: str, backend: str, intent: str, duration_ms: int,
                    success: bool = True, client_ip: str = "",
                    ide_source: str = "", sys_prompt_preview: str = ""):
    pass

def _convert_tools_anthropic_to_openai(tools: list) -> list:
    """Anthropic tools format -> OpenAI tools format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {"name": tool["name"],
                         "description": tool.get("description", ""),
                         "parameters": tool.get("input_schema", {})}
        })
    return openai_tools

def _convert_messages_anthropic_to_openai(messages: list) -> list:
    """Anthropic messages -> OpenAI messages (handles tool_use and tool_result)."""
    openai_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts, tool_calls, tool_results = [], [], []
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({"id": block["id"], "type": "function",
                        "function": {"name": block["name"],
                                     "arguments": json.dumps(block.get("input", {}))}})
                elif btype == "tool_result":
                    tr_content = block.get("content", "")
                    if isinstance(tr_content, list):
                        tr_content = "\n".join(b.get("text", "") for b in tr_content if b.get("type") == "text")
                    tool_results.append({"role": "tool", "tool_call_id": block.get("tool_use_id", ""),
                                         "content": str(tr_content)})
            if tool_calls:
                openai_msgs.append({"role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                    "tool_calls": tool_calls})
            elif tool_results:
                for tr in tool_results:
                    openai_msgs.append(tr)
            else:
                openai_msgs.append({"role": role, "content": "\n".join(text_parts)})
    return openai_msgs

def _convert_response_openai_to_anthropic(openai_response: dict, model: str) -> dict:
    """OpenAI response -> Anthropic response (handles tool_calls)."""
    choice = openai_response["choices"][0]
    message = choice["message"]
    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            args_str = tc["function"].get("arguments", "{}")
            try: args = json.loads(args_str)
            except (json.JSONDecodeError, TypeError): args = {}
            content.append({"type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": tc["function"]["name"], "input": args})
    usage = openai_response.get("usage", {})
    return {"id": f"msg_{uuid.uuid4().hex[:24]}", "type": "message",
        "role": "assistant", "model": model, "content": content,
        "stop_reason": "tool_use" if message.get("tool_calls") else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": usage.get("prompt_tokens", 0),
                  "output_tokens": usage.get("completion_tokens", 0)}}

async def _tool_call_forward(body: dict) -> dict:
    """Forward tool call request to DeepSeek R1 via OpenRouter."""
    openai_tools = _convert_tools_anthropic_to_openai(body["tools"])
    openai_messages = _convert_messages_anthropic_to_openai(body["messages"])
    if body.get("system"):
        if isinstance(body["system"], str):
            sys_text = body["system"]
        else:
            sys_text = " ".join(b.get("text", "") for b in body["system"] if b.get("type") == "text")
        openai_messages.insert(0, {"role": "system", "content": sys_text})
    payload = {"model": TOOL_BACKEND_MODEL, "messages": openai_messages,
               "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096)}
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(TOOL_BACKEND_URL,
                headers={"Authorization": f"Bearer {TOOL_BACKEND_KEY}",
                         "Content-Type": "application/json"},
                json=payload)
            openai_resp = resp.json()
    except Exception as e:
        return {"id": f"msg_{uuid.uuid4().hex[:24]}", "type": "message",
            "role": "assistant", "model": body.get("model", MODEL_ID),
            "content": [{"type": "text", "text": f"[Tool backend error: {e}]"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}}
    duration_ms = int((time.time() - t0) * 1000)
    _record_request("tool_call", TOOL_BACKEND_MODEL, "tool_use", duration_ms, True)
    if "error" in openai_resp:
        err_msg = openai_resp["error"].get("message", str(openai_resp["error"]))
        return {"id": f"msg_{uuid.uuid4().hex[:24]}", "type": "message",
            "role": "assistant", "model": body.get("model", MODEL_ID),
            "content": [{"type": "text", "text": f"[Tool backend error: {err_msg}]"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}}
    return _convert_response_openai_to_anthropic(openai_resp, body.get("model", MODEL_ID))

async def _tool_call_stream(body: dict):
    """Tool call streaming response (waits for full response, then simulates SSE)."""
    result = await _tool_call_forward(body)
    msg_id, model = result["id"], result["model"]
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':0,'output_tokens':0}}})}\n\n"
    for i, block in enumerate(result.get("content", [])):
        if block["type"] == "text":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}})}\n\n"
            text = block["text"]
            for j in range(0, len(text), 40):
                chunk = text[j:j+40]
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
        elif block["type"] == "tool_use":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':block['id'],'name':block['name']}})}\n\n"
            input_json = json.dumps(block["input"], ensure_ascii=False)
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':input_json}})}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
    stop_reason = result.get("stop_reason", "end_turn")
    usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':stop_reason,'stop_sequence':None},'usage':usage})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"
