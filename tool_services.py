# tool_services.py
# Defines and implements tools that can be used by the LLM or application logic.
# Part of Application Version 0.10.0+

import json
from langchain_community.tools import DuckDuckGoSearchRun
from logger import log_event 
from llm_setup import get_llm_instance 
# Corrected import: select_relevant_chunks_llm and compress_selected_text_llm are in planning_services
from planning_services import select_relevant_chunks_llm, compress_selected_text_llm 
from config import COMPRESSED_DOC_MAX_CHARS, TOOL_SUMMARIZER_MAX_LENGTH
import streamlit as st 

# --- Tool Instances (Initialized once) ---
duckduckgo_search_tool_instance = DuckDuckGoSearchRun()

# --- Tool Executor Functions ---
def custom_duckduckgo_search(query: str) -> str:
    """
    Performs a DuckDuckGo search for the given query.
    """
    log_event("TOOL_CALL", "Executing custom_duckduckgo_search", details={"query": query})
    try:
        result = duckduckgo_search_tool_instance.run(query) 
        log_event("TOOL_RESULT", "custom_duckduckgo_search successful", details={"result_snippet": str(result)[:200]})
        return str(result) 
    except Exception as e:
        log_event("ERROR", f"Error in custom_duckduckgo_search: {e}", details={"query": query})
        return f"Error performing search: {e}"

def execute_get_relevant_document_content(document_type: str, period_label: str, analysis_context: str, max_length: int = TOOL_SUMMARIZER_MAX_LENGTH) -> str:
    """
    Retrieves relevant content from pre-processed document chunks based on analysis_context.
    Uses a multi-step LLM process: chunk selection -> text concatenation -> final compression.
    """
    llm = get_llm_instance()
    log_event("TOOL_CALL", f"Executing get_relevant_document_content for {document_type} of {period_label}", 
              details={"analysis_context": analysis_context, "target_max_length": max_length})

    if not llm:
        return "错误：LLM服务不可用，无法处理文档内容提取。"

    target_report_entry = None
    for report_entry in st.session_state.cwp['base_data']['financial_reports']:
        if report_entry['period_label'] == period_label:
            target_report_entry = report_entry
            break
    
    if not target_report_entry:
        log_event("ERROR", f"未找到报告期为 '{period_label}' 的已处理文档数据。", "DocContentTool")
        return f"错误：未找到报告期为 '{period_label}' 的文档数据。"

    processed_chunks_key = None
    if document_type.lower() == "footnotes":
        processed_chunks_key = 'footnotes_processed_chunks'
    elif document_type.lower() == "mda":
        processed_chunks_key = 'mda_processed_chunks'
    else:
        log_event("ERROR", f"无效的文档类型 '{document_type}' 请求。", "DocContentTool")
        return f"错误：无效的文档类型 '{document_type}'。"

    chunks_with_overviews = target_report_entry.get(processed_chunks_key, [])
    if not chunks_with_overviews:
        log_event("WARNING", f"文档 '{document_type}' ({period_label}) 未找到预处理的分块数据或分块列表为空。", "DocContentTool")
        return f"文档 '{document_type}' ({period_label}) 无可用的预处理内容分块。"

    log_event("INFO", f"为文档 '{document_type}' ({period_label}) 基于上下文 '{analysis_context}' 选择相关文本块...", "DocContentTool")
    selected_chunk_ids = select_relevant_chunks_llm([analysis_context], chunks_with_overviews)

    if not selected_chunk_ids:
        log_event("INFO", f"选择器LLM未为上下文 '{analysis_context}' 在文档 '{document_type}' ({period_label}) 中找到相关文本块。", "DocContentTool")
        return "根据分析上下文，未在指定文档的概述中找到直接相关的内容片段。"

    concatenated_original_text = ""
    for chunk_id_to_fetch in selected_chunk_ids:
        found_chunk = next((chunk for chunk in chunks_with_overviews if chunk["chunk_id"] == chunk_id_to_fetch), None)
        if found_chunk:
            concatenated_original_text += found_chunk.get("original_text", "") + "\n\n"
        else:
            log_event("WARNING", f"规划选中的块ID '{chunk_id_to_fetch}' 未在 {document_type} ({period_label}) 的分块中找到。", "DocContentTool")
    
    if not concatenated_original_text.strip():
        log_event("WARNING", f"为上下文 '{analysis_context}' 在文档 '{document_type}' ({period_label}) 中选中的相关文本块内容为空。", "DocContentTool")
        return "选中的相关文本块内容为空。"

    log_event("INFO", f"准备压缩选中的文本 (原始拼接长度: {len(concatenated_original_text)})，目标上下文: '{analysis_context}'", "DocContentTool")
    compressed_text = compress_selected_text_llm(concatenated_original_text, analysis_context, target_max_chars=max_length) 
                                                
    log_event("TOOL_RESULT", f"工具 'get_relevant_document_content' 成功返回处理后的内容 for {document_type} of {period_label}.", "DocContentTool", {"content_length": len(compressed_text)})
    return compressed_text


# --- Tool Schemas (Defined Globally) ---
CUSTOM_DUCKDUCKGO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "CustomDuckDuckGoSearch", 
        "description": "Useful for when you need to answer questions about current events, find general information, or get specific data by searching the web. Use this to find information on companies, industries, economic data, market data, financial ratios, etc.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query string."}},
            "required": ["query"]
        },
    }
}

GET_RELEVANT_DOCUMENT_CONTENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_relevant_document_content",
        "description": "Extracts and summarizes relevant information from pre-processed company financial document chunks (footnotes or MD&A) for a specific reporting period based on a given analysis context. This tool internally selects the most relevant chunks and then summarizes them.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_type": {"type": "string", "description": "The type of document to query, e.g., 'footnotes' or 'mda'."},
                "period_label": {"type": "string", "description": "The reporting period label of the document, e.g., '2023 Annual'."},
                "analysis_context": {"type": "string", "description": "A clear description of the specific information or question the LLM needs answered from the document."},
                "max_length": {"type": "integer", "default": TOOL_SUMMARIZER_MAX_LENGTH, "description": f"Target maximum character length for the final summarized/extracted content. Default is {TOOL_SUMMARIZER_MAX_LENGTH}."}
            },
            "required": ["document_type", "period_label", "analysis_context"]
        }
    }
}

AVAILABLE_TOOLS_SCHEMAS = [CUSTOM_DUCKDUCKGO_TOOL_SCHEMA, GET_RELEVANT_DOCUMENT_CONTENT_SCHEMA] 

TOOL_EXECUTORS = {
    "CustomDuckDuckGoSearch": custom_duckduckgo_search, 
    "get_relevant_document_content": execute_get_relevant_document_content
}
