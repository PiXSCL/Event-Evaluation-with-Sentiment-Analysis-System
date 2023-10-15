from datetime import datetime
from email.policy import default
from flask import Flask, render_template, request, redirect, url_for, session
from Event_Evaluation_with_Sentiment_Analysis_System import app
from flask_sqlalchemy import SQLAlchemy
import json

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:ra05182002@localhost:3306/EventDB'
app.secret_key = 'secret_key' 

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

    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Question(db.Model):
    questionid = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(255))
    question_type = db.Column(db.String(50))  
    is_required = db.Column(db.Boolean, default=False)

    formid = db.Column(db.Integer, db.ForeignKey('form.formid'), nullable=False)
    form = db.relationship('Form', backref='questions')
    choices = db.relationship('Choice', backref='question')

class Choice(db.Model):
    choice_id = db.Column(db.Integer, primary_key=True)
    choice_text = db.Column(db.String(255), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.questionid'))
    question_rel = db.relationship('Question', back_populates='choices')

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
        # Get the JSON data from the hidden input field
        html_content = request.form['html_content']
        form_data = json.loads(html_content)

        # Extract the form title and description
        title = form_data['title']
        description = form_data['description']

        # Create a new instance of the Form model and set its title and description
        new_form = Form(title=title, description=description)

        # Get the user ID of the currently logged-in user from the session
        user_id = session.get('user_id')  # Assuming you store user ID in the session

        # Set the user ID for the form
        new_form.userid = user_id

        # Create a list to store the questions associated with this form
        questions_data = []

        for key, value in request.form.items():
            if key.startswith('question_text_'):
                boxCounter = key.split('_')[2]

                is_required_key = f'is_required_{boxCounter}'
                is_required = is_required_key in request.form


        for question_data in form_data['questions']:
            question_text = question_data['question_text']
            question_type = question_data['question_type']
            is_required = is_required

            try:
                question = Question(
                    question_text=question_text,
                    question_type=question_type,
                    is_required=is_required,
                    form=new_form  # Associate the question with the form
                )
                questions_data.append(question)

                if question_type in ['Multiple Choices', 'CheckBox']:
                    # Get the choices from the question_data
                    choices_data = question_data.get('choices', [])
                    choices = []

                    for choice_data in choices_data:
                        choice_text = choice_data['choice_text']
                        choice = Choice(choice_text=choice_text)

                        # Associate choice with the question
                        choice.question = question
                        choices.append(choice)

                    # Add choices to the question
                    question.choices = choices

            except Exception as e:
                print(f"Error inserting question: {str(e)}")

        try:
            # Save the new_form instance to the database
            db.session.add(new_form)
            db.session.commit()

            # Add all questions to the session and then commit
            db.session.add_all(questions_data)
            db.session.commit()

            print("Form and choices successfully inserted into the database.")
        except Exception as e:
            print(f"Error inserting form or choices: {str(e)}")

        # Redirect to a success page or any other page you want
        return redirect(url_for('home'))

    # Handle other cases or render templates as needed
    return render_template('questions.html')

@app.route('/edit_form/<string:form_id>')
def edit_form(form_id):
    # Retrieve the saved HTML content from the database based on form_id
    saved_html_content = retrieve_saved_html(form_id)  # Replace with your database retrieval logic

    return render_template('edit_form.html', saved_html_content=saved_html_content)