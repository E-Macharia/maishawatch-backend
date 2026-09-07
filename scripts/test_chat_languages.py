# scripts/fix_chat_tables.py
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.paths import DB_FILE

def fix_chat_tables():
    """Fix chat tables and foreign key constraints"""
    print(f"Fixing chat tables in {DB_FILE}")
    
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute('PRAGMA foreign_keys=ON')
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_conversations'")
    if not cursor.fetchone():
        print("❌ chat_conversations table doesn't exist. Run migration first.")
        conn.close()
        return
    
    # Check if chat_messages table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'")
    if not cursor.fetchone():
        print("❌ chat_messages table doesn't exist. Run migration first.")
        conn.close()
        return
    
    # Check foreign keys
    cursor.execute("PRAGMA foreign_key_list(chat_messages)")
    fks = cursor.fetchall()
    
    if not fks:
        print("⚠️  Foreign keys not found. Creating...")
        
        # Drop and recreate tables with foreign keys
        cursor.execute('DROP TABLE IF EXISTS chat_messages')
        cursor.execute('DROP TABLE IF EXISTS chat_conversations')
        
        # Recreate with proper foreign keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                action TEXT,
                data TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES chat_conversations(conversation_id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation ON chat_messages(conversation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at)')
        
        print("✅ Chat tables recreated with proper foreign keys")
    else:
        print("✅ Foreign keys already exist")
    
    conn.commit()
    conn.close()
    print("✅ Chat tables fixed!")

if __name__ == "__main__":
    fix_chat_tables()