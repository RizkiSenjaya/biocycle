from flask import Flask, render_template, jsonify, redirect, url_for, request, session, send_file
from firebase_admin import credentials, auth, db
import firebase_admin
import requests
import mysql.connector
from mysql.connector import pooling
import os
import datetime
import pandas as pd
from fpdf import FPDF
import io

# CORS support (optional - install dengan: pip install flask-cors)
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("⚠️  flask-cors tidak terinstall. Install dengan: pip install flask-cors")

app = Flask(__name__)
app.secret_key = "biocycle_secret_key"

# Enable CORS untuk mengatasi masalah koneksi frontend-backend
if CORS_AVAILABLE:
    CORS(app)
else:
    # Manual CORS headers jika flask-cors tidak tersedia
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

# ========================
# KONFIGURASI FIREBASE
# ========================
firebase_cred_path = os.path.join(os.getcwd(), "firebase-adminsdk.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_cred_path)
    # Inisialisasi dengan databaseURL untuk Realtime Database
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'
    })

FIREBASE_API_KEY = "AIzaSyB393qWoErLcFOhTd7MMpl_93iVUKynIF0"

# ========================
# KONFIGURASI DATABASE (MySQL)
# ========================
dbconfig = {
    "user": "root",
    "password": "",
    "host": "localhost",
    "database": "biocycle"
}
connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **dbconfig)


# ========================
# HELPER FUNCTIONS - RBAC
# ========================
def get_user_role(email):
    """Mengambil role user dari database"""
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role, status FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return result.get('role'), result.get('status')
        return None, None
    except Exception as e:
        print(f"❌ Error get user role: {e}")
        return None, None


def require_login(f):
    """Decorator untuk memastikan user sudah login"""
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def require_admin(f):
    """Decorator untuk memastikan user adalah admin"""
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        user_role, user_status = get_user_role(session.get('email'))
        if user_role != 'admin' or user_status != 'approved':
            return render_template('error.html', 
                                 error="Akses Ditolak", 
                                 message="Hanya Admin yang dapat mengakses halaman ini."), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def require_approved(f):
    """Decorator untuk memastikan user sudah approved"""
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        user_role, user_status = get_user_role(session.get('email'))
        if user_status != 'approved':
            return render_template('error.html',
                                 error="Akun Belum Disetujui",
                                 message="Akun Anda masih menunggu persetujuan dari Admin."), 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


# ========================
# ROUTES AUTH
# ========================
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


