from datetime import datetime
from email.policy import default
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from Event_Evaluation_with_Sentiment_Analysis_System import app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from transformers import pipeline
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import json
from gensim.summarization import summarize
from googletrans import Translator
import pandas as pd
import tempfile

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:ra05182002@localhost:3306/EventDB'
app.secret_key = 'secret_key' 

db = SQLAlchemy(app)

sia = SentimentIntensityAnalyzer()

translator = Translator()

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
    respondent = db.Column(db.Integer, nullable=False)

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

        return render_template('form.html', form=form, form_id=form_id)

    elif request.method == 'POST':
        # Get the form object based on form_id
        form = Form.query.get(form_id)

        if not form:
            return "Form not found", 404
        # Get the highest respondent identifier from the database
        highest_respondent = db.session.query(func.max(Response.respondent)).scalar()

        # Increment the highest respondent identifier by 1
        respondent_id = highest_respondent + 1 if highest_respondent is not None else 1

        # Iterate through the form questions to collect responses
        for question in form.questions:
            field_name = f'question_{question.questionid}'

            # Check if the question is of type 'Open-Ended Response'
            if question.question_type == 'Open-Ended Response' and field_name in request.form:
                response_text = request.form[field_name]
                translated_response = translator.translate(response_text, src='tl', dest='en').text

                # Perform sentiment analysis using NLTK's VADER
                sentiment_scores = sia.polarity_scores(translated_response)
                sentiment_score = sentiment_scores['compound']
                sentiment = 'Positive' if sentiment_score > 0 else 'Negative' if sentiment_score < 0 else 'Neutral'

                # Create a new Response record
                response = Response(
                    form_id=form_id,
                    question_id=question.questionid,
                    response=response_text,
                    sentiment_score=sentiment_score,
                    sentiment=sentiment,
                    respondent=respondent_id
                )

                # Add and commit the response record to the database
                db.session.add(response)
            
            elif question.question_type in ('Multiple Choices'):
                # For Multiple Choices and CheckBox, collect the selected choices
                selected_choices = request.form.getlist(field_name)

                if selected_choices:
                    # Insert each selected choice as a separate response
                    for choice in selected_choices:
                        response = Response(
                            form_id=form_id,
                            question_id=question.questionid,
                            response=choice,
                            sentiment_score=None,
                            sentiment=None,
                            respondent=respondent_id
                        )

                        # Add and commit the response record to the database
                        db.session.add(response)
            
            elif question.question_type == 'CheckBox':
                selected_choices = []

                for choice in question.choices:
                    field_name = f'question_{question.questionid}_{choice.choice_id}'
                    if field_name in request.form:
                        selected_choices.append(choice.choice_text)

                if selected_choices:
                    for choice_text in selected_choices:
                        response = Response(
                            form_id=form_id,
                            question_id=question.questionid,
                            response=choice_text,
                            sentiment_score=None,
                            sentiment=None,
                            respondent=respondent_id
                        )

                        # Add and commit the response record to the database
                        db.session.add(response)
        
        db.session.commit()

        # Display a JavaScript alert indicating a successful submission
        return redirect(url_for('success', form_id=form_id))
    else:
        return "Invalid request method", 400
@app.route('/preview-form/<int:form_id>', methods=['GET', 'POST'])
def form_preview(form_id):
    if request.method == 'GET':
        form = Form.query.filter_by(formid=form_id).options(joinedload(Form.questions).joinedload(Question.choices)).first()

        if not form:
            return "Form not found", 404

        return render_template('form_preview.html', form=form, form_id=form_id)

@app.route('/success/<int:form_id>')
def success(form_id):
    # Query the Form object based on form_id
    form = Form.query.get(form_id)

    if not form:
        return "Form not found", 404

    # Retrieve the associated user for the form
    user = form.user

    if not user:
        return "User not found", 404

    name = user.name  # Assuming "name" is the field in the User model

    return render_template('response_success.html', name=name, form=form)

