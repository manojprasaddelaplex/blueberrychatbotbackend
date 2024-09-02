from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
from sqlalchemy import create_engine, text
import openai
import os
import re
import urllib.parse

load_dotenv(".env")

# OpenAI API configuration
openai.api_key = os.getenv('OPENAI_API_KEY')
openai.api_base = os.getenv('OPENAI_API_BASE')
openai.api_type = os.getenv('OPENAI_API_TYPE')
openai.api_version = os.getenv('OPENAI_API_VERSION')

#MongoDB Configurations
client = MongoClient(os.getenv('CONNECTION_STRING'))
DB = client['ChabotFeedback']
collection = DB['BBChatBotOnline']

#SQL Server Configurations
conn_str = os.getenv('SQL_CONNECTION_STRING')
#conn_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"

if isinstance(conn_str, bytes):
    conn_str = conn_str.decode('utf-8')  # Convert bytes to string

conn_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
engine = create_engine(conn_url)

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


def generateSqlQuery(conversation_history):
    response = openai.ChatCompletion.create(
            deployment_id=os.getenv('DEPLOYMENT_ID'),
            messages=conversation_history,
            max_tokens=2000
        )
    return response.choices[0].message['content'].strip()


def readSqlDatabse(sql_query):
    with engine.connect() as connection:
        result = connection.execute(text(sql_query))
        rows = [dict(row._mapping) for row in result]
        headers = list(rows[0].keys()) if rows else []
    return headers, rows

def saveFeedback(resID,feedback):
    collection.update_one(
            {"_id": ObjectId(resID)},
            {"$set": {
                "IsCorrect": feedback,
                "FeedbackDateTime": datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                }
            }
        )


def findSqlQueryFromDB(userQuestion):
    result = collection.find_one(
        {"UserQuestion": userQuestion, "IsCorrect": True},
        sort=[("timestamp", 1)],  # Sort by timestamp in ascending order
        projection={"SqlQuery": 1}
    )
    return result['SqlQuery'] if result else None

def extractSqlQueryFromResponse(response):
    sql_pattern = r'(WITH|SELECT)[\s\S]+?;'
    matches = re.search(sql_pattern, response, re.IGNORECASE)
    if matches:
        return matches.group(0).strip()
    else:
        return None
