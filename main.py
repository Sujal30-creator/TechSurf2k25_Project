from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Initialize FastAPI app
app = FastAPI()

# ADD CORS MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize TF-IDF vectorizer (lightweight alternative to sentence transformers)
vectorizer = TfidfVectorizer(
    max_features=1000,
    stop_words='english',
    ngram_range=(1, 2)
)

# In-memory storage for documents and embeddings
documents = {}
document_texts = []
document_ids = []
tfidf_matrix = None

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

def rebuild_index():
    """Rebuild the TF-IDF index with current documents"""
    global tfidf_matrix, document_texts, document_ids
    
    if len(documents) > 0:
        # Prepare texts and IDs
        document_texts = []
        document_ids = []
        
        for doc_id, doc_data in documents.items():
            document_texts.append(doc_data['text'])
            document_ids.append(doc_id)
        
        # Build TF-IDF matrix
        tfidf_matrix = vectorizer.fit_transform(document_texts)
        logger.info(f"TF-IDF index rebuilt with {len(documents)} documents")
    else:
        tfidf_matrix = None
        document_texts = []
        document_ids = []
        logger.info("No documents available, index cleared")

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
        "message": "Contentstack Search API is running! (Lightweight Version)",
        "endpoints": {
            "/index": "POST - Index content from Contentstack webhook",
            "/search": "POST - Search for content",
            "/find_similar": "POST - Find similar content",
            "/health": "GET - Health check"
        },
        "total_documents": len(documents),
        "search_ready": tfidf_matrix is not None,
        "version": "lightweight"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "total_documents": len(documents),
        "search_index_ready": tfidf_matrix is not None,
        "version": "lightweight"
    }

@app.post("/index")
async def index_content(webhook: ContentstackWebhook):
    """Index content from Contentstack webhook"""
    global documents
    
    try:
        # Extract entry data
        entry = webhook.data.get('entry', {})
        entry_uid = entry.get('uid')
        
        if not entry_uid:
            raise HTTPException(status_code=400, detail="No entry UID found")
        
        # Prepare content for indexing
        title = entry.get('title', '')
        description = entry.get('description', '')
        content = entry.get('content', '')
        
        # Combine text for searching
        text_for_search = f"{title} {description} {content}".strip()
        
        if not text_for_search:
            raise HTTPException(status_code=400, detail="No content to index")
        
        # Store document
        documents[entry_uid] = {
            'id': entry_uid,
            'text': text_for_search,
            'metadata': {
                'title': title,
                'description': description,
                'content': content,
                'content_type': entry.get('content_type', {}).get('uid', 'unknown'),
                'locale': entry.get('locale', 'en-us')
            }
        }
        
        # Rebuild search index
        rebuild_index()
        
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
    """Search for content using TF-IDF similarity"""
    
    if not documents or tfidf_matrix is None:
        raise HTTPException(status_code=404, detail="No content indexed yet")
    
    try:
        # Transform query using the same vectorizer
        query_vector = vectorizer.transform([request.query])
        
        # Calculate cosine similarity
        similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
        
        # Get top results (sorted by similarity)
        top_indices = similarities.argsort()[-5:][::-1]  # Top 5 results, descending
        
        # Prepare results
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # Only include results with some similarity
                doc_id = document_ids[idx]
                doc = documents[doc_id]
                
                results.append(SearchResult(
                    id=doc_id,
                    score=float(similarities[idx]),
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
    
    if not documents or tfidf_matrix is None:
        raise HTTPException(status_code=404, detail="No content indexed for similarity search")
    
    try:
        # Find the index of the document
        doc_index = document_ids.index(request.id)
        
        # Get the document vector
        doc_vector = tfidf_matrix[doc_index:doc_index+1]
        
        # Calculate similarities with all other documents
        similarities = cosine_similarity(doc_vector, tfidf_matrix).flatten()
        
        # Get top similar documents (excluding the original)
        top_indices = similarities.argsort()[-6:][::-1]  # Top 6, descending
        
        # Prepare results (excluding the original document)
        results = []
        for idx in top_indices:
            if idx != doc_index and similarities[idx] > 0:  # Exclude original
                similar_doc_id = document_ids[idx]
                doc = documents[similar_doc_id]
                
                results.append(SearchResult(
                    id=similar_doc_id,
                    score=float(similarities[idx]),
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