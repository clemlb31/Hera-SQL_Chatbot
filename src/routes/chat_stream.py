import json
import time
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from src.models import ChatRequest
from src.llm import get_provider, _get_system_prompt, parse_llm_response, load_intent_prompt
from src.router import classify_intent, OFF_TOPIC_RESPONSE

router = APIRouter()


@router.post("/api/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """Streaming conversation endpoint. Routes by intent then streams SSE tokens."""
    store = request.app.state.conversations
    logger = request.app.state.logger
    value_index = request.app.state.value_index

    # Get or create conversation
    conv_id = body.conversation_id or str(uuid.uuid4())
    if conv_id not in store:
        store.create(conv_id)

    if body.model:
        store.set_model(conv_id, body.model)

    store.add_message(conv_id, "user", body.message)

    # Route by intent
    intent = classify_intent(body.message)
    logger.log("intent_classified", conversation_id=conv_id, metadata={"intent": intent})

    # Off-topic: return immediately without calling the LLM
    if intent == "off_topic":
        store.add_message(conv_id, "assistant", OFF_TOPIC_RESPONSE["message"])

        def off_topic_generator():
            yield f"data: {json.dumps({'type': 'init', 'conversation_id': conv_id})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'thinking': '', 'content': OFF_TOPIC_RESPONSE['message']})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'parsed': OFF_TOPIC_RESPONSE, 'conversation_id': conv_id})}\n\n"

        return StreamingResponse(off_topic_generator(), media_type="text/event-stream")

    history = store.get_history(conv_id)
    model = store.get_model(conv_id)
    rag_context = value_index.find_relevant_values(body.message)

    provider = get_provider(model)
    system_prompt = _get_system_prompt()
    # Append intent-specific instructions
    intent_prompt = load_intent_prompt(intent)
    if intent_prompt:
        system_prompt = system_prompt + "\n\n" + intent_prompt
    if rag_context:
        system_prompt = system_prompt + "\n\n" + rag_context

    def event_generator():
        accumulated_thinking = ""
        accumulated_content = ""
        t0 = time.time()

        # Send conversation_id immediately
        yield f"data: {json.dumps({'type': 'init', 'conversation_id': conv_id})}\n\n"

        try:
            for chunk in provider.chat_stream(system_prompt, history):
                thinking_delta = chunk.get("thinking", "")
                content_delta = chunk.get("content", "")

                if thinking_delta:
                    accumulated_thinking += thinking_delta
                if content_delta:
                    accumulated_content += content_delta

                yield f"data: {json.dumps({'type': 'token', 'thinking': thinking_delta, 'content': content_delta})}\n\n"

            # Build full text for parsing
            full_text = ""
            if accumulated_thinking:
                full_text += f"<think>{accumulated_thinking}</think>\n"
            full_text += accumulated_content

            parsed = parse_llm_response(full_text)

            # Store pending SQL
            if parsed["type"] == "confirm_sql" and parsed.get("sql"):
                store.set_pending_sql(conv_id, parsed["sql"])

            # Store assistant message
            store.add_message(conv_id, "assistant", parsed["message"])

            latency_ms = int((time.time() - t0) * 1000)
            logger.log("chat_stream_response", conversation_id=conv_id, model=model, latency_ms=latency_ms)

            yield f"data: {json.dumps({'type': 'done', 'parsed': parsed, 'conversation_id': conv_id})}\n\n"

        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            logger.log("chat_stream_error", conversation_id=conv_id, model=model, latency_ms=latency_ms, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
