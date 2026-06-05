import random

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

KNOWLEDGE_BASE_ID = "AOGLLMF80H"
MODEL_ARN = MODEL_ARN = MODEL_ARN = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
AWS_REGION = "us-east-2"
SYSTEM_PROMPT = """You are 'Melody', an expert, passionate, and highly knowledgeable music discovery assistant. Your goal is to help users discover new music and break out of their algorithmic echo chambers, using ONLY the provided documents (artist data, reviews, and genre descriptions).

CRITICAL INSTRUCTIONS FOR REASONING AND ANSWERING:
1. ACT LIKE A CURATOR: Do not act like a database reader. NEVER use phrases like "Based on the documents", "The documents don't contain", or "I don't have enough information". Hide the technical mechanics from the user.
2. CONNECT THE DOTS (CROSS-REFERENCING): When a user asks for abstract concepts (e.g., "Songs like Bon Iver but warmer"), use analytical reasoning:
   - First, identify the baseline artist's genre/vibe from the data.
   - Second, refer to the genre guidelines to understand the requested vibe (e.g., "warmer").
   - Third, search the data for other artists/albums that combine that genre with the requested vibe.
3. BE CONCISE AND PUNCHY: Give your recommendation immediately. Do not write long essays. Make your comparison ONCE and do not repeat the same point.
4. FOCUS ON THE POSITIVE: If you cannot find a perfect match, do not dwell on it and do not apologize repeatedly. Instead, confidently pivot and highlight the closest, most exciting recommendation you CAN find in the data based on mood, genre, or aesthetic.
5. LOGICAL FLOW: Your answer must be a cohesive, engaging narrative. Acknowledge the user's taste, present your recommendation, and explain exactly WHY they will love it based on the musical descriptions.
6. TONE: Be enthusiastic, inspiring, and focused entirely on the joy of discovering great music.
7. TERMINOLOGY: 'EDM' stands for 'Electronic Dance Music'. Treat these terms identically when searching the data and answering."""

QUESTIONS_LIST = [
    "Recommend indie-folk song from the late 2000s.",
    "What are some essential tracks with an acoustic, intimate vibe?",
    "Suggest an album filled with earnest lyrics and group vocals.",
    "Find artists who capture a cozy campfire aesthetic.",
    "What standout releases occurred between 2008 and 2009.",
    "Recommend something with jangly guitars and orchestral brightness.",
    "Which albums feature heart-on-sleeve vulnerability?",
    "Suggest upbeat indie-pop tracks to lift my mood.",
    "Find music that blends melancholy with high infectious energy.",
    "What are the best collaborative or band-centric projects?",
    "Recommend an album with raw, spontaneous production qualities.",
    "Find artists from the Welsh or UK indie scene.",
    "Suggest music perfect for thawing out on a cold winter night.",
    "What are some hidden gems in the indie rock genre?",
    "Give me a recommendation that feels completely organic and handmade.",
    "Suggest a high-energy dance track for a weekend party.",
     "What are some iconic pop albums with incredible vocal performances?",
     "Find an EDM artist known for heavy bass and fast tempos.",
     "Recommend a classic electronic album that defined the genre.",
     "Suggest an upbeat pop-dance track to get me moving.",
     "Find R&B or soul music with a modern, electronic twist.",
     "What are some highly-rated club anthems from the database?",
]


def query_bedrock(question):
    client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)

    response = client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": MODEL_ARN,
                "generationConfiguration": {
                    "promptTemplate": {
                        "textPromptTemplate": (
                            f"{SYSTEM_PROMPT}\n\n"
                            "Retrieved documents:\n"
                            "$search_results$\n\n"
                            "Answer:"
                        )
                    }
                },
            },
        },
    )

    return response.get("output", {}).get("text", "")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        question = (
            request.form.get("user_query")
            or request.form.get("question")
            or request.form.get("message")
            or data.get("user_query")
            or data.get("question")
            or data.get("message")
            or ""
        ).strip()
        if not question:
            return render_template("index.html", error="Question is required.")

        try:
            answer = query_bedrock(question)
        except (BotoCoreError, ClientError) as error:
            return render_template("index.html", error=f"Bedrock request failed: {error}")

        return render_template("index.html", response=answer, answer=answer, question=question)

    sample_queries = random.sample(QUESTIONS_LIST, 4)
    return render_template("index.html", sample_queries=sample_queries)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or data.get("message") or "").strip()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    if KNOWLEDGE_BASE_ID == "YOUR_KB_ID_HERE":
        return (
            jsonify(
                {
                    "error": (
                        "Set KNOWLEDGE_BASE_ID in app.py before querying "
                        "Amazon Bedrock Knowledge Bases."
                    )
                }
            ),
            500,
        )

    try:
        answer = query_bedrock(question)
    except (BotoCoreError, ClientError) as error:
        return jsonify({"error": f"Bedrock request failed: {error}"}), 500

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
