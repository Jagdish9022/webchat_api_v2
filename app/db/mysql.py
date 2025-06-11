import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import logging
import sys

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection(use_database=True):
    try:
        connection_params = {
            'host': os.getenv("DB_HOST", "localhost"),
            'user': os.getenv("DB_USER", "root"),
            'password': os.getenv("DB_PASSWORD", "Saish@05"),
        }
        
        if use_database:
            connection_params['database'] = os.getenv("DB_NAME", "webchat_db")
            
        logger.info(f"Attempting to connect to MySQL {'database' if use_database else 'server'}...")
        connection = mysql.connector.connect(**connection_params)
        logger.info(f"Successfully connected to MySQL {'database' if use_database else 'server'}")
        return connection
    except Error as e:
        logger.error(f"Failed to connect to MySQL: {e}")
        raise e

def create_database():
    """Create database if it doesn't exist"""
    connection = None
    cursor = None
    try:
        logger.info("Starting database creation process...")
        connection = get_db_connection(use_database=False)
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        db_name = os.getenv("DB_NAME", "webchat_db")
        logger.info(f"Creating database '{db_name}' if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        connection.commit()
        logger.info(f"Database '{db_name}' created or already exists")
        
    except Error as e:
        logger.error(f"Failed to create database: {e}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Database connection closed")

def init_db():
    """Initialize database with required tables."""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Create users table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create conversations table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR(36) PRIMARY KEY,
                collection_name VARCHAR(255) NOT NULL,
                messages JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_collection_name (collection_name),
                INDEX idx_updated_at (updated_at)
            )
        """)
        
        connection.commit()
        logger.info("Database tables initialized successfully")
    except Error as e:
        logger.error(f"Error initializing database tables: {e}")
        raise e
    finally:
        cursor.close()
        connection.close()
        logger.info("Database connection closed")

def get_db():
    """Get database connection"""
    connection = get_db_connection()
    try:
        yield connection
    finally:
        if connection.is_connected():
            connection.close()
            # logger.info("Database connection closed") 

def get_user_by_email(db, email: str):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    return user

def get_user_by_id(db, user_id: str):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    return user

def create_user(db, user_data: dict):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO users (id, email, username, password_hash)
        VALUES (%s, %s, %s, %s)
    """, (
        user_data['id'],
        user_data['email'],
        user_data['username'],
        user_data['password_hash']
    ))
    db.commit()
    cursor.close()