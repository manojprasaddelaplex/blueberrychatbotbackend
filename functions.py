from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
import openai
import os
import re
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np
from utility.systemPrompt import system_prompt
from utility.userPrompt import user_prompt

load_dotenv(".env")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

endpoint = os.getenv("ENDPOINT_URL")
deployment = os.getenv("DEPLOYMENT_NAME")
search_endpoint = os.getenv("SEARCH_ENDPOINT")
search_key = os.getenv("SEARCH_KEY")
search_index = os.getenv("SEARCH_INDEX_NAME")
cognitive_service = os.getenv("COGNITIVE_SERVICE")
api_version = os.getenv("API_VERSION")
asure_openai_api_key = os.environ.get("AZURE_OPENAI_API_KEY")


client = openai.AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=asure_openai_api_key,
    api_version=api_version,
)

#MongoDB Configurations
clientMongo = MongoClient(os.getenv('CONNECTION_STRING'))
DB = clientMongo['ChabotFeedback']
collection = DB['BBChatBotOnline']


def is_follow_up(user_input):
    keywords = ["then"]
    return any(keyword in user_input.lower() for keyword in keywords)

def insertQueryLog(userQuestion, sqlQuery=None, Response=None, exceptionMessage=None, 
                     isDataFetchedFromDB=False, isCorrect=None, feedbackDateTime=None):
    
    document = {
        "UserQuestion":userQuestion,
        "SqlQuery": sqlQuery,
        "Response":Response,
        "ExceptionMessage":exceptionMessage,
        "IsDataFetchedFromDB":isDataFetchedFromDB,
        "IsCorrect":isCorrect,
        "CreatedDateTime": datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
        "FeedbackDateTime":feedbackDateTime
    }
    
    insertDocument = collection.insert_one(document=document)
    return insertDocument.inserted_id

def format_headers(headers):
    def format_header(header):
        formatted = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', header)
        return formatted
    
    if type(headers)==str:
        return format_header(headers)

    return [format_header(header) for header in headers]


def saveFeedback(resID,feedback,userQuestion):
    existing_correct = collection.find_one({
        "UserQuestion": userQuestion,
        "IsCorrect": feedback
    })

    if not existing_correct:
        collection.update_one(
            {"_id": ObjectId(resID)},
            {"$set": {
                "IsCorrect": feedback,
                "FeedbackDateTime": datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            }}
        )


def find_best_matching_user_questions(userQuestion):
    try:
        # Perform a text search to find the best matching UserQuestion
        results = list(collection.find(
            {
                "$text": {"$search": userQuestion},  # Use text search for matching
                "IsCorrect": True,
                "ExceptionMessage": None
            },
            sort=[("score", {"$meta": "textScore"}), ("createdAt", 1)],  # Sort by text score (highest first)
            projection={"UserQuestion": 1, "score": {"$meta": "textScore"}, "_id": 0}  # Project UserQuestion and score
        ).limit(10))  # Limit to top 5 results

        # Use a set to track unique questions
        seen_questions = set()
        unique_results = []

        for res in results:
            user_question = res['UserQuestion']
            if user_question not in seen_questions:
                seen_questions.add(user_question)
                unique_results.append(user_question)

        return unique_results[:3] if unique_results else None
    except Exception as e:
        return None



def load_data(sql_files, generic_file):
    sql_question_sql_pairs = []
    
    # Load SQL-related files, each file has 50 questions and 1 shared SQL query
    for file in sql_files:
        df = pd.read_csv(file)
        questions = df['question'].tolist()
        sql = df['sql'].iloc[0]  # First SQL applies to all questions in the file
        sql_question_sql_pairs.append((questions, sql))
    
    # Load the generic question-answer pairs
    generic_df = pd.read_csv(generic_file)
    generic_questions = generic_df['question'].tolist()
    generic_answers = generic_df['answer'].tolist()

    return sql_question_sql_pairs, generic_questions, generic_answers

