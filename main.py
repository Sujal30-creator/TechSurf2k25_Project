import os
from pinecone import Pinecone
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import redis
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
import shutil

# initialize FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#load env variables from .env file
load_dotenv()

# !!--- Load API keys from env variables ---!!
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT") 
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")    
CS_API_KEY = os.getenv("CONTENTSTACK_API_KEY")
CS_MANAGEMENT_TOKEN = os.getenv("CONTENTSTACK_MANAGEMENT_TOKEN")


#--- Vercel KV (Redis) connectn. ---
KV_URL = os.getenv("KV_URL")
if KV_URL:
    r = redis.from_url(KV_URL)
    print("Connected to Vercel KV (Redis)!")
else:
    r = None
    print("Vercel KV URL not found. Analytics will be disabled.")


# initialize openai client!!
client = OpenAI(api_key=OPENAI_API_KEY)

#initialize pinecone client inst. 
pc = Pinecone(api_key=PINECONE_API_KEY)

# connection to the pinecone index!!
index = pc.Index(PINECONE_INDEX_NAME)

print("Services Initialized Successfully!")

# Helper fnx.
def extract_text_from_rte(rte_json):
    texts = []
    def recurse(nodes):
        for node in nodes:
            if node.get("text"):
                texts.append(node["text"])
            if node.get("children"):
                recurse(node["children"])
    if isinstance(rte_json, dict) and rte_json.get("children"):
        recurse(rte_json["children"])
    return " ".join(texts)

# Pydantic model for the incoming webhook payload
class WebhookPayload(BaseModel):
    module: str
    event: str
    data: dict

class SearchQuery(BaseModel):
    query: str
    locale: str | None = None 
    content_type: str | None = None 
    threshold: float | None = 35.0

class SimilarityQuery(BaseModel):
    id: str

class FeedbackPayload(BaseModel):
    result_id: str
    feedback_type: str # like / dislike

class AnalyticsSummary(BaseModel):
    total_searches: int
    content_gaps: int

