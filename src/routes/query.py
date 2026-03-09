import time
from fastapi import APIRouter, Request, HTTPException
from src.models import ExecuteRequest, ChatResponse
from src.database import execute_query, validate_sql, check_expensive_query
from src.llm import explain_results, fix_sql, fix_empty_results

router = APIRouter()

MAX_SQL_RETRIES = 2


@router.post("/api/execute")
async def execute(request: Request, body: ExecuteRequest) -> ChatResponse:
    """Execute a confirmed SQL query and return results with summary."""
    store = request.app.state.conversations
    db = request.app.state.db
    cache = request.app.state.cache
    logger = request.app.state.logger

    conv_id = body.conversation_id
    if conv_id not in store:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")

    # Check for expensive query patterns (unless force=True)
    if not body.force:
        warnings = check_expensive_query(body.sql)
        if warnings:
            return ChatResponse(
                type="warning",
                message="Attention, cette requête pourrait être coûteuse.",
                sql=body.sql,
                warnings=warnings,
                conversation_id=conv_id,
            )

    # Validate and execute with self-healing retry
    model = store.get_model(conv_id)
    current_sql = body.sql
    corrections: list[dict] = []
    results: dict = {}

    t0 = time.time()
    for attempt in range(MAX_SQL_RETRIES + 1):
        try:
            validate_sql(current_sql)
            results = execute_query(db, current_sql, cache=cache)
            latency_ms = int((time.time() - t0) * 1000)
            logger.log("sql_execute", conversation_id=conv_id, sql=current_sql, latency_ms=latency_ms)
            break
        except (ValueError, Exception) as e:
            error_msg = str(e)
            logger.log("sql_error", conversation_id=conv_id, sql=current_sql, error=error_msg)

            if attempt < MAX_SQL_RETRIES:
                # Try to fix the SQL with LLM
                try:
                    fix_response = fix_sql(current_sql, error_msg, model_id=model)
                    if fix_response.get("sql"):
                        corrections.append({"sql": current_sql, "error": error_msg})
                        current_sql = fix_response["sql"]
                        continue
                except Exception:
                    pass

            # All retries exhausted or fix failed
            return ChatResponse(
                type="error",
                message=f"Erreur SQL : {error_msg}",
                corrections=corrections if corrections else None,
                conversation_id=conv_id,
            )

    # Handle empty results: ask LLM to relax filters
    if results and results["total_count"] == 0 and not body.force:
        try:
            # Retrieve original user question from conversation history
            history = store.get_history(conv_id)
            user_question = ""
            for msg in reversed(history):
                if msg.get("role") == "user":
                    user_question = msg.get("content", "")
                    break
            if user_question:
                fix_response = fix_empty_results(current_sql, user_question, model_id=model)
                if fix_response.get("sql") and fix_response["sql"] != current_sql:
                    corrections.append({"sql": current_sql, "error": "0 résultats — filtres relâchés"})
                    try:
                        validate_sql(fix_response["sql"])
                        new_results = execute_query(db, fix_response["sql"], cache=cache)
                        if new_results["total_count"] > 0:
                            current_sql = fix_response["sql"]
                            results = new_results
                            logger.log("empty_result_fix", conversation_id=conv_id, sql=current_sql)
                    except Exception:
                        pass  # Keep original empty results
        except Exception:
            pass  # Keep original empty results

    # Store results and SQL for export
    store.set_last_results(conv_id, results)
    store.set_pending_sql(conv_id, current_sql)

    # Generate summary
    try:
        summary = explain_results(current_sql, results, model_id=model)
    except Exception:
        summary = f"{results['total_count']} résultat(s) trouvé(s)."

    # Add to history
    store.add_message(conv_id, "assistant", f"Résultats : {summary}")

    return ChatResponse(
        type="results",
        message=summary,
        sql=current_sql,
        results=results,
        corrections=corrections if corrections else None,
        conversation_id=conv_id,
    )
