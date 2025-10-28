from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, auth, db
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# --- Firebase Initialization ---
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-adminsdk.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://biocycle-2a810-default-rtdb.firebaseio.com/'
    })

# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect(url_for('login'))


# ---------------- LOGIN ----------------
@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login_email', methods=['POST'])
def login_email():
    email = request.form['email']
    password = request.form['password']

    if not email or not password:
        return render_template('login.html', error="Email dan password wajib diisi.")

    # Hanya simulasi — validasi seharusnya dilakukan di sisi Firebase client
    session['user'] = {'email': email}
    return redirect(url_for('dashboard'))


@app.route('/login_google', methods=['POST'])
def login_google():
    """Login via Google (token dikirim dari front-end Firebase)"""
    try:
        data = request.get_json(force=True)
        id_token = data.get('idToken')

        decoded_token = auth.verify_id_token(id_token)
        email = decoded_token.get('email')
        name = decoded_token.get('name', 'User')
        uid = decoded_token.get('uid')

        # Simpan user ke session
        session['user'] = {
            'uid': uid,
            'email': email,
            'name': name
        }

        return jsonify({'success': True})
    except Exception as e:
        print("Error Google login:", e)
        return jsonify({'success': False, 'error': str(e)}), 400


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=user)


# Endpoint API yang dipanggil JS dashboard
@app.route('/get_data', methods=['GET'])
def get_data():
    """Mengambil 10 data terakhir dari Realtime Database"""
    try:
        ref = db.reference('SensorData')
        data = ref.order_by_key().limit_to_last(10).get()

        if not data:
            return jsonify([])

        result = []
        for key, val in data.items():
            result.append({
                'timestamp': val.get('timestamp'),
                'temperature': val.get('temperature'),
                'humidity': val.get('humidity'),
                'fanStatus': val.get('fanStatus'),
                'gas': val.get('gas'),
                'solenoid': val.get('solenoid')
            })

        # Urutkan berdasarkan waktu (data lama ke baru)
        result.sort(key=lambda x: x.get('timestamp', ''))
        return jsonify(result)
    except Exception as e:
        print("Error get_data:", e)
        return jsonify([])


# ---------------- PROFILE ----------------
@app.route('/profile')
def profile():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    
    try:
        users = [u for u in auth.list_users().iterate_all()]
        user_data = []
        for u in users:
            user_data.append({
                'uid': u.uid,
                'email': u.email,
                'display_name': u.display_name,
                'email_verified': u.email_verified
            })
    except Exception as e:
        print("Error fetching users:", e)
        user_data = []

    return render_template('profile.html', user=user, users=user_data)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


# ---------------- ERROR HANDLER ----------------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True)
