import json
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import os
import logging
import re

from app.db.qdrant import query_qdrant
load_dotenv()

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=api_key)

# def translate_to_english(user_query: str) -> str:
#     model = genai.GenerativeModel("gemini-2.0-flash")
#     prompt = f"Translate the following into English:\n\n{user_query}"
#     response = model.generate_content(prompt)
#     return response.text.strip()

import google.generativeai as genai

# Make sure to configure your API key before calling the function, e.g.:
genai.configure(api_key="AIzaSyCo2Hhvv_Qs1O52jGj7EMXL1Ve4HgaOLyM")

def translate_to_english(user_query: str) -> str:
    """
    Translates the given text into English using the Gemini-2.0-flash model.

    This function aims to provide a clear and direct translation by instructing the
    model to return only the translated text, without any additional commentary,
    introductions, or formatting. It also includes error handling for robustness.

    Args:
        user_query (str): The text string to be translated into English.

    Returns:
        str: The clean, translated English text. Returns an empty string if
             translation fails or no text is returned by the model.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Refined prompt: Explicitly instruct the model to return only the translation.
    prompt = (
        "Translate the following text into English.\n"
        "Text may be in any language. \n"
        "Your response should be a direct translation without any additional commentary, introductions, or formatting.\n\n"
        "You are a professional translator. Your task is to provide a clear and accurate translation of the given text.\n\n"
        "Instructions:\n"
        "- Translate the text into English.\n"
        "- Do not include any additional text, explanations, or formatting.\n"
        "Provide ONLY the translated text, with no additional commentary, introductions, "
        "or formatting (e.g., 'Here is the translation:').\n\n"
        f"Text to translate: {user_query}"
    )

    try:
        response = model.generate_content(prompt)

        # Check if the response object and its 'text' attribute exist and are not empty
        if response and hasattr(response, 'text') and response.text:
            # Use .strip() to remove any leading/trailing whitespace just in case
            return response.text.strip()
        else:
            print(f"Warning: Gemini model returned an empty or invalid response for query: '{user_query}'")
            return "" # Return an empty string for no valid translation
    except Exception as e:
        # Catch any exceptions that might occur during the API call (e.g., network issues, API errors)
        print(f"Error during translation for query '{user_query}': {e}")
        return "" # Return an empty string on error


def ask_gemini(context: str, question: str, query_analysis: dict, enhanced_results: dict, conversation_history: Optional[List[Dict[str, str]]] = None) -> dict:
    """Ask Gemini and return a structured JSON response with optional buttons."""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Format conversation history if available
        conversation_context = ""
        if conversation_history:
            conversation_context = "Previous conversation:\n"
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_context += f"{role.capitalize()}: {content}\n"
            conversation_context += "\n"

        prompt = (
            "You are the official AI assistant of the company, designed to be smart, professional, and friendly.\n"
            "Use the internal company content below to help answer the user's question. Prioritize providing comprehensive and helpful information based on the provided context.\n\n"

            "🎯 Output Format Instructions:\n"
            "- ONLY return a **valid raw JSON object**. Do NOT include markdown (```json), quotes, or any extra text outside the JSON structure.\n"
            "- The JSON must contain exactly these 4 keys:\n"
            "  1. 'response': string → a clear, helpful, and grammatically correct explanation or answer to the user's question. This field should be detailed and comprehensive, drawing as much relevant information as possible from the provided context. **You may use Markdown elements within this string to enhance readability for UI display:**\n"
            "     - Use `\\n` for new paragraphs or line breaks.\n"
            "     - Use `**text**` for bolding important keywords or phrases.\n"
            "     - Avoid complex Markdown (e.g., headings, lists, tables) beyond `\\n` and `**` to keep the response concise and parseable.\n"
            "  2. 'buttons': boolean → true **only if actionable info** (email, phone, LinkedIn, etc.) is found in the context and relevant to the question.\n"
            "  3. 'button_type': list of strings like [\"email\", \"linkedin\", \"website\", \"phone\"], or null if buttons is false.\n"
            "  4. 'button_data': list of actual values from context matching the types above, or null if buttons is false.\n\n"

            "🧠 Rules:\n"
            "- If the user greets you (e.g., says 'hi', 'hello', 'hey'), respond warmly and naturally. For greetings, a concise, friendly response is appropriate.\n"
            "- If the question is general or out-of-scope but can be answered politely, do so in a professional tone. If no relevant information is in the context for an out-of-scope question, state that you can only answer questions related to the company content.\n"
            "- **Elaborate and provide details** in the 'response' field by synthesizing information from the 'Internal Company Content'. Aim for a thorough explanation that directly addresses the user's query.\n"
            "- Use only real data from the context for button values. Never guess or hallucinate values.\n"
            "- If no actionable data is present or needed, set:\n"
            "  \"buttons\": false,\n"
            "  \"button_type\": null,\n"
            "  \"button_data\": null\n\n"

            "✅ Example Output:\n"
            '{\n'
            '  "response": "Welcome!\\n\\nI\'m here to help you with any questions about the company. I can provide **detailed information** on our products, services, contact options, and more, based on the internal company content I have access to. How can I assist you today with a specific query about our company?",\n'
            '  "buttons": false,\n'
            '  "button_type": null,\n'
            '  "button_data": null\n'
            '}\n\n'

            "OR (if contact info is found and a detailed response is still needed):\n"
            '{\n'
            '  "response": "You can reach our support team through multiple channels.\\n\\nFor general inquiries or technical assistance, the most direct method is via **email at info@company.com**. If you prefer to connect on professional networking platforms, our official **LinkedIn page**, accessible at https://linkedin.com/company/example, is regularly updated with company news and job openings. We aim to respond to all inquiries within 24 business hours.",\n'
            '  "buttons": true,\n'
            '  "button_type": ["email", "linkedin"],\n'
            '  "button_data": ["info@company.com", "https://linkedin.com/company/example"]\n'
            '}\n\n'

            f"{conversation_context}"
            f"📄 Internal Company Content:\n{enhanced_results}\n\n"
            f"❓ User Question:\n{question}\n\n"
            "✍️ Please respond now with the final raw JSON object only:"
        )

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown-like ```json block
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                cleaned_json = json_match.group()
                return json.loads(cleaned_json)
            else:
                logging.warning("Could not extract valid JSON from Gemini response.")
                return {
                    "response": "Sorry, I couldn't generate a valid response.",
                    "buttons": False,
                    "button_type": None,
                    "button_data": None
                }

    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return {
            "response": "Sorry, an error occurred while processing your request.",
            "buttons": False,
            "button_type": None,
            "button_data": None
        }

def analyze_user_query(question: str) -> dict:
    """Analyze user query to extract key information and intent."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = (
        "Analyze this user question and extract key information:\n"
        "1. Main topic/subject\n"
        "2. Key keywords for search\n"
        "3. Question type (factual, how-to, definition, comparison, etc.)\n"
        "4. Intent (what specifically they want to know)\n\n"
        "Return response in this JSON format:\n"
        "{\n"
        '  "main_topic": "extracted main topic",\n'
        '  "keywords": ["keyword1", "keyword2", "keyword3"],\n'
        '  "question_type": "factual/how-to/definition/etc",\n'
        '  "intent": "specific intent description"\n'
        "}\n\n"
        f"User Question: {question}"
    )
    
    try:
        response = model.generate_content(prompt)
        import json
        return json.loads(response.text.strip())
    except:
        return {
            "main_topic": question,
            "keywords": [question],
            "question_type": "general",
            "intent": "general information"
        }

