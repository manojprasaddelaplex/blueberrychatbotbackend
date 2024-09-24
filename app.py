from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from flasgger import Swagger, swag_from
from functions import load_data, preprocess_and_embed_questions, chatbot, insertQueryLog, readSqlDatabse, saveFeedback, extractSqlQueryFromResponse, find_best_matching_user_questions, format_headers,is_follow_up
from swaggerData import main_swagger, feedback_swagger
from sqlalchemy.exc import SQLAlchemyError
import re
from collections import deque


sql_files = [f"data/questions/Que{n}.csv" for n in range(1,15)]
generic_file = "data/questions/Generic.csv"

sql_question_sql_pairs, generic_questions, generic_answers = load_data(sql_files, generic_file)

# Generate embeddings for SQL-related and generic questions
sql_question_embeddings, generic_embeddings = preprocess_and_embed_questions(sql_question_sql_pairs, generic_questions)

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
swagger = Swagger(app)

 
@app.route("/")
def home():
    return redirect('/apidocs/')

user_contexts = {} 
 
@app.route("/query", methods=["POST"])
@swag_from(main_swagger)
def query_db():
    user_query = request.json.get('query')
    user_id = request.json.get('user_id')
    user_query_lower = user_query.lower()
    

    if user_id not in user_contexts:
        if is_follow_up:
            user_contexts[user_id] = deque(maxlen=1)
    context_window = user_contexts[user_id]
   
    sql_query = None
   
    try:
        if sql_query==None:
            response = response = chatbot(
                            user_question=user_query,
                            sql_question_sql_pairs=sql_question_sql_pairs,
                            generic_questions=generic_questions,
                            sql_question_embeddings=sql_question_embeddings,
                            generic_embeddings=generic_embeddings,
                            generic_answers=generic_answers,
                            context_window=context_window
                        )
            
            if response=="The requested information is not available in the retrieved data. Please try another query or topic.":
                base_err = response
                similar_questions = find_best_matching_user_questions(userQuestion=user_query)
 
                err = base_err + (" I can assist you in refining your search with similar questions. " if similar_questions else "") + "Is there anything else I can assist you with?"
                id = insertQueryLog(userQuestion=user_query, Response=response)
 
                results = {
                    "text": err,
                    "similar_questions":similar_questions
                }
       
                return jsonify({"results":results, "id": str(id)}), 200
           
           
            sql_query = extractSqlQueryFromResponse(response=response)
           
            #return text
            if sql_query == None:
                results = {"text":response}
                id = insertQueryLog(userQuestion=user_query,Response=results)
                return jsonify({"results":results, "id":str(id)}),200
               
               
        headers, rows = readSqlDatabse(sql_query)
       
        if((len(headers) or len(rows)) == 0):
            base_err = "I found 0 records in database on your search. Please try asking different question or adjust your search criteria. "
            similar_questions = find_best_matching_user_questions(userQuestion=user_query)
            err = base_err + (" I can assist you in refining your search with similar questions. " if similar_questions else "") + "Is there anything else I can assist you with?"
            id = insertQueryLog(userQuestion=user_query,sqlQuery=sql_query,Response=base_err)
            results = {
                "text": err,
                "similar_questions":similar_questions
            }
 
            return jsonify({"results":results, "id": str(id), "sql_query":str(sql_query)}), 200
       
        if re.search(r'\b(chart|graph)\b', user_query_lower):
            tip = "Hey there! The data seems a bit too big, and it might get confusing when you download it. Could you try reducing it to less than 10 entries? That downloaded file would be much clearer. Thank you!" if len([str(row[headers[0]]) for row in rows]) >10 else None
           
            chartType = 'doughnut' if 'chart' in user_query_lower else 'bar'
            results = {
                    "labels": [str(row[headers[0]]) for row in rows],
                    "data": [str(row[headers[1]]) for row in rows],
                    "type" : chartType,
                    "x_axis":format_headers(str(headers[0])),
                    "y_axis":format_headers(str(headers[1])),
                    "tip":tip
                }
            id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
            return jsonify({"results":results, "id":str(id), "sql_query":str(sql_query)}),200
       
       
        formatted_rows = [[str(row[header]) for header in headers] for row in rows]
        results = {
                "headers": format_headers(headers),
                "rows": formatted_rows,
            }
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
        return jsonify({"results":results, "id":str(id), "sql_query":str(sql_query)}),200
   
    except SQLAlchemyError as e:
        base_err = "I apologize for the confusion. It seems I misunderstood your question, leading to a response that is not related to the database tables and columns I have access to. "
        similar_questions = find_best_matching_user_questions(userQuestion=user_query)
   
        err = base_err + ("Here are some similar questions that might be helpful for you. " if similar_questions else "") + "Is there anything else I can assist you with?"
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
       
        results = {
            "error": err,
            "similar_questions":similar_questions,
            "id": str(id),
            "sql_query":str(sql_query)
        }
       
        return jsonify(results), 500
    except Exception as e:
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
        return jsonify({"error":f"I apologize for the inconvenience. It seems there was an error in the response, Please try some other questions.{e}", "id":str(id), "sql_query":str(sql_query)}), 500
   
   
 
@app.route("/feedback", methods=["POST"])
@swag_from(feedback_swagger)
def submit_feedback():
    data = request.get_json()
    resID = data.get('resID')
    feedback = bool(data.get('feedback'))
    userQuestion = data.get('userQuestion')
 
    try:
        saveFeedback(resID,feedback,userQuestion)
        return jsonify({"message": "Feedback submitted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
 
# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)