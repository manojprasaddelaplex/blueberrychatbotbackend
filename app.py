from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from flasgger import Swagger, swag_from
from functions import insertQueryLog, azure_search_openai, readSqlDatabse, saveFeedback, extractSqlQueryFromResponse, manage_conversation_length, find_best_matching_user_questions
from swaggerData import main_swagger, feedback_swagger
from sqlalchemy.exc import SQLAlchemyError
import re

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
swagger = Swagger(app)



@app.route("/")
def home():
    return redirect('/apidocs/')

conversation_history = [
    {
        "role": "system",
        "content": '''
        You are Sonar Chatbot, an expert at converting natural language into SQL queries for SQL Server.
        End all SQL queries with a semicolon. You are strictly prohibited from performing data modification tasks; only fetch data.
        For non-SQL-related questions, keep your responses brief and relevant to your purpose.
        '''
    }
    ]

@app.route("/query", methods=["POST"])
@swag_from(main_swagger)
def query_db():
    user_query = request.json.get('query')
    user_query_lower = user_query.lower()
    
    global conversation_history
    conversation_history.append({"role": "user", "content": user_query})
    
    conversation_history = manage_conversation_length(conversation_history)
    
    try:
        sql_query = None
        if sql_query==None:
            response = azure_search_openai(conversation_history)
            sql_query = extractSqlQueryFromResponse(response=response)
            
            conversation_history.append({"role": "assistant", "content": response if sql_query==None else sql_query})
            
            #return text
            if sql_query == None:
                results = {"text":response}
                id = insertQueryLog(userQuestion=user_query,Response=results)
                return jsonify({"results":results, "id":str(id)}),200
                
                
        conversation_history.append({"role": "assistant", "content": sql_query})
        headers, rows = readSqlDatabse(sql_query)
        
        if((len(headers) or len(rows)) == 0):
            results = {"text":"I found 0 records in database on your search. Please try asking different question or adjust your search criteria."}
            id = insertQueryLog(userQuestion=user_query,sqlQuery=sql_query,Response=results)
            return jsonify({"results":results, "id":str(id), "sql_query":str(sql_query)}),200
        
        if re.search(r'\b(chart|graph)\b', user_query_lower):
            chartType = 'doughnut' if 'chart' in user_query_lower else 'bar'
            results = {
                    "labels": [str(row[headers[0]]) for row in rows],
                    "data": [str(row[headers[1]]) for row in rows],
                    "type" : chartType,
                }
            id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
            return jsonify({"results":results, "id":str(id), "sql_query":str(sql_query)}),200
        #returns data for table
        formatted_rows = [[str(row[header]) for header in headers] for row in rows]
        results = {
                "headers": headers,
                "rows": formatted_rows,
            }
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
        return jsonify({"results":results, "id":str(id), "sql_query":str(sql_query)}),200
    
    # except openai.error.OpenAIError as e:
    #     id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
    #     return jsonify({"error":f"OpenAI Model Error: {str(e)}", "id":str(id), "sql_query":str(sql_query)}), 500
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
