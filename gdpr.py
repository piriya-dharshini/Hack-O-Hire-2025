from presidio_analyzer import AnalyzerEngine, RecognizerResult, EntityRecognizer
from presidio_anonymizer import AnonymizerEngine

class BarclaysCompanyRecognizer(EntityRecognizer):
    def __init__(self):
        super().__init__(supported_entities=["COMPANY"])
        self.name = "BarclaysCompanyRecognizer"
        self.version = "1.0"

    def load(self):
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        company_name = "Barclays"
        start = text.lower().find(company_name.lower())
        while start != -1:
            end = start + len(company_name)
            results.append(RecognizerResult(
                entity_type="COMPANY",
                start=start,
                end=end,
                score=1.0
            ))
            start = text.lower().find(company_name.lower(), end)
        return results

# Initialize Presidio engines
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
analyzer.registry.add_recognizer(BarclaysCompanyRecognizer())

def anonymize_text_with_presidio(extracted_text: str) -> str:
    """
    Analyze and anonymize sensitive data in the extracted text.
    
    Args:
        extracted_text (str): The text content from a term sheet or document.
        
    Returns:
        str: Anonymized text with PII masked or replaced.
    """
    pii_entities = ["PERSON", "EMAIL_ADDRESS", "LOCATION", "PHONE_NUMBER", "ORGANIZATION", "DATE", "COMPANY"]
    results = analyzer.analyze(text=extracted_text, entities=pii_entities, language="en")
    anonymized_result = anonymizer.anonymize(text=extracted_text, analyzer_results=results)
    return anonymized_result.text

# # --- Read from file and anonymize ---
# input_path = r"C:\placements\projects\termsheetvalidatrion\Barclays-Termsheet-Validation-master\extracted_files\BAR38GDOIFR001400XD93_F_PC_N_extracted_20250516_112729.txt"

# with open(input_path, "r", encoding="utf-8") as file:
#     raw_text = file.read()

# # Call the function
# anonymized_text = anonymize_text_with_presidio(raw_text)

# # Print or save
# print(anonymized_text)

