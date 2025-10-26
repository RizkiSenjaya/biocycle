import firebase_admin
from firebase_admin import credentials, db
import random
import time
from datetime import datetime

cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'  # ganti sesuai project kamu
})

ref = db.reference('BioCycle/sensor')

motor_on_time = None
motor_status = "OFF"
solenoid_valve = "OFF"

while True:
    suhu = round(random.uniform(25, 35), 2)
    kelembapan = round(random.uniform(50, 80), 2)
    mq = round(random.uniform(100, 400), 2)

    # Logika hubungan motor AC dan solenoid valve
    if motor_status == "ON":
        if motor_on_time and (time.time() - motor_on_time) >= 180:  # 3 menit
            solenoid_valve = "ON"
            motor_status = "OFF"
            motor_on_time = None
    else:
        if random.choice([True, False]):  # 50% kemungkinan nyala lagi
            motor_status = "ON"
            solenoid_valve = "OFF"
            motor_on_time = time.time()

    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": suhu,
        "humidity": kelembapan,
        "mq": mq,
        "motor_status": motor_status,
        "solenoid_valve": solenoid_valve
    }

    ref.set(data)
    print(f"Sent to Firebase: {data}")
    time.sleep(5)