@app.route('/data/<int:form_id>')
def data(form_id):
    responses_with_questions = db.session.query(Response, Question).join(Question).filter(Response.form_id == form_id).all()
    open_ended_responses = db.session.query(Response, Question).join(Question).filter(Response.form_id == form_id, Question.question_type == 'Open-Ended Response').all()
    multiple_choice_responses = db.session.query(Response, Question).join(Question).filter(Response.form_id == form_id, Question.question_type == 'Multiple Choices').all()
    checkbox_responses = db.session.query(Response, Question).join(Question).filter(Response.form_id == form_id, Question.question_type == 'CheckBox').all()

    total_respondents = len(open_ended_responses)

    sentiment_counts = {
        'Positive': 0,
        'Neutral': 0,
        'Negative': 0
    }

    # Initialize an empty list to store responses and questions
    responses_and_questions = []
    positive_responses = []
    negative_responses = []

    for response, question in open_ended_responses:
        response_sentiment = response.sentiment
        sentiment_counts[response_sentiment] += 1

        # Translate the response to English here
        translated_response = translator.translate(response.response, src='tl', dest='en').text
        responses_and_questions.append((translated_response, question.question_text))

        if response_sentiment == "Positive":
            positive_responses.append((translated_response, question.question_text))
        elif response_sentiment == "Negative":
            negative_responses.append((translated_response, question.question_text))

    # Find the sentiment with the most counts
    most_common_sentiment = max(sentiment_counts, key=sentiment_counts.get)

    # Process all responses to generate a single summary
    combined_responses = [response for response, _ in responses_and_questions]
    combined_questions = [question for _, question in responses_and_questions]
    combined_positive_responses = [response for response, _ in positive_responses]
    combined_negative_responses = [response for response, _ in negative_responses]
 
    if most_common_sentiment == "Positive":
        summary = f"The questions received a total of {total_respondents} responses, with most of them being positive. They include: {combined_positive_responses}."
    elif most_common_sentiment == "Negative":
        summary = f"The questions received a total of {total_respondents} responses, and most of them were negative. They include: {combined_negative_responses}."
    else:
        summary = f"The questions received a total of {total_respondents} responses, with mixed sentiments. They include: {combined_responses}."

    chart_data = [['Sentiment', 'Count']]
    for sentiment, count in sentiment_counts.items():
        chart_data.append([sentiment, count])

    # Collect data for the bar graph
    choice_counts = {}  # Initialize a dictionary to count multiple-choice responses

    for response, question in multiple_choice_responses:
        response_choice = response.response
        question_text = question.question_text

        if question_text not in choice_counts:
            choice_counts[question_text] = {}

        if response_choice not in choice_counts[question_text]:
            choice_counts[question_text][response_choice] = 0

        choice_counts[question_text][response_choice] += 1

    # Prepare the data for the bar chart
    choice_chart_data = [['Choice', 'Count', { 'role': 'style' }]]
    for question_text, choices in choice_counts.items():
        for choice, count in choices.items():
            choice_chart_data.append([f'{choice}', count, "#CEA778"])

    # Group responses by question text for open-ended responses
    question_responses = {}

    for response, question in open_ended_responses:
        question_text = question.question_text
        response_sentiment = response.sentiment

        if question_text not in question_responses:
            question_responses[question_text] = {}

        if response_sentiment not in question_responses[question_text]:
            question_responses[question_text][response_sentiment] = []

        question_responses[question_text][response_sentiment].append(response.response)

    # Initialize an empty list to store choice summaries
    choice_summaries = []

    # Process multiple-choice responses and count the choices
    for question_text, choices in choice_counts.items():
        # Calculate the total count for the question
        total_count = sum(choices.values())

        # Find the choice with the highest count
        max_choice = max(choices, key=choices.get)
        max_count = choices[max_choice]

        # Calculate the percentage for the most popular choice
        percentage = (max_count / total_count) * 100

        # Construct the summary for the question
        question_summary = f"In response to the question, '{question_text}', survey participants provided insights into the question. "
        question_summary += f"The majority, constituting {percentage:.2f}% of respondents, selected {max_choice}, with a total count of {max_count}. "
        choice_summaries.append(question_summary)

    # Fetch data for CheckBox type responses
    checkbox_responses = db.session.query(Response, Question).join(Question).filter(Question.question_type == 'CheckBox').all()

    # Calculate the total number of respondents for CheckBox questions
    total_checkbox_respondents = len(checkbox_responses)

    # Process and count the CheckBox responses
    checkbox_counts = {}
    for response, question in checkbox_responses:
        response_text = response.response
        question_text = question.question_text

        if question_text not in checkbox_counts:
            checkbox_counts[question_text] = {}

        if response_text not in checkbox_counts[question_text]:
            checkbox_counts[question_text][response_text] = 0

        checkbox_counts[question_text][response_text] += 1

    # Prepare the data for the CheckBox bar chart
    checkbox_chart_data = [['Choice', 'Count', { 'role': 'style' }]]
    for question_text, choices in checkbox_counts.items():
        for choice, count in choices.items():
            checkbox_chart_data.append([f'{choice}', count, "#CEA778"])

    # Initialize an empty list to store choice summaries
    checkbox_choice_summaries = []

    # Process multiple-choice responses and count the choices
    for question_text, choices in checkbox_counts.items():
        # Calculate the total count for the question
        total_count = sum(choices.values())

        # Find the maximum count among all choices
        max_count = max(choices.values())

        # Find all choices with the maximum count
        max_choices = [choice for choice, count in choices.items() if count == max_count]

        # Calculate the percentage for the most popular choices
        percentage = (max_count / total_count) * 100

        # Construct the summary for the CheckBox question
        question_summary = f"In response to the question, '{question_text}', survey participants provided insights into the question. "
    
        if len(max_choices) == 1:
            question_summary += f"The majority, constituting {percentage:.2f}% of respondents, selected '{max_choices[0]}', with a total count of {max_count}. "
        else:
            # If there are multiple choices with the same highest count
            choices_text = ", ".join(f"'{choice}'" for choice in max_choices)
            question_summary += f"The majority, constituting {percentage:.2f}% of respondents, selected {choices_text}, each with a total count of {max_count}. "

        checkbox_choice_summaries.append(question_summary)

    # Join the summaries for multiple-choice questions
    checkbox_choice_summary_text = "\n".join(checkbox_choice_summaries)

    return render_template('data.html', form_id=form_id , chart_data=chart_data, choice_chart_data=choice_chart_data, total_respondents=total_respondents, responses_with_questions=responses_with_questions, summary=summary, question_responses=question_responses, choice_summaries=choice_summaries, checkbox_chart_data=checkbox_chart_data, total_checkbox_respondents=total_checkbox_respondents, checkbox_choice_summary_text=checkbox_choice_summary_text)

