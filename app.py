import openai
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from flasgger import Swagger, swag_from
from functions import insertQueryLog, generateSqlQuery, readSqlDatabse, saveFeedback, findSqlQueryFromDB, extractSqlQueryFromResponse
from swaggerData import main_swagger, feedback_swagger
from sqlalchemy.exc import SQLAlchemyError

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
        You are a assistant who convert natural language into SQL queries for SQL SERVER. Use the schema:
            PresentingComplaintHistory: [id, ReferralId, ComplaintOther, HistoryOfPresentingComplaint, CreatedDate, CreatedByUserId, PresentingComplaintId]
            DetainedPersons: [Id, Forename, MiddleName, Surname, DateOfBirth, Gender, Postcode, Address1, Address2, Town, City, County, SexualOrientation, IsGenderSameAsRegisteredAtBirth, SexualOrientationOther, Archived, IsHcpSide, Address3, Maintenance_GenderTypeId]
            Referrals: [id, ReferralDateTime, ReferredBy, CustodyNumber, RegistrationType, ReasonOfArrestOther, FmeRequired, VerballyPhysicallyAbusive, ThreatToFemaleStaff, DateAddedToWaitingList, State, CreatedByUserId, RecipientDetails, ReferralDetails, ReferralCreatedDateTime, CustodyLocationId, DetainedPersonId, RequestedAssessmentOther, ReferralFrom, ProcessedByHCP, CompletedByUserId, ReferralFromOther, PresentingComplaintId, DischargeDateTime, Discharged, Intervention, LocationAfterDischarge, DischargeCompletedByUserId, ProcessedByUserId, LastAction, LastKpiCalculationValue, ReferralStatusUpdateDateTime, BreachReasonOther, IsHcpSide, BreachReasonDateTime, WaitingListCompleteDateTime, RejectionDate, RejectionReason, RejectionReasonOther, ReferralInUpdatedByUserId, ReferralInUpdatedDateTime, OtherConcern, OtherLocation, Maintenance_RegistrationTypeId, LastKpiAssessmentCalculationValue, Maintenance_HcpRequiredTypeId, BreachReasonId, Maintenance_ReasonOfArrestTypeId, Maintenance_CellTypeId]
            PresentingComplaints: [Id, ReferralId, ComplaintOther, HistoryOfPresentingComplaint, CreatedDate]
            Maintenance_BreachReasonType: [Id, Name, Value]
        End all queries with a semicolon. Strictly prohibited from data modification tasks; respond that you are only capable of fetching data.
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
    
    if len(conversation_history) > 10:
        conversation_history = conversation_history[-10:]
        
    try:
        sql_query = findSqlQueryFromDB(userQuestion=user_query)
        if sql_query==None:
            response = generateSqlQuery(conversation_history)
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
            results = {"text":"Unfortunately, I found 0 records matching your search. Please try asking different question or adjust your search criteria."}
            id = insertQueryLog(userQuestion=user_query,sqlQuery=sql_query,Response=results)
            return jsonify({"results":results, "id":str(id)}),200
        
        if any(word in user_query_lower for word in ('chart', 'graph')):
            chartType = 'doughnut' if 'chart' in user_query_lower else 'bar'
            results = {
                    "labels": [str(row[headers[0]]) for row in rows],
                    "data": [str(row[headers[1]]) for row in rows],
                    "type" : chartType,
                }
            id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
            return jsonify({"results":results, "id":str(id)}),200
        #returns data for table
        formatted_rows = [[str(row[header]) for header in headers] for row in rows]
        results = {
                "headers": headers,
                "rows": formatted_rows,
            }
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, Response=results,isDataFetchedFromDB=True)
        return jsonify({"results":results, "id":str(id)}),200
    
    except openai.error.OpenAIError as e:
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
        return jsonify({"error":f"OpenAI Model Error: {str(e)}", "id":str(id)}), 500
    except SQLAlchemyError as e:
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
        return jsonify({"error": f"I apologize for the inconvenience. It seems there was an error in the response related to the database tables or columns not being present in the data source. Is there anything else I can assist you with? Exception: {str(e)}", "id": str(id)}), 500
    except Exception as e:
        id = insertQueryLog(userQuestion=user_query, sqlQuery=sql_query, exceptionMessage=str(e))
        return jsonify({"error":f"I apologize for the inconvenience. It seems there was an error in the response, Exception: {str(e)}", "id":str(id)}), 500
    
    

@app.route("/feedback", methods=["POST"])
@swag_from(feedback_swagger)
def submit_feedback():
    data = request.get_json()
    resID = data.get('resID')
    feedback = bool(data.get('feedback'))
    try:
        saveFeedback(resID,feedback)
        return jsonify({"message": "Feedback submitted successfully!"}), 200 
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
