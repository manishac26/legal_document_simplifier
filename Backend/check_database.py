# check_database.py
import sqlite3

def view_database():
    # Connect to the database
    conn = sqlite3.connect('legal_app.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in database:")
    for table in tables:
        print(f" - {table[0]}")
    
    print("\n" + "="*50)
    
    # View users table
    cursor.execute("SELECT * FROM users;")
    users = cursor.fetchall()
    print("Users table:")
    if users:
        for user in users:
            print(f"ID: {user[0]}, Name: {user[1]}, Email: {user[2]}, Created: {user[4]}")
    else:
        print("No users found")
    
    print("\n" + "="*50)
    
    # View documents table
    cursor.execute("SELECT * FROM documents;")
    documents = cursor.fetchall()
    print("Documents table:")
    if documents:
        for doc in documents:
            print(f"ID: {doc[0]}, User ID: {doc[1]}, Created: {doc[5]}")
            if doc[2]:  # original_text
                print(f"  Original text: {doc[2][:100]}...")
            if doc[3]:  # simplified_text
                print(f"  Simplified text: {doc[3][:100]}...")
            if doc[4]:  # translated_text
                print(f"  Translated text: {doc[4][:100]}...")
            print()
    else:
        print("No documents found")
    
    conn.close()

if __name__ == "__main__":
    view_database()