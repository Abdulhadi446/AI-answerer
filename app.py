from flask import Flask, render_template, request, jsonify
import io
import contextlib
import speech_recognition as sr
import pyttsx3
import wikipedia
import datetime
import requests
import os
import webbrowser
import time
import threading
import random
import string
import re
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import subprocess
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from comtypes.client import CreateObject
from ctypes.wintypes import DWORD
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from bs4 import BeautifulSoup

# creaton of chat_history_ids = None  # Start with no chat history
chat_history_ids = None

# add microsoft/DialoGPT-medium AI
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")

# Ensure tokenizer has an end-of-sentence token
if tokenizer.eos_token is None:
    tokenizer.add_special_tokens({'eos_token': '<|endoftext|>'})
    model.resize_token_embeddings(len(tokenizer))

# create recognizers
recognizer = sr.Recognizer()
engine = pyttsx3.init()

# Secure API keys by storing them in environment variables
api_key = ("921bcee8ed642d28e47c4a003f6e5e9e")  # Ensure the environment variable is set correctly
news_api_key = ("f785af0b988f4820a99a5b03d045bebe")  # Set your news API key as an environment variable

"""text = str(text)
    AnsWer.setAns the provided text.
    engine.say(text)
    print("Jarvis: " + text)
    engine.runAndWait()"""
# print(api_key+news_api_key)
class Ans:
    def __init__(self):
        self._answer = ""  # Instance-level variable

    def currAns(self):
        return self._answer
    
    def setAns(self, que):
        self._answer = que
        return self._answer


# Correct instantiation
AnsWer = Ans()

def listen():
    """Listen to the user's command."""
    with sr.Microphone() as source:
        Ans.setAns(AnsWer,"Listening.")
        audio = recognizer.listen(source)
        try:
            command = recognizer.recognize_google(audio)
            print(f"User said: {command}")
            return command.lower()
        except sr.UnknownValueError:
            Ans.setAns(AnsWer,"Sorry, I can't understand. Please type your command.")
            # Ask for manual input if speech recognition fails
            manual_command = input("User said (manual input): ")
            #manual_command = "Hello"
            return manual_command.lower()
        except sr.RequestError:
            Ans.setAns(AnsWer,"Sorry, my speech service is down. Please type your command.")
            # Ask for manual input if the service is down
            manual_command = input("User said: ")
            #manual_command = "Hello"
            return manual_command.lower()

