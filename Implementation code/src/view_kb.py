"""
Script pour visualiser le contenu de la KB Chroma
"""

from kb import ChromaDBManager
import json

# Initialiser Chroma
chroma = ChromaDBManager()

# ==================== SOLUTION 1: Afficher TOUS les documents ====================
print("=" * 80)
print("📋 TOUS LES DOCUMENTS STOCKÉS")
print("=" * 80)

all_docs = chroma.query_all()

if all_docs['ids']:
    print(f"\n✅ Total: {len(all_docs['ids'])} document(s)\n")
    
    for i, doc_id in enumerate(all_docs['ids'], 1):
        metadata = all_docs['metadatas'][i-1]
        
        print(f"\n{'=' * 80}")
        print(f"📌 Document {i}/{len(all_docs['ids'])}")
        print(f"{'=' * 80}")
        print(f"ID: {doc_id}")
        print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
        print(f"\n👤 User Request:")
        print(f"   {metadata.get('user_request', 'N/A')}")
        print(f"\n✏️  Reformulated Request:")
        print(f"   {metadata.get('reformulated_request', 'N/A')}")
        print()
else:
    print("❌ Aucun document trouvé dans la KB")

# ==================== SOLUTION 2: Recherche par similarité ====================
print("\n" + "=" * 80)
print("🔍 RECHERCHE PAR SIMILARITÉ (Exemple)")
print("=" * 80)

query = "deploy application"  # À modifier selon votre besoin
results = chroma.search(query, n_results=3)

if results['ids'][0]:
    print(f"\nRecherche: '{query}'")
    print(f"Résultats trouvés: {len(results['ids'][0])}\n")
    
    for i, doc_id in enumerate(results['ids'][0], 1):
        metadata = results['metadatas'][0][i-1]
        distance = results['distances'][0][i-1] if 'distances' in results else 'N/A'
        
        print(f"{i}. [{distance}] {metadata.get('user_request', 'N/A')}")
else:
    print("❌ Aucun résultat trouvé")

# ==================== SOLUTION 3: Export JSON ====================
print("\n" + "=" * 80)
print("💾 EXPORT EN JSON")
print("=" * 80)

all_docs = chroma.query_all()
export_data = []

for i, doc_id in enumerate(all_docs['ids']):
    export_data.append({
        'id': doc_id,
        'metadata': all_docs['metadatas'][i]
    })

with open('kb_backup.json', 'w', encoding='utf-8') as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2)

print(f"✅ Exported to 'kb_backup.json' ({len(export_data)} documents)")