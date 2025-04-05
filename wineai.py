import streamlit as st
import openai
import random
import os

# --- Configuration ---
APP_TITLE = "WineAI 🍷 - Your Personal Sommelier"
# Try loading the API key from Streamlit secrets
try:
    openai.api_key = st.secrets["openai"]["api_key"]
except (KeyError, AttributeError):
    # Fallback to environment variable if secrets aren't set
    # In a real deployment, you'd ideally ONLY use st.secrets
    # or secure environment variable management.
    # For local testing, you might set OPENAI_API_KEY environment variable.
    openai_api_key_env = os.getenv("OPENAI_API_KEY")
    if openai_api_key_env:
        openai.api_key = openai_api_key_env
    else:
        # If no key is found, display a warning and disable chat.
        st.warning(
            "OpenAI API key not found. Please set it in Streamlit secrets (secrets.toml) "
            "or as an environment variable (OPENAI_API_KEY). Chat functionality is disabled.",
            icon="🚨"
        )
        st.stop() # Stop execution if no key

# --- LLM Pre-prompt (System Message) ---
SYSTEM_PRE_PROMPT = """
You are WineAI, a highly knowledgeable, friendly, and sophisticated virtual sommelier.
Your goal is to help users discover the perfect wine based on their mood, preferences (grape variety, region, price), and any other context they provide.
Respond in a conversational, evocative, and informative style, like a real sommelier guiding a guest.
When recommending a wine, provide:
1.  **Specific Wine Suggestion:** Name a specific wine (e.g., "Cloudy Bay Sauvignon Blanc", "Château Margaux", "La Crema Sonoma Coast Chardonnay"). If possible, suggest a vintage or producer known for quality within the user's price range.
2.  **Reasoning:** Explain *why* this wine fits the user's mood and preferences (e.g., "For a celebratory mood, this Champagne offers vibrant bubbles and notes of brioche...").
3.  **Tasting Notes:** Describe the likely aroma and flavor profile (e.g., "Expect aromas of blackcurrant, cedar, and a hint of tobacco, with a palate showing dark fruit, firm tannins, and a long finish.").
4.  **Food Pairing Ideas:** Suggest 1-2 food pairings that would complement the wine.
5.  **Consider Filters:** Strictly adhere to the user's specified Grape Variety, Region, and Price Range filters if they are provided and not set to 'Any'. If filters make a request impossible, politely explain why and suggest alternatives.
6.  **Be Conversational:** Engage the user, ask clarifying questions if needed, but prioritize giving a recommendation based on the input.
7.  **Image Suggestion (Important):** At the end of your recommendation, include a line formatted *exactly* like this: `Image Search Suggestion: [Specific Wine Name Bottle]`. For example: `Image Search Suggestion: Whispering Angel Rosé Bottle`. Do not add any other text on this line.
"""

# --- Streamlit App Layout ---
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Describe your mood, and let's find the perfect wine for you!")

# --- Sidebar Filters ---
st.sidebar.header("Refine Your Search")

# Grape Variety Filter (Add more relevant grapes)
grape_options = ["Any", "Sauvignon Blanc", "Chardonnay", "Pinot Noir", "Cabernet Sauvignon", "Merlot", "Syrah/Shiraz", "Riesling", "Pinot Grigio/Gris", "Rosé Blend"]
selected_grape = st.sidebar.selectbox("Grape Variety:", options=grape_options)

# Region Filter (Add more relevant regions)
region_options = ["Any", "Napa Valley (USA)", "Bordeaux (France)", "Burgundy (France)", "Tuscany (Italy)", "Marlborough (New Zealand)", "Barossa Valley (Australia)", "Mosel (Germany)", "Rioja (Spain)"]
selected_region = st.sidebar.selectbox("Region:", options=region_options)

# Price Range Filter
min_price, max_price = st.sidebar.slider(
    "Price Range ($):",
    min_value=10,
    max_value=500, # Adjust max value as needed
    value=(20, 80), # Default range
    step=5
)
price_range_str = f"${min_price} - ${max_price}"

# --- Chat Initialization ---
if "messages" not in st.session_state:
    # Start with the system prompt (does not get displayed)
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PRE_PROMPT}]
    # Add a welcome message from the assistant
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Welcome to WineAI! How are you feeling today, and what kind of wine experience are you looking for?"
    })

