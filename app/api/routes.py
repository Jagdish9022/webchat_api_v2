from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from app.utils.conversation import get_conversation_history, get_or_create_conversation, update_conversation_history
from app.utils.process_files import process_pdf, process_svg, process_text_file
from app.db.models import QARequest, ScrapeRequest, UserCreate, UserLogin, User, Token
from app.services.gemini import ask_gemini, enhanced_query_with_gemini, translate_to_english
from app.services.embeddings import get_embeddings, get_question_embedding
from app.utils.common import clean_text, crawl_website, create_chunks
from app.db.qdrant import ingest_to_qdrant
from app.auth.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.db.mysql import get_db
import logging
from typing import Dict
import asyncio
from datetime import datetime, timedelta
import hashlib
import uuid
import traceback
import json


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Store scraping progress with last update time
scraping_progress: Dict[str, dict] = {}

# Allowed file types
ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'svg': 'image/svg+xml',
    'txt': 'text/plain',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

@router.post("/signup", response_model=User)
async def signup(user: UserCreate, db = Depends(get_db)):
    """Create a new user account."""
    try:
        logger.info(f"Signup attempt for email: {user.email}")
        
        # Check if user already exists
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        existing_user = cursor.fetchone()
        cursor.close()
        
        if existing_user:
            logger.warning(f"Signup failed: Email already registered: {user.email}")
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user.password)
        
        # Insert new user
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (id, email, username, password_hash)
            VALUES (%s, %s, %s, %s)
        """, (
            user_id,
            user.email,
            user.username,
            hashed_password
        ))
        db.commit()
        cursor.close()
        
        logger.info(f"User created successfully: {user.email}")
        return {
            'id': user_id,
            'email': user.email,
            'username': user.username,
            'created_at': datetime.now(),
            'is_active': True
        }
    except HTTPException as he:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise he
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="An error occurred during signup. Please try again."
        )

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db)
):
    """Login endpoint for OAuth2 password flow"""
    try:
        logger.info(f"Login attempt for username: {form_data.username}")
        
        # Find user
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (form_data.username,))
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            logger.warning(f"Login failed: User not found with email {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user['password_hash']):
            logger.warning(f"Login failed: Invalid password for user {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['id']}, expires_delta=access_token_expires
        )
        
        logger.info(f"Login successful for user {form_data.username}")
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again."
        )

@router.post("/login/json", response_model=Token)
async def login_json(user_data: UserLogin, db = Depends(get_db)):
    """Login endpoint for JSON data"""
    try:
        logger.info(f"Login attempt for email: {user_data.email}")
        
        # Find user
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (user_data.email,))
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            logger.warning(f"Login failed: User not found with email {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(user_data.password, user['password_hash']):
            logger.warning(f"Login failed: Invalid password for user {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['id']}, expires_delta=access_token_expires
        )
        
        logger.info(f"Login successful for user {user_data.email}")
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again."
        )

@router.post("/upload-and-process")
async def upload_and_process(
    file: UploadFile = File(...),
    current_user = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = None,
    db = Depends(get_db)
):
    """Upload and process files (PDF, SVG, etc.) and store in user's collection."""
    try:
        # Use user's ID as collection name
        collection_name = current_user['id']
        
        logger.info(f"Starting file upload process for file: {file.filename}")
        
        # Validate file type
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            logger.warning(f"Invalid file type: {file_extension}")
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS.keys())}"
            )

        # Read file content
        try:
            file_content = await file.read()
            if not file_content:
                raise HTTPException(status_code=400, detail="Empty file received")
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        
        # Process file based on type
        text_content = ""
        try:
            if file_extension == 'pdf':
                text_content = process_pdf(file_content)
            elif file_extension == 'svg':
                text_content = process_svg(file_content)
            else:
                text_content = process_text_file(file_content)
        except Exception as e:
            logger.error(f"Error processing file content: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error processing file content: {str(e)}")

        if not text_content.strip():
            logger.warning("No text content extracted from file")
            raise HTTPException(status_code=400, detail="No text content could be extracted from the file")

        # Create chunks from the text
        try:
            chunks = create_chunks(text_content, chunk_size=1000, overlap=200)
            logger.info(f"Created {len(chunks)} chunks from text")
            
            # Validate chunks
            valid_chunks = [chunk for chunk in chunks if chunk.strip()]
            if len(valid_chunks) != len(chunks):
                logger.warning(f"Filtered out {len(chunks) - len(valid_chunks)} empty chunks")
                chunks = valid_chunks
                
            if not chunks:
                raise HTTPException(status_code=400, detail="No valid text chunks could be created from the file")
                
        except Exception as e:
            logger.error(f"Error creating chunks: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error creating text chunks: {str(e)}")

        # Generate embeddings
        try:
            embeddings = get_embeddings(chunks)
            if not embeddings or len(embeddings) != len(chunks):
                raise Exception("Embedding generation failed or produced mismatched results")
            logger.info(f"Generated {len(embeddings)} embeddings")
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating embeddings: {str(e)}")

        # Ingest to Qdrant
        try:
            ingest_to_qdrant(collection_name, chunks, embeddings)
            logger.info(f"Successfully ingested {len(chunks)} chunks to collection {collection_name}")
        except Exception as e:
            logger.error(f"Error ingesting to Qdrant: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error storing data: {str(e)}")

        return {
            "status": "success",
            "message": "File processed and stored successfully",
            "collection_name": collection_name,
            "chunks_created": len(chunks),
            "file_name": file.filename
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in upload_and_process: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/scrape-and-ingest")
async def scrape_and_ingest(
    req: ScrapeRequest,
    current_user = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = None,
    db = Depends(get_db)
):
    """Scrape a website and ingest the content into user's collection."""
    try:
        # Use user's ID as collection name
        collection_name = current_user['id']
        
        logger.info(f"Starting scrape and ingest for URL: {req.url}")
        
        # Generate a unique ID for this scraping task
        task_id = hashlib.md5(f"{req.url}_{datetime.now().timestamp()}".encode()).hexdigest()
        
        # Initialize progress tracking
        scraping_progress[task_id] = {
            "status": "crawling",
            "start_time": datetime.now(),
            "last_update": datetime.now(),
            "pages_scraped": 0,
            "chunks_created": 0,
            "error": None,
            "is_completed": False
        }
        
        # Start background task
        background_tasks.add_task(process_scraping, req.url, task_id, collection_name)
        
        return {"task_id": task_id, "status": "started"}
        
    except Exception as e:
        logger.error(f"Error starting scrape process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scraping-progress/{task_id}")
async def get_scraping_progress(task_id: str):
    """Get the current progress of a scraping task."""
    if task_id not in scraping_progress:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if we should return cached response
    current_time = datetime.now()
    last_update = scraping_progress[task_id]["last_update"]
    time_diff = (current_time - last_update).total_seconds()
    
    # If the task is completed or there's an error, return immediately
    if scraping_progress[task_id]["is_completed"] or scraping_progress[task_id]["error"]:
        return scraping_progress[task_id]
    
    # If less than 2 seconds have passed since last update, return cached response
    if time_diff < 2:
        return scraping_progress[task_id]
    
    # Update last update time
    scraping_progress[task_id]["last_update"] = current_time
    return scraping_progress[task_id]

async def process_scraping(url: str, task_id: str, collection_name: str):
    """Background task to process scraping and ingestion."""
    try:
        # Update status to crawling
        update_progress(task_id, "crawling")
        
        # Crawl the website WITHOUT LIMIT - will crawl all pages
        pages = crawl_website(str(url), max_pages=None)  # None means unlimited
        
        if not pages:
            update_progress(task_id, "error", error="No pages could be scraped from the provided URL")
            return
        
        update_progress(task_id, "crawling", pages_scraped=len(pages))
        
        # Update status to processing
        update_progress(task_id, "processing")
        
        all_chunks = []
        
        # Process each page
        for url, html in pages.items():
            if html and isinstance(html, str) and len(html) > 0:
                cleaned_text = clean_text(html)
                if cleaned_text.strip():
                    # Create chunks with size 64
                    chunks = create_chunks(cleaned_text, chunk_size=64, overlap=10)
                    all_chunks.extend(chunks)
        
        if not all_chunks:
            update_progress(task_id, "error", error="No valid text content found to ingest from the website")
            return
        
        update_progress(task_id, "processing", chunks_created=len(all_chunks))
        
        # Update status to generating embeddings
        update_progress(task_id, "generating_embeddings")
        
        # Generate embeddings
        embeddings = get_embeddings(all_chunks)
        
        # Update status to storing
        update_progress(task_id, "storing")
        
        # Ingest to Qdrant using user's collection
        ingest_to_qdrant(collection_name, all_chunks, embeddings)
        
        # Update status to completed
        update_progress(task_id, "completed", 
                       result={
                           "collection_name": collection_name,
                           "pages_scraped": len(pages),
                           "chunks_created": len(all_chunks)
                       })
        
    except Exception as e:
        logger.error(f"Error in scraping process: {e}")
        update_progress(task_id, "error", error=str(e))

def update_progress(task_id: str, status: str, **kwargs):
    """Update progress with new status and optional data."""
    if task_id not in scraping_progress:
        return
        
    scraping_progress[task_id].update({
        "status": status,
        "last_update": datetime.now(),
        **kwargs
    })
    
    if status in ["completed", "error"]:
        scraping_progress[task_id]["is_completed"] = True


@router.post("/ask-question")
async def ask_question(req: QARequest, db=Depends(get_db)):
    try:
        logging.info(f"Processing question: {req.question}")
        
        # Get or create conversation
        conversation_id = get_or_create_conversation(db, req.collection_name)
        
        # Get existing conversation history
        conversation_history = get_conversation_history(db, conversation_id)
        
        translated_query = translate_to_english(req.question)

        # Step 1: Get embedding
        question_embedding = get_question_embedding(translated_query)

        # Step 2: Enhanced query to get search results and context
        enhanced_results = enhanced_query_with_gemini(
            collection_name=req.collection_name,
            user_query=translated_query,
            query_vector=question_embedding,
            limit=5
        )

        # Step 3: Ask Gemini with the full context and results
        final_response = ask_gemini(
            enhanced_results.get("context_text", ""),  # context string
            req.question,                              # user question
            enhanced_results.get("processed_query", {}),  # parsed search info
            enhanced_results,                          # full result dict
            conversation_history                       # conversation history
        )

        # Update conversation history with new messages
        conversation_history.append({"role": "user", "content": req.question})
        conversation_history.append({"role": "assistant", "content": final_response["response"]})
        update_conversation_history(db, conversation_id, conversation_history)

        # Add conversation_id to response
        final_response["conversation_id"] = conversation_id
        return final_response

    except Exception as e:
        logging.error(f"Error in ask_question: {e}")
        return {
            "response": "Something went wrong while answering your question.",
            "buttons": False,
            "button_type": None,
            "button_data": None,
            "conversation_id": None
        }

@router.get("/process-status/{task_id}")
async def process_status(task_id: str):
    async def generate():
        # Initial state
        states = {
            'crawling': {
                'status': 'pending',
                'message': 'Waiting to start crawling...',
                'progress': 0
            },
            'processing': {
                'status': 'pending',
                'message': 'Waiting to start processing...',
                'progress': 0
            },
            'generating_embeddings': {
                'status': 'pending',
                'message': 'Waiting to generate embeddings...',
                'progress': 0
            },
            'storing': {
                'status': 'pending',
                'message': 'Waiting to store data...',
                'progress': 0
            },
            'completed': {
                'status': 'pending',
                'message': 'Waiting for completion...',
                'progress': 0
            }
        }
        
        current_state = 'crawling'
        total_steps = len(states)
        
        try:
            # Simulate processing steps
            for step in states.keys():
                current_state = step
                states[step]['status'] = 'active'
                states[step]['message'] = f'Starting {step.replace("_", " ")}...'
                states[step]['progress'] = 0
                
                # Send initial state
                yield f"data: {json.dumps({'states': states, 'current_state': current_state})}\n\n"
                
                # Simulate progress for current step
                for progress in range(0, 101, 10):
                    states[step]['progress'] = progress
                    states[step]['message'] = f'{step.replace("_", " ").title()}: {progress}% complete'
                    
                    # Log to terminal
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {step}: {progress}% - {states[step]['message']}")
                    
                    yield f"data: {json.dumps({'states': states, 'current_state': current_state})}\n\n"
                    await asyncio.sleep(0.5)  # Use asyncio.sleep instead of time.sleep
                
                # Mark step as completed
                states[step]['status'] = 'completed'
                states[step]['message'] = f'{step.replace("_", " ").title()} completed'
                states[step]['progress'] = 100
                
                yield f"data: {json.dumps({'states': states, 'current_state': current_state})}\n\n"
                
                if step != 'completed':
                    await asyncio.sleep(1)  # Use asyncio.sleep instead of time.sleep
            
            # Send final completion message
            yield f"data: {json.dumps({'states': states, 'current_state': 'completed', 'is_complete': True})}\n\n"
            
        except Exception as e:
            print(f"Error in process_status: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
