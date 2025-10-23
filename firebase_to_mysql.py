import firebase_admin
from firebase_admin import credentials, db
import mysql.connector
from datetime import datetime
import time

cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://<YOUR_PROJECT_ID>.firebaseio.com/'
})

# Koneksi ke MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",       # ganti sesuai user MySQL kamu
    password="",       # ganti sesuai password MySQL kamu
    database="biocycle"
)
cursor = conn.cursor()

ref = db.reference('BioCycle/sensor')

def sync_data():
    data = ref.get()
    if not data:
        return

    query = """INSERT INTO sensor_data (timestamp, temperature, humidity, mq, motor_status, solenoid_valve)
               VALUES (%s, %s, %s, %s, %s, %s)"""
    values = (
        datetime.strptime(data['timestamp'], "%Y-%m-%d %H:%M:%S"),
        data['temperature'],
        data['humidity'],
        data['mq'],
        data['motor_status'],
        data['solenoid_valve']
    )
    cursor.execute(query, values)
    conn.commit()
    print(f"Data saved to MySQL: {values}")

while True:
    sync_data()
    time.sleep(5)