# 🔹 REGISTER
@app.route('/register_user', methods=['POST'])
def register_user():
    email = request.form['email']
    password = request.form['password']
    role = request.form.get('role', 'peternak')  # Default peternak
    
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()
        if "error" in data:
            return render_template('register.html', error=f"Gagal daftar: {data['error']['message']}")
        
        # Simpan ke database MySQL dengan status 'approved' langsung
        uid = data.get('localId')
        try:
            conn = connection_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (uid, email, name, role, status) 
                VALUES (%s, %s, %s, %s, 'approved')
            """, (uid, email, email.split('@')[0].capitalize(), role))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ User {email} terdaftar sebagai {role} dengan status approved")
        except mysql.connector.IntegrityError:
            # User sudah ada, update role dan status
            conn = connection_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET role = %s, status = 'approved' WHERE email = %s
            """, (role, email))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as db_error:
            print(f"⚠️ Error simpan ke database: {db_error}")
        
        return render_template('login.html', success="Pendaftaran berhasil! Silakan login untuk masuk ke dashboard.")
    except Exception as e:
        return render_template('register.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN Email/Password
@app.route('/login_email', methods=['POST'])
def login_email():
    email = request.form['email']
    password = request.form['password']
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()
        if "error" in data:
            return render_template('login.html', error=f"Gagal login: {data['error']['message']}")
        
        # Ambil role dan status dari database
        user_role, user_status = get_user_role(email)
        
        # Jika user belum ada di database, buat sebagai peternak dengan status approved
        if user_role is None:
            try:
                conn = connection_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (uid, email, name, role, status) 
                    VALUES (%s, %s, %s, 'peternak', 'approved')
                """, (data.get('localId'), email, email.split('@')[0].capitalize()))
                conn.commit()
                cursor.close()
                conn.close()
                user_role, user_status = 'peternak', 'approved'
            except Exception as db_error:
                print(f"⚠️ Error simpan user ke database: {db_error}")
                user_role, user_status = 'peternak', 'approved'
        
        session['logged_in'] = True
        session['email'] = data.get('email')
        session['idToken'] = data.get('idToken')
        session['photo'] = "/static/default-avatar.png"
        session['name'] = data.get('email').split('@')[0].capitalize()
        session['role'] = user_role
        session['status'] = user_status
        
        # Semua user langsung masuk ke dashboard tanpa perlu approval
        print(f"✅ Login berhasil: {email} ({user_role})")
        return redirect(url_for('dashboard'))
    except requests.exceptions.RequestException as e:
        print(f"❌ Error koneksi Firebase: {e}")
        return render_template('login.html', error="Gagal koneksi ke server Firebase. Pastikan koneksi internet aktif.")
    except Exception as e:
        print(f"❌ Error login: {e}")
        return render_template('login.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN Google
@app.route('/login_google', methods=['POST'])
def login_google():
    try:
        data = request.get_json()
        id_token = data.get('idToken')
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
        response = requests.post(verify_url, json={"idToken": id_token})
        user_info = response.json()

        if 'users' not in user_info:
            return jsonify({"success": False, "message": "Token tidak valid."}), 401

        user_data = user_info['users'][0]
        user_email = user_data.get('email')
        user_name = user_data.get('displayName', user_email.split('@')[0] if user_email else 'User')
        user_photo = user_data.get('photoUrl', '/static/default-avatar.png')
        user_uid = user_data.get('localId')

        # Ambil role dan status dari database
        user_role, user_status = get_user_role(user_email)
        
        # Jika user belum ada di database, buat akun baru dengan role sesuai aturan
        if user_role is None:
            # Tentukan role berdasarkan email
            # Jika email = superadmin@gmail.com → role = 'admin'
            # Semua email lainnya → role = 'peternak'
            if user_email and user_email.lower() == 'superadmin@gmail.com':
                assigned_role = 'admin'
            else:
                assigned_role = 'peternak'
            
            try:
                conn = connection_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (uid, email, name, role, status) 
                    VALUES (%s, %s, %s, %s, 'approved')
                """, (user_uid, user_email, user_name, assigned_role))
                conn.commit()
                cursor.close()
                conn.close()
                user_role, user_status = assigned_role, 'approved'
                print(f"✅ User baru dibuat: {user_email} dengan role {assigned_role}")
            except Exception as db_error:
                print(f"⚠️ Error simpan user ke database: {db_error}")
                # Fallback: tetap gunakan role yang sudah ditentukan
                user_role, user_status = assigned_role, 'approved'
        else:
            # User sudah ada, gunakan role yang sudah ada di database
            # Pastikan status selalu 'approved' untuk menghindari error login
            if user_status != 'approved':
                try:
                    conn = connection_pool.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET status = 'approved' WHERE email = %s", (user_email,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    user_status = 'approved'
                    print(f"✅ Status user {user_email} diupdate menjadi 'approved'")
                except Exception as db_error:
                    print(f"⚠️ Error update status user: {db_error}")
                    # Tetap set status ke approved untuk session
                    user_status = 'approved'

        # Set session dengan role dan status yang benar (sebelum mengirim response)
        session['logged_in'] = True
        session['email'] = user_email
        session['name'] = user_name
        session['photo'] = user_photo
        session['role'] = user_role
        session['status'] = user_status

        # Semua user langsung masuk ke dashboard tanpa perlu approval
        print(f"✅ Login berhasil: {user_email} (role: {user_role}, status: {user_status})")
        return jsonify({
            "success": True, 
            "redirect": "/dashboard",
            "role": user_role,
            "status": user_status
        })
    except requests.exceptions.RequestException as e:
        print(f"❌ Error koneksi Firebase (Google login): {e}")
        return jsonify({"success": False, "message": "Gagal koneksi ke server Firebase. Pastikan koneksi internet aktif."}), 500
    except Exception as e:
        print(f"❌ Error login_google: {e}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan pada server: {str(e)}"}), 500