@app.route('/data_summary/<int:form_id>')
def data_summary(form_id):
    return render_template('data_summary.html', form_id=form_id)

@app.route('/individual_data/<int:form_id>')
def individual_data(form_id):

    responses_with_questions = db.session.query(Response, Question).join(Question).filter(Response.form_id == form_id).all()

    grouped_responses = {}

    for response, question in responses_with_questions:
        respondent = response.respondent
        if respondent not in grouped_responses:
            grouped_responses[respondent] = []
        grouped_responses[respondent].append((question.question_text, response.response))

    unique_respondents = len(grouped_responses)

    return render_template('individual_data.html', grouped_responses=grouped_responses, unique_respondents=unique_respondents, form_id=form_id)

@app.route('/generate_report/<int:form_id>')
def generate_report(form_id):
    return render_template('report.html', form_id=form_id)

@app.route('/download_report/<int:form_id>')
def download_report(form_id):
    responses_with_questions = db.session.query(Response, Question, Form.title).\
        join(Question, Response.question_id == Question.questionid).\
        join(Form, Response.form_id == Form.formid).\
        filter(Response.form_id == form_id).all()

    # Create a temporary directory and get the path
    temp_dir = tempfile.mkdtemp()

    # Specify the full path for the temporary file
    file_name = f'{temp_dir}/Form_{form_id}_Report.xlsx'
    print(f"File will be saved as: {file_name}")

    # Create a list to hold unique question text
    unique_questions = []

    # Create a dictionary to store data for each unique question
    data_by_question = {}

    # Iterate through the responses and group them by unique question text
    for response, question, title in responses_with_questions:
        question_text = question.question_text
        if question_text not in unique_questions:
            unique_questions.append(question_text)
            data_by_question[question_text] = {
                'question_type': question.question_type,
                'responses': [],
                'sentiments': [],
                'sentiment_scores': [],
                'dates': [],
            }
        data_by_question[question_text]['responses'].append(response.response)
        data_by_question[question_text]['sentiments'].append(response.sentiment)
        data_by_question[question_text]['sentiment_scores'].append(response.sentiment_score)
        data_by_question[question_text]['dates'].append(response.date)

    # Create a Pandas DataFrame for the unique questions
    df = pd.DataFrame(data_by_question).T.reset_index()
    df = df.rename(columns={'index': 'question_text'})

    # Create an Excel writer object
    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')

    # Get the xlsxwriter workbook and worksheet objects
    workbook = writer.book
    worksheet = workbook.add_worksheet('Responses')

    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
    # Add formatting to the worksheet
    header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top'})

    # Define the starting row for writing data
    row = 4

    # Iterate through the responses and group them by unique question text
    for question_text, data in data_by_question.items():
        num_responses = len(data['responses'])

        # Merge the question and question type cells to cover all responses
        worksheet.merge_range(row, 1, row + num_responses - 1, 1, question_text, header_format)
        worksheet.merge_range(row, 2, row + num_responses - 1, 2, data['question_type'], header_format)

        # Write responses, sentiments, sentiment scores, and dates
        for i in range(num_responses):
            worksheet.write(row + i, 3, data['responses'][i])
            worksheet.write(row + i, 4, data['sentiments'][i])
            worksheet.write(row + i, 5, data['sentiment_scores'][i])
            worksheet.write(row + i, 6, data['dates'][i], date_format)

        # Move to the next question
        row += num_responses

    # Write column names
    column_names = list(df.columns)
    worksheet.write_row(3, 1, column_names, header_format)

    # Merge the title cells
    title = responses_with_questions[0].title
    worksheet.merge_range(0, 1, 0, len(df.columns), title, header_format)

    try:
        # Save the Excel file using Pandas ExcelWriter's save method
        writer.save()
        print("File saved successfully")
        writer.close()
    except Exception as e:
        print(f"Error while saving the file: {str(e)}")

    # Serve the file for download
    response = send_file(file_name, as_attachment=True)

    return response





