"""
db.py
------
Handles all MySQL database operations: schema setup, saving/reading
PubMed search results, and user account management (signup/login).
"""

import mysql.connector
from mysql.connector import Error
import bcrypt

from dotenv import load_dotenv
import os

load_dotenv()

# --- Your MySQL connection details ---
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = "pubmed_app"


def get_connection(use_database=True):
    try:
        if use_database:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
        else:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD
            )
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None


def setup_database():
    conn = get_connection(use_database=False)
    if conn is None:
        return False

    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.close()
    conn.close()

    conn = get_connection(use_database=True)
    if conn is None:
        return False

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INT AUTO_INCREMENT PRIMARY KEY,
            keyword VARCHAR(255) NOT NULL,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
            FOREIGN KEY (search_id) REFERENCES searches(id)
        )
    """)

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
    return True


def save_search_results(keyword, articles):
    conn = get_connection()
    if conn is None:
        return None

    cursor = conn.cursor()
    cursor.execute("INSERT INTO searches (keyword) VALUES (%s)", (keyword,))
    search_id = cursor.lastrowid

    insert_query = """
        INSERT INTO articles (search_id, pmid, title, authors, journal, pub_date, abstract)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    for article in articles:
        cursor.execute(insert_query, (
            search_id, article["pmid"], article["title"], article["authors"],
            article["journal"], article["pub_date"], article["abstract"]
        ))

    conn.commit()
    cursor.close()
    conn.close()
    return search_id


def get_all_searches():
    conn = get_connection()
    if conn is None:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM searches ORDER BY searched_at DESC")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def get_articles_for_search(search_id):
    conn = get_connection()
    if conn is None:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM articles WHERE search_id = %s", (search_id,))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def create_user(username, password):
    """Registers a new user with a bcrypt-hashed password."""
    conn = get_connection()
    if conn is None:
        return False

    cursor = conn.cursor()
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hashed.decode("utf-8"))
        )
        conn.commit()
        return True
    except mysql.connector.IntegrityError:
        return False
    finally:
        cursor.close()
        conn.close()


def verify_user(username, password):
    """Checks a login attempt against the stored bcrypt hash."""
    conn = get_connection()
    if conn is None:
        return False

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        return False

    stored_hash = user["password_hash"].encode("utf-8")
    attempt_bytes = password.encode("utf-8")
    return bcrypt.checkpw(attempt_bytes, stored_hash)


if __name__ == "__main__":
    print("Setting up database and tables...")
    success = setup_database()
    print("Database ready." if success else "Setup failed.")