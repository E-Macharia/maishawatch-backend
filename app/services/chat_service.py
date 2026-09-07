# app/services/chat_service.py
from datetime import datetime, timezone, timedelta
import json
from typing import Optional, List, Dict, Any
from app.core.db import db
import uuid

class ChatMemory:
    """Handle chat conversation memory and history"""
    
    @staticmethod
    def create_conversation(user_id: str, title: str = None) -> str:
        """Create a new conversation"""
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        if not title:
            title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        with db() as c:
            c.execute('''
                INSERT INTO chat_conversations 
                (conversation_id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, user_id, title, now, now))
        
        return conversation_id
    
    @staticmethod
    def add_message(conversation_id: str, role: str, content: str, action: str = None, data: Dict = None):
        """Add a message to conversation"""
        now = datetime.now(timezone.utc).isoformat()
        
        with db() as c:
            c.execute('''
                INSERT INTO chat_messages 
                (conversation_id, role, content, action, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (conversation_id, role, content, action, json.dumps(data) if data else None, now))
            
            # Update conversation timestamp
            c.execute('''
                UPDATE chat_conversations SET updated_at=? WHERE conversation_id=?
            ''', (now, conversation_id))
    
    @staticmethod
    def get_conversation(conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history"""
        with db() as c:
            messages = c.execute('''
                SELECT role, content, action, data, created_at
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            ''', (conversation_id, limit)).fetchall()
            
            return [dict(m) for m in messages]
    
    @staticmethod
    def get_conversations(user_id: str, limit: int = 20) -> List[Dict]:
        """Get all conversations for a user"""
        with db() as c:
            conversations = c.execute('''
                SELECT conversation_id, title, created_at, updated_at,
                       (SELECT COUNT(*) FROM chat_messages WHERE conversation_id = c.conversation_id) as message_count
                FROM chat_conversations c
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (user_id, limit)).fetchall()
            
            return [dict(c) for c in conversations]
    
    @staticmethod
    def delete_conversation(conversation_id: str):
        """Delete a conversation and all its messages"""
        with db() as c:
            c.execute('DELETE FROM chat_messages WHERE conversation_id=?', (conversation_id,))
            c.execute('DELETE FROM chat_conversations WHERE conversation_id=?', (conversation_id,))