import time
import uuid
from fastapi import APIRouter, Request
from src.models import ChatRequest, ChatResponse
from src.llm import generate_response
from src.router import classify_intent, OFF_TOPIC_RESPONSE

router = APIRouter()


@router.post("/api/chat")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Main conversation endpoint. Routes by intent then sends to LLM."""
    store = request.app.state.conversations
    logger = request.app.state.logger

    # Get or create conversation
    conv_id = body.conversation_id or str(uuid.uuid4())
    if conv_id not in store:
        store.create(conv_id)

    # Track selected model
    if body.model:
        store.set_model(conv_id, body.model)

    # Add user message to history
    store.add_message(conv_id, "user", body.message)

    # Route by intent
    intent = classify_intent(body.message)
    logger.log("intent_classified", conversation_id=conv_id, metadata={"intent": intent})

    if intent == "off_topic":
        store.add_message(conv_id, "assistant", OFF_TOPIC_RESPONSE["message"])
        return ChatResponse(
            type=OFF_TOPIC_RESPONSE["type"],
            message=OFF_TOPIC_RESPONSE["message"],
            conversation_id=conv_id,
        )

    # Call LLM with RAG context + intent
    history = store.get_history(conv_id)
    model = store.get_model(conv_id)
    value_index = request.app.state.value_index
    rag_context = value_index.find_relevant_values(body.message)
    t0 = time.time()
    try:
        llm_response = generate_response(history, model_id=model, context=rag_context, intent=intent)
        latency_ms = int((time.time() - t0) * 1000)
        logger.log("chat_response", conversation_id=conv_id, model=model, latency_ms=latency_ms,
                    metadata={"intent": intent})
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        logger.log("chat_error", conversation_id=conv_id, model=model, latency_ms=latency_ms, error=str(e))
        return ChatResponse(
            type="error",
            message=f"Erreur lors de la communication avec le LLM : {str(e)}",
            conversation_id=conv_id,
        )

    # Store pending SQL if confirm_sql
    if llm_response["type"] == "confirm_sql" and llm_response.get("sql"):
        store.set_pending_sql(conv_id, llm_response["sql"])

    # Add assistant response to history
    store.add_message(conv_id, "assistant", llm_response["message"])

    return ChatResponse(
        type=llm_response["type"],
        message=llm_response["message"],
        sql=llm_response.get("sql"),
        reasoning=llm_response.get("reasoning"),
        thinking=llm_response.get("thinking"),
        conversation_id=conv_id,
    )
