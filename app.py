from flask import Flask, render_template, jsonify, redirect, url_for, request, session
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
import requests  # untuk verifikasi token ke Google

app = Flask(__name__)
app.secret_key = "biocycle_secret_key"

# Konfigurasi koneksi database
dbconfig = {
    "user": "root",
    "password": "",
    "host": "localhost",
    "database": "biocycle"
}

connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **dbconfig)

# ==============================================
# LOGIN ROUTE (GOOGLE)
# ==============================================
@app.route('/login_google', methods=['POST'])
def login_google():
    """Terima ID Token dari frontend dan verifikasi ke Firebase"""
    try:
        data = request.get_json()
        id_token = data.get('idToken')

        # Verifikasi token ke Google
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=AIzaSyB393qWoErLcFOhTd7MMpl_93iVUKynIF0"
        response = requests.post(verify_url, json={"idToken": id_token})
        user_info = response.json()

        # Jika gagal verifikasi
        if 'users' not in user_info:
            return jsonify({"success": False, "message": "Token tidak valid."}), 401

        # Ambil info user dari Firebase
        user_email = user_info['users'][0]['email']
        user_name = user_info['users'][0].get('displayName', 'User')

        # Simpan sesi login
        session['logged_in'] = True
        session['email'] = user_email
        session['name'] = user_name

        print(f"✅ Login berhasil: {user_email}")
        return jsonify({"success": True, "redirect": "/dashboard"})

    except Exception as e:
        print("❌ Error login_google:", e)
        return jsonify({"success": False, "message": str(e)}), 500

# ==============================================
# ROUTES UTAMA
# ==============================================
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==============================================
# DATA SENSOR
# ==============================================
@app.route('/get_latest_data')
def get_latest_data():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1;")
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        if data:
            return jsonify(data)
        else:
            return jsonify({"message": "No data found"}), 404
    except Exception as e:
        print("❌ Error ambil data terbaru:", e)
        return jsonify({"error": str(e)}), 500


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
