def user_prompt(user_question,existing_question,existing_sql,context):
    if existing_sql:
        prompt = f'''
        You are tasked with generating an SQL query by updating the datetime and user intent fields.**
        1. **First, check if the `New User Question` contains a datetime. If found, use that datetime to update the SQL query.**
        2. **If no datetime is found in the `New User Question`, check the latest SQL from `Context Window`. Use the latest datetime found there to update the SQL query.**
        3. **If neither the `New User Question` nor the `Context Window` contains a datetime, use the datetime from the `SQL Query` (from the `Similar Question`).**
        4. **Do not modify the structure or variables of the SQL query. Only update the datetime and user intent fields.**
        
        **Context Window:** {context}
        **Similar Question:** {existing_question}
        **SQL Query from Similar Question:** {existing_sql}
        **New User Question:** {user_question}
        
        Return the SQL query with the datetime updated accordingly, preserving the structure.
        '''
    else:
        # If no SQL is found, generate a response using GPT-4
        prompt = f"{context}\nUser Question: {user_question}\nPlease provide a response based on the user's question."
    
    return prompt