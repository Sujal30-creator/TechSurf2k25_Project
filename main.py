import os
from pinecone import Pinecone
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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
pc = Pinecone(api_key=PINECONE_API_KEY)

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

class SimilarityQuery(BaseModel):
    id: str

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

# main.py

@app.post("/search")
async def search_entries(query: SearchQuery):
    try:
        # --- (Steps 1-3 are the same as before) ---
        response = client.embeddings.create(input=[query.query], model="text-embedding-3-small")
        query_embedding = response.data[0].embedding
        
        metadata_filter = {}
        if query.locale:
            metadata_filter["locale"] = query.locale
        if query.content_type:
            metadata_filter["content_type"] = query.content_type

        search_results = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True,
            filter=metadata_filter if metadata_filter else None
        )

        # --- 4. (NEW) GENERATE SMART SNIPPET ---
        smart_snippet = ""
        if search_results['matches']:
            # Get the text from the top search result
            top_result_text = search_results['matches'][0]['metadata'].get('text_content', '')
            
            # Create a prompt for the LLM
            prompt = f"""Based on the following context, provide a concise, one-sentence answer to the user's question. If the context is not relevant, say so.
            Context: "{top_result_text}"
            Question: "{query.query}"
            Answer:"""

            # Call the Chat Completions API
            chat_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50, # Limit the response length
                temperature=0.0 # Make the response deterministic
            )
            smart_snippet = chat_response.choices[0].message.content

        # --- 5. FORMAT THE RESPONSE (Now including the snippet) ---
        results = []
        for match in search_results['matches']:
            results.append({
                "id": match['id'],
                "score": match['score'],
                "metadata": match['metadata']
            })

        return {"status": "success", "smart_snippet": smart_snippet, "results": results}

    except Exception as e:
        print(f"An error occurred during search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/find_similar")
async def find_similar_entries(query: SimilarityQuery):
    try:
        # 1. Fetch the vector for the given ID from Pinecone
        fetch_response = index.fetch(ids=[query.id])
        # New, corrected line
        source_vector = fetch_response.vectors[query.id].values

        # 2. Query Pinecone using the fetched vector
        search_results = index.query(
            vector=source_vector,
            top_k=6,  # Get 6 results, as the original will be one of them
            include_metadata=True
        )

        # 3. Format results, skipping the original document itself
        results = []
        for match in search_results['matches']:
            if match['id'] != query.id: # Filter out the source document
                results.append({
                    "id": match['id'],
                    "score": match['score'],
                    "metadata": match['metadata']
                })

        # Return the top 5 results
        return {"status": "success", "results": results[:5]}

    except Exception as e:
        print(f"An error occurred during similarity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
