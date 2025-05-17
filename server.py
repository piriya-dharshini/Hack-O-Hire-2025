import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import uvicorn
from dotenv import load_dotenv
import json
# ========== FASTAPI INIT ========== 
app = FastAPI(
    title="Term Sheet Validator",
    version="1.1",
    description="Validate term sheets using Google Gemini and human-defined rules"
)

# Access the variable
os.environ["GOOGLE_API_KEY"] = "your_google_api_key"

# ========== LANGCHAIN SETUP ========== 
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, max_tokens=2000)

@app.post("/validate/")
async def validate_termsheet(
    file: UploadFile = File(...),
    recap_values: str = Form(...),
    human_prompt: str = Form("")
):
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        temp_file.write(await file.read())
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "r", encoding="utf-8") as f:
            extracted_text = f.read()

        try:
            recap_dict = json.loads(recap_values)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in recap_values"}

        # ----------- 1. RECAP VALIDATION PROMPT -----------
        recap_prompt = f"""
    You are a validation assistant for term sheets. Compare the provided extracted text against the dynamic recap values.

    Instructions:
    - For EACH parameter in the recap values:
    - Search for the corresponding value in the extracted text.
    - Compare the extracted value against the recap value.
    - Determine whether the parameter is "economic" or "non-economic".
    - Return a JSON object with:
        {{
            "parameter_name": {{
                "recap_value": "...",
                "extracted_value": "...",
                "is_valid": true/false,
                "confidence": 0.0-1.0,
                "reason": "...",
                "parameter_type": "economic" or "non-economic"
            }}
        }}
        - Mark it as VALID if the values match exactly or closely, else INVALID.
        - If found, return the extracted value.
        - If not found, set extracted_value as "NOT FOUND".
        - Give a confidence score between 0 and 1.
        - Justify the decision in a short reason.
        - Use financial logic to determine economic vs non-economic (e.g., if the value relates to money, price, yield, amount, etc., it's economic).

        Return the result as a valid JSON object only — no extra text, no explanations, no markdown, just a JSON string. Ensure all values are enclosed in double quotes, no trailing commas, and escape all internal quotes.

        Extracted Text:
        {extracted_text}

        Recap Values:
        {json.dumps(recap_dict, indent=2)}
        """

        if human_prompt:
            recap_prompt += f"\nAdditional instructions:\n{human_prompt}"

        recap_response = llm.invoke(recap_prompt)

        # ----------- 2. COMPLIANCE RULE CHECK PROMPT -----------
        rules_prompt = f"""
        You are a compliance validation assistant for term sheets. Evaluate the following 9 rules.

        For EACH rule:
        - Mark it as COMPLIANT or NON-COMPLIANT.
        - Give a CONFIDENCE SCORE between 0 and 1.
        - Explain the decision briefly.

        At the end:
        - Provide OVERALL COMPLIANT: YES/NO
        - Provide REASON: <main issue or confirmation>
        - Provide Total Confidence Score (out of 100)

        Extracted Text:
        {extracted_text}

        Rules:
        1. No sales to EEA retail investors without PRIIPs KID.
        2. No sales to Swiss retail investors without FinSA KID.
        3. Must have a redemption date.
        4. Reference underlying assets (e.g., FTSE 100, S&P 500).
        5. Disclose MREL exemption status.
        6. Include autocall conditions, dates, and payout structure.
        7. Restrictions on US persons under Regulation S must be noted.
        8. Include disclaimers on protections (CISA, FINMA).
        9. Issuer name and LEI must be present.
        """

        compliance_response = llm.invoke(rules_prompt)

        # Return both validation results
        return {
            "validation_result": recap_response.content,
            "compliance_result": compliance_response.content
        }

    finally:
        os.remove(temp_file_path)

# ========== RUN LOCALLY ==========
if __name__ == "__main__":
    uvicorn.run("server:app", host="localhost", port=8000, reload=True)