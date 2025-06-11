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
        # Check if using hosted or local database
        use_hosted_db = os.getenv("USE_HOSTED_DB", "false").lower() == "true"
        
        if use_hosted_db:
            # Hosted database configuration
            connection_params = {
                'host': os.getenv("HOSTED_DB_HOST"),
                'user': os.getenv("HOSTED_DB_USER"),
                'password': os.getenv("HOSTED_DB_PASSWORD"),
                'port': int(os.getenv("HOSTED_DB_PORT", "3306")),
                'ssl_disabled': os.getenv("HOSTED_DB_SSL_DISABLED", "false").lower() == "true",
            }
            
            # Add SSL configuration if needed for hosted database
            if not connection_params['ssl_disabled']:
                connection_params['ssl_ca'] = os.getenv("HOSTED_DB_SSL_CA")
                connection_params['ssl_cert'] = os.getenv("HOSTED_DB_SSL_CERT")
                connection_params['ssl_key'] = os.getenv("HOSTED_DB_SSL_KEY")
                # Remove None values
                connection_params = {k: v for k, v in connection_params.items() if v is not None}
            else:
                connection_params.pop('ssl_disabled')
            
            if use_database:
                connection_params['database'] = os.getenv("HOSTED_DB_NAME")
                
            logger.info(f"Attempting to connect to hosted MySQL {'database' if use_database else 'server'}...")
            
        else:
            # Local database configuration
            connection_params = {
                'host': os.getenv("LOCAL_DB_HOST", "localhost"),
                'user': os.getenv("LOCAL_DB_USER", "root"),
                'password': os.getenv("LOCAL_DB_PASSWORD", "Saish@05"),
                'port': int(os.getenv("LOCAL_DB_PORT", "3306")),
            }
            
            if use_database:
                connection_params['database'] = os.getenv("LOCAL_DB_NAME", "webchat_db")
                
            logger.info(f"Attempting to connect to local MySQL {'database' if use_database else 'server'}...")
            
        connection = mysql.connector.connect(**connection_params)
        logger.info(f"Successfully connected to {'hosted' if use_hosted_db else 'local'} MySQL {'database' if use_database else 'server'}")
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
        
        # Get database name based on configuration
        use_hosted_db = os.getenv("USE_HOSTED_DB", "false").lower() == "true"
        if use_hosted_db:
            db_name = os.getenv("HOSTED_DB_NAME")
        else:
            db_name = os.getenv("LOCAL_DB_NAME", "webchat_db")
        
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