import firebase_admin
from firebase_admin import credentials, db
import mysql.connector
from datetime import datetime
import time

# Inisialisasi Firebase
cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# Koneksi ke MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="biocycle"
)
cursor = conn.cursor()

ref = db.reference('BioCycle/sensor')

def sync_data():
    data = ref.get()
    if not data:
        print("⚠️ Tidak ada data di Firebase")
        return

    print("🔥 Data dari Firebase:", data)

    try:
        timestamp_str = data.get('timestamp', None)
        if not timestamp_str:
            print("⚠️ Tidak ada timestamp, data dilewati")
            return

        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        temperature = float(data.get('temperature', 0.0))
        humidity = float(data.get('humidity', 0.0))
        mq = float(data.get('mq', 0.0))
        pressure = float(data.get('pressure', 0.0))
        motor_status = data.get('motor_status', 'OFF')
        solenoid_valve = data.get('solenoid_valve', 'OFF')

        query = """INSERT INTO sensor_data 
                   (timestamp, temperature, humidity, mq, pressure, motor_status, solenoid_valve)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        values = (timestamp, temperature, humidity, mq, pressure, motor_status, solenoid_valve)
        cursor.execute(query, values)
        conn.commit()

        print(f"✅ Data saved to MySQL: {values}")

        # 🔥 Update node realtime untuk dashboard
        db.reference("BioCycle/sensor/latest").set({
            "timestamp": timestamp_str,
            "temperature": temperature,
            "humidity": humidity,
            "mq": mq,
            "pressure": pressure,
            "motor_status": motor_status,
            "solenoid_valve": solenoid_valve
        })

    except Exception as e:
        print(f"❌ Error saat menyimpan ke MySQL: {e}")

while True:
    sync_data()
    time.sleep(5)
