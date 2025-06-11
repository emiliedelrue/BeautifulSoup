import pymongo

# Connexion MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.blogdumoderateur
collection = db.articles

# Compter avant
count_before = collection.count_documents({})
print(f"📊 Articles avant suppression: {count_before}")

# Supprimer tous les documents
result = collection.delete_many({})
print(f"🗑️ {result.deleted_count} articles supprimés")

# Vérifier après
count_after = collection.count_documents({})
print(f"📊 Articles après suppression: {count_after}")

if count_after == 0:
    print("✅ Base de données complètement vidée !")
else:
    print("❌ Quelque chose s'est mal passé...")

client.close()
