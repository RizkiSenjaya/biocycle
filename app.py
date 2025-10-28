from flask import Flask, render_template, jsonify, redirect, url_for, request, session
from firebase_admin import credentials, auth
import firebase_admin
import requests
import mysql.connector
from mysql.connector import pooling
import os
import datetime

app = Flask(__name__)
app.secret_key = "biocycle_secret_key"

# ========================
# KONFIGURASI FIREBASE
# ========================
# Pastikan file firebase-adminsdk.json ada di root project (sesuai struktur kamu)
firebase_cred_path = os.path.join(os.getcwd(), "firebase-adminsdk.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_cred_path)
    firebase_admin.initialize_app(cred)

# Firebase Web API Key (dipakai untuk REST sign-in / sign-up)
FIREBASE_API_KEY = "AIzaSyB393qWoErLcFOhTd7MMpl_93iVUKynIF0"

# ========================
# KONFIGURASI DATABASE (MySQL) - tetap seperti sebelumnya
# ========================
dbconfig = {
    "user": "root",
    "password": "",
    "host": "localhost",
    "database": "biocycle"
}
connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **dbconfig)


# ========================
# ROUTES AUTH
# ========================
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


# 🔹 REGISTER via Firebase REST API
@app.route('/register_user', methods=['POST'])
def register_user():
    email = request.form['email']
    password = request.form['password']

    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()

        if "error" in data:
            message = data["error"]["message"]
            return render_template('register.html', error=f"Gagal daftar: {message}")

        return render_template('login.html', success="Pendaftaran berhasil! Silakan login.")

    except Exception as e:
        return render_template('register.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN via Firebase REST API
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
            message = data["error"]["message"]
            return render_template('login.html', error=f"Gagal login: {message}")

        session['logged_in'] = True
        session['email'] = data.get('email')
        session['idToken'] = data.get('idToken')
        session['photo'] = "/static/default-avatar.png"
        session['name'] = data.get('email').split('@')[0].capitalize()

        return redirect(url_for('dashboard'))

    except Exception as e:
        return render_template('login.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN dengan Google (dipanggil oleh frontend yang mengirim idToken)
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

        session['logged_in'] = True
        session['email'] = user_email
        session['name'] = user_name
        session['photo'] = user_photo

        print(f"✅ Login berhasil: {user_email}")
        return jsonify({"success": True, "redirect": "/dashboard"})

    except Exception as e:
        print("❌ Error login_google:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# ========================
# HALAMAN LAIN
# ========================
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', user=session)


@app.route('/profile')
def profile():
    """
    Render halaman profile dan kirim daftar users ke template.
    Profile akan menampilkan session (user yang login) + daftar user Firebase (auth.list_users()).
    """
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))

    # Ambil daftar user dari Firebase Authentication
    users = []
    try:
        for u in auth.list_users().iterate_all():
            created_ts = None
            if getattr(u, "user_metadata", None) and getattr(u.user_metadata, "creation_timestamp", None):
                # creation_timestamp di firebase_admin biasanya dalam milliseconds
                try:
                    created_ts = int(u.user_metadata.creation_timestamp)
                    # ubah menjadi string readable
                    created_str = datetime.datetime.fromtimestamp(created_ts / 1000).strftime('%d %B %Y')
                except Exception:
                    created_str = str(u.user_metadata.creation_timestamp)
            else:
                created_str = "-"

            users.append({
                "uid": getattr(u, "uid", "-"),
                "email": getattr(u, "email", "-"),
                "name": getattr(u, "display_name", None) or (u.email.split('@')[0] if getattr(u, "email", None) else "-"),
                "created_at": created_str
            })
    except Exception as e:
        print("❌ Error ambil user Firebase di /profile:", e)
        # tetap lanjut render template tapi users kosong atau berisi pesan
        users = []

    return render_template('profile.html', user=session, users=users)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ========================
# DATA SENSOR
# ========================
@app.route('/get_sensor_history')
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


# ========================
# AMBIL SEMUA PENGGUNA FIREBASE (API untuk frontend jika diperlukan)
# ========================
@app.route('/get_all_users')
def get_all_users():
    if not session.get('logged_in'):
        return jsonify([]), 401

    try:
        users = []
        for u in auth.list_users().iterate_all():
            created_ts = None
            if getattr(u, "user_metadata", None) and getattr(u.user_metadata, "creation_timestamp", None):
                try:
                    created_ts = int(u.user_metadata.creation_timestamp)
                    created_str = datetime.datetime.fromtimestamp(created_ts / 1000).isoformat()
                except Exception:
                    created_str = str(u.user_metadata.creation_timestamp)
            else:
                created_str = None

            users.append({
                'uid': getattr(u, "uid", "-"),
                'email': getattr(u, "email", "-"),
                'name': getattr(u, "display_name", None) or (u.email.split('@')[0] if getattr(u, "email", None) else "-"),
                'created': created_str
            })
        return jsonify(users)
    except Exception as e:
        print("❌ Error ambil data user (API):", e)
        return jsonify([]), 500


if __name__ == '__main__':
    app.run(debug=True)
