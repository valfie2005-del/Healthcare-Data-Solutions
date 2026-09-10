import os
import bcrypt
import mysql.connector
from mysql.connector import Error
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

def get_secret(name, default=None):
    """
    Get configuration from Streamlit Cloud secrets first.
    If running locally, fall back to environment variables.
    """
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name, default)


DB_HOST = get_secret("MYSQL_HOST")
DB_USER = get_secret("MYSQL_USER")
DB_PASSWORD = get_secret("MYSQL_PASSWORD")
DB_NAME = get_secret("MYSQL_DATABASE", "pubmed_app")
DB_PORT = int(get_secret("MYSQL_PORT", 3306))


# ============================================================
# MYSQL CONNECTION
# ============================================================

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        return conn

    except Error as e:
        print(f"MySQL connection error: {e}")
        return None


# ============================================================
# DATABASE / TABLE SETUP
# ============================================================

def setup_database():
    """
    Creates required tables if they don't already exist.

    The database itself should already exist on the MySQL server.
    """

    conn = get_connection()

    if conn is None:
        print("Could not connect to MySQL.")
        return False

    try:
        cursor = conn.cursor()

        # ----------------------------------------------------
        # Searches table
        # ----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                keyword VARCHAR(255) NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ----------------------------------------------------
        # Articles table
        # ----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                search_id INT NOT NULL,
                pmid VARCHAR(20),
                title TEXT,
                authors TEXT,
                journal VARCHAR(500),
                pub_date VARCHAR(100),
                abstract TEXT,
                FOREIGN KEY (search_id)
                    REFERENCES searches(id)
            )
        """)

        # ----------------------------------------------------
        # Users table
        # ----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

        cursor.close()
        conn.close()

        print("Database tables ready.")
        return True

    except Error as e:
        print(f"Database setup error: {e}")
        return False


# ============================================================
# SAVE PUBMED SEARCH RESULTS
# ============================================================

def save_search_results(keyword, articles):

    conn = get_connection()

    if conn is None:
        return None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO searches (keyword) VALUES (%s)",
            (keyword,)
        )

        search_id = cursor.lastrowid

        insert_query = """
            INSERT INTO articles
            (
                search_id,
                pmid,
                title,
                authors,
                journal,
                pub_date,
                abstract
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for article in articles:

            cursor.execute(
                insert_query,
                (
                    search_id,
                    article["pmid"],
                    article["title"],
                    article["authors"],
                    article["journal"],
                    article["pub_date"],
                    article["abstract"]
                )
            )

        conn.commit()

        cursor.close()
        conn.close()

        return search_id

    except Error as e:
        print(f"Error saving search results: {e}")

        if conn:
            conn.close()

        return None


# ============================================================
# GET ALL SEARCHES
# ============================================================

def get_all_searches():

    conn = get_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM searches ORDER BY searched_at DESC"
        )

        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results

    except Error as e:
        print(f"Error getting searches: {e}")
        return []


# ============================================================
# GET ARTICLES
# ============================================================

def get_articles_for_search(search_id):

    conn = get_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM articles WHERE search_id = %s",
            (search_id,)
        )

        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results

    except Error as e:
        print(f"Error getting articles: {e}")
        return []


# ============================================================
# CREATE USER
# ============================================================

def create_user(username, password):
    """
    Creates a new user using bcrypt password hashing.

    Returns:
        "success"   -> account created
        "duplicate" -> username already exists
        "db_error"  -> database problem
    """

    conn = get_connection()

    if conn is None:
        return "db_error"

    cursor = conn.cursor()

    try:

        password_bytes = password.encode("utf-8")

        hashed = bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt()
        )

        cursor.execute(
            """
            INSERT INTO users
            (username, password_hash)
            VALUES (%s, %s)
            """,
            (
                username,
                hashed.decode("utf-8")
            )
        )

        conn.commit()

        return "success"

    except mysql.connector.IntegrityError:
        return "duplicate"

    except Error as e:
        print(f"Create user database error: {e}")
        return "db_error"

    finally:

        cursor.close()
        conn.close()


# ============================================================
# VERIFY USER
# ============================================================

def verify_user(username, password):

    conn = get_connection()

    if conn is None:
        return False

    try:

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user is None:
            return False

        stored_hash = user["password_hash"].encode("utf-8")
        attempt_bytes = password.encode("utf-8")

        return bcrypt.checkpw(
            attempt_bytes,
            stored_hash
        )

    except Error as e:
        print(f"Login database error: {e}")
        return False


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("Testing database connection...")

    if setup_database():
        print("Database ready.")

    else:
        print("Database setup failed.")