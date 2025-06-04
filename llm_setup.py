# llm_setup.py
# Handles LLM initialization and provides the LLM instance.
# Part of Application Version 0.10.0

import streamlit as st
from langchain_deepseek.chat_models import ChatDeepSeek
from logger import log_event # Assuming logger.py is in the same directory

@st.cache_resource
def get_llm():
    """
    Initializes and returns the ChatDeepSeek LLM instance.
    Uses Streamlit secrets for the API key.
    Logs errors/warnings using the centralized log_event function.
    """
    llm_instance = None
    try:
        # Ensure run_log exists in session_state for log_event to work during early init
        if 'run_log' not in st.session_state:
            st.session_state.run_log = []

        api_key = st.secrets.get("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY_PLACEHOLDER")
        
        if api_key == "YOUR_DEEPSEEK_API_KEY_PLACEHOLDER" or not api_key:
            warning_msg = "DeepSeek API Key not found or is placeholder in Streamlit secrets (secrets.toml). Please configure your DEEPSEEK_API_KEY. LLM functionality will be disabled."
            log_event("WARNING", warning_msg, module_name="LLM_SETUP")
            return None 
            
        llm_instance = ChatDeepSeek(model="deepseek-reasoner", api_key=api_key, temperature=0.1)
        log_event("INFO", "ChatDeepSeek LLM initialized successfully.", module_name="LLM_SETUP")

    except FileNotFoundError: 
        error_msg = "Streamlit secrets file (secrets.toml) not found. Please create it in your .streamlit directory and add your DEEPSEEK_API_KEY. LLM functionality will be disabled."
        log_event("ERROR", error_msg, module_name="LLM_SETUP")
        llm_instance = None 
    except Exception as e:
        error_msg = f"LLM (ChatDeepSeek) Initialization Error: {e}. Check your API key and model name. LLM functionality may be limited or disabled."
        log_event("ERROR", error_msg, module_name="LLM_SETUP", details=str(e))
        llm_instance = None 
    return llm_instance

# Initialize the LLM instance globally for use by other modules
llm = get_llm()

def get_llm_instance():
    """Returns the globally initialized LLM instance."""
    return llm
