import mysql.connector as connector

def db():
    try:
        conn = connector.connect(
            host="localhost",
            database="drone",
            user="root",
            password=""
        )
        
        cursor = conn.cursor(dictionary=True)
        
        return (conn, cursor)
    except connector.Error as e:
        print(f'[database] Error while connecting to database: {e}')
        raise e