@app.post("/index")
async def index_entry(payload: WebhookPayload):
    try:
        entry_data = payload.data.get("entry", {})
        entry_uid = entry_data.get("uid")
        locale = entry_data.get("locale")
        
        content_type_uid = entry_data.get("content_type", {}).get("uid")
        if not content_type_uid:
            content_type = payload.data.get("content_type", {})
            if isinstance(content_type, dict):
                 content_type_uid = content_type.get("uid")

        if not all([entry_uid, content_type_uid, locale]):
            raise HTTPException(status_code=400, detail="Missing essential data from webhook.")

        vector_id = f"{locale}-{content_type_uid}-{entry_uid}"

        if payload.event in ["unpublish", "delete"]:
            index.delete(ids=[vector_id])
            print(f"Vector deleted: {vector_id}")
            return {"status": "success", "message": f"Vector {vector_id} deleted."}

        if payload.event == "publish":
            fetch_url = f"https://eu-api.contentstack.com/v3/content_types/{content_type_uid}/entries/{entry_uid}?locale={locale}"
            headers = {"api_key": CS_API_KEY, "authorization": CS_MANAGEMENT_TOKEN}
            
            response = requests.get(fetch_url, headers=headers)
            response.raise_for_status()
            full_entry_data = response.json().get("entry", {})

            title = full_entry_data.get("title", "")
            body_text = extract_text_from_rte(full_entry_data.get("article_body", {}))
            text_to_embed = f"Title: {title}. Content: {body_text}"
            
            if not text_to_embed.strip() or text_to_embed.strip() == "Title: . Content:":
                return {"status": "success", "message": "No text content found to index."}

            embedding_response = client.embeddings.create(input=[text_to_embed], model="text-embedding-3-small")
            embedding = embedding_response.data[0].embedding
            
            metadata = {"title": title, "locale": locale, "content_type": content_type_uid, "text_content": text_to_embed}
            index.upsert(vectors=[(vector_id, embedding, metadata)])
            print(f"Vector upserted: {vector_id}")
            return {"status": "success", "vector_id": vector_id}

        return {"status": "success", "message": f"Event '{payload.event}' ignored."}

    except Exception as e:
        print(f"An error occurred during indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_entries(query: SearchQuery):
    try:
        # Define a minimum similarity score to consider a result relevant
        

        relevance_threshold = (query.threshold / 100.0) if query.threshold else 0.10

        CONTENT_GAP_THRESHOLD = 0.35

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

        #Filter the results based on our threshold
        raw_matches = search_results.get('matches', [])
        relevant_matches = [match for match in raw_matches if match['score'] >= relevance_threshold]

        is_content_gap = True
        if r and query.query:
            r.zincrby("top_searches", 1, query.query.lower().strip())
            
            if relevant_matches and relevant_matches[0]['score'] >= CONTENT_GAP_THRESHOLD:
                is_content_gap = False
            
            # If no result met the quality threshold, log it as a content gap
            if is_content_gap:
                r.zincrby("content_gaps", 1, query.query.lower().strip())

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
            entry_uid = match['id'].split('-')[-1]
            content_type_uid = match['metadata']['content_type']

            # Construct the URL to the Contentstack entry editor
            entry_url = f"https://eu-app.contentstack.com/#!/stack/{CS_API_KEY}/content-type/{content_type_uid}/en-us/entry/{entry_uid}/edit?branch=main"

            match['metadata']['url'] = entry_url


            results.append({
                "id": match['id'],
                "score": match['score'],
                "metadata": match['metadata']
            })

        #Log to content gaps only if there are NO RELEVANT results
        if not relevant_matches and r and query.query:
            r.zincrby("top_searches", 1, query.query.lower().strip())
            r.zincrby("content_gaps", 1, query.query.lower().strip())
        elif r and query.query: 
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
            if match['id'] != query.id:
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

@app.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary():
    # If Redis is not connected, return zero values gracefully.
    if not r:
        return {"total_searches": 0, "content_gaps": 0}

    try:
        # zrange with withscores=True returns [item, score, item, score, ...]
        # We only need the scores (counts), which are at odd indices.
        all_searches_with_scores = r.zrange("top_searches", 0, -1, withscores=True)
        total_searches = sum(int(score) for item, score in all_searches_with_scores)

        all_gaps_with_scores = r.zrange("content_gaps", 0, -1, withscores=True)
        total_gaps = sum(int(score) for item, score in all_gaps_with_scores)

        return {"total_searches": total_searches, "content_gaps": total_gaps}

    except Exception as e:
        print(f"An error occurred during analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics summary.")
    
@app.get("/analytics/feedback")
async def get_feedback_analytics():
    if not r:
        return {"most_liked": [], "most_disliked": []}

    try:
        feedback_keys = [key.decode() for key in r.scan_iter("feedback:*")]

        all_feedback = []
        for key in feedback_keys:
            feedback_data = r.hgetall(key)
            # Decode from bytes to string/int
            likes = int(feedback_data.get(b'likes', 0))
            dislikes = int(feedback_data.get(b'dislikes', 0))
            # Extract the entry ID from the key "feedback:locale-ct-uid"
            entry_id = key.split(":", 1)[1]

            # We need the title for the chart, so let's fetch it from Pinecone
            fetch_response = index.fetch(ids=[entry_id])
            title = fetch_response.vectors.get(entry_id, {}).metadata.get('title', entry_id)

            all_feedback.append({"title": title, "likes": likes, "dislikes": dislikes})

        # Sort to find the top 5 most liked and most disliked
        most_liked = sorted(all_feedback, key=lambda x: x['likes'], reverse=True)[:5]
        most_disliked = sorted(all_feedback, key=lambda x: x['dislikes'], reverse=True)[:5]

        return {"most_liked": most_liked, "most_disliked": most_disliked}

    except Exception as e:
        print(f"An error occurred during feedback analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback analytics.")

@app.post("/voice-search")
async def voice_search(audio: UploadFile = File(...)):
    # A temporary path to save the uploaded audio file
    temp_file_path = f"/tmp/{audio.filename}"

    try:
        # Save the uploaded file to the temporary path
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Open the saved file and send it to OpenAI's Whisper API
        with open(temp_file_path, "rb") as audio_file:
            transcription_response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )

        transcript_text = transcription_response.text

        return {"status": "success", "transcript": transcript_text}

    except Exception as e:
        print(f"An error occurred during voice search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # CRITICAL: Clean up and delete the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/feedback")
async def handle_feedback(payload: FeedbackPayload):
    # Only proceed if Redis is connected
    if not r:
        return {"status": "success", "message": "Feedback received, but analytics are disabled."}

    try:
        # Use a Redis Hash to store likes/dislikes for each result ID
        # 'hincrby' is a new one in my journey it means "hash increment by"
        key = f"feedback:{payload.result_id}"

        if payload.feedback_type == 'like':
            r.hincrby(key, "likes", 1)
        elif payload.feedback_type == 'dislike':
            r.hincrby(key, "dislikes", 1)

        return {"status": "success", "message": f"Feedback for {payload.result_id} recorded."}

    except Exception as e:
        print(f"An error occurred during feedback processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to process feedback.")
