import os
from pinecone import Pinecone
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import redis
import requests

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
# PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")  # e.g. "us-east-1-aws"
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")    # e.g. "contentstack-search"


#--- Vercel KV (Redis) Connection ---
KV_URL = os.getenv("KV_URL")
if KV_URL:
    r = redis.from_url(KV_URL)
    print("Connected to Vercel KV (Redis)!")
else:
    r = None
    print("Vercel KV URL not found. Analytics will be disabled.")


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
        # --- Get basic info from the webhook ---
        entry_data = payload.data.get("entry", {})
        entry_uid = entry_data.get("uid")
        content_type_uid = payload.data.get("content_type", {}).get("uid") or entry_data.get("content_type", {}).get("uid")
        locale = entry_data.get("locale")

        if not all([entry_uid, content_type_uid, locale]):
            raise HTTPException(status_code=400, detail="Missing essential data from webhook.")

        vector_id = f"{locale}-{content_type_uid}-{entry_uid}"

        # --- Handle Delete/Unpublish Events ---
        if payload.event in ["unpublish", "delete"]:
            index.delete(ids=[vector_id])
            print(f"Vector deleted from Pinecone with ID: {vector_id}")
            return {"status": "success", "message": f"Vector {vector_id} deleted."}

        # --- Handle Publish/Update Events ---
        if payload.event == "publish":
            # 1. Fetch the full entry from Contentstack Management API
            CS_API_KEY = os.getenv("CONTENTSTACK_API_KEY")
            CS_MANAGEMENT_TOKEN = os.getenv("CONTENTSTACK_MANAGEMENT_TOKEN")
            
            fetch_url = f"https://eu-api.contentstack.com/v3/content_types/{content_type_uid}/entries/{entry_uid}?locale={locale}&branch=main"
            headers = { "api_key": CS_API_KEY, "authorization": CS_MANAGEMENT_TOKEN }
            
            response = requests.get(fetch_url, headers=headers)
            response.raise_for_status()
            full_entry_data = response.json().get("entry", {})

            # 2. Combine multiple fields for a richer embedding
            title = full_entry_data.get("title", "")
            # NOTE: Rich Text content is complex. For now, we'll just check if the key exists.
            # A more advanced version would parse the JSON to extract all the text.
            body = " ".join([p["children"][0]["text"] for p in full_entry_data.get("article_body", {}).get("children", []) if p.get("children")])

            text_to_embed = f"Title: {title}. Content: {body}"
            
            if not text_to_embed.strip():
                return {"status": "success", "message": "No text content found to index."}

            # 3. Generate embedding and upsert to Pinecone
            embedding_response = client.embeddings.create(input=[text_to_embed], model="text-embedding-3-small")
            embedding = embedding_response.data[0].embedding
            
            metadata = { "title": title, "locale": locale, "content_type": content_type_uid, "text_content": text_to_embed }
            index.upsert(vectors=[(vector_id, embedding, metadata)])
            return {"status": "success", "vector_id": vector_id}

        return {"status": "success", "message": f"Event '{payload.event}' ignored."}

    except Exception as e:
        print(f"An error occurred during indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_entries(query: SearchQuery):
    try:
        # Define a minimum similarity score to consider a result relevant
        RELEVANCE_THRESHOLD = 0.30  # 30% similarity

        response = client.embeddings.create(input=[query.query], model="text-embedding-3-small")
        query_embedding = response.data[0].embedding
        
        metadata_filter = {}
        if query.locale:
            metadata_filter["locale"] = query.locale
        if query.content_type:
            metadata_filter["content_type"] = query.content_type

        # Get the initial top 5 results from Pinecone
        search_results = index.query(
            vector=query_embedding,
            top_k=5,
            include_metadata=True,
            filter=metadata_filter if metadata_filter else None
        )

        # NEW: Filter the results based on our threshold
        raw_matches = search_results.get('matches', [])
        relevant_matches = [match for match in raw_matches if match['score'] >= RELEVANCE_THRESHOLD]

        smart_snippet = ""
        # Only generate a snippet if there are RELEVANT results
        if relevant_matches:
            top_result_text = relevant_matches[0]['metadata'].get('text_content', '')
            
            prompt = f"""Based on the following context, provide a concise, one-sentence answer to the user's question. If the context is not relevant, say so.
            Context: "{top_result_text}"
            Question: "{query.query}"
            Answer:"""

            chat_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.0
            )
            smart_snippet = chat_response.choices[0].message.content

        # Format the relevant results for the frontend
        results = []
        for match in relevant_matches:
            results.append({
                "id": match['id'],
                "score": match['score'],
                "metadata": match['metadata']
            })

        # NEW: Log to content gaps only if there are NO RELEVANT results
        if not relevant_matches and r and query.query:
            r.zincrby("top_searches", 1, query.query.lower().strip())
            r.zincrby("content_gaps", 1, query.query.lower().strip())
        elif r and query.query: # Log to top searches if there were results
             r.zincrby("top_searches", 1, query.query.lower().strip())


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
    
@app.get("/analytics")
async def get_analytics():
    if not r:
        return {"top_searches": [], "content_gaps": []}
    
    # Fetch top 10 from 'top_searches' (most searched first)
    top_searches = r.zrevrange("top_searches", 0, 9, withscores=True)
    
    # Fetch top 10 from 'content_gaps' (most searched with no results first)
    content_gaps = r.zrevrange("content_gaps", 0, 9, withscores=True)

    # Format the data for the frontend
    formatted_top = [{"query": item.decode(), "count": int(score)} for item, score in top_searches]
    formatted_gaps = [{"query": item.decode(), "count": int(score)} for item, score in content_gaps]

    return {"top_searches": formatted_top, "content_gaps": formatted_gaps}