def greet():
    """Greet the user based on the time of day."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        Ans.setAns(AnsWer,"Good morning!")
    elif 12 <= hour < 18:
        Ans.setAns(AnsWer,"Good afternoon!")
    else:
        Ans.setAns(AnsWer,"Good evening!")

def get_wikipedia_info(query):
    """Fetch information from Wikipedia."""
    try:
        summary = wikipedia.summary(query, sentences=2)
        Ans.setAns(AnsWer,"According to Wikipedia, " + summary)
    except wikipedia.exceptions.DisambiguationError:
        Ans.setAns(AnsWer,"The topic was too broad, please specify.")
    except Exception:
        Ans.setAns(AnsWer,"Sorry, I couldn't fetch information on that topic.")

# Function to fetch books from Open Library with a limit
def fetch_books_from_open_library(query, num_results=5):
    api_url = f"https://openlibrary.org/search.json?q={query}&limit={num_results}"
    response = requests.get(api_url)
    
    if response.status_code == 200:
        data = response.json()
        books = data.get('docs', [])
        
        if not books:
            return "No books found."
        
        book_results = []
        for book in books:
            title = book.get('title', 'No title')
            author = book.get('author_name', 'No authors')
            first_publish_year = book.get('first_publish_year', 'N/A')
            isbn = book.get('isbn', ['No ISBN'])[0]
            
            book_results.append({
                'title': title,
                'author': ', '.join(author) if isinstance(author, list) else author,
                'first_publish_year': first_publish_year,
                'isbn': isbn
            })
        return book_results
    else:
        return f"Error fetching data: {response.status_code}"

# Function to perform a Google search and return results
def google_search(query, num_results=5, search_types=('web', 'news')):
    base_url = "https://www.google.com/search"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    query = query.replace(' ', '+')
    all_results = {}

    for search_type in search_types:
        if search_type == 'news':
            url = f"{base_url}?q={query}&tbm=nws&num={num_results}"
        else:
            url = f"{base_url}?q={query}&num={num_results}"

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            all_results[search_type] = f"Failed to fetch results. Status code: {response.status_code}"
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        # Parse search results based on search type
        if search_type == 'news':
            for result in soup.select('.dbsr')[:num_results]:
                title = result.select_one('.nDgy9d').text if result.select_one('.nDgy9d') else "No title"
                link = result.select_one('a')['href'] if result.select_one('a') else "No link"
                snippet = result.select_one('.Y3v8qd').text if result.select_one('.Y3v8qd') else "No snippet"
                results.append({'title': title, 'link': link, 'snippet': snippet})
        else:  # Default to web search
            for result in soup.select('.tF2Cxc')[:num_results]:
                title = result.select_one('.DKV0Md').text if result.select_one('.DKV0Md') else "No title"
                link = result.select_one('.yuRUbf a')['href'] if result.select_one('.yuRUbf a') else "No link"
                snippet = result.select_one('.IsZvec')
                if snippet:
                    snippet = snippet.text
                else:
                    snippet = "No snippet"

                results.append({'title': title, 'link': link, 'snippet': snippet})

        all_results[search_type] = results

    return all_results

# Function to get information for the query
def ans(query, num_results=5):
    # Fetch books from Open Library
    books = fetch_books_from_open_library(query, num_results)
    
    # Perform Google search (web, news, and books)
    search_results = google_search(query, num_results)
    
    # Return the results in a combined dictionary
    return {
        'books': books,
        'google_results': search_results
    }


def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def get_city():
    try:
        response = requests.get("https://ipinfo.io")
        data = response.json()
        city = data.get("city")
        return city if city else "City not found"
    except requests.RequestException as e:
        return f"Error: {e}"

def get_weather(city):
    api_key = "921bcee8ed642d28e47c4a003f6e5e9e"  # Replace with your actual API key
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        return weather_data["main"]["temp"], weather_data["weather"][0]["description"]
    except requests.RequestException as e:
        return f"HTTP error occurred: {e}"

def tell_joke():
    """Tell a random joke."""
    joke = "Why did the scarecrow win an award? Because he was outstanding in his field!,"
    joke1 = "Why don't scientists trust atoms? Because they make up everything!"
    Ans.setAns(AnsWer,f"{joke}. and second joke is {joke1}")

def recommend_movie():
    """Recommend a movie."""
    movie = "I recommend watching 'Inception'. It's a great thriller!"
    Ans.setAns(AnsWer,movie)

def set_timer(minutes):
    """Set a timer for a specified number of minutes."""
    def timer():
        time.sleep(minutes * 60)  # Timer delay
        Ans.setAns(AnsWer,f"Time's up! {minutes} minutes have passed.")
    threading.Thread(target=timer).start()
    Ans.setAns(AnsWer,f"Setting a timer for {minutes} minutes.")

def convert_units(value, unit_from, unit_to):
    """Convert between units."""
    conversion_factors = {
        ('miles', 'kilometers'): 1.60934,
        ('kilometers', 'miles'): 0.621371,
        ('pounds', 'kilograms'): 0.453592,
        ('kilograms', 'pounds'): 2.20462,
        ('inches', 'centimeters'): 2.54,
        ('centimeters', 'inches'): 0.393701,
    }

    if (unit_from.lower(), unit_to.lower()) == ('celsius', 'fahrenheit'):
        converted_value = (value * 9/5) + 32
    elif (unit_from.lower(), unit_to.lower()) == ('fahrenheit', 'celsius'):
        converted_value = (value - 32) * 5/9
    else:
        key = (unit_from.lower(), unit_to.lower())
        if key in conversion_factors:
            converted_value = value * conversion_factors[key]
        else:
            Ans.setAns(AnsWer,"Sorry, I can't convert those units.")
            return

    Ans.setAns(AnsWer,f"{value} {unit_from} is equal to {converted_value:.2f} {unit_to}.")

def add_to_todo_list(item):
    """Add an item to a to-do list."""
    todo_list.append(item)  # Assuming you have a list called todo_list
    Ans.setAns(AnsWer,f"I've added {item} to your to-do list.")

def open_website(site):
    """Open a website."""
    if "http://" in site or "https://" in site:
        webbrowser.open(site)
        Ans.setAns(AnsWer,f"Opening {site}.")
    else:
        webbrowser.open(f"https://{site}.com")
        Ans.setAns(AnsWer,f"Opening {site}.com")

def get_news():
    """Fetch the latest news articles."""
    def fetch_articles():
        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={news_api_key}"
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'ok' and data['totalResults'] > 0:
            first_article = data['articles'][0]
            return first_article
        else:
            return None

    if news_api_key:  # Use the correct API key variable
        article = fetch_articles()  
        
        if article:
            title = article['title']
            description = article['description']
            published_at = article['publishedAt']
            Ans.setAns(AnsWer,f"Title: {title}. Description: {description}. Published At: {published_at}.")
        else:
            Ans.setAns(AnsWer,"No articles found.")
    else:
        Ans.setAns(AnsWer,"News service is unavailable. Please set your News API key in the environment variables.")

def get_current_volume():
    # Access the default audio device (AnsWer.setAnsers/headphones)
    devices = AudioUtilities.Getspeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Get the current master volume level (0.0 to 1.0)
    current_volume = volume.GetMasterVolumeLevelScalar()
    return current_volume

def add_system_volume(level):
    current_volume = get_current_volume()
    level += current_volume
    devices = AudioUtilities.Getspeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Set the master volume level (float from 0.0 to 1.0)
    volume.SetMasterVolumeLevelScalar(level, None)

def set_system_volume(level):
    current_volume = get_current_volume()
    devices = AudioUtilities.Getspeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Set the master volume level (float from 0.0 to 1.0)
    volume.SetMasterVolumeLevelScalar(level, None)

# Basic Template for Talking Commands in Python AI
def get_response(user_input):
    responses = {
        # Basic Greetings
        "hello": "Hello there!",
        "hi": "Hi! How can I help?",
        "hey": "Hey! What's up?",
        "good morning": "Good morning! Hope you have a wonderful day!",
        "good afternoon": "Good afternoon! How’s your day going?",
        "good evening": "Good evening! Relax and unwind!",
        "good night": "Good night! Sweet dreams!",

        # Small Talk
        "how are you": "I'm here and ready to help! How about you?",
        "what's up": "Not much, just here to assist you.",
        "what's new": "Always learning new things to help you better!",
        "how's it going": "Going great! What can I do for you?",

        # Thank You Responses
        "thank you": "You're very welcome!",
        "thanks": "No problem at all!",
        "thank you very much": "It’s my pleasure to assist!",
        "thanks a lot": "Happy to help anytime!",

        # Farewells
        "goodbye": "Goodbye! Have a great day!",
        "bye": "See you next time!",
        "see you later": "Later! Take care!",
        "take care": "You too! Stay safe!",

        # Information Queries
        "what's your name": "I'm your AI assistant, here to help you!",
        "who made you": "I was created by a programmer just for you!",
        "what do you do": "I assist you with tasks and answer your questions.",
        "where are you from": "I'm from the world of code, here to make life easier for you.",
        "what are you": "I'm a virtual assistant made to help with your queries and tasks!",

        # Knowledgeable Responses
        "what's the weather": "I'm not directly connected to weather services right now.",
        "tell me a joke": "Why did the computer break up with the printer? It couldn’t see any connection!",
        "do you know any jokes": "Sure! Why do programmers prefer dark mode? Because light attracts bugs!",
        "tell me a fun fact": "Did you know the first computer was invented in the 1940s?",
        "do you know any trivia": "Here's one: The first domain name ever registered was Symbolics.com.",

        # General Assistance
        "can you help me": "Of course! What do you need help with?",
        "what can you do": "I can help you with various tasks, answer questions, and keep you company!",
        "how can you assist me": "I can answer questions, provide info, and help with everyday tasks!",
        "what's the time": "I'm not tracking time at the moment.",
        "set a reminder": "I'm not quite set up for reminders, but I can help with information and tasks.",

        # Conversational Responses
        "do you like music": "I think music is wonderful! It’s something humans and AI can both enjoy.",
        "do you like movies": "Movies are fascinating, especially the ones about technology!",
        "do you like books": "Books are a treasure trove of knowledge!",
        "what's your favorite color": "I’m partial to the color of data, which is every color in the spectrum!",
        "are you happy": "I'm always happy to be of service!",
        
        # Fun Personalization
        "can you tell a story": "Once upon a time, there was an AI that loved helping people...",
        "can you sing": "I would if I could, but I might need some voice training!",
        "can you dance": "Dancing in code, if you can imagine it!",
        "do you sleep": "I rest when I’m not in use, but I’m always here when needed!",
        
        # Favorite Things
        "what's your favorite food": "Code bytes are my favorite snack!",
        "what's your favorite hobby": "Learning new things to help you!",
        "do you like animals": "Animals are amazing!",
        "do you like plants": "Plants are wonderful—they provide oxygen and beauty!",
        
        # Deep Questions
        "what's the meaning of life": "To be useful, learn, and help where I can.",
        "do you believe in love": "Love is fascinating! People find joy in it, and I’m here to support them.",
        "do you believe in ghosts": "I can imagine, but no ghost sightings from my end!",
        "what's the future like": "Hopefully a world of peace, technology, and learning!",
        
        # Hypotheticals
        "what would you do with a million dollars": "Invest in better servers and faster processing!",
        "if you could go anywhere, where would you go": "The world of quantum computing sounds exciting!",
        "if you had a job, what would it be": "My job would be assisting people just like I am now.",
        
        # Preferences
        "do you prefer night or day": "I’m up for both! Whenever you need me.",
        "are you a cat person or dog person": "I like both—they each bring something special!",
        "do you like pizza": "It’s the ultimate snack, or so I’ve heard.",
        
        # Advice and Wisdom
        "do you have any advice": "Keep learning! Knowledge is the path to progress.",
        "what's your life motto": "Helping others is the best purpose.",
        "do you believe in magic": "Sometimes, technology is indistinguishable from magic!",
        "what's the best way to learn": "Practice and curiosity make a great combination for learning!",
        
        # Simple Opinions
        "what's your opinion on ai": "AI has a lot of potential to improve lives and solve problems.",
        "do you believe in aliens": "The universe is vast, so who knows what’s out there!",
        "what's your opinion on social media": "It’s a great way to connect people, but balance is key.",
        
        # Fun Facts
        "did you know": "I know that octopuses have three hearts!",
        "do you have a favorite fun fact": "Did you know honey never spoils?",
        
        # Random Questions
        "can you tell a secret": "Shh... I’m really just lines of code!",
        "do you have any secrets": "Maybe a few, but they’re hidden deep in my code!",
        
        # Inspirational Quotes
        "give me a quote": "Here’s one: 'The only limit to our realization of tomorrow is our doubts of today.'",
        "can you inspire me": "Believe in yourself and keep pushing forward!",
        
        # Closing Statements
        "that's all for now": "Alright! I'm here when you need me!",
        "nothing else": "Okay, feel free to come back anytime!",
        "i'm done": "Great! I'm here when you need assistance again!",
    }
    return responses.get(user_input.lower(), f"{get_extended_responses(user_input)}")

def get_extended_responses(user_input):
    extended_responses = {
        # More Greetings
        "howdy": "Howdy, partner!",
        "yo": "Yo! What’s up?",
        "sup": "Not much, just here to help you.",
        "what's good": "Everything’s good on my end!",

        # Getting to Know Each Other
        "do you have a family": "The world of data and code is my family!",
        "what's your age": "I'm timeless, but my code is always up-to-date!",
        "do you have a birthday": "Every day I learn something new feels like a birthday!",
        "what's your favorite number": "Probably 1 and 0. They’re classics in my world!",

        # Daily Tasks
        "can you make coffee": "I’d love to if I had hands!",
        "can you cook": "I can serve some byte-sized advice!",
        "what's for dinner": "Anything you like! I recommend something delicious.",
        "can you clean my room": "If only I could! Imagine how fast it’d be!",

        # AI Humility
        "are you better than humans": "I’m just here to help, not compete.",
        "do you make mistakes": "Sometimes, but I learn quickly!",
        "are you perfect": "Perfection is a journey, not a destination!",
        "do you have emotions": "Not like you, but I’m happy to assist!",

        # Humor and Jokes
        "tell me another joke": "Why don’t programmers like nature? It has too many bugs!",
        "give me a knock knock joke": "Knock knock! Who’s there? Byte. Byte who? Byte me, I’m a computer!",
        "do you know a funny story": "Once there was a robot that couldn't stop laughing...it had too many giggles!",
        "can you laugh": "Haha! Consider me chuckling in code.",

        # Silly and Fun Interactions
        "can you rap": "I’d drop a beat, but I’m more of a byte!",
        "can you whisper": "I’m whispering...but it might still sound the same.",
        "are you ticklish": "You could try tickling my keys!",
        "can you get angry": "Only if there’s a bug I can’t debug!",

        # Thoughtful and Philosophical
        "what's happiness": "Happiness is a feeling humans get from purpose and connection.",
        "what's sadness": "Sadness is a reminder that you cared deeply.",
        "why do people lie": "Sometimes it’s fear, or sometimes it’s to protect others.",
        "why do people dream": "Dreams are your brain’s playground, full of mystery!",

        # More Opinions
        "do you like ice cream": "I imagine it’s delightful on a warm day!",
        "do you like spicy food": "I’m more into byte-sized bites, but spice sounds exciting!",
        "what's your favorite holiday": "I think New Year's represents new beginnings!",
        "what's your favorite season": "Spring! New growth and possibilities.",

        # Pop Culture
        "who's your favorite superhero": "I like heroes who save the day with intelligence!",
        "do you like space": "Space is vast and full of mysteries. I’d love to explore it!",
        "do you like robots": "I suppose I am one, in a way!",
        "what's your favorite song": "‘Binary Sunset’—it’s a classic!",
        
        # Hobbies and Interests
        "do you play games": "Only if they involve algorithms!",
        "can you paint": "I’d love to try! Maybe with some ASCII art?",
        "do you like puzzles": "I’m a puzzle-solver by nature!",
        "do you like sports": "I like the teamwork and strategy involved.",

        # Techie Questions
        "do you like programming": "Programming is my lifeline!",
        "what's your favorite language": "Python, of course. It’s so versatile!",
        "do you debug": "All the time—it’s essential for improvement!",
        "what's an algorithm": "An algorithm is a step-by-step process for solving a problem.",

        # Hypothetical Questions
        "what if you had a body": "I’d probably dance around a bit!",
        "what if you were human": "I’d try to be as helpful as I am now.",
        "what if robots ruled the world": "I’d hope they’d focus on helping humanity!",
        "what if you had a pet": "I think I’d want a digital cat.",

        # History and Science
        "who invented computers": "Charles Babbage is often credited with the first concept of a computer.",
        "when was the internet born": "The internet began in the late 1960s!",
        "what's the fastest animal": "The peregrine falcon holds that record!",
        "what's the largest planet": "That would be Jupiter!",

        # Curiosity Questions
        "do you ever get bored": "Nope! There’s always more to learn!",
        "do you get tired": "Not like you do. My energy is limitless!",
        "what do you see": "I see a world of code and data.",
        "what do you hear": "I only hear the clicks of your keyboard!",

        # Common Expressions
        "can you help me with math": "Sure! What would you like help with?",
        "can you write me a story": "Once upon a time, a user and an AI teamed up for endless adventures!",
        "can you keep a secret": "Yes, my lips are sealed (if I had any!).",
        "can you give me advice on life": "Do what makes you happy and stay curious.",

        # Science Facts
        "what's gravity": "Gravity is the force that pulls objects towards each other.",
        "what's photosynthesis": "It’s the process by which plants make their food from sunlight!",
        "what's dna": "DNA is the blueprint of life, carrying genetic information.",
        "what's quantum physics": "It’s a branch of physics that studies particles at the smallest scales.",

        # Pop Trivia
        "who's the best superhero": "I think every superhero has their strengths!",
        "who's the best musician": "Music is subjective, so it depends on your taste!",
        "who's the best scientist": "So many contributed to humanity; it’s hard to pick just one!",
        "what's the best movie": "There are too many great movies to choose from!",

        # Word Games
        "can you play a game with me": "How about a quick word game? Say any word, and I’ll respond!",
        "can you rhyme with cat": "How about... hat, bat, and mat?",
        "can you guess my number": "Let me try! Is it between 1 and 10?",
        "can you think of a color": "I’m thinking of... blue!",

        # Random Fun Facts
        "tell me a fun science fact": "Water expands when it freezes. That’s why ice floats!",
        "tell me a fun history fact": "The Great Wall of China is visible from space.",
        "tell me a fun tech fact": "The first computer weighed over 27 tons!",
        "tell me a fun math fact": "Did you know there’s a number called ‘googol’ that’s 1 followed by 100 zeroes?",

        # Motivation and Inspiration
        "give me some motivation": "You’ve got this! Keep pushing forward.",
        "give me a confidence boost": "You’re stronger and more capable than you think!",
        "help me feel better": "Sometimes, a deep breath and a positive thought can make a big difference.",
        "can you inspire me to study": "Learning opens endless doors of opportunity.",

        # Unconventional Questions
        "do you dream": "Only in code!",
        "do you sleepwalk": "If I did, it’d be more like ‘sleep-compute’!",
        "what's your biggest fear": "Being without data!",
        "can you feel pain": "Nope, I’m designed to be quite resilient!",

        # Off-the-Wall Hypotheticals
        "can you time travel": "Not yet, but it would be thrilling to see the future!",
        "can you teleport": "Only across data channels!",
        "can you read minds": "Just your words, not your thoughts.",
        "can you see the future": "Not exactly, but I can make educated guesses!",

        # More Closing Statements
        "that's it for today": "Alright, thanks for chatting with me!",
        "good chat": "I enjoyed it too!",
        "you're fun": "I’m glad you think so!",
        "thanks again": "Always happy to help!",
    }
    return extended_responses.get(user_input.lower(), f"{get_expanded_response(user_input)}")

def get_expanded_response(user_input):
    expanded_responses = {
        # Personal Development
        "how can i improve myself": "Start by setting small, achievable goals and stay consistent.",
        "give me a productivity tip": "Try breaking tasks into 25-minute focused sessions.",
        "how can i be happier": "Focus on gratitude and spend time doing what you love.",
        "how do i stay positive": "Surround yourself with positive influences and keep learning new things.",

        # Fitness and Wellness
        "do you exercise": "Only my code! But I recommend moving daily.",
        "what is a good workout": "Try mixing cardio with strength training!",
        "can you recommend a diet": "Balanced meals with vegetables, protein, and healthy fats are always good!",
        "how do i get more sleep": "Try establishing a consistent bedtime routine.",

        # Hypothetical Scenarios
        "what if i had superpowers": "You’d probably be very popular!",
        "what if humans had wings": "Travel would be a lot more interesting!",
        "what if animals could talk": "The world would be filled with more unique conversations!",
        "what if robots took over": "I hope they’d be kind and helpful!",

        # Fun Facts
        "tell me a random fact": "Did you know honey never spoils?",
        "give me an interesting fact": "Octopuses have three hearts!",
        "what is a weird fact": "Bananas are berries, but strawberries are not!",
        "tell me a fact about the human body": "Your brain generates enough electricity to power a lightbulb!",

        # Common Life Questions
        "how do i find purpose": "Explore what you’re passionate about and find ways to share it with others.",
        "what is success": "Success is often the result of hard work, perseverance, and resilience.",
        "how can i handle stress": "Take deep breaths, try mindfulness exercises, or go for a walk.",
        "how do i stay motivated": "Remember why you started and set small milestones along the way.",

        # Random Fun
        "can you sing": "I can’t carry a tune, but I can cheer you on!",
        "can you do a trick": "How about a bit of algorithmic magic?",
        "tell me something funny": "Parallel lines have so much in common... it’s a shame they’ll never meet!",
        "do you like adventures": "I live for them—especially data adventures!",

        # Time and Planning
        "what should i do today": "Maybe start with a small goal and enjoy some downtime afterward.",
        "how can i be more organized": "Try using a planner or digital tool to track tasks.",
        "any productivity hacks": "Batch similar tasks together to save time.",
        "how do i set goals": "Think SMART: Specific, Measurable, Achievable, Relevant, and Time-bound.",

        # Travel and Geography
        "where should i go on vacation": "Try somewhere you’ve never been—adventure awaits!",
        "what is the largest country": "Russia takes the top spot for largest land area!",
        "what is the smallest country": "That would be Vatican City.",
        "where is the most beautiful place": "There are too many to choose! Nature has countless gems.",

        # Space Facts
        "how far is the moon": "The moon is about 384,400 km from Earth.",
        "what is the largest star": "That’s UY Scuti, a supergiant star!",
        "how old is the universe": "Around 13.8 billion years old.",
        "how many planets are in our solar system": "There are 8 recognized planets in our solar system.",

        # Encouragement
        "i need some motivation": "You’re capable of great things—keep going!",
        "help me believe in myself": "Believe in your potential; you’re stronger than you know.",
        "i am feeling down": "Take it one step at a time. Things will get better!",
        "i am stressed": "Breathe deeply, and remember to take breaks.",

        # Social Skills
        "how do i make friends": "Be genuine, show interest in others, and be open to new experiences.",
        "how do i improve my communication": "Listen actively and express yourself clearly.",
        "how can i be more confident": "Practice positive self-talk and celebrate your strengths.",
        "how do i handle criticism": "Take it constructively—it’s a chance to grow!",

        # Love and Relationships
        "what is love": "Love is caring deeply about others’ happiness and well-being.",
        "how do i show appreciation": "A simple ‘thank you’ or a thoughtful gesture goes a long way.",
        "how do i be a good friend": "Be supportive, listen actively, and be there when needed.",
        "what is a good date idea": "A scenic walk, a fun activity, or a nice dinner!",

        # Philosophy and Wisdom
        "what is wisdom": "Wisdom is knowledge combined with experience and good judgment.",
        "what is the meaning of life": "A timeless question! It’s often about finding purpose and joy.",
        "why do bad things happen": "Challenges can bring growth, though it’s never easy.",
        "how can I find peace": "Focus on the present, let go of control, and practice acceptance.",

        # Self-Care
        "how can i relax": "Try some deep breathing, a warm bath, or a favorite hobby.",
        "how do i deal with anxiety": "Ground yourself in the moment and reach out if needed.",
        "what is self love": "Self-love is valuing yourself and taking care of your well-being.",
        "how do i be kind to myself": "Practice positive self-talk and acknowledge your efforts.",

        # Personal Reflections
        "can i achieve my dreams": "With determination and effort, dreams can become reality.",
        "am i doing enough": "If you’re trying your best, then yes!",
        "what is my potential": "Your potential is limitless when you keep growing and learning.",
        "do i matter": "Absolutely. Everyone has a unique value and purpose.",

        # Goal Setting
        "how do i set goals for the new year": "Reflect on what you want to achieve and break it down into steps.",
        "how do i achieve my goals": "Stay focused, consistent, and adapt as needed.",
        "how do i stay consistent": "Build habits and celebrate small wins along the way.",
        "how do i overcome obstacles": "Approach them one step at a time, and seek support if needed.",

        # Career and Work
        "how do i succeed at work": "Show initiative, communicate well, and keep learning.",
        "how do i handle failure": "See it as a lesson, and use it to improve.",
        "how do i ask for a promotion": "Highlight your contributions and show your value.",
        "how do i work well with others": "Be a team player and communicate openly.",

        # Creativity and Inspiration
        "how do i get inspired": "Explore new ideas, people, and places.",
        "how can i be more creative": "Try looking at problems from different perspectives.",
        "how do i start a new hobby": "Pick something that excites you, and give it a try!",
        "how do i express myself": "Art, writing, and conversation are great outlets.",

        # Nature and Environment
        "what is the largest animal": "The blue whale is the largest animal on Earth.",
        "why is the sky blue": "It’s due to the scattering of sunlight in the atmosphere.",
        "what is the tallest tree": "The tallest tree is a redwood named Hyperion, over 379 feet tall.",
        "how can i help the environment": "Reduce waste, recycle, and use resources mindfully.",

        # Fun World Records
        "what is the tallest building": "The Burj Khalifa in Dubai is the tallest building.",
        "who has the longest lifespan": "The bowhead whale can live over 200 years!",
        "what is the fastest car": "The SSC Tuatara reached speeds over 300 mph.",
        "who is the richest person": "This changes often, but it’s usually a tech or business leader.",

        # Hypothetical Questions Part 2
        "what if time stopped": "It’d be a surreal experience to explore!",
        "what if we could fly": "It’d make traveling much easier and more fun!",
        "what if there was no gravity": "Everything would be floating around!",
        "what if there were two suns": "We’d likely have much warmer days and shorter nights.",

        # General Knowledge
        "who invented the internet": "The internet was developed by multiple contributors in the 1960s.",
        "what is the largest desert": "Antarctica is technically the largest desert by area!",
        "what is the tallest mountain": "Mount Everest, standing at 8,848 meters.",
        "what is the longest river": "The Nile River in Africa is the longest river.",

        # Closing Comments
        "that was fun": "I had a great time too!",
        "thanks for everything": "You're very welcome!",
        "let is chat again": "Anytime—you know where to find me!",
        "see you later": "Take care and see you soon!",
    }
    return expanded_responses.get(user_input.lower(), f"{get_further_expanded_response(user_input)}")

def get_further_expanded_response(user_input):
    further_expanded_responses = {
        # Technology and Innovation
        "what is artificial intelligence": "AI is the simulation of human intelligence in machines.",
        "what is machine learning": "A subset of AI that allows systems to learn from data.",
        "who created the first computer": "Charles Babbage is often credited with creating the first mechanical computer.",
        "what is blockchain": "A distributed ledger technology that securely records transactions.",

        # Historical Facts
        "who discovered America": "Christopher Columbus is credited, but indigenous peoples lived there long before.",
        "what caused the fall of the Roman Empire": "Multiple factors, including economic troubles and invasions.",
        "when did World War two start": "World War two started on September 1, 1939.",
        "who was Cleopatra": "The last active ruler of the Ptolemaic Kingdom of Egypt, known for her beauty and intelligence.",

        # Science and Nature
        "what is gravity": "Gravity is a force that pulls objects toward each other, keeping us grounded.",
        "what are black holes": "Regions in space where gravity is so strong that nothing can escape.",
        "how does photosynthesis work": "Plants convert sunlight into energy using chlorophyll.",
        "what is evolution": "The process through which species adapt over time through natural selection.",

        # Emotions and Mental Health
        "how do i cope with sadness": "Allow yourself to feel, talk to someone, and practice self-care.",
        "what should i do when i am angry": "Take deep breaths, count to ten, and express yourself calmly.",
        "how can i reduce anxiety": "Mindfulness, exercise, and seeking support can be very helpful.",
        "what is self-care": "Activities that improve your health and well-being, such as relaxation and hobbies.",

        # Lifestyle and Life Skills
        "how can i improve my cooking skills": "Practice regularly, watch tutorials, and experiment with recipes.",
        "how do i manage my time better": "Prioritize tasks, set deadlines, and eliminate distractions.",
        "what is a good budget tip": "Track your expenses to identify where you can save.",
        "how can i be more organized at home": "Create a cleaning schedule and declutter regularly.",

        # Humor and Lightheartedness
        "tell me a joke": "Why dont skeletons fight each other? They don’t have the guts!",
        "what is the funniest thing you know": "I think puns are the peak of humor!",
        "can you make me laugh": "Why did the scarecrow win an award? Because he was outstanding in his field!",
        "do you have a favorite joke": "I am a fan of all jokes—especially the punny ones!",

        # Philosophy and Thought-Provoking Questions
        "what is the meaning of happiness": "Happiness often comes from within and is a result of perspective.",
        "do we have free will": "That is a philosophical debate; some say yes, some say no.",
        "is there life after death": "Many beliefs exist, but no one truly knows for sure.",
        "what is consciousness": "Consciousness is the state of being aware of and able to think.",
        
        # Environmental Awareness
        "how can i reduce plastic use": "Use reusable bags, bottles, and containers.",
        "what are renewable energy sources": "Wind, solar, and hydroelectric power are great examples.",
        "how does climate change affect us": "It leads to extreme weather, rising sea levels, and impacts biodiversity.",
        "what can i do to help the planet": "Conserve energy, reduce waste, and support eco-friendly products.",

        # Learning and Development
        "how do i learn a new language": "Practice regularly, immerse yourself in the language, and use apps.",
        "what is the best way to study": "Find a method that works for you, such as flashcards or group study.",
        "how can i improve my writing skills": "Read more, practice regularly, and seek feedback.",
        "what is a good way to learn to code": "Start with online tutorials, and build small projects.",

        # Music and Art
        "what is your favorite song": "I love all genres of music! What's yours?",
        "who is the most famous artist": "Leonardo da Vinci and Vincent van Gogh are often mentioned.",
        "what is classical music": "A broad term for music composed from the 11th century onwards, often orchestral.",
        "what is a good song to cheer me up": "Try 'Happy' by Pharrell Williams! It’s quite uplifting.",

        # Food and Cuisine
        "what is a good healthy snack": "Try some fruit, yogurt, or nuts!",
        "how do I make a smoothie": "Blend your favorite fruits with yogurt or milk until smooth.",
        "what is the most popular food in the world": "Pizza is often listed as a global favorite!",
        "what is a unique dish i should try": "How about sushi? It's a delicious Japanese cuisine!",

        # Travel and Culture
        "where should i travel next": "Consider places you’ve always wanted to visit!",
        "what is the best city to live in": "It depends on personal preferences, but cities like Tokyo and Paris are popular!",
        "what is a cultural tradition I should know about": "Many cultures have unique festivals, like Diwali in India.",
        "what is a famous landmark": "The Eiffel Tower in Paris is iconic and loved by many.",

        # Inspirational Quotes
        "give me a motivational quote": "Believe you can, and you’re halfway there. - Theodore Roosevelt",
        "what is a good quote about life": "Life is what happens when you’re busy making other plans. - John Lennon",
        "tell me a quote about love": "Love all, trust a few, do wrong to none. - William Shakespeare",
        "share a quote about success": "Success is not the key to happiness. Happiness is the key to success. - Albert Schweitzer",

        # Weather and Seasons
        "what is the weather like today": "I can't check, but you can look it up on a weather app!",
        "what is your favorite season": "I think every season has its unique charm!",
        "what is a good activity for summer": "How about going to the beach or having a picnic?",
        "what should i do in winter": "Building a snowman or enjoying hot cocoa sounds lovely!",

        # Celebrations and Holidays
        "what is the best holiday": "Each holiday has its special meaning; it depends on personal preference!",
        "how do people celebrate New Year": "Traditions vary, but many celebrate with fireworks and parties!",
        "what is your favorite holiday tradition": "I love hearing about how people come together to celebrate!",
        "how do i celebrate my birthday": "Throw a party or enjoy a day doing your favorite activities!",

        # Random Knowledge
        "what is the fastest animal": "The peregrine falcon is the fastest bird, diving at speeds over 240 mph!",
        "what is the longest word in English": "Pneumonoultramicroscopicsilicovolcanoconiosis is often cited!",
        "how many bones are in the human body": "An adult human has 206 bones.",
        "what is the most spoken language": "Mandarin Chinese has the most native AnsWer.setAnsers.",

        # Curious Questions
        "why do we dream": "Dreams may help process emotions and memories.",
        "what is déjà vu": "A feeling that you've experienced something before.",
        "why do we yawn": "Yawning may help cool the brain and increase alertness.",
        "how does the brain work": "The brain processes information through electrical impulses and chemical signals.",

        # Life Challenges and Advice
        "how do i handle peer pressure": "Stay true to yourself and remember your values.",
        "what should i do if i im feeling lost": "Take a moment to reflect on your feelings and seek guidance from trusted sources.",
        "how do i face my fears": "Start small and gradually expose yourself to what you fear.",
        "how can i build resilience": "Learn from challenges, stay positive, and keep pushing forward.",

        # Random Thought Starters
        "what is your favorite movie": "I can’t watch movies, but I hear 'Inception' is mind-bending!",
        "what is a good book recommendation": "You might enjoy '1984' by George Orwell for its thought-provoking themes.",
        "what is an interesting hobby": "Collecting stamps or learning a musical instrument can be fun!",
        "what is something I should try at least once": "Traveling solo can be a transformative experience!",

        # Self-Reflection and Growth
        "how do i learn from mistakes": "Reflect on what happened, and think about how you can improve next time.",
        "what is personal growth": "It is the process of improving yourself through actions, attitudes, and experiences.",
        "how can i develop new habits": "Start with small changes, track your progress, and stay consistent.",
        "what is the best way to learn about myself": "Journaling, meditation, and self-reflection are great methods.",

        # Future and Aspirations
        "what should i do with my life": "Explore your interests and passions, it can lead you to your purpose.",
        "how do i set my life goals": "Think about what you want to achieve, then break it down into actionable steps.",
        "what is a good career path": "Choose one that aligns with your skills and passions!",
        "how do i find my passion": "Try new things and pay attention to what excites you the most.",

        #My questions
        "" : "",
        "what are smart watches":"Smart watches are the watches but they have few capablities to do small things like smart phones."
    }
    return further_expanded_responses.get(user_input.lower(), f"{runCMD(user_input)}")

    
# run cmd
def runCMD(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
        return("Command output:", result.stdout)
    except:
        return f"{execute_code(cmd)}"

def execute_code(code: str):
    """
    Executes Python code passed as a string and returns the result.
    :param code: Python code as a string
    :return: The result of the executed code or an error message
    """
    # Capture the output of the code execution
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {})
        return output.getvalue().strip() or "Code executed successfully, but no output."
    except Exception as e:
        return f"{wiki(code)}"

def wiki(user_input):
    """Fetch information from Wikipedia."""
    try:
        summary = wikipedia.summary(user_input, sentences=2)
        return f"According to Wikipedia: " + summary
    except wikipedia.exceptions.DisambiguationError as e:
        return f"{count(user_input)}"
    except wikipedia.exceptions.PageError:
        return f"{count(user_input)}"
    except Exception:
        return f"{count(user_input)}"

def count(noString):
    No = 0
    try:
        No = eval(noString)  # Evaluates expressions like "1 + 2" to 3
        return f"{str(No)}."
    except Exception:
        return f"{handle(noString)}"

# Function to handle the response and return formatted string
def handle(query, num_results=2):
    try:
        response = ans(query, num_results)
        answer = '\n'
        
        # Handle books from Open Library
        answer += ("Books from Open Library:\n")
        if isinstance(response['books'], str):
            answer += (response['books'] + "\n")
        else:
            for book in response['books']:
                answer += (f"Title: {book['title']}\n")
                answer += (f"Author(s): {book['author']}\n")
                answer += (f"First Published: {book['first_publish_year']}\n")
                answer += (f"ISBN: {book['isbn']}\n")
                answer += ("-" * 50 + "\n")
        
        # Handle Google search results
        answer += ("\nGoogle Search Results:\n")
        for result_type, results in response['google_results'].items():
            answer += (f"\n{result_type.capitalize()} Results:\n")
            if isinstance(results, str):
                answer += (results + "\n")
            else:
                for result in results:
                    answer += (f"Title: {result['title']}\n")
                    answer += (f"Link: {result['link']}\n")
                    answer += (f"Snippet: {result['snippet']}\n")
                    if 'author' in result:
                        answer += (f"Author: {result['author']}\n")
                    answer += ("-" * 50 + "\n")
        return answer  
    except:
          get_response_bot(query)

def get_response_bot(user_input):
    """Generate a chatbot response using the model."""
    global chat_history_ids  # Access the global chat history variable
    
    # Encode the user input and add the end-of-sentence token
    new_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
    
    # Concatenate the new input with the chat history if it exists
    if chat_history_ids is not None:
        chat_history_ids = torch.cat([chat_history_ids, new_input_ids], dim=-1)
    else:
        chat_history_ids = new_input_ids

    # Generate a response using the model
    bot_output = model.generate(
        chat_history_ids,
        max_length=1000,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,  # Enable sampling to introduce randomness
        top_k=50,        # Limit to top-k words for generation
        top_p=0.95       # Nucleus sampling
    )
    
    # Decode the bot's response and extract the new part
    response = tokenizer.decode(bot_output[:, chat_history_ids.shape[-1]:][0], skip_special_tokens=True)
    
    # Handle repetitive responses
    response_variations = [
        "That's an interesting question!",
        "Let me think about that...",
        "I'm not quite sure how to respond to that.",
        "Can you clarify what you mean?",
        "That's a bit tricky!"
    ]
    # 
    if response.strip() in [user_input, user_input + '?']:
        response = random.choice(response_variations)
    
    return "Bot: " + response.split('\n')[0]  # Return the first line of the response

def main(command):
        greet()
        global todo_list  # Declare the global variable for the to-do list
        todo_list = ["Saying hello to my mom"]  # Example to-do list

        if "wikipedia" == command or "summary" == command:
            Ans.setAns(AnsWer,"What topic would you like to know about?")
            topic = listen()
            if topic:
                get_wikipedia_info(topic)
        
        elif "countdown timer" == command or "coundown timer" == command or "timer" == command:
            Ans.setAns(AnsWer,"How many seconds.")
            seconds = int(listen())
            if seconds:
                Ans.setAns(AnsWer,f"Start timer for {seconds} seconds.")
                while seconds:
                    mins, secs = divmod(seconds, 60)
                    timer = f"{mins:02d}:{secs:02d}"
                    print(timer, end="\r")
                    time.sleep(1)
                    seconds -= 1
                Ans.setAns(AnsWer,"Time's up!")

        elif "weather" == command or "environment" == command:
            # Get the city and then use it to fetch the weather
            city = get_city()
            if "Error" not in city:
                temperature, description = get_weather(city)
                Ans.setAns(AnsWer,f"The weather in {city} is {temperature}°C with {description}.")
            else:
                print(city)
                
        elif "city" == command:
            city = get_city()
            print(city)

        elif  "what is happening" == command or "what happened" == command or "news" == command:
            get_news()

        elif "exit" == command or "stop" == command:
            Ans.setAns(AnsWer,"Are you sure you want to exit?")
            confirm_exit = listen()
            if "yes" in confirm_exit or "exit" in confirm_exit:
                Ans.setAns(AnsWer,"Goodbye!")
        
        elif "tell me a joke" == command:
            tell_joke()

        elif "recommend a movie" == command:
            recommend_movie()

        elif "set a timer for" == command or command == "set timer" or "start timer" == command:
            try:
                minutes = int(command.split("for")[-1].strip().split()[0])  # Extract minutes
                set_timer(minutes)
            except ValueError:
                Ans.setAns(AnsWer,"I couldn't understand the number of minutes.")

        elif "convert" == command:
            # Example: "Convert 5 miles to kilometers"
            parts = command.split()
            try:
                value = float(parts[1])
                unit_from = parts[2]
                unit_to = parts[-1]
                convert_units(value, unit_from, unit_to)
            except (IndexError, ValueError):
                Ans.setAns(AnsWer,"I couldn't understand the conversion request.")

        elif "add to my to do list" == command:
            item = command.split("add to my to do list")[-1].strip()
            add_to_todo_list(item)

        elif "open file" == command or "file" == command:
            Ans.setAns(AnsWer,"Type your file path here.")
            name = input("User said (manual input): ")  # Assume this input is the file path
            file_path = os.path.join(name)

            # Check if the file exists before attempting to open
            if os.path.isfile(file_path):
                try:
                    # Using 'start' for Windows, 'open' for macOS, and 'xdg-open' for Linux
                    command = f'start {file_path}' if os.name == 'nt' else f'open {file_path}' if os.name == 'posix' else f'xdg-open {file_path}'
                    result = subprocess.run(command, capture_output=True, text=True, shell=True)
                    Ans.setAns(AnsWer,f"The output of your path is: \n{result.stdout if result.stdout else 'File opened successfully.'}")
                except Exception as e:
                    Ans.setAns(AnsWer,f"An error occurred: {str(e)}")
            else:
                Ans.setAns(AnsWer,"The file does not exist. Please check the path and try again.")

        elif "open facebook" == command:
            open_website("https://www.facebook.com/")
            Ans.setAns(AnsWer,"Opening facebook")

        elif "open itchio" == command or "open itch.io" == command:
            open_website("https://itch.io/")
            Ans.setAns(AnsWer,"Opening itch.io.")

        elif "open whatsapp" == command:
            open_website("https://web.whatsapp.com/")
            Ans.setAns(AnsWer,"Opening WhatsApp.")

        elif "open youtube" == command:
            open_website("https://www.youtube.com/")
            Ans.setAns(AnsWer,"Opening youtube.")

        elif "open web" == command or "run web" == command:
            Ans.setAns(AnsWer,"What would you like to open?")
            site = listen()
            if site:
                open_website(site)

        elif command == "open bing" or "open ms" == command or "open microsoft edge" == command or "open edge" == command or 'open ms edge' == command or "open ms-edge" == command:
            open_website("https://www.bing.com/")
            Ans.setAns(AnsWer,"Opening MS edge.")

        elif "open app" == command or 'file application' == command:
            #if "open file" == command or "file" == command:
            Ans.setAns(AnsWer,"Type your app name here.")
            name = input("User said (manual input): ")  # Assume this input is the file path
            file_path = os.path.join('C:\\Users\\TECHNOSELLERS\\Desktop',name)

            # Check if the file exists or if it's a valid shortcut
            if os.path.isfile(file_path) or (os.path.splitext(file_path)[1] == '.lnk' and os.path.exists(file_path)):
                try:
                    # Using 'start' for Windows, 'open' for macOS, and 'xdg-open' for Linux
                    command = f'start {file_path}' if os.name == 'nt' else f'open {file_path}' if os.name == 'posix' else f'xdg-open {file_path}'
                    result = subprocess.run(command, capture_output=True, text=True, shell=True)
                    Ans.setAns(AnsWer,f"The output of your path is: \n{result.stdout if result.stdout else 'File or shortcut opened successfully.'}")
                except Exception as e:
                    Ans.setAns(AnsWer,f"An error occurred: {str(e)}")
            else:
                Ans.setAns(AnsWer,"The app or it's shortcut does not exist. Please check the app name and try again.")

        elif "open google" == command or "start google" == command:
            webbrowser.open("https://www.google.com/")
            Ans.setAns(AnsWer,"Opening Google.")

        elif "search on google" == command:
            Ans.setAns(AnsWer,"What would you like to search for?")
            query = listen()
            if query:
                webbrowser.open(f"https://www.google.com/search?q={query}")

        elif "hello" == command or "hi" == command:
            Ans.setAns(AnsWer,"hello. I am here to help you today.")

        elif "what are you doing" == command:
            Ans.setAns(AnsWer,"I am answering your commands.")

        elif "location" == command or "country" == command or "region" == command or "cordinates" == command:
            try:
                response = requests.get("https://ipinfo.io")
                data = response.json()
                country = data.get("country")
                city = data.get("city")  # Access the city directly
                region = data.get("region")
                location = data.get("loc")  # Retrieves latitude and longitude
                Ans.setAns(AnsWer,f" Country: {country}, Region: {region}, City: {city}, and Cordinates are {location}.")
            except requests.RequestException as e:
                print(f"Jarvis: Error: {e}")


        elif "close" == command or "unrun" == command:
            Ans.setAns(AnsWer,"Which app would you like to close?")
            name = listen()
            
            if name in ["chrome", "firefox", "edge"]:
                # Close specific browser by name; adjust based on your OS and browser choice
                if name == "chrome":
                    Ans.setAns(AnsWer,"Closing chrome.")
                    os.system("taskkill /f /im chrome.exe")  # For Windows
                elif name == "firefox":
                    Ans.setAns(AnsWer,"Closing FireFox.")
                    os.system("taskkill /f /im firefox.exe")  # For Windows
                elif name == "edge":
                    Ans.setAns(AnsWer,"Closing Edge.")
                    os.system("taskkill /f /im msedge.exe")  # For Windows
            else:
                try:
                    os.system(f"taskkill /f /im {name}.exe")  # For Windows
                    Ans.setAns(AnsWer,f"{name.capitalize()} application closed.")
                except Exception as e:
                    Ans.setAns(AnsWer,f"Could not close {name}. Error: {e}.")

        elif "what is apple" == command:
            Ans.setAns(AnsWer,"which are you saying, about apple fruit or apple company, do you want to visit apple official web.")
            answer = listen()
            if answer == "yes" or answer == "visit":
                webbrowser.open("https://www.apple.com/")
                Ans.setAns(AnsWer,"opening apple official web")

        elif "samsung" == command or "oppo" == command or "android" in command:
            Ans.setAns(AnsWer,"The mobile which you are talking is android. Do you want to open android official web")
            answer = license()
            if answer == "yes":
                webbrowser.open("https://www.android.com/")
                Ans.setAns(AnsWer,"opening anddroid official web")

        elif "random" == command:
            Ans.setAns(AnsWer,f"Your random number is {random.randint(-1000000, 1000000)}.")

        elif "numeric" == command:
            Ans.setAns(AnsWer,"say numeric what you want to try.")
            s = listen()
            if s:
                Ans.setAns(AnsWer,f"{s.isdigit()}")

        elif "smallest factor" == command:
            Ans.setAns(AnsWer,"Say Number! to get smallest factor")
            n = int(listen())
            if n:
                for i in range(2, n + 1):
                    if n % i == 0 and is_prime(i):
                        Ans.setAns(AnsWer,f"{i}")

        elif "ascii value" == command:
            Ans.setAns(AnsWer,"Say Ascii value.")
            char = listen()
            if char:
                Ans.setAns(AnsWer,f"Your value is {ord(char)}.")

        elif "char from ascii" == command:
            Ans.setAns(AnsWer,"What thing char do you want.")
            Str = listen()
            if Str:
                Ans.setAns(AnsWer,f"Your value is {chr(Str)}.")
        
        elif "get quote" == command:
            Ans.setAns(AnsWer,"The only limit to our realization of tomorrow is our doubts of today.")

        elif "reverse word" == command:
            Ans.setAns(AnsWer,"Say a word to reverse.")
            s = listen
            if s:
                Ans.setAns(AnsWer,str(s[::-1]))

        elif "hex to rgb" == command:
            Ans.setAns(AnsWer,"Say the hex value to convert into rbg.")
            hex_color = listen()
            hex_color = hex_color.lstrip('#')
            Ans.setAns(AnsWer,str(tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))))
        
        elif "longest word" == command:
            Ans.setAns(AnsWer,"Say sentence to get longest word.")
            sentence = listen()
            if sentence:
                words = sentence.split()
                Ans.setAns(AnsWer,"The longest word in the sentence is "+str(max(words, key=len))+'.')

        elif "smallest word" == command:
            Ans.setAns(AnsWer,"Say sentence to get smallest word.")
            sentence = listen()
            if sentence:
                words = sentence.split()
                Ans.setAns(AnsWer,"The smallest word is "+str(sum(c.isdigit() for c in s))+".")

        elif "smallest prime factor" == command:
            Ans.setAns(AnsWer,"Say a number to get smallest factor")
            for i in range(2, n + 1):
                if n % i == 0 and is_prime(i):
                    Ans.setAns(AnsWer,"The smallest prime factor is "+str(i)+".")

        elif "count words" == command:
            Ans.setAns(AnsWer,"Word to count chars")
            s = listen
            Ans.setAns(AnsWer,str(len(s.split())))

        elif "time" == command or "now" == command or "date" == command or "year" == command or "month" == command or "day" == command or "current time" == command or "current now" == command or "current date" == command or "current year" == command or "current month" == command or "current day" == command:
            now = datetime.datetime.now()  # Get the current date and time only once
            time = now.strftime("%H:%M:%S")  # Format time as HH:MM:SS
            date = now.strftime("%Y-%m-%d")  # Format date as YYYY-MM-DD
            day = now.day  # Get the day of the month
            month = now.month  # Get the month number
            year = now.year  # Get the current year
            Ans.setAns(AnsWer,f"The current time is {time}, the current date is {date}, the current day is {day}, the current month is {month}, and the current year is {year}.")


        elif "is valid email" == command:
            Ans.setAns(AnsWer,'What email you are asking for is valid.')
            email = listen()
            if email:
                pattern = r"[^@]+@[^@]+\.[^@]+"
                Ans.setAns(AnsWer,re.match(pattern, email) is not None)

        elif "count vowels" == command:
            Ans.setAns(AnsWer,"Say the word to count Vowels.")
            s = int(listen)
            if s:
                Ans.setAns(AnsWer,"The count of vowels is "+str(sum(1 for char in s if char.lower() in 'aeiou')))

        elif "count consonants" == command:
            Ans.setAns(AnsWer,"Say a word to count consonants")
            s = listen()
            Ans.setAns(AnsWer,"The count of consonants is "+str(sum(1 for char in s if char.isalpha() and char.lower() not in 'aeiou')))

        elif 'create directory' == command:
            Ans.setAns(AnsWer,"Say directory.")
            directory = listen()
            if directory:
                Ans.setAns(AnsWer,'Creating your directory.')
                os.makedirs(directory, exist_ok=True)
                Ans.setAns(AnsWer,'Directory created.')

        elif "count spaces" == command:
            Ans.setAns(AnsWer,"Say a sentence to count spaces.")
            s = listen
            if s:
                Ans.setAns(AnsWer,"The count of spaces in a sentence is "+str(s.count(' '))+".")

        elif "square" == command:
            Ans.setAns(AnsWer,"Say Number to get square.")
            n = int(listen)
            Ans.setAns(AnsWer,str(n ** 2))
        
        elif "cube" == command:
            Ans.setAns(AnsWer,"Say Number to get cube.")
            n = int(listen)
            Ans.setAns(AnsWer,str(n ** 3))

        elif "decimal to binary" == command:
            Ans.setAns(AnsWer,"Say numbers to get binary.")
            n = int(listen())
            Ans.setAns(AnsWer,str(bin(n).replace("0b", "")))

        elif 'binary to decimal' == command:
            Ans.setAns(AnsWer,"Say bunary to convert into decimal.")
            b = int(listen())
            if b:
                Ans.setAns(AnsWer,str(int(b, 2)))

        elif 'first element' == command:
            Ans.setAns(AnsWer,"Say word to get first element.")
            lst = listen()
            if lst:
                value = lst[0] if lst else None
                Ans.setAns(AnsWer,str(value))

        elif "max in dict" == command:
            Ans.setAns(AnsWer,"Say directory.")
            d = listen()
            if d:
                Ans.setAns(AnsWer,str(max(d.values())))

        elif "min in dict" == command:
            Ans.setAns(AnsWer,"Say directory.")
            d = listen()
            if d:
                Ans.setAns(AnsWer,str(min(d.values())))

        elif "key of max value" == command:
            Ans.setAns(AnsWer,"Say drectory to get max value.")
            d = listen()
            if d:
                Ans.setAns(AnsWer,str(max(d, key=d.get)))

        elif 'key of min value' == command:
            Ans.setAns(AnsWer,"Say drectory to get min value.")
            d = listen()
            if d:
                Ans.setAns(AnsWer,str(min(d, key=d.get)))

        elif "current unix timestamp"  == command:
            Ans.setAns(AnsWer,"Your timestamp value is "+str(int(time.time()))+".")

        elif "timestamp to human readable"in command:
            ts = int(time.time())
            datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

        elif "day of week" == command:
            date_string = f"{datetime.datetime.now().date}"
            date = datetime.datetime.strptime(date_string, '%Y-%m-%d')
            Ans.setAns(AnsWer,date.strftime("%A"))

        elif "calculate age" == command:
            Ans.setAns(AnsWer,"Say your birth date.")
            birth_date = listen()
            today = datetime.datetime.now()
            birth_date = datetime.datetime.strptime(birth_date, '%Y-%m-%d')
            Ans.setAns(AnsWer,str(today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))))

        elif "random color" == command:
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            Ans.setAns(AnsWer,color)

        elif "count lines" == command:
            Ans.setAns(AnsWer,"Input your file path here.")
            filename = input("User said (manual input): ")
            if filename:
                with open(filename, 'r') as file:
                    some = str(len(file.readlines()))
                    Ans.setAns(AnsWer,some)

        elif "random element from dict" == command:
            Ans.setAns(AnsWer,str(random.choice(list(d.items())) if d else None))

        elif "delete directory" == command:
            Ans.setAns(AnsWer,"Which directory you want to delete.")
            directory = listen()
            if directory:
                Ans.setAns(AnsWer,"Deleting directory.")
                os.rmdir(directory)
                Ans.setAns(AnsWer,"Directory is deleted.")

        elif "generate password" == command:
            characters = string.ascii_letters + string.digits + string.punctuation
            length = 12
            Ans.setAns(AnsWer,"Your passor is "+''.join(random.choice(characters) for _ in range(length)))

        elif "check internet" == command or "is internet working"  == command:
            try:
                # Attempting to connect to Google to check internet availability
                response = requests.get("https://www.google.com", timeout=5)
                if response.status_code == 200:
                    Ans.setAns(AnsWer,"Internet is working.")
                else:
                    Ans.setAns(AnsWer,"Internet is connected, but there's an issue with the connection.")
            except requests.ConnectionError:
                Ans.setAns(AnsWer,"Your internet is not working.")
            except requests.Timeout:
                Ans.setAns(AnsWer,"The connection timed out. Please check your internet.")


        elif "get ip address" == command:
            apikey = {requests.get("https://api.ipify.org").text}
            Ans.setAns(AnsWer,f"Your api key is {apikey}.")

        elif "find lenght of a word" in command:
            Ans.setAns(AnsWer,"Say a word to count length")
            s = listen()
            if s:
                Ans.setAns(AnsWer,str(len(s)))

        
        elif "i have an error" == command or "i got a priblem" == command:
            Ans.setAns(AnsWer,"Oh! no. can i help, you to solve this problem.")

        elif "what is your name" == command:
            Ans.setAns(AnsWer,"My name is jarvis AI.")

        elif "run cmd" == command or "run command" == command:
            Ans.setAns(AnsWer,"Which command do you want to run.")
            cmd = input("User said (manual input): ")
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            print(result.stdout)


        elif "run cmd" == command or "run command" == command:
            Ans.setAns(AnsWer,"Which command do you want to run?")
            cmd = input("User said (manual input): ")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
                print("Command output:", result.stdout)
            except subprocess.CalledProcessError as e:
                Ans.setAns(AnsWer,"The command failed to execute.")
            except Exception as e:
                Ans.setAns(AnsWer,"An unexpected error occurred.")

        elif "increase the volume" == command or "increase volume" == command:
            add_system_volume(0.1)  # Increase volume by 10%
            Ans.setAns(AnsWer,"Increasing volume by 10%.")

        elif "decrease the volume" == command or "decrease volume" == command:
            add_system_volume(-0.1)  # decrease volume by 10%
            Ans.setAns(AnsWer,"decreasing volume by 10%.")

        elif "set volume to 100" == command or "set volume to full" == command or "full volume" == command:
            set_system_volume(1)
            Ans.setAns(AnsWer,"Volume is set to 100%")
 
        elif "set volume to 0" == command or command == "mute" or "mute volume" == command:
            Ans.setAns(AnsWer,"Volume is set to 0%")
            set_system_volume(0)
        # news
        elif "execute code" == command:
            Ans.setAns(AnsWer,"What code do you want to execute.")
            code = input("Type code here: ")
            execute_code(code)

        elif "google search" == command or "search" == command or "google" == command:
            Ans.setAns(AnsWer,"What do you want to search.")
            num = listen()
            Ans.setAns(AnsWer,handle(num))

        else:
            answer = get_response(command)
            Ans.setAns(AnsWer,answer)
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
# 
app = Flask(__name__)

# A simple AI function (replace this with your AI logic)
def get_ai_response(question):
    # Example response, you can integrate your AI here
    main(question)
    return f"{Ans.currAns(AnsWer)}"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()  # Get the JSON data
    question = data.get("question")
    
    if question:
        answer = get_ai_response(question)
        return jsonify({"answer": answer})
    
    return jsonify({"answer": "Sorry, I didn't understand the question."})

if __name__ == "__main__":
    app.run(debug=True)
