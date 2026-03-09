from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


@router.get("/api/conversations")
async def list_conversations(request: Request):
    """List all conversations, most recent first."""
    store = request.app.state.conversations
    return store.list_all()


@router.get("/api/conversations/{conv_id}")
async def get_conversation(request: Request, conv_id: str):
    """Get a full conversation with messages."""
    store = request.app.state.conversations
    conv = store.get(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return {"id": conv_id, **conv}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(request: Request, conv_id: str):
    """Delete a conversation and its messages."""
    store = request.app.state.conversations
    if conv_id not in store:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    store.delete(conv_id)
    return {"status": "deleted"}
