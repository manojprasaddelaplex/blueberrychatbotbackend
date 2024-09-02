# Swagger for @app.route("/query", methods=["POST"])
main_swagger = {
    'summary': 'Process user query to generate SQL and retrieve results.',
    'description': 'This endpoint processes the user query to generate an SQL statement using OpenAI, executes it against the database, and returns results in various formats such as text, table, chart, or graph.',
    'tags': ['Sending User Question'],
    'parameters': [
        {
            'name': 'query',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'The user query to be processed into an SQL query and then fetching data from database.',
                        'default': 'user_question'  # Set default value here
                    }
                },
                'example': {
                    'query': 'user_question'  # This sets the default example in Swagger UI
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Successful response with query results',
            'examples': {
                'application/json': {
                    "results": {
                        "text": "SELECT * FROM HcpPatients"
                    }
                }
            }
        },
        500: {
            'description': 'Internal Server Error',
            'examples': {
                'application/json': {
                    "error": "OpenAI API error: ..."
                }
            }
        }
    }
}


# Swagger for @app.route("/feedback", methods=["POST"])
feedback_swagger = {
    'summary': 'Submit feedback for a resource',
    'description': 'This endpoint allows submitting feedback for a specific resource using its `resID`. The feedback is submitted as a boolean value.',
    'tags': ['Feedback'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'resID': {
                        'type': 'string',
                        'description': 'The ID of the resource to which feedback is related.',
                        'example': '12345'
                    },
                    'feedback': {
                        'type': 'boolean',
                        'description': 'Feedback value, where `true` indicates positive feedback and `false` indicates negative feedback.',
                        'example': True
                    }
                },
                'example': {
                    'resID': '12345',
                    'feedback': True
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Feedback submitted successfully.',
            'examples': {
                'application/json': {
                    'message': 'Feedback submitted successfully!'
                }
            }
        },
        500: {
            'description': 'Internal Server Error',
            'examples': {
                'application/json': {
                    'error': 'An error occurred: Error details'
                }
            }
        }
    }
}



