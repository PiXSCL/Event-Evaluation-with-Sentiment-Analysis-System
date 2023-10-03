from datetime import datetime
from email.policy import default
from flask import Flask, render_template, request, flash, redirect, url_for, session
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

    forms = db.relationship('Form', backref='user', lazy=True)

class Form(db.Model):  
    formid = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))  
    description = db.Column(db.String(255)) 
    date_created = db.Column(db.DateTime,default=datetime.now)
    form_data = db.Column(db.TEXT)

    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Question(db.Model):
    questionid = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(255))
    question_type = db.Column(db.String(50))  # E.g., "Open-Ended", "Multiple Choices", "CheckBox"
    is_required = db.Column(db.Boolean, default=False)

    formid = db.Column(db.Integer, db.ForeignKey('form.formid'), nullable=False)

class Choice(db.Model):
    choice_id = db.Column(db.Integer, primary_key=True)
    choice_text = db.Column(db.String(255), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.questionid'), nullable=False)

    def __init__(self, choice_text, question_id):
        self.choice_text = choice_text
        self.question_id = question_id


def retrieve_saved_html(form_id):
    try:
        form = Form.query.get(form_id)

        if form:
            return form.form_data
        else:
            return None
    except Exception as e:
        print(str(e))
        return None

@app.route('/')
@app.route('/login')
def login():
    session.clear()
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login_post():
    email = request.form['email']
    password = request.form['password']

    user = User.query.filter_by(email=email, password=password).first()

    if user:
        # Store user's email and ID in the session
        session['user_email'] = user.email
        session['user_id'] = user.id

        # Redirect to the user's home page
        return redirect(url_for('home'))
    else:
        return '<script>alert("Invalid account. Please check the email and password you entered."); window.location.href="/login";</script>'

def fetch_form_data(user_id):
    form_data = Form.query.with_entities(Form.formid, Form.title, Form.date_created).filter_by(userid=user_id).order_by(Form.date_created.desc()).all()
    return form_data

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
           return '<script>alert("Email already exists. Please use a different email."); window.location.href="/signup";</script>'
        else:
            new_user = User(name=name, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            return '<script>alert("Signup successful!"); window.location.href="/login";</script>'

    return render_template('signup.html')

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)

@app.route('/home')
def home():
    user_email = session.get('user_email', None)
    user_id = session.get('user_id', None)

    if user_email:
        form_data = fetch_form_data(user_id)
        return render_template('home.html', user_email=user_email, form_data=form_data)
    else:
        return redirect(url_for('login'))

@app.route('/questions')
def questions():
    user_id = session.get('user_id', None)

    if user_id:
        return render_template('questions.html', user_id=user_id)
    else:
        return redirect(url_for('login'))

@app.route('/save_form', methods=['POST'])
def save_form():
    if request.method == 'POST':
        # Get the HTML content of the page (the entire form)
        form_data = request.form['html_content']  # Make sure to use the appropriate field name

        # Get the user ID of the currently logged-in user from the session
        user_id = session.get('user_id')  # Assuming you store user ID in the session

        # Get the title and description from the form
        title = request.form['title']
        description = request.form['description']

        # Create a new instance of the Form model with all the data
        new_form = Form(
            form_data=form_data,
            title=title,
            description=description,
            userid=user_id
        )
        
        # Save the new_form instance to the database
        db.session.add(new_form)
        db.session.commit()

        # Redirect to a success page or any other page you want
        return redirect(url_for('questions'))

    # Handle other cases or render templates as needed
    return render_template('questions.html')

@app.route('/edit_form/<string:form_id>')
def edit_form(form_id):
    # Retrieve the saved HTML content from the database based on form_id
    saved_html_content = retrieve_saved_html(form_id)  # Replace with your database retrieval logic

    return render_template('edit_form.html', saved_html_content=saved_html_content)