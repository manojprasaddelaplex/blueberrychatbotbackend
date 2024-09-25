import re

def extract_summary(response):
    lines = response.splitlines()
    print(response)
    summary = ""
    for line in lines:
        if line.strip().startswith("**Summary**:"):
            summary = line.strip().replace("**Summary**: ", "")
            break
    return summary


def extractSqlQueryFromResponse(response):
    code_block_pattern = r'```(?:sql)?\s*([\s\S]+?)\s*```'
    code_block_match = re.search(code_block_pattern, response, re.IGNORECASE)
    
    if code_block_match:
        return code_block_match.group(1)
    else:
        return None