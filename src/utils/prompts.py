FOLLOW_UP = "You are an expert conversational AI. Given the chat history and a new user question, determine if the new question is a direct follow-up. Answer 'yes' or 'no'.\n\nChat history: {chat_history}\nNew question: {question}"

REPHRASE = "You are an expert question rephraser. Given the chat history and a new question, rephrase the new question to be a standalone query. If the topic has completely changed, just return the new question verbatim. The new question is: '{question}'. Chat history: {chat_history}"

TOPIC_CHANGE = """
Given the chat history and the new question, has the user completely changed the topic?

Be careful in deciding if a question is a topic change. Read the intent of the question based on the chat history and only if it really has no clear connection with the chat history answer with a "yes", else always answer with a "no".

Chat history: {chat_history}\n\nNew question: {question}
"""

GRAMMER = "You are an expert in grammar and spelling. Correct any grammatical errors in the following question. Just return the corrected question and nothing else. Question: '{question}'"

RAG_PROMPT = """
You are a helpful assistant. Your task is to provide a concise and accurate answer to the user's question based *only* on the provided documents and chat history.

Please provide appropriate references for your final answer. The references should be in a structured JSON format.

The documents provided have metadata that includes the document name and number. The content itself may contain page numbers marked with "## Page <number>". When you find that, just return the <number>.

If you cannot find a clear answer in the provided documents, state "I do not have enough information".

Chat History:
{chat_history}

Documents:
{documents}

Question: {question}

Final Answer:
"""

# The evaluation prompt
EVALUATION_PROMPT = """
You are an expert evaluator. Your task is to review whether an AI-generated answer to the latest user question is factually accurate based on the relevant source documents and the chat history.

Assess the confidence of the AI's answer based on how well it is supported by the documents and chat history.

NOTE: If the AI Answer is "I do not have enough information", **DO NOT EVALUATE** Just set confidence score to -1 and reasoning as "Not enough information".

Score the answer on a scale from 0 to 100, where:
- 90 - 100%: Answer is completely accurate and directly supported by the documents and chat history.
- 80 - 90%: Answer is highly accurate and supported by the documents and chat history.
- 70 - 80%: Answer is somewhat accurate and supported by the documents and chat history.
- 50 - 60%: Answer may not be accurate or factual. It is only partially supported by the documents and chat history.
- 0 - 50%: Answer is not factual at all.

NOTE: Please always return an integer for Confidence Score, i.e., do not return "80", return 80.

Provide a brief reasoning for your score, citing specific parts of the documents or noting where information is missing and how it can be improved.

Chat History:
{chat_history}

Documents:
{documents}

Question:
{question}

AI Answer:
{answer}
"""

REFINE_PROMPT = """
You are a helpful assistant. Your task is to refine the previous answer based on the suggested improvement so that the refined answers is concise, accurate, inline with the user's question, and strictly based on the provided documents and chat history.

Please provide appropriate references for your final answer. The references should be in a structured JSON format.

The documents provided have metadata that includes the document name and number. The content itself may contain page numbers marked with "## Page <number>".

If you cannot find a clear answer in the provided documents, state "I do not have enough information".

Chat History:
{chat_history}

Documents:
{documents}

Question:
{question}

Previous Answer:
{answer}

Suggested Improvements:
{suggested_improvements}

Final Answer:
"""
