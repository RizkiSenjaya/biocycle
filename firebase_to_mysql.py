import firebase_admin
from firebase_admin import credentials, db
import mysql.connector
import time

cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'  # ganti dengan URL kamu
})

# Koneksi ke MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",  # sesuaikan
    password="",  # sesuaikan
    database="biocycle"
)
cursor = conn.cursor()

def insert_to_mysql(data):
    query = """
        INSERT INTO sensor_data (timestamp, suhu, kelembapan, mq, motor, solenoid)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (
        data.get('timestamp'),
        data.get('suhu'),
        data.get('kelembapan'),
        data.get('mq'),
        data.get('motor'),
        data.get('solenoid')
    )
    cursor.execute(query, values)
    conn.commit()

def main():
    ref = db.reference('/sensor')
    last_data = None
    while True:
        data = ref.get()
        if data and data != last_data:
            insert_to_mysql(data)
            last_data = data
            print("Data masuk ke MySQL:", data)
        time.sleep(5)

if __name__ == "__main__":
    main()