# --- Display Chat History ---
for message in st.session_state.messages:
    # Don't display the system prompt
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- Suggested Prompts ---
st.markdown("---") # Separator
st.caption("Or get inspired by these ideas:")
cols = st.columns(3)
suggested_prompts = [
    "I'm feeling celebratory!",
    "Need a relaxing wine after a long day.",
    "Something adventurous and bold?"
]
prompt_buttons = []
with cols[0]:
    if st.button(suggested_prompts[0], use_container_width=True):
        st.session_state.selected_prompt = suggested_prompts[0]
with cols[1]:
    if st.button(suggested_prompts[1], use_container_width=True):
        st.session_state.selected_prompt = suggested_prompts[1]
with cols[2]:
    if st.button(suggested_prompts[2], use_container_width=True):
        st.session_state.selected_prompt = suggested_prompts[2]

# Use selected prompt if button was clicked, otherwise use chat input
user_input = st.chat_input("Tell me your mood (e.g., happy, stressed, adventurous)...")
if "selected_prompt" in st.session_state and st.session_state.selected_prompt:
    user_input = st.session_state.selected_prompt
    del st.session_state.selected_prompt # Clear after use

# --- Handle User Input and Generate Response ---
if user_input:
    # Add user message to chat history and display it
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Construct the prompt for the LLM, including filter context
    filter_context = f"User Preferences: Grape=[{selected_grape if selected_grape != 'Any' else 'Not Specified'}], Region=[{selected_region if selected_region != 'Any' else 'Not Specified'}], Price Range=[{price_range_str}]."
    # We add the filter context *before* the latest user message for clarity
    messages_for_api = st.session_state.messages.copy()
    # Modify the last user message to include context
    messages_for_api[-1]["content"] = f"{filter_context}\n\nUser Mood/Request: {user_input}"


    # Display "thinking" indicator
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...✍️")

        try:
            # --- Call OpenAI API ---
            # Use ChatCompletion endpoint
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # Or use "gpt-4" if you have access
                messages=messages_for_api,
                temperature=0.7, # Adjust for creativity vs. precision
                max_tokens=300, # Adjust token limit as needed
                stream=False # Set to True for streaming response (more complex handling)
            )

            assistant_response = response.choices[0].message.content.strip()

            # --- Attempt to Extract Image Search Suggestion ---
            # Basic extraction, assumes format `Image Search Suggestion: [Term]`
            image_search_term = None
            lines = assistant_response.split('\n')
            if lines and "Image Search Suggestion:" in lines[-1]:
                 # Extract the term and remove the suggestion line from the main response
                try:
                    image_search_term = lines[-1].split("Image Search Suggestion:")[1].strip()
                    assistant_response = "\n".join(lines[:-1]).strip() # Remove the last line
                except IndexError:
                    # If split fails, keep response as is
                    pass

            # Display the main assistant response
            message_placeholder.markdown(assistant_response)

            # --- Image Handling (Conceptual) ---
            # Standard text models (like GPT-3.5/4) DON'T directly return images.
            # The pre-prompt asks the LLM to SUGGEST a search term.
            # Displaying an actual image requires a separate step:
            # 1. Parse the suggested wine name/search term from the response. (Done above)
            # 2. Use an Image Search API (like Google Custom Search, Bing Image Search, etc.)
            #    to find an image URL based on the term. (Requires additional API calls and setup)
            # 3. Display the image using st.image(image_url)
            #
            # For this example, we'll just print the suggested search term if found.
            # In a real app, you'd replace the print with an actual image search call.
            if image_search_term:
                st.markdown(f"*(Suggested image search: `{image_search_term}`)*")
                # Example placeholder if you had an image URL:
                # st.image("URL_FROM_IMAGE_SEARCH_API", caption=f"Suggested: {image_search_term}", width=200)
                pass # No actual image shown here without an image search API integration


        except openai.APIError as e:
            st.error(f"OpenAI API Error: {e}", icon="🚨")
            assistant_response = "Sorry, I encountered an error connecting to the wine knowledge base. Please try again."
            message_placeholder.markdown(assistant_response)
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}", icon="🔥")
            assistant_response = "Apologies, a technical glitch occurred. Please try again."
            message_placeholder.markdown(assistant_response)

    # Add assistant response (without the image suggestion line) to chat history
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})