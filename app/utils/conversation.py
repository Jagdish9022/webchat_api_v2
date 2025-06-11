import json
from typing import Dict, List
import uuid


def get_or_create_conversation(db, collection_name: str) -> str:
    """Get existing conversation or create new one for collection."""
    cursor = db.cursor(dictionary=True)
    
    # Try to get existing conversation
    cursor.execute("""
        SELECT id FROM conversations 
        WHERE collection_name = %s 
        ORDER BY updated_at DESC 
        LIMIT 1
    """, (collection_name,))
    
    conversation = cursor.fetchone()
    
    if conversation:
        conversation_id = conversation['id']
        # Update timestamp
        cursor.execute("""
            UPDATE conversations 
            SET updated_at = NOW() 
            WHERE id = %s
        """, (conversation_id,))
    else:
        # Create new conversation
        conversation_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO conversations (id, collection_name, messages, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """, (conversation_id, collection_name, json.dumps([])))
    
    db.commit()
    cursor.close()
    return conversation_id

def get_conversation_history(db, conversation_id: str) -> List[Dict[str, str]]:
    """Get conversation history from database."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT messages FROM conversations 
        WHERE id = %s
    """, (conversation_id,))
    
    result = cursor.fetchone()
    cursor.close()
    
    if result and result['messages']:
        return json.loads(result['messages'])
    return []

def update_conversation_history(db, conversation_id: str, messages: List[Dict[str, str]]):
    """Update conversation history in database."""
    cursor = db.cursor()
    cursor.execute("""
        UPDATE conversations 
        SET messages = %s, updated_at = NOW()
        WHERE id = %s
    """, (json.dumps(messages), conversation_id))
    
    db.commit()
    cursor.close()
