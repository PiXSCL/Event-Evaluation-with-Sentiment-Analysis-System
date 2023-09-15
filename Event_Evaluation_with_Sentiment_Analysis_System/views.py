
from datetime import datetime
from flask import render_template
from Event_Evaluation_with_Sentiment_Analysis_System import app

@app.route('/')
@app.route('/login')
def login():
    return render_template(
        'index.html',
        title='Login Page',
        year=datetime.now().year,
    )


