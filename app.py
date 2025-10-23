from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import firebase_admin
from firebase_admin import credentials, auth
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Inisialisasi Firebase Admin SDK
cred = credentials.Certificate("firebase-adminsdk.json")  # pastikan file ini ada di folder yang sama
firebase_admin.initialize_app(cred)


# ======= ROUTES ========

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login_google', methods=['POST'])
def login_google():
    try:
        id_token = request.json.get('idToken')
        decoded_token = auth.verify_id_token(id_token)
        session['user'] = decoded_token['email']
        return jsonify({'success': True})
    except Exception as e:
        print(e)
        return jsonify({'success': False}), 401


@app.route('/login_email', methods=['POST'])
def login_email():
    email = request.form['email']
    password = request.form['password']
    # catatan: Firebase email/password login dilakukan di JS, 
    # tapi kalau mau pakai Flask backend bisa juga via REST API Firebase (optional)
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


if __name__ == '__main__':
    app.run(debug=True)
