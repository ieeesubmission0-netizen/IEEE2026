import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import uuid
import os

class ChromaDBManager:
    def __init__(self, persist_directory: str = "./chroma_data", embedding_model: str = "all-MiniLM-L6-v2"):
        os.makedirs(persist_directory, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
        self.collection = self.client.get_or_create_collection(
            name="tosca_requests",
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def _count(self) -> int:
        """Retourne le nombre de documents dans la collection."""
        return self.collection.count()
    
    def store_request(self, user_request: str, reformulated_request: str):
        """Store user request + FINAL reformulated request in the KB"""
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        self.collection.add(
            ids=[doc_id],
            documents=[user_request],
            metadatas=[{
                "timestamp": timestamp,
                "user_request": user_request,
                "reformulated_request": reformulated_request
            }]
        )
        
        print(f"[KB] Collection size après ajout: {self._count()}")
        return doc_id
    
    def query_all(self):
        """Récupérer TOUS les documents stockés"""
        results = self.collection.get()
        return results

    def search(self, query: str, n_results: int = 4):
        """
        Rechercher des requêtes similaires dans la KB.
        Retourne les métadonnées structurées.
        """
        total = self._count()
        print(f"[KB] search() — documents dans la collection: {total}, n_results demandé: {n_results}")

        if total == 0:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        # ✅ ChromaDB lève une exception si n_results > nombre de documents
        effective_n = min(n_results, total)
        if effective_n < n_results:
            print(f"[KB] ⚠️ n_results réduit à {effective_n} (seulement {total} doc(s) disponible(s))")

        results = self.collection.query(
            query_texts=[query],
            n_results=effective_n,
            include=["documents", "metadatas", "distances"]
        )
        
        if results and results.get("metadatas"):
            return {
                "ids": results.get("ids", []),
                "documents": results.get("documents", []),
                "metadatas": results.get("metadatas", []),
                "distances": results.get("distances", []),
            }
        
        return {"ids": [], "documents": [], "metadatas": [], "distances": []}
    
    def get_formatted_examples(self, query: str, n_examples: int = 4):
        """
        Retourne les exemples dans un format prêt pour le few-shot.
        """
        results = self.search(query, n_results=n_examples)
        examples = []
        
        raw_metadatas = results.get("metadatas", [])
        
        # ✅ ChromaDB query() retourne toujours une liste de listes :
        # metadatas = [[meta1, meta2, meta3, meta4]]  ← une entrée par query_text
        # L'ancien code faisait `for metadata in raw_metadatas` ce qui itérait
        # sur la liste externe (1 élément) au lieu des N métadonnées internes.
        if raw_metadatas and isinstance(raw_metadatas[0], list):
            flat_metadatas = raw_metadatas[0]   # ← liste des N métadonnées
        else:
            flat_metadatas = raw_metadatas       # fallback si déjà plat
        
        print(f"[KB] {len(flat_metadatas)} métadonnée(s) après aplatissement")

        for metadata in flat_metadatas:
            if isinstance(metadata, dict):
                example = {
                    "request": metadata.get("user_request", ""),
                    "reformulated_request": metadata.get("reformulated_request", "")
                }
                if example["request"] and example["reformulated_request"]:
                    examples.append(example)
        
        print(f"[KB] {len(examples)} exemple(s) valide(s) retourné(s) pour le few-shot")
        return examples
    
    def delete_by_id(self, doc_id: str):
        """Supprimer un document par ID"""
        self.collection.delete(ids=[doc_id])
    
    def clear_collection(self):
        """Vider toute la collection (utile pour les tests)"""
        all_docs = self.collection.get()
        if all_docs and all_docs.get("ids"):
            self.collection.delete(ids=all_docs["ids"])