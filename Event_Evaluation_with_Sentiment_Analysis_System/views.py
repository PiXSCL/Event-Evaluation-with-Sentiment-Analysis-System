from flask import Flask, render_template, request, flash, redirect, url_for
from Event_Evaluation_with_Sentiment_Analysis_System import app
from flask_sqlalchemy import SQLAlchemy

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:ra05182002@localhost:3306/EventDB'
app.secret_key = 'your_secret_key'  # Replace with a secret key

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

@app.route('/')
@app.route('/login')
def login():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists. Please use a different email.', 'danger')
        else:
            new_user = User(name=name, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Signup successful!', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)


