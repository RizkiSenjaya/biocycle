from flask import Flask, render_template, jsonify, redirect, url_for, request, session
import requests
import mysql.connector
from mysql.connector import pooling

app = Flask(__name__)
app.secret_key = "biocycle_secret_key"

# Firebase Web API Key
FIREBASE_API_KEY = "AIzaSyB393qWoErLcFOhTd7MMpl_93iVUKynIF0"

# Konfigurasi koneksi database untuk sensor
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


# 🔹 REGISTER via Firebase
@app.route('/register_user', methods=['POST'])
def register_user():
    email = request.form['email']
    password = request.form['password']

    try:
        # API endpoint Firebase untuk membuat akun email/password
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()

        if "error" in data:
            message = data["error"]["message"]
            return render_template('register.html', error=f"Gagal daftar: {message}")

        # Jika sukses, arahkan ke halaman login
        return render_template('login.html', success="Pendaftaran berhasil! Silakan login.")

    except Exception as e:
        return render_template('register.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN via Firebase
@app.route('/login_email', methods=['POST'])
def login_email():
    email = request.form['email']
    password = request.form['password']

    try:
        # API endpoint Firebase untuk login email/password
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()

        if "error" in data:
            message = data["error"]["message"]
            return render_template('login.html', error=f"Gagal login: {message}")

        # Simpan sesi user
        session['logged_in'] = True
        session['email'] = data.get('email')
        session['idToken'] = data.get('idToken')
        session['photo'] = "/static/default-avatar.png"
        session['name'] = data.get('email').split('@')[0].capitalize()

        return redirect(url_for('dashboard'))

    except Exception as e:
        return render_template('login.html', error=f"Terjadi kesalahan: {e}")


# 🔹 LOGIN dengan Google
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
        user_email = user_data['email']
        user_name = user_data.get('displayName', 'User')
        user_photo = user_data.get('photoUrl', '/static/default-avatar.png')

        # Simpan ke session
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
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('profile.html', user=session)


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


if __name__ == '__main__':
    app.run(debug=True)