# ========================
# HALAMAN DASHBOARD, PROFILE, MACHINE LEARNING, EXPORT
# ========================
@app.route('/dashboard')
@require_login
def dashboard():
    return render_template('dashboard.html', user=session)


@app.route('/profile')
@require_login
def profile():

    users = []
    try:
        for u in auth.list_users().iterate_all():
            if hasattr(u, "user_metadata") and hasattr(u.user_metadata, "creation_timestamp"):
                ts = int(u.user_metadata.creation_timestamp)
                created_str = datetime.datetime.fromtimestamp(ts / 1000).strftime('%d %B %Y')
            else:
                created_str = "-"
            users.append({
                "uid": u.uid,
                "email": u.email or "-",
                "name": u.display_name or (u.email.split('@')[0] if u.email else "-"),
                "created_at": created_str
            })
    except Exception as e:
        print("❌ Error ambil user Firebase:", e)
    return render_template('profile.html', user=session, users=users)


@app.route('/machine_learning')
@require_login
def machine_learning():
    return render_template('machine_learning.html', user=session)


@app.route('/mesin_analisis')
@require_login
def mesin_analisis():
    return render_template('mesin_analisis.html', user=session)


@app.route('/kontrol_alat')
@require_login
@require_admin
def kontrol_alat():
    return render_template('kontrol_alat.html', user=session)


@app.route('/edukasi')
@require_login
def edukasi():
    return render_template('edukasi.html', user=session)


@app.route('/export_file')
@require_login
def export_file():
    return render_template('export_file.html', user=session)


@app.route('/stok')
@require_login
def stok():
    return render_template('stok.html', user=session)


# ========================
# LOGOUT
# ========================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ========================
# DATA SENSOR API
# ========================
@app.route('/get_sensor_history')
@require_login
def get_sensor_history():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM (SELECT * FROM sensor_data ORDER BY id DESC LIMIT 10) sub ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        print("❌ Error ambil riwayat data:", e)
        return jsonify({'error': str(e)}), 500


@app.route('/get_ml_data')
@require_login
def get_ml_data():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM (SELECT * FROM sensor_data ORDER BY id DESC LIMIT 10) sub ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        for r in rows:
            temp = r['temperature']
            mq = r['mq']
            if temp < 33 and mq < 400:
                r['kompos'] = 'A'; r['biogas'] = 'A'
            elif temp < 36 and mq < 500:
                r['kompos'] = 'B'; r['biogas'] = 'B'
            else:
                r['kompos'] = 'C'; r['biogas'] = 'C'
        return jsonify(rows)
    except Exception as e:
        print("❌ Error ambil data ML:", e)
        return jsonify({'error': str(e)}), 500


# ========================
# EXPORT DATA SENSOR (EXCEL & PDF)
# ========================
@app.route('/export_excel')
@require_login
def export_excel():
    try:
        conn = connection_pool.get_connection()
        query = "SELECT * FROM sensor_data ORDER BY id DESC"
        df = pd.read_sql(query, conn)
        conn.close()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='SensorData')
        output.seek(0)

        return send_file(output, as_attachment=True,
                         download_name='sensor_data.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        print("❌ Error export Excel:", e)
        return jsonify({'error': str(e)}), 500


@app.route('/export_pdf')
@require_login
def export_pdf():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(200, 10, txt="Laporan Data Sensor BioCycle", ln=True, align='C')
        pdf.ln(8)

        pdf.set_font("Arial", "B", 10)
        headers = ["No", "Waktu", "Suhu", "Kelembapan", "Tekanan", "Gas", "Motor", "Solenoid"]
        col_widths = [10, 35, 20, 25, 20, 20, 25, 25]

        for h, w in zip(headers, col_widths):
            pdf.cell(w, 8, h, 1)
        pdf.ln()

        pdf.set_font("Arial", size=9)
        for i, r in enumerate(rows, start=1):
            pdf.cell(10, 8, str(i), 1)
            pdf.cell(35, 8, str(r['timestamp']), 1)
            pdf.cell(20, 8, f"{r['temperature']:.2f}", 1)
            pdf.cell(25, 8, f"{r['humidity']:.2f}", 1)
            pdf.cell(20, 8, f"{r['pressure']:.2f}", 1)
            pdf.cell(20, 8, f"{r['mq']:.2f}", 1)
            pdf.cell(25, 8, r['motor_status'], 1)
            pdf.cell(25, 8, r['solenoid_valve'], 1)
            pdf.ln()

        # ✅ cara yang benar: hasilkan PDF sebagai bytes
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='sensor_data.pdf'
        )

    except Exception as e:
        print("❌ Error export PDF:", e)
        return jsonify({"error": str(e)}), 500


