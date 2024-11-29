import os
import openai
import json
import hmac
import hashlib
import time
import re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt import App
from dotenv import find_dotenv, load_dotenv
from flask import Flask, request, jsonify, abort
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import DirectoryLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain_openai import OpenAIEmbeddings


# Set Slack API credentials
SLACK_BOT_TOKEN = "replace your bot token here..."
SLACK_SIGNING_SECRET = "replace your key here..."
SLACK_BOT_USER_ID = "slackbot user id..."  # Set this after fetching

# Initialize the Slack app
# Initialize the Slack app with the signing secret
app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Initialize the Flask app
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# Set OpenAI API Key
OPENAI_API_KEY = "your openai key..."
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
openai.api_key = OPENAI_API_KEY
embeddings_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# Load the LocalAI directory
loader = DirectoryLoader("paste your directory, windows must use // instead of single slash...)
index = VectorstoreIndexCreator(embedding=embeddings_model).from_loaders([loader])

# Adjusted custom pretext
custom_pretext = (
    "You are the LocalAI assistant. "
    "When providing answers, please format your response using Slack's formatting syntax: "
    "- Use single asterisks (*) around text to make it bold. "
    "- Do not use Markdown headings like ###. "
    "- Instead of headings, use bold text on a new line. "
    "Avoid any formatting that is not supported by Slack.\n\n"
)

# Initialize the conversation chain for gpt-4o engine
chain = ConversationalRetrievalChain.from_llm(
    llm=ChatOpenAI(model="gpt-4o-2024-05-13"),
    retriever=index.vectorstore.as_retriever(search_kwargs={"k": 20}),
)

def query_openai_model(input_text, custom_pretext):
    result = chain({"question": custom_pretext + input_text, "chat_history": []})
    return result['answer']

def get_bot_user_id():
    try:
        slack_client = WebClient(token=SLACK_BOT_TOKEN)
        response = slack_client.auth_test()
        return response["user_id"]
    except SlackApiError as e:
        print(f"Error: {e}")

def format_for_slack(text):
    # Replace '### ' headings with bold text
    text = re.sub(r'^### (.*)', r'*\1*', text, flags=re.MULTILINE)
    
    # Replace '**text**' with '*text*' for bold text
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # Handle any additional formatting as needed
    return text

@app.event("app_mention")
def handle_mentions(body, say):
    text = body["event"]["text"]

    mention = f"<@{SLACK_BOT_USER_ID}>"
    text = text.replace(mention, "").strip()

    response = query_openai_model(text, custom_pretext)
    formatted_response = format_for_slack(response)
    say(formatted_response)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

SLACK_BOT_USER_ID = get_bot_user_id()
print(f"Bot User ID: {SLACK_BOT_USER_ID}")

# Run the Flask app
if __name__ == "__main__":
    flask_app.run(port=3000)