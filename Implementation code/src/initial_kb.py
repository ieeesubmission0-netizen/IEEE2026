from kb import ChromaDBManager
from datetime import datetime
import uuid

# Initialiser Chroma
chroma = ChromaDBManager()

# 1️⃣ Vider la collection existante
chroma.clear_collection()
print("✅ Collection vidée")

# 2️⃣ Définir les 4 exemples
examples = [
    {
        "user_request": "I want a Java web application in which the backend stores and manages data, while the frontend handles user requests and delivers responses through a main interface. The frontend and backend should be deployed in separate environments.",
        "reformulated_request": "I want to develop a web application that runs on the Java Runtime Environment since it is a Java-based application. The data should be stored in a PostgreSQL database. The frontend will use React, and the backend will use Spring Boot. The frontend and backend should be deployed on separate virtual machines."
    },
    {
        "user_request": "I want a web application; the traffic is evenly distributed across servers and supports seamless connectivity",
        "reformulated_request": "I want a web application which runs on a virtual machine. A load balancer routes traffic to the application , which is connected to a network."
    },
    {
        "user_request": "I want a static website. For that, I need Nginx to serve the site, a storage space to store my files, and a virtual machine with ample RAM, 3 CPUs, and an appropriate operating system.",
        "reformulated_request": "I want a static website. For that, I need Nginx to serve the site, block storage to store my files, and a virtual machine with 20 GB of RAM, 3 CPUs, and a Linux operating system."
    },
    {
        "user_request": "I want to deploy an application with a JavaScript frontend for the user interface, a Node.js backend to handle business logic and APIs, Elasticsearch for advanced search and analytics, and object storage for managing and storing files and other data efficiently",
        "reformulated_request": "I want to build an application with a React-based JavaScript frontend hosted on a virtual machine, along with a Node.js backend to handle business logic and APIs. The application will connect to Elasticsearch for advanced search and analytics, and will rely on object storage for efficiently managing and storing files and other data. Both Elasticsearch and the object storage will be deployed on the Node.js server, which is also hosted on the virtual machine."
    }
]

# 3️⃣ Ajouter chaque exemple dans Chroma
for ex in examples:
    chroma.store_request(ex["user_request"], ex["reformulated_request"])

print(f"✅ {len(examples)} exemples ajoutés à la KB")

# 4️⃣ Vérifier le contenu
all_docs = chroma.query_all()
print(f"📋 Total documents dans la KB après remplissage: {len(all_docs['ids'])}")
for i, doc_id in enumerate(all_docs['ids'], 1):
    print(f"{i}. ID: {doc_id}")
