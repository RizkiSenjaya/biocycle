from flask import Flask, render_template, jsonify, redirect, url_for, request, session, send_file
from firebase_admin import credentials, auth
import firebase_admin
import requests
import mysql.connector
from mysql.connector import pooling
import os
import datetime
import pandas as pd
from fpdf import FPDF
import io

app = Flask(__name__)
app.secret_key = "biocycle_secret_key"

# ========================
# KONFIGURASI FIREBASE
# ========================
firebase_cred_path = os.path.join(os.getcwd(), "firebase-adminsdk.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_cred_path)
    firebase_admin.initialize_app(cred)

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
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        response = requests.post(url, json=payload)
        data = response.json()
        if "error" in data:
            return render_template('register.html', error=f"Gagal daftar: {data['error']['message']}")
        return render_template('login.html', success="Pendaftaran berhasil! Silakan login.")
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
        session['logged_in'] = True
        session['email'] = data.get('email')
        session['idToken'] = data.get('idToken')
        session['photo'] = "/static/default-avatar.png"
        session['name'] = data.get('email').split('@')[0].capitalize()
        return redirect(url_for('dashboard'))
    except Exception as e:
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
# HALAMAN DASHBOARD, PROFILE, MACHINE LEARNING, EXPORT
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
def machine_learning():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('machine_learning.html', user=session)


@app.route('/export_file')
def export_file():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return render_template('export_file.html', user=session)


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
# AMBIL SEMUA USER FIREBASE
# ========================
@app.route('/get_all_users')
def get_all_users():
    if not session.get('logged_in'):
        return jsonify([]), 401
    try:
        users = []
        for u in auth.list_users().iterate_all():
            ts = getattr(u.user_metadata, "creation_timestamp", None)
            created_str = datetime.datetime.fromtimestamp(int(ts) / 1000).isoformat() if ts else None
            users.append({
                'uid': u.uid,
                'email': u.email,
                'name': u.display_name or u.email.split('@')[0],
                'created': created_str
            })
        return jsonify(users)
    except Exception as e:
        print("❌ Error ambil user (API):", e)
        return jsonify([]), 500


# ========================
# MAIN
# ========================
if __name__ == '__main__':
    app.run(debug=True)
