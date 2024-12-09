import os
from flask import Flask, request, jsonify
from openai import OpenAI
import time
import json

app = Flask(__name__)

client = OpenAI()
# Set your OpenAI API key
client.api_key = os.environ.get("OPENAI_API_KEY", None)

# Your previously created assistant ID
# You must create an assistant resource before using it.
# Example: assistant = openai.Assistant.create(name="My Assistant")
# Then: assistant_id = assistant.id
assistantID = os.environ.get("OPENAI_ASSISTANT_ID", None)


# Pretty printing helper
def response_dict(messages) -> dict:
    data = {}
    for m in messages:
        # If we haven't seen this role before, initialize a list
        if m.role not in data:
            data[m.role] = []
        # Append the message content to the list associated with this role
        # Assuming m.content[0].text.value is a string
        data[m.role].append(m.content[0].text.value)

    return data


def wait_on_run(run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


@app.route("/")
def hello():
    return "app is running"


@app.route("/chat", methods=["POST"])
def chat():
    """
    POST JSON:
    {
      "user_text": "hello my world",
      "thread_id": "<optional: if you have one from previous request>"
    }

    If no thread_id is provided, we create a new thread.
    Then we add the user_text as a message in that thread and get the assistant's response.
    Returns:
    {
      "response": "<assistant message>",
      "thread_id": "<thread_id>"
    }
    """
    data = request.get_json()
    if not data or "user_text" not in data:
        return jsonify({"error": "Missing 'user_text' in request"}), 400

    user_text = data["user_text"]
    thread_id = data.get("thread_id", None)

    # If no thread_id, create a new thread
    if not thread_id:
        try:
            # Create a new thread
            thread = client.beta.threads.create()
            thread_id = thread.id
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        # retrieve thread
        thread = client.beta.threads.retrieve(thread_id)

        # Add a message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_text,
        )

        # create a run (linking thread to assistant)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistantID,
            instructions="Be a helpful therapist",
        )
        run = wait_on_run(run, thread)

        if run.status == "completed":
            # contains all the messages between user and assistant
            messages = client.beta.threads.messages.list(thread_id=thread.id)

            # only last message (to show user)
            messages_last = client.beta.threads.messages.list(
                thread_id=thread.id, order="asc", after=message.id
            )
        else:
            print(run.status)

        conversation = client.beta.threads.messages.list(
            thread_id=thread.id, order="asc"
        )

        response = response_dict(conversation)

        return jsonify({"response": response, "thread_id": thread_id}), 200

    except Exception as e:
        print(e)
        return 500


@app.route("/thread/<thread_id>", methods=["GET"])
def retrieve_thread(thread_id):
    """
    Retrieve a thread and its messages.
    GET /thread/<thread_id>
    """
    try:
        thread = client.beta.threads.retrieve(
            assistant_id=assistantID, thread_id=thread_id
        )
        # The thread object includes messages, title, etc.
        return jsonify(thread), 200
    except Exception as e:
        return 500


if __name__ == "__main__":
    # Note: In production, you might want to run behind a WSGI server.
    app.run(host="0.0.0.0", port=5050, debug=True)
