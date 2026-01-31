from sentence_transformers import SentenceTransformer
import pandas as pd
import faiss


MODEL_NAME = "all-MiniLM-L6-v2"
model_embedding = SentenceTransformer(MODEL_NAME)


def build_faiss_index(texts: [str], show: bool=True, batch_size: int=64):
    embeddings = model_embedding.encode(texts, batch_size=batch_size, show_progress_bar=show, normalize_embeddings=True)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    return index


def retrieve_index(dataframe: pd.DataFrame, query: str, index, k: int=10) -> pd.DataFrame:
    query_embbeding = model_embedding.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(query_embbeding, k)

    results = dataframe.iloc[indices[0]].copy()
    results["score"] = scores[0]

    return results.sort_values("score", ascending=False)