# ========================
# ADMIN ROUTES (HANYA UNTUK ADMIN)
# ========================
@app.route('/admin')
@require_login
@require_admin
def admin_dashboard():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin.html', user=session, users=users)
    except Exception as e:
        print(f"❌ Error admin dashboard: {e}")
        return render_template('error.html', error="Error", message=str(e)), 500


@app.route('/admin/approve_user', methods=['POST'])
@require_login
@require_admin
def approve_user():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        action = data.get('action')  # 'approve' or 'reject'
        
        if action not in ['approve', 'reject']:
            return jsonify({'success': False, 'message': 'Action tidak valid'}), 400
        
        status = 'approved' if action == 'approve' else 'rejected'
        
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = %s WHERE id = %s", (status, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'User berhasil di{action}'})
    except Exception as e:
        print(f"❌ Error approve user: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/update_role', methods=['POST'])
@require_login
@require_admin
def update_role():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if new_role not in ['admin', 'peternak']:
            return jsonify({'success': False, 'message': 'Role tidak valid'}), 400
        
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Role user berhasil diubah menjadi {new_role}'})
    except Exception as e:
        print(f"❌ Error update role: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/create_user', methods=['POST'])
@require_login
@require_admin
def create_user():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        role = data.get('role', 'peternak')
        
        if not email or not password or not name:
            return jsonify({'success': False, 'message': 'Data tidak lengkap'}), 400
        
        # Buat user di Firebase
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        firebase_data = response.json()
        
        if "error" in firebase_data:
            return jsonify({'success': False, 'message': firebase_data['error']['message']}), 400
        
        uid = firebase_data.get('localId')
        
        # Simpan ke database
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (uid, email, name, role, status) 
            VALUES (%s, %s, %s, %s, 'approved')
        """, (uid, email, name, role))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'User berhasil dibuat'})
    except Exception as e:
        print(f"❌ Error create user: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/laporan')
@require_login
@require_admin
def admin_laporan():
    return render_template('admin_laporan.html', user=session)


# ========================
# AMBIL SEMUA USER FIREBASE
# ========================
@app.route('/get_all_users')
@require_login
def get_all_users():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(users)
    except Exception as e:
        print("❌ Error ambil user (API):", e)
        return jsonify([]), 500


# ========================
# KONTROL ALAT (SOLENOID & MOTOR)
# ========================

# Endpoint terpadu untuk kontrol alat (sesuai struktur Firebase /BioCycle/sensor/)
@app.route('/control', methods=['POST'])
@require_login
def control_device():
    """
    Endpoint terpadu untuk mengontrol motor_status dan solenoid_valve
    Menerima: { "device_id": "motor_status" atau "solenoid_valve", "status": "ON" atau "OFF" }
    Menulis ke: /BioCycle/sensor/[device_id]
    """
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        status = data.get('status')
        
        # Validasi input
        if not device_id or not status:
            return jsonify({'success': False, 'message': 'Parameter device_id dan status diperlukan'}), 400
        
        if device_id not in ['motor_status', 'solenoid_valve']:
            return jsonify({'success': False, 'message': 'Device ID tidak valid. Harus motor_status atau solenoid_valve'}), 400
        
        if status not in ['ON', 'OFF']:
            return jsonify({'success': False, 'message': 'Status tidak valid. Harus ON atau OFF'}), 400
        
        # Update data di Firebase Realtime Database pada path /BioCycle/sensor/
        sensor_ref = db.reference('/BioCycle/sensor')
        updates = {
            device_id: status,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        sensor_ref.update(updates)
        
        # Tandai sebagai kontrol manual di /BioCycle/control
        control_ref = db.reference(f'BioCycle/control/{device_id}')
        control_ref.set({
            'status': status,
            'manual': True,  # Tandai sebagai kontrol manual
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        print(f"✅ {device_id} berhasil diubah menjadi {status} (MANUAL)")
        return jsonify({
            'success': True, 
            'message': f'{device_id} berhasil diubah menjadi {status}.'
        })
        
    except Exception as e:
        print(f"❌ Error kontrol device: {e}")
        return jsonify({'success': False, 'message': f'Terjadi kesalahan pada server saat mengontrol alat: {str(e)}'}), 500


@app.route('/control_solenoid', methods=['POST'])
@require_login
def control_solenoid():
    """
    Endpoint untuk kontrol solenoid valve (backward compatibility)
    Menulis ke /BioCycle/sensor/solenoid_valve
    """
    try:
        data = request.get_json()
        solenoid_id = data.get('solenoid')
        status = data.get('status')
        
        if not solenoid_id or not status:
            return jsonify({'success': False, 'message': 'Parameter tidak lengkap'}), 400
        
        # Update ke Firebase pada path /BioCycle/sensor/solenoid_valve
        sensor_ref = db.reference('/BioCycle/sensor')
        updates = {
            'solenoid_valve': status,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        sensor_ref.update(updates)
        
        print(f"✅ Solenoid {solenoid_id} diubah menjadi {status}")
        return jsonify({'success': True, 'message': f'Solenoid {solenoid_id} berhasil diubah'})
        
    except Exception as e:
        print(f"❌ Error kontrol solenoid: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/control_motor', methods=['POST'])
@require_login
def control_motor():
    """
    Endpoint untuk kontrol motor (backward compatibility)
    Menulis ke /BioCycle/sensor/motor_status
    """
    try:
        data = request.get_json()
        action = data.get('action')
        speed = data.get('speed')
        duration = data.get('duration')
        
        if action not in ['start', 'stop']:
            return jsonify({'success': False, 'message': 'Action tidak valid'}), 400
        
        # Update ke Firebase pada path /BioCycle/sensor/motor_status
        sensor_ref = db.reference('/BioCycle/sensor')
        motor_status = 'ON' if action == 'start' else 'OFF'
        
        updates = {
            'motor_status': motor_status,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if action == 'start':
            if not speed or not duration:
                return jsonify({'success': False, 'message': 'Speed dan duration diperlukan untuk start'}), 400
            # Simpan speed dan duration di control jika diperlukan
            control_ref = db.reference('BioCycle/control/motor')
            control_ref.set({
                'speed': float(speed),
                'duration': float(duration),
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        sensor_ref.update(updates)
        
        print(f"✅ Motor {action} - Status: {motor_status}")
        return jsonify({'success': True, 'message': f'Motor berhasil di{action}'})
        
    except Exception as e:
        print(f"❌ Error kontrol motor: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/get_control_status')
@require_login
def get_control_status():
    """
    Mengambil status kontrol dari Firebase
    Membaca dari /BioCycle/sensor/ untuk motor_status dan solenoid_valve
    """
    try:
        # Baca dari path sensor
        sensor_ref = db.reference('/BioCycle/sensor')
        sensor_data = sensor_ref.get()
        
        # Ambil status motor dan solenoid dari sensor
        motor_status = sensor_data.get('motor_status', 'OFF') if sensor_data else 'OFF'
        solenoid_valve = sensor_data.get('solenoid_valve', 'OFF') if sensor_data else 'OFF'
        
        # Baca detail motor dari control jika ada
        control_motor_ref = db.reference('BioCycle/control/motor')
        motor_control_data = control_motor_ref.get()
        
        motor = {
            'status': motor_status,
            'speed': motor_control_data.get('speed', 0) if motor_control_data else 0,
            'duration': motor_control_data.get('duration', 0) if motor_control_data else 0
        }
        
        # Untuk backward compatibility, simulasikan solenoid A, B, C, D
        # (dalam implementasi nyata, Anda mungkin perlu mapping yang berbeda)
        solenoids = {
            'solenoid_A': solenoid_valve,
            'solenoid_B': solenoid_valve,
            'solenoid_C': solenoid_valve,
            'solenoid_D': solenoid_valve
        }
        
        return jsonify({
            'success': True,
            'solenoids': solenoids,
            'motor': motor
        })
        
    except Exception as e:
        print(f"❌ Error get control status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========================
# MAIN
# ========================
if __name__ == '__main__':
    app.run(debug=True)
