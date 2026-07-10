"""
Optional offline job — embed the menu and upsert into Qdrant so the L3 vector
layer and semantic menu search work. Safe to skip (L3 is guarded); run only if
Qdrant + fastembed are available.

    python -m app.build_index
"""
from app.config import config
from app.db import get_db


def main():
    from qdrant_client import QdrantClient, models as qm
    from app.pipeline.embeddings import embed

    db = get_db()
    products = list(db.products.find({"available": True}))
    if not products:
        print("[index] no products — seed first")
        return

    texts = [
        f"{p['name_vi']} | {p.get('category','')} | {p.get('description','')} | {' '.join(p.get('tags',[]))}"
        for p in products
    ]
    vectors = embed(texts)
    dim = len(vectors[0])

    client = QdrantClient(url=config.QDRANT_URL)
    client.recreate_collection(
        config.RAG_COLLECTION,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )
    points = [
        qm.PointStruct(id=i, vector=vectors[i],
                       payload={"sku": products[i]["sku"], "name": products[i]["name_vi"],
                                "category": products[i].get("category")})
        for i in range(len(products))
    ]
    client.upsert(config.RAG_COLLECTION, points=points)
    print(f"[index] upserted {len(points)} menu items → {config.RAG_COLLECTION} (dim={dim})")


if __name__ == "__main__":
    main()
