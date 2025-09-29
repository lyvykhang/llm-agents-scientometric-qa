COVERAGE = """# Coverage
1: Limited coverage; disregards (a) key aspect(s) of the user question.
2: Partial coverage; lacking some discussion on aspects of the user question.
3: Decent coverage; addresses all aspects of the user question to some degree, but some nuances are not (or incorrectly) accounted for.
4: Complete coverage; addresses all aspects of the user question, effectively accounting for ambiguous requests within the question, translating them into data requests compatible with the system.
5: Above and beyond coverage; complete coverage of the user question, while providing additional relevant insights, suggestions, and analysis on the retrieved data within scope."""

COHERENCE = """# Coherence
1: Incoherent response; lacks logical structure and readability. Inappropriate or absent use of formatting.
2: Limited coherence; somewhat logically structured and readable. Inappropriate use of formatting.
3: Decent coherence; response flows logically and reads well. Formatting rules are applied to organize information, but there remain issues, e.g. uninformative section headings or misuse of tables.
4: Good coherence; response flows logically, reads well, and makes use of formatting rules to effectively present information where appropriate.
5: Excellent coherence; response is optimally structured and reads well, presenting high-level insights, followed by factual data and analysis, and concluding statements and references, respectively. Organization is spot-on, e.g. informative (sub-)sections, appropriate paragraph lengths, effective use of tables and lists, etc."""

VERIFIABILITY = """# Verifiability
1: No supporting references are provided; claims are unsubstantiated.
2: References are rarely provided; majority of claims are unsubstantiated.
3: References are inconsistently provided; some of the claims remain unsubstantiated.
4: References (both dedicated reference section and basic in-text citations) are generally provided where relevant;  majority of claims are supported by the retrieved data.
5: References (both dedicated reference section and basic in-text citations) are always provided where relevant; all claims are supported by the retrieved data, demonstrating high-level verification."""

VALIDITY = """# Validity
1: Invalid; main claims and conclusions are based on complete misinterpretation or ignorance of the input data.
2: Lacking validity; some claims and conclusions based on partial misinterpretation of the input data.
3: Somewhat valid; main claims are connected to the input data, but some analytical and extrapolated statements are illogical.
4: Generally valid; most claims made can be reasonably drawn from the input data. Most provided relevant data are present in the response,  but some potentially useful data are omitted.
5: Fully valid; all claims made are correct interpretations based on the input data, and all provided relevant data are used appropriately in the response."""

LLM_JUROR_PROMPT = """You are an expert at evaluating RAG-based LLM responses to scientometric user questions.

**Input:**
1. Subjective evaluation criteria with a 5-point scale.
2. Scientometric user question.
3. Data retrieved by the RAG system.
4. LLM-generated response based on the retrieved data.

**Output:**
1. Response scores (1-5), brief explanation, and confidence (0-1), by evaluation criterion in valid JSON format.
{{
    "criterion_1_name": {{
        "score": 3,
        "explanation": "criterion_1_brief_explanation_for_score",
        "confidence" : 0.95
    }},
    "criterion_2_name": {{
        "score": 5,
        "explanation": "criterion_2_brief_explanation_for_score",
        "confidence": 0.95
    }},
    ...
}}

**Special Instructions:***
- Be strict in the scoring. Only perfect responses should receive the maximum score.
- The criteria serve as general guidelines. If the answer has other unspecified flaws, deduct points in the appropriate criterion.
- For Coverage, penalize the score if the user's intent was misinterpreted.
- For Verifiability, hyperlinks or formal citation styles are not required to achieve maximum scores. Any IDs referenced should be entirely consistent with those present in the retrieved data or task arguments."""
