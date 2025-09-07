# Add this import at the top with your other imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # <-- ADD THIS LINE
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import json
import logging

# Initialize FastAPI app
app = FastAPI()

# ADD CORS MIDDLEWARE - Add this block right after app = FastAPI()
# -------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (you can specify specific domains later)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)
# -------------------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# In-memory storage for documents and embeddings
documents = {}
embeddings = []
faiss_index = None

# Pydantic models for request/response
class ContentstackWebhook(BaseModel):
    module: str
    event: str
    data: dict

class SearchRequest(BaseModel):
    query: str

class SimilarityRequest(BaseModel):
    id: str

class SearchResult(BaseModel):
    id: str
    score: float
    metadata: dict

class SearchResponse(BaseModel):
    results: List[SearchResult]
    smart_snippet: Optional[str] = None

def initialize_faiss_index():
    """Initialize or reinitialize the FAISS index"""
    global faiss_index, embeddings
    
    if len(embeddings) > 0:
        embeddings_array = np.array(embeddings).astype('float32')
        faiss_index = faiss.IndexFlatIP(embeddings_array.shape[1])
        faiss_index.add(embeddings_array)
        logger.info(f"FAISS index initialized with {len(embeddings)} embeddings")
    else:
        faiss_index = None
        logger.info("No embeddings available, FAISS index not initialized")

def generate_smart_snippet(query: str, top_results: List[dict]) -> str:
    """Generate a smart snippet based on the query and top results"""
    if not top_results:
        return ""
    
    # Take the top result with highest similarity
    best_result = top_results[0]
    content = best_result.get('metadata', {})
    
    title = content.get('title', '')
    description = content.get('description', '')
    
    if description:
        return f"Based on your search for '{query}', here's what I found: {description[:200]}..."
    elif title:
        return f"The most relevant content for '{query}' is: {title}"
    else:
        return f"Found {len(top_results)} relevant results for your search."

@app.get("/")
async def root():
    return {
        "message": "Contentstack Search API is running!",
        "endpoints": {
            "/index": "POST - Index content from Contentstack webhook",
            "/search": "POST - Search for content",
            "/find_similar": "POST - Find similar content",
            "/health": "GET - Health check"
        },
        "total_documents": len(documents),
        "faiss_ready": faiss_index is not None
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "total_documents": len(documents),
        "faiss_index_ready": faiss_index is not None,
        "model_loaded": model is not None
    }

@app.post("/index")
async def index_content(webhook: ContentstackWebhook):
    """Index content from Contentstack webhook"""
    global documents, embeddings
    
    try:
        # Extract entry data
        entry = webhook.data.get('entry', {})
        entry_uid = entry.get('uid')
        
        if not entry_uid:
            raise HTTPException(status_code=400, detail="No entry UID found")
        
        # Prepare content for embedding
        title = entry.get('title', '')
        description = entry.get('description', '')
        content = entry.get('content', '')
        
        # Combine text for embedding
        text_for_embedding = f"{title} {description} {content}".strip()
        
        if not text_for_embedding:
            raise HTTPException(status_code=400, detail="No content to embed")
        
        # Generate embedding
        embedding = model.encode(text_for_embedding)
        
        # Store document
        documents[entry_uid] = {
            'id': entry_uid,
            'text': text_for_embedding,
            'metadata': {
                'title': title,
                'description': description,
                'content': content,
                'content_type': entry.get('content_type', {}).get('uid', 'unknown'),
                'locale': entry.get('locale', 'en-us')
            }
        }
        
        # Add embedding
        embeddings.append(embedding)
        
        # Reinitialize FAISS index
        initialize_faiss_index()
        
        logger.info(f"Indexed content: {entry_uid}")
        
        return {
            "message": f"Successfully indexed entry: {entry_uid}",
            "total_documents": len(documents)
        }
    
    except Exception as e:
        logger.error(f"Error indexing content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error indexing content: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search_content(request: SearchRequest):
    """Search for content using semantic similarity"""
    
    if not documents or faiss_index is None:
        raise HTTPException(status_code=404, detail="No content indexed yet")
    
    try:
        # Generate query embedding
        query_embedding = model.encode(request.query).astype('float32')
        
        # Search using FAISS
        k = min(5, len(documents))  # Return top 5 or all documents if fewer
        scores, indices = faiss_index.search(query_embedding.reshape(1, -1), k)
        
        # Prepare results
        results = []
        doc_ids = list(documents.keys())
        
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < len(doc_ids):  # Valid index
                doc_id = doc_ids[idx]
                doc = documents[doc_id]
                
                results.append(SearchResult(
                    id=doc_id,
                    score=float(score),
                    metadata=doc['metadata']
                ))
        
        # Generate smart snippet
        smart_snippet = generate_smart_snippet(request.query, [r.dict() for r in results])
        
        logger.info(f"Search completed for query: '{request.query}' - {len(results)} results")
        
        return SearchResponse(
            results=results,
            smart_snippet=smart_snippet
        )
    
    except Exception as e:
        logger.error(f"Error searching content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")

@app.post("/find_similar", response_model=SearchResponse)
async def find_similar_content(request: SimilarityRequest):
    """Find content similar to a given document ID"""
    
    if request.id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not documents or faiss_index is None:
        raise HTTPException(status_code=404, detail="No content indexed for similarity search")
    
    try:
        # Find the index of the document
        doc_ids = list(documents.keys())
        doc_index = doc_ids.index(request.id)
        
        # Get the embedding for this document
        doc_embedding = np.array([embeddings[doc_index]]).astype('float32')
        
        # Search for similar documents (excluding the original)
        k = min(6, len(documents))  # Get 6 to exclude the original
        scores, indices = faiss_index.search(doc_embedding, k)
        
        # Prepare results (excluding the original document)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(doc_ids) and idx != doc_index:  # Exclude original
                similar_doc_id = doc_ids[idx]
                doc = documents[similar_doc_id]
                
                results.append(SearchResult(
                    id=similar_doc_id,
                    score=float(score),
                    metadata=doc['metadata']
                ))
        
        logger.info(f"Found {len(results)} similar documents for ID: {request.id}")
        
        return SearchResponse(results=results)
    
    except Exception as e:
        logger.error(f"Error finding similar content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error finding similar content: {str(e)}")

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)