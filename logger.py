# logger.py
# Contains logging functionalities for the financial analyzer.
# Part of Application Version 0.10.0

import json
import os
from datetime import datetime
import streamlit as st # Required for st.session_state

# Import global constants if they are used by log_event, e.g., DEBUG_LOG_FILE_NAME
# For now, assuming DEBUG_LOG_FILE_NAME is passed or globally accessible in app.py context
# If DEBUG_LOG_FILE_NAME is defined in config.py, it should be imported here.
# from config import DEBUG_LOG_FILE_NAME # Example if DEBUG_LOG_FILE_NAME is in config.py

def log_event(log_type, message, module_name=None, details=None):
    """
    Logs an event to both the Streamlit UI run_log and a debug.txt file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Log for Streamlit UI (if session state is available)
    if 'run_log' in st.session_state:
        log_entry_ui = {"timestamp": timestamp, "type": log_type, "message": message}
        if module_name: 
            log_entry_ui["module"] = module_name
        if details: 
            # For UI, we might want a more concise version of details or skip very large ones
            if isinstance(details, dict) and "full_prompt" in details:
                 log_entry_ui["details"] = {"prompt_snippet": str(details["full_prompt"])[:200] + "..."}
            elif isinstance(details, dict) and "conversation" in details:
                 log_entry_ui["details"] = {"conversation_summary": f"Length: {len(details['conversation'])} messages"}
            else:
                try:
                    # Attempt to serialize, but keep it brief for UI
                    details_ui_str = json.dumps(details, ensure_ascii=False, indent=None)
                    log_entry_ui["details"] = details_ui_str[:200] + "..." if len(details_ui_str) > 200 else details_ui_str
                except TypeError:
                    log_entry_ui["details"] = str(details)[:200] + "..."

        st.session_state.run_log.insert(0, log_entry_ui) 
    
    # Log for debug.txt file (more detailed)
    log_message_file = f"{timestamp} [{log_type}]"
    if module_name: 
        log_message_file += f" (Module: {module_name})"
    log_message_file += f": {message}"
    
    if details: 
        if isinstance(details, (dict, list)):
            try: 
                # For file log, attempt to dump with indent for readability
                details_str = json.dumps(details, ensure_ascii=False, indent=2)
            except TypeError: 
                details_str = str(details) # Fallback for non-serializable details
            log_message_file += f"\n  Details: {details_str}"
        else: 
            log_message_file += f"\n  Details: {str(details)}"
    log_message_file += "\n---\n" 
    
    # Determine log file path
    # This assumes DEBUG_LOG_FILE_NAME is a global constant accessible here
    # or passed appropriately. For modularity, it's better if it's from a config.
    # We'll rely on app.py to set current_run_result_dir if needed.
    from config import DEBUG_LOG_FILE_NAME # Import here or pass as argument
    
    log_file_path_to_use = DEBUG_LOG_FILE_NAME 
    if 'current_run_result_dir' in st.session_state and st.session_state.current_run_result_dir is not None:
        log_file_path_to_use = os.path.join(st.session_state.current_run_result_dir, DEBUG_LOG_FILE_NAME)
    
    try:
        with open(log_file_path_to_use, "a", encoding="utf-8") as f:
            f.write(log_message_file)
    except Exception as e:
        # Fallback to print if file logging fails (e.g., in restricted environments)
        print(f"CRITICAL: Failed to write to debug log file '{log_file_path_to_use}': {e}")
        print(f"Original log message was: {log_message_file.strip()}")

