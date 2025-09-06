import os
from pinecone import Pinecone
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Initialize FastAPI app
app = FastAPI()

# Load environment variables from .env file
load_dotenv()

# Load API keys from environment variables
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")  # e.g. "us-east-1-aws"
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")    # e.g. "contentstack-search"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone client instance (new style)
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)

# Connect to the Pinecone index
index = pc.Index(PINECONE_INDEX_NAME)

print("Services Initialized Successfully!")

# Pydantic model for the incoming webhook payload
class WebhookPayload(BaseModel):
    module: str
    event: str
    data: dict

class SearchQuery(BaseModel):
    query: str
    locale: str | None = None # Optional filter
    content_type: str | None = None # Optional filter

@app.post("/index")
async def index_entry(payload: WebhookPayload):
    try:
        # Only process entry publication events
        if payload.module != "entry" or payload.event != "publish":
            return {"status": "success", "message": "Event ignored."}

        # Extract entry data
        entry_data = payload.data.get("entry", {})
        entry_uid = entry_data.get("uid")
        content_type_uid = entry_data.get("content_type", {}).get("uid")
        locale = entry_data.get("locale")

        if not all([entry_uid, content_type_uid, locale]):
            raise HTTPException(status_code=400, detail="Missing essential data in payload.")

        text_to_embed = entry_data.get("title", "")
        if not text_to_embed:
            return {"status": "success", "message": "Entry has no title to index."}

        print(f"Text to embed: '{text_to_embed}'")

        # Generate embedding with OpenAI
        response = client.embeddings.create(
            input=[text_to_embed],
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        print("Embedding created successfully.")

        # Prepare data & upsert to Pinecone
        vector_id = f"{locale}-{content_type_uid}-{entry_uid}"
        metadata = {
            "title": entry_data.get("title", ""),
            "locale": locale,
            "content_type": content_type_uid,
            "text_content": text_to_embed
        }

        # Upsert vector using new API
        index.upsert(vectors=[(vector_id, embedding, metadata)])
        print(f"Vector upserted to Pinecone with ID: {vector_id}")

        return {"status": "success", "vector_id": vector_id}

    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_entries(query: SearchQuery):
    try:
        # 1. Generate an embedding for the incoming search query
        response = client.embeddings.create(
            input=[query.query],
            model="text-embedding-3-small"
        )
        query_embedding = response.data[0].embedding
        print("Query embedding created successfully.")

        # 2. Build a metadata filter for the query
        metadata_filter = {}
        if query.locale:
            metadata_filter["locale"] = query.locale
        if query.content_type:
            metadata_filter["content_type"] = query.content_type

        # 3. Query Pinecone to find the most similar vectors
        search_results = index.query(
            vector=query_embedding,
            top_k=5,  # Return the top 5 results
            include_metadata=True,
            filter=metadata_filter if metadata_filter else None
        )
        print("Pinecone queried successfully.")

        # 4. Format the results into a clean list
        results = []
        for match in search_results['matches']:
            results.append({
                "id": match['id'],
                "score": match['score'],
                "metadata": match['metadata']
            })

        return {"status": "success", "results": results}

    except Exception as e:
        print(f"An error occurred during search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