# Embed questions for similarity search
def preprocess_and_embed_questions(sql_question_sql_pairs, generic_questions):
    sql_question_embeddings = []
    for questions, _ in sql_question_sql_pairs:
        embeddings = embedding_model.encode(questions, convert_to_tensor=True)
        sql_question_embeddings.append(embeddings)
    
    generic_embeddings = embedding_model.encode(generic_questions, convert_to_tensor=True)
    
    return sql_question_embeddings, generic_embeddings

# Find the most similar question across all SQL-related files
def find_similar_question(user_question, sql_question_sql_pairs, sql_question_embeddings, threshold=0.7):
    user_embedding = embedding_model.encode([user_question], convert_to_tensor=True)
    
    best_similarity = 0
    best_question = None
    best_sql = None
    
    # Search all files' questions for similarity
    for idx, embeddings in enumerate(sql_question_embeddings):
        similarities = cosine_similarity(user_embedding, embeddings)[0]
        file_best_match_idx = np.argmax(similarities)
        file_best_similarity = similarities[file_best_match_idx]
        
        # Update if this file has a better match
        if file_best_similarity > best_similarity:
            best_similarity = file_best_similarity
            matched_questions, sql = sql_question_sql_pairs[idx]
            best_question = matched_questions[file_best_match_idx]
            best_sql = sql
    
    # Return the best match if it's above the threshold
    if best_similarity > threshold:
        return best_question, best_sql
    else:
        return None, None

# Find similar question in the generic questions file
def find_in_generic_questions(user_question, generic_questions, generic_embeddings, threshold=0.7):
    user_embedding = embedding_model.encode([user_question], convert_to_tensor=True)
    similarities = cosine_similarity(user_embedding, generic_embeddings)[0]
    best_match_idx = np.argmax(similarities)
    best_similarity = similarities[best_match_idx]

    # Check if the similarity is above the threshold
    if best_similarity > threshold:
        return generic_questions[best_match_idx]
    
    return None


def get_gpt4omini_response(user_question,existing_question=None, existing_sql=None, context_window=None):
    if context_window is None:
        context_window = []
    
    # Prepare conversation history (last 3 question-answer pairs)
    context = "\n".join([f"Question {i+1}: {qa[0]}\nSQL/Answer of Question {i+1}: {qa[1]}" for i, qa in enumerate(context_window)])
    
    prompt = user_prompt(
        user_question=user_question,
        existing_question=existing_question,
        existing_sql=existing_sql,
        context=context
        )
    

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            system_prompt(),
            {"role": "user", "content": prompt}
        ],
        max_tokens=3000,
        temperature=0.3,
        top_p=0.95
    )
    return response.choices[0].message.content

# Main chatbot function
def chatbot(user_question, sql_question_sql_pairs, generic_questions, sql_question_embeddings, generic_embeddings, generic_answers, context_window):
    similar_question, sql = find_similar_question(user_question, sql_question_sql_pairs, sql_question_embeddings)
        
    if similar_question:
        # If similar question found, modify the SQL query using GPT-4
        modified_sql = get_gpt4omini_response(user_question,existing_question=similar_question, existing_sql=sql, context_window=context_window)
        #
        context_window.append((user_question, modified_sql))  # Update context window
        if len(context_window) > 3:  # Maintain only last 3 interactions
            context_window.popleft()
        return modified_sql
    
    # If no match in SQL-related files, try the generic questions
    generic_match = find_in_generic_questions(user_question, generic_questions, generic_embeddings)
    
    if generic_match:
        # Return the corresponding answer from generic answers
        answer_idx = generic_questions.index(generic_match)
        answer = generic_answers[answer_idx]
        context_window.append((user_question, answer))  # Update context window
        if len(context_window) > 3:  # Maintain only last 3 interactions
            context_window.popleft()
        return answer
    
    # If no match found, ask GPT-4 to generate a response
    gpt4_response = get_gpt4omini_response(user_question, context_window=context_window)
    context_window.append((user_question, gpt4_response))  # Update context window
    if len(context_window) > 3:  # Maintain only last 3 interactions
        context_window.popleft()
    return gpt4_response