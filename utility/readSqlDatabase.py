from sqlalchemy import text, create_engine
from decimal import Decimal
from datetime import datetime
import urllib
import os

conn_str = os.getenv('SQL_CONNECTION_STRING')

if isinstance(conn_str, bytes):
    conn_str = conn_str.decode('utf-8')  # Convert bytes to string

conn_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
engine = create_engine(conn_url)
 
def readSqlDatabase(sql_query):
    with engine.connect() as connection:
        result = connection.execute(text(sql_query))
        rows = [dict(row._mapping) for row in result]
        headers = list(rows[0].keys()) if rows else []
        # Round decimal values to 2 decimal places and format dates in UK format (DD/MM/YYYY)
        for row in rows:
            for key, value in row.items():
                if isinstance(value, Decimal):  # Check if the value is a Decimal
                    row[key] = round(value, 2)  # Round the decimal value to 2 decimal places
                elif isinstance(value, datetime):  # Check if the value is a datetime object
                    row[key] = value.strftime('%d/%m/%Y')  # Format date into UK format DD/MM/YYYY
                elif key == 'ReferralHour':  # Check for 'ReferralHour' column
                    row[key] = f'{int(value):02}:00'

    return headers, rows