def process_query_with_gemini(user_query: str) -> Dict[str, Any]:
    """
    Process user query with Gemini to extract key information and generate search parameters.
    Translates query if needed.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        You are a multilingual assistant. The user query might be in any language.

        Step 1: Translate the query to English if it's not already.
        Step 2: Extract key information for database search.

        Query: {user_query}

        Output this JSON structure:
        {{
          "search_terms": [ ... ],
          "requirements": [ ... ],
          "context": "..." 
        }}
        """

        response = model.generate_content(prompt)
        processed_text = response.text.strip()
        print("Gemini raw response:", processed_text)

        # Clean ```json block if present
        match = re.search(r'\{.*\}', processed_text, re.DOTALL)
        if match:
            cleaned_json = match.group(0)
            search_params = json.loads(cleaned_json)
        else:
            raise ValueError("No valid JSON object found.")

        print("Parsed search parameters:", search_params)
        return search_params

    except Exception as e:
        logger.error(f"Error processing query with Gemini: {e}")
        return {
            "search_terms": [user_query],
            "requirements": [],
            "context": ""
        }
    
def enhanced_query_with_gemini(
    collection_name: str,
    user_query: str,
    query_vector: List[float],
    limit: int = 5
) -> Dict[str, Any]:
    """
    Enhanced query process that uses Gemini for query understanding and response generation.
    """
    try:
        # Step 1: Process query with Gemini
        processed_query = process_query_with_gemini(user_query)
        logger.debug(f"Processed query: {processed_query}")

        # Step 2: Perform vector search in Qdrant
        search_results = query_qdrant(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        logger.debug(f"Search results from Qdrant: {search_results}")

        # Step 3: Extract context text from search results
        context_chunks = []
        for result in search_results:
            if result.get("payload") and result["payload"].get("text"):
                score = result.get("score", 0)
                text = result["payload"]["text"]
                context_chunks.append(f"[Relevance: {score:.3f}] {text}")
        
        print("context_chunks (context text from search results) : ", context_chunks)

        context_text = "\n\n".join(context_chunks)

        print("context_text (context text from search results) : ", context_text)

        return {
            "processed_query": processed_query,
            "search_results": search_results,
            "context_text": context_text
        }

    except Exception as e:
        logger.error(f"Error in enhanced_query_with_gemini: {e}")
        return {
            "error": str(e),
            "response": "I apologize, but I encountered an error while processing your query."
        }