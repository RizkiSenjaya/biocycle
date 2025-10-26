from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import firebase_admin
from firebase_admin import credentials, auth, db
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === Inisialisasi Firebase ===
cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://biocycle-2a810-default-rtdb.asia-southeast1.firebasedatabase.app'  # ganti sesuai project Firebase kamu
})


# ========== ROUTES ==========

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login_email', methods=['POST'])
def login_email():
    email = request.form['email']
    password = request.form['password']
    # Sementara login manual
    session['user'] = email
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', user=session['user'])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# API untuk ambil data sensor dari Firebase
@app.route('/get_sensor_data')
def get_sensor_data():
    ref = db.reference('BioCycle/sensor')
    data = ref.get()
    if not data:
        return jsonify({'error': 'No data available'}), 404
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True)
