from flask import Flask, request, jsonify,render_template,url_for,redirect,session,flash
from nltk import sent_tokenize, word_tokenize, WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import random
import psycopg2
import psycopg2.extras
import re
import pickle
import datetime
from werkzeug.security import generate_password_hash,check_password_hash
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime
import nltk


nltk.download('wordnet')


app = Flask(__name__)

app.secret_key="X41romc$4F"
# Load the legal dataset from CSV
df = pd.read_csv('ipc_sections.csv')

# Preprocess the dataset
df['text'] = df['Description'] + ' ' + df['Offense'] + ' ' + df['Punishment'] + ' ' + df['Section']
df['text'] = df['text'].astype(str)  # Convert all values to string

hostname='localhost'
database='MOM'
user_name='postgres'
pwd='Achutham@123'
port_id=5432

def db_conn():
    conn=psycopg2.connect(
        host=hostname,
        dbname=database,
        user=user_name,
        password=pwd,
        port=port_id
    )
    return conn

scopes = ['https://www.googleapis.com/auth/calendar']
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=scopes)
credentials = flow.run_local_server() 
pickle.dump(credentials, open("token.pkl", "wb"))
credentials = pickle.load(open("token.pkl", "rb"))
service = build("calendar", "v3", credentials=credentials)
result = service.calendarList().list().execute()
calendar_id = result['items'][0]['id']

insert_script='INSERT INTO tasks(work_detail,user_name,final_time) VALUES(%s,%s,%s)'

conn=db_conn()
curr=conn.cursor()

@app.route("/MOM",methods=['GET','POST'])
def MOM():
    if "account" in session:
        if request.method=='POST':
            conn=db_conn()
            curr=conn.cursor()
            task=request.form["newtask"]
            final=request.form["deadline"]
            new=final.split("T")
            new_insert_values=(task,session["account"],f"{new[0]} {new[1]+':00'}")
            curr.execute(insert_script,new_insert_values)
            conn.commit()
            now=datetime.now()
            start_time = str(now)
            end_time = str(final)
            timezone = 'Asia/Kolkata'
            event = {
            'summary': "The work assigned to you",
            'location': 'Vellore',
            'description': task,
            'start': {
                'dateTime': start_time,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': timezone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
                ],
            },
            }
            service.events().insert(calendarId=calendar_id, body=event).execute()
            taskList=[]
            curr.execute('SELECT * FROM tasks WHERE user_name = %s', (session["account"],))
            for record in curr.fetchall():
                taskList.append(record)
            curr.close()
            conn.close()
            return render_template("mom.html",ttasks=taskList)
        else:
            taskList=[]
            conn=db_conn()
            curr=conn.cursor()
            curr.execute('SELECT * FROM tasks WHERE user_name = %s', (session["account"],))
            for record in curr.fetchall():
                taskList.append(record)
            curr.close()
            conn.close()
            return render_template("mom.html",ttasks=taskList)
    else:
        return redirect(url_for("login"))
    

@app.route("/delete",methods=['POST'])
def delete():
    if request.method=='POST':
        i=request.form.getlist('del')
        for id in i:
            delete_script='DELETE FROM tasks WHERE id='
        return "deleted"

@app.route("/")
def home():
    if "account" in session:
        return render_template("home.html",logged=True)
    else:
        return redirect(url_for("login"))

@app.route("/user/register",methods=['POST','GET'])
def register():
        if request.method=="POST":
            username=request.form["username"]
            email=request.form["email"]
            password=request.form["password"]
            hashed=generate_password_hash(password)
            conn=db_conn()
            curr=conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            curr.execute('SELECT * FROM users WHERE username = %s', (username,))
            account=curr.fetchone()
            if account:
                flash('Already existing user')
                return redirect(url_for("login"))
            else:
                curr.execute('INSERT INTO users (username,email,password) VALUES(%s,%s,%s)',(username,email,hashed))
                conn.commit()
                session["account"]=username
                return redirect(url_for("home",logged=True))
        else:
            return render_template("register.html")
        
@app.route("/login",methods=['POST','GET'])
def login():
        if request.method=='POST':
            username=request.form["username"]
            email=request.form["email"]
            password=request.form["password"]
            conn=db_conn()
            curr=conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            curr.execute('SELECT * FROM users WHERE username = %s', (username,))
            account=curr.fetchone()
            if(account):
                if check_password_hash(account["password"],password):
                    session["account"]=account["username"]
                    return redirect(url_for("home",logged=True))
                else:
                    flash("Incorrect Password")
                    return render_template("login.html")
            else:
                flash("Incorrect credentials, Make sure you hava an account")
                return render_template("login.html")
        else:
            return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("account")
    return redirect(url_for("login"))



# Initialize NLTK resources
lemmer = WordNetLemmatizer()

def LemNormalize(text):
    return [lemmer.lemmatize(token) for token in word_tokenize(text.lower())]

TfidfVec = TfidfVectorizer(tokenizer=LemNormalize, stop_words='english', token_pattern=r'(?u)\b\w\w+\b')
tfidf_matrix = TfidfVec.fit_transform(df['text'])

# Pre-defined greetings and responses
greet_inputs = ('hello', 'hi', 'wassup', 'hey')
greet_responses = ('hi', 'hey!', 'hey there!', 'hola user')

def greet(sentence):
    for word in sentence.split():
        if word.lower() in greet_inputs:
            return random.choice(greet_responses)

@app.route('/chatbot', methods=['POST','GET'])
def chatbot():
    if "account" in session:
        if request.method=='POST':
            user_input = request.form['user_input']
            user_input = ' '.join(word_tokenize(user_input.lower()))

            # Check if user input is a greeting
            if greet(user_input) is not None:
                bot_response = greet(user_input)
                return render_template("index.html",answer=bot_response,logged=True)
            else:
                query_vector = TfidfVec.transform([user_input])
                cosine_similarities = cosine_similarity(query_vector, tfidf_matrix)
                idx = cosine_similarities.argsort()[0][-1]
                bot_response = df.iloc[idx]['text']
                # result=jsonify({'bot_response': bot_response})
                return render_template("index.html",answer=bot_response,logged=True)
        else:
            return render_template("index.html",logged=True)
    else:
        return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)
