import firebase_admin
from firebase_admin import credentials, db
import random, time, datetime

cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://console.firebase.google.com/project/biocycle-2a810/database/biocycle-2a810-default-rtdb/data/~2F'  # ganti dengan URL kamu
})

ref = db.reference('/sensor')

motor_on_time = None
motor_state = "OFF"
solenoid_state = "OFF"

while True:
    suhu = round(random.uniform(25, 35), 2)
    kelembapan = round(random.uniform(40, 70), 2)
    mq = round(random.uniform(200, 500), 2)

    # Logika sederhana motor & solenoid
    if motor_state == "OFF":
        motor_state = "ON"
        motor_on_time = time.time()
    else:
        if time.time() - motor_on_time >= 180:  # 3 menit
            motor_state = "OFF"
            solenoid_state = "ON"
        else:
            solenoid_state = "OFF"

    data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "suhu": suhu,
        "kelembapan": kelembapan,
        "mq": mq,
        "motor": motor_state,
        "solenoid": solenoid_state
    }

    ref.set(data)
    print("Data dikirim:", data)
    time.sleep(5)
