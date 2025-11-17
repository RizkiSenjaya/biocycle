import firebase_admin
from firebase_admin import credentials, db
import random
import time
import requests
from datetime import datetime

cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'
})

ref = db.reference('BioCycle/sensor')
control_ref = db.reference('BioCycle/control')

# Status kontrol
motor_on_time = None
motor_status = "OFF"
solenoid_valve = "OFF"
auto_mode = True  # Mode otomatis aktif secara default
FLASK_URL = "http://127.0.0.1:5000"  # URL Flask server

# Status kontrol manual (mutlak)
motor_manual_locked = False
solenoid_manual_locked = False
manual_lock_timeout = 300  # 5 menit

# Threshold otomatis
PRESSURE_LIMIT = 1.5
HUMIDITY_LOW = 60
HUMIDITY_HIGH = 75
TEMPERATURE_LOW = 30
TEMPERATURE_HIGH = 38


def check_manual_control():
    """Cek apakah ada kontrol manual dari Firebase."""
    try:
        control_data = control_ref.get()
        if control_data:
            manual_control = {
                'motor': None,
                'solenoid': None,
                'motor_timestamp': None,
                'solenoid_timestamp': None
            }

            # Motor
            if 'motor_status' in control_data:
                motor_control = control_data['motor_status']
                if motor_control.get('manual', False):
                    manual_control['motor'] = motor_control.get('status', 'OFF')
                    manual_control['motor_timestamp'] = motor_control.get('timestamp')

            # Solenoid
            if 'solenoid_valve' in control_data:
                solenoid_control = control_data['solenoid_valve']
                if solenoid_control.get('manual', False):
                    manual_control['solenoid'] = solenoid_control.get('status', 'OFF')
                    manual_control['solenoid_timestamp'] = solenoid_control.get('timestamp')

            if manual_control['motor'] or manual_control['solenoid']:
                return manual_control

    except Exception as e:
        print(f"⚠️ Error cek kontrol manual: {e}")

    return None


def auto_control_motor(temperature, humidity):
    """Kontrol motor otomatis."""
    global motor_status, motor_on_time

    if humidity < HUMIDITY_LOW or temperature < TEMPERATURE_LOW:
        if motor_status == "OFF":
            motor_status = "ON"
            motor_on_time = time.time()
            print(f"🔄 Motor AUTO ON (Hum={humidity} Temp={temperature})")
            return True

    if motor_status == "ON":
        if humidity > HUMIDITY_HIGH or temperature > TEMPERATURE_HIGH:
            motor_status = "OFF"
            motor_on_time = None
            print(f"⏹️ Motor AUTO OFF (Hum={humidity} Temp={temperature})")
            return True

        elif motor_on_time and (time.time() - motor_on_time >= 180):
            motor_status = "OFF"
            motor_on_time = None
            print(f"⏹️ Motor AUTO OFF (durasi 3 menit)")
            return True

    return False


def auto_control_solenoid(pressure):
    """Kontrol solenoid otomatis."""
    global solenoid_valve

    if pressure > PRESSURE_LIMIT:
        if solenoid_valve != "ON":
            solenoid_valve = "ON"
            print(f"🔓 Solenoid AUTO ON ({pressure} bar)")
            return True
    else:
        if solenoid_valve != "OFF":
            solenoid_valve = "OFF"
            print(f"🔒 Solenoid AUTO OFF ({pressure} bar)")
            return True

    return False


def send_control_to_flask(device_id, status):
    """Kirim status kontrol ke API Flask."""
    try:
        response = requests.post(
            f"{FLASK_URL}/control",
            json={"device_id": device_id, "status": status},
            timeout=2
        )
        if response.status_code == 200:
            print(f"✅ Terkirim ke Flask: {device_id} = {status}")
        else:
            print(f"⚠️ Error Flask: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Flask tidak tersedia: {e}")


# Tracking timestamp manual
last_motor_manual_time = None
last_solenoid_manual_time = None


while True:
    # Generate data dummy
    suhu = round(random.uniform(25, 38), 2)
    kelembapan = round(random.uniform(50, 80), 2)
    mq = round(random.uniform(100, 400), 2)
    pressure = round(random.uniform(1.0, 2.5), 2)

    manual_control = check_manual_control()
    current_time = time.time()

    # === MOTOR ===
    if manual_control and manual_control['motor']:
        motor_timestamp_str = manual_control.get('motor_timestamp')

        if motor_timestamp_str:
            try:
                motor_timestamp = datetime.strptime(
                    motor_timestamp_str, "%Y-%m-%d %H:%M:%S").timestamp()

                if last_motor_manual_time is None or motor_timestamp > last_motor_manual_time:
                    motor_status = manual_control['motor']
                    motor_manual_locked = True
                    last_motor_manual_time = motor_timestamp
                    print(f"👆 Motor MANUAL LOCKED: {motor_status}")

                elif motor_manual_locked:
                    motor_status = manual_control['motor']
                    print(f"👆 Motor MANUAL UPDATE: {motor_status}")

            except:
                motor_status = manual_control['motor']
                motor_manual_locked = True
                print(f"👆 Motor MANUAL LOCKED: {motor_status}")

    elif motor_manual_locked:
        # Tetap locked, tidak diubah otomatis
        pass

    else:
        try:
            mode_data = control_ref.child('mode').get()
            if mode_data:
                auto_mode = mode_data.get('auto', True)
        except:
            auto_mode = True

        if auto_mode:
            if auto_control_motor(suhu, kelembapan):
                send_control_to_flask("motor_status", motor_status)

    # === SOLENOID ===
    if manual_control and manual_control['solenoid']:
        solenoid_timestamp_str = manual_control.get('solenoid_timestamp')

        if solenoid_timestamp_str:
            try:
                solenoid_timestamp = datetime.strptime(
                    solenoid_timestamp_str, "%Y-%m-%d %H:%M:%S").timestamp()

                if last_solenoid_manual_time is None or solenoid_timestamp > last_solenoid_manual_time:
                    solenoid_valve = manual_control['solenoid']
                    solenoid_manual_locked = True
                    last_solenoid_manual_time = solenoid_timestamp
                    print(f"👆 Solenoid MANUAL LOCKED: {solenoid_valve}")

                elif solenoid_manual_locked:
                    solenoid_valve = manual_control['solenoid']
                    print(f"👆 Solenoid MANUAL UPDATE: {solenoid_valve}")

            except:
                solenoid_valve = manual_control['solenoid']
                solenoid_manual_locked = True
                print(f"👆 Solenoid MANUAL LOCKED: {solenoid_valve}")

    elif solenoid_manual_locked:
        # Tetap locked
        pass

    else:
        if auto_mode:
            if auto_control_solenoid(pressure):
                send_control_to_flask("solenoid_valve", solenoid_valve)

    # === UPDATE DATA FIREBASE ===
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": suhu,
        "humidity": kelembapan,
        "mq": mq,
        "pressure": pressure,
        "motor_status": motor_status,
        "solenoid_valve": solenoid_valve
    }

    ref.set(data)

    print(f"📊 DATA → Temp={suhu}°C | Hum={kelembapan}% | Press={pressure} bar | Motor={motor_status} | Solenoid={solenoid_valve}")

    time.sleep(5)
