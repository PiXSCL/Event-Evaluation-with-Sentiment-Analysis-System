from flask import render_template
from Event_Evaluation_with_Sentiment_Analysis_System import app

@app.route('/')
@app.route('/login')
def login():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')


