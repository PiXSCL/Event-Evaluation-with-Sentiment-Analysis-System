from datetime import datetime
from email.policy import default
from flask import Flask, render_template, request, redirect, url_for, session
from Event_Evaluation_with_Sentiment_Analysis_System import app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from transformers import pipeline
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import json
import re

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

class Response(db.Model):
    response_id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('form.formid'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.questionid'), nullable=False)
    response = db.Column(db.String(255))
    sentiment_score = db.Column(db.Integer)
    sentiment = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.now)

    form = db.relationship('Form', backref='responses')
    question = db.relationship('Question', backref='responses')

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

@app.route('/edit_form/<int:form_id>', methods=['GET', 'POST'])
def edit_form(form_id):
    if request.method == 'GET':
        # Retrieve the form and related questions from the database
        form = Form.query.filter_by(formid=form_id).options(joinedload(Form.questions).joinedload(Question.choices)).first()

        if not form:
            # Handle form not found
            return "Form not found", 404

        return render_template('edit_form.html', form=form)

    elif request.method == 'POST':
        # Handle form submission and update here
        title = request.form.get('title')
        description = request.form.get('description')

        # Retrieve the form by ID
        form = Form.query.get(form_id)

        if form:
            # Update the form details
            form.title = title
            form.description = description

            # Clear existing questions and choices
            form.questions = []

            for i in range(1, 6):  # Adjust this based on the maximum number of questions
                question_text = request.form.get(f'question_text_{i}')
                question_type = request.form.get(f'question_type_{i}')
                is_required = request.form.get(f'is_required_{i}')

                if question_text and question_type:
                    question = Question(
                        question_text=question_text,
                        question_type=question_type,
                        is_required=is_required
                    )

                    # Add choices for Multiple Choices and CheckBox questions
                    if question_type in ('Multiple Choices', 'CheckBox'):
                        choices = request.form.getlist(f'choices_{i}')
                        for choice_text in choices:
                            if choice_text:
                                choice = Choice(choice_text=choice_text)
                                question.choices.append(choice)

                    form.questions.append(question)

            # Commit changes to the database
            db.session.commit()

            # Redirect to a success page or anywhere you like
            return redirect(url_for('edit_form'))

        # Handle form not found
        return "Form not found", 404

@app.route('/form/<int:form_id>', methods=['GET', 'POST'])
def submit_form(form_id):
    if request.method == 'GET':
        form = Form.query.filter_by(formid=form_id).options(joinedload(Form.questions).joinedload(Question.choices)).first()

        if not form:
            return "Form not found", 404

        return render_template('form.html', form=form)


@app.route('/data')
def data():

    responses_with_questions = db.session.query(Response, Question).join(Question).all()
    # Query only responses for Open-Ended questions
    open_ended_responses = db.session.query(Response, Question).join(Question).filter(Question.question_type == 'Open-Ended Response').all()

    total_respondents = len(open_ended_responses)

    sentiment_counts = {
        'Positive': 0,
        'Neutral': 0,
        'Negative': 0
    }

    # Initialize an empty list to store responses and questions
    responses_and_questions = []

    for response, question in open_ended_responses:
        response_sentiment = response.sentiment
        sentiment_counts[response_sentiment] += 1

        responses_and_questions.append((response.response, question.question_text))

    # Find the sentiment with the most counts
    most_common_sentiment = max(sentiment_counts, key=sentiment_counts.get)

    # Process all responses to generate a single summary
    combined_responses = [response for response, _ in responses_and_questions]
    combined_questions = [question for _, question in responses_and_questions]

    # Combine all responses and questions
    all_responses = " ".join(combined_responses)
    all_questions = " ".join(combined_questions)

    # Generate a summary for all responses and questions
    summary = generate_summary(all_responses, all_questions, most_common_sentiment, total_respondents)

    # Prepare the data for the pie chart
    chart_data = [['Sentiment', 'Count']]
    for sentiment, count in sentiment_counts.items():
        chart_data.append([sentiment, count])

    print(f"Chart Data: {chart_data}")
    print(f"Summary: {summary}")

    return render_template('data.html', chart_data=chart_data, total_respondents=total_respondents, responses_with_questions=responses_with_questions, summary=summary)

def generate_summary(feedback, question, sentiment, total_respondents):
    # Define your custom summary template
    if sentiment == "positive":
        template = f"The questions received a total of {total_respondents} responses, with most of them being positive. They include: {feedback}"
    elif sentiment == "negative":
        template = f"The questions received a total of {total_respondents} responses, and most of them were negative. They include: {feedback}"
    else:
        template = f"The questions received a total of {total_respondents} responses, with mixed sentiments. They include: {feedback}"

    # Initialize the text generation pipeline
    text_generator = pipeline("text-generation", model="gpt2")

    # Generate the summary
    generated_summary = text_generator(template, max_length=150, num_return_sequences=1)

    generated_text = generated_summary[0]['generated_text']
    
    sentences = re.split(r'(?<=[.!?])\s', generated_text)

    # Keep only the first 7 sentences
    final_summary = ' '.join(sentences[:7])
    return final_summary

@app.route('/data_summary')
def data_summary():
    return render_template('data_summary.html')