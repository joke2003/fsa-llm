# utils.py
# Contains general utility functions for the financial analyzer.
# Part of Application Version 0.10.0

import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
from logger import log_event # Assuming logger.py is in the same directory
from config import MODULE_DEPENDENCIES # Import necessary constants
# Import get_llm_instance if any utility here needs it (e.g. for summarization within get_prior_analyses_summary)
from llm_setup import get_llm_instance


def sanitize_filename(name: str) -> str:
    """Sanitizes a string to be used as a filename."""
    name = str(name)
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '-', name)
    return name if name else "untitled"

def create_run_result_directory(company_name_str: str, base_result_dir: str) -> str | None:
    """Creates a unique directory for the current analysis run results."""
    if not os.path.exists(base_result_dir):
        try:
            os.makedirs(base_result_dir)
            log_event("INFO", f"基础结果目录 '{base_result_dir}' 已创建。", module_name="系统初始化")
        except Exception as e:
            error_msg = f"创建基础结果目录 '{base_result_dir}' 失败: {e}"
            if 'streamlit' in globals() and hasattr(st, 'error'): # Check if st is available
                 st.error(error_msg)
            log_event("ERROR", error_msg, module_name="系统初始化")
            return None 
            
    sanitized_company_name = sanitize_filename(company_name_str)
    timestamp_dir = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(100000, 999999)
    run_dir_name = f"{timestamp_dir}-{sanitized_company_name}-{random_suffix}"
    run_dir_path = os.path.join(base_result_dir, run_dir_name)
    
    try:
        os.makedirs(run_dir_path, exist_ok=True)
        log_event("INFO", f"当前运行结果目录已创建: {run_dir_path}", module_name="系统初始化")
        return run_dir_path
    except Exception as e:
        error_msg = f"创建运行结果目录 '{run_dir_path}' 失败: {e}"
        if 'streamlit' in globals() and hasattr(st, 'error'): # Check if st is available
            st.error(error_msg)
        log_event("ERROR", error_msg, module_name="系统初始化")
        return None

def get_latest_period_info(cwp_data: dict) -> tuple[dict | None, str]:
    """Extracts the latest report object and its label from CWP data."""
    if not cwp_data or not cwp_data.get('base_data', {}).get('financial_reports'):
        return None, "无可用报告期"
    financial_reports = cwp_data['base_data']['financial_reports']
    if not financial_reports: # Check if the list is empty
        return None, "无可用报告期"
    # Assuming reports are sorted descending by date, so the first one is the latest.
    latest_report = financial_reports[0]
    return latest_report, latest_report.get('period_label', "未知报告期")


def format_core_statements_for_llm(reports: list) -> str:
    """Formats BS, IS, CFS from all reports into a compact JSON string for the LLM."""
    all_statements_data = []
    # MAX_JSON_TABLE_ROWS should be defined in config.py
    from config import CHUNK_MAX_CHARS_FOR_OVERVIEW # Reusing this, or define a specific one
    MAX_JSON_TABLE_ROWS = 100 # Or import from config if defined there for this purpose

    for report in reports:
        report_period_label = report.get("period_label", "未知报告期")
        
        for stmt_key, stmt_name_full in [
            ("balance_sheet_data", "资产负债表 (Balance Sheet)"), 
            ("income_statement_data", "利润表 (Income Statement)"), 
            ("cash_flow_statement_data", "现金流量表 (Cash Flow Statement)")
        ]:
            notes_for_statement = ""
            if report.get(stmt_key) and report[stmt_key] is not None:
                try:
                    df = pd.DataFrame.from_dict(report[stmt_key])
                    if not df.empty:
                        for col in df.columns:
                            if pd.api.types.is_datetime64_any_dtype(df[col]):
                                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("")
                        df = df.fillna("").astype(str) 
                        columns = df.columns.tolist()
                        data_list = df.head(MAX_JSON_TABLE_ROWS).values.tolist()
                        if len(df) > MAX_JSON_TABLE_ROWS:
                            notes_for_statement = f"注意: 表格数据较长，此处仅包含前 {MAX_JSON_TABLE_ROWS} 行。"
                        all_statements_data.append({
                            "report_period": report_period_label,
                            "statement_name": stmt_name_full,
                            "columns": columns,
                            "data": data_list,
                            "notes": notes_for_statement
                        })
                    else: 
                        log_event("WARNING", f"{stmt_name_full} for {report_period_label} is empty.", "format_core_statements")
                except Exception as e: 
                    log_event("ERROR", f"Error processing {stmt_name_full} for {report_period_label} into JSON: {e}", "format_core_statements")
            else:
                log_event("WARNING", f"{stmt_name_full} for {report_period_label} not found or is None.", "format_core_statements")

    if not all_statements_data:
        return "无核心三表数据可供分析。"
    
    try:
        json_string = json.dumps(all_statements_data, ensure_ascii=False, indent=None) 
        return json_string
    except Exception as e:
        log_event("ERROR", f"Error serializing core statements to JSON: {e}", "format_core_statements")
        return "核心三表数据序列化为JSON时出错。"

def get_prior_analyses_summary(current_module_name: str) -> str:
    """
    Retrieves and summarizes conclusions from preceding analysis modules.
    If a summary doesn't exist, it generates one using an LLM.
    """
    llm = get_llm_instance() # Get the initialized LLM
    dependencies = MODULE_DEPENDENCIES.get(current_module_name, [])
    summary_parts = []

    if not dependencies:
        return "无特定的前序模块分析结论可供直接参考，或依赖关系未定义。"

    for dep_module_name in dependencies:
        if dep_module_name in st.session_state.cwp['analytical_module_outputs']:
            dep_output_entry = st.session_state.cwp['analytical_module_outputs'][dep_module_name]
            if dep_output_entry.get('status') == 'Completed':
                if dep_output_entry.get('abbreviated_summary'):
                    log_event("CWP_INTERACTION", f"使用已缓存的模块 '{dep_module_name}' 的缩略摘要。", module_name=current_module_name, details={"dependency": dep_module_name})
                    summary_parts.append(f"来自模块“{dep_module_name}”的缩略摘要：\n{dep_output_entry['abbreviated_summary']}")
                elif dep_output_entry.get('text_summary'): 
                    log_event("MODULE_EVENT", f"模块 '{dep_module_name}' 的缩略摘要不存在，正在按需生成...", module_name=current_module_name, details={"dependency": dep_module_name})
                    original_text = dep_output_entry['text_summary']
                    # Truncate original_text if it's too long for the summarizer LLM
                    summarization_input_text = original_text[:15000] 
                    if len(original_text) > 15000:
                         log_event("WARNING", f"Original text for '{dep_module_name}' was truncated for summarization input.", module_name=current_module_name)

                    summarization_prompt = f"""请将以下文本内容精确地总结为一段不超过1000个汉字的关键信息摘要。此摘要将作为后续财务分析模块 '{current_module_name}' 的重要参考输入。请确保摘要保留所有核心观点、关键数据和重要结论，同时尽可能简洁。原始文本如下：\n---\n{summarization_input_text}\n---\n1000字以内的摘要："""
                    
                    if llm:
                        try:
                            summary_messages = [{"role": "user", "content": summarization_prompt}]
                            summary_response = llm.invoke(summary_messages)
                            abbreviated_summary_text = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                            st.session_state.cwp['analytical_module_outputs'][dep_module_name]['abbreviated_summary'] = abbreviated_summary_text
                            log_event("CWP_INTERACTION", f"模块 '{dep_module_name}' 的缩略摘要已生成并存入核心底稿 (长度: {len(abbreviated_summary_text)})。", module_name=current_module_name, details={"dependency": dep_module_name, "original_length": len(original_text), "summary_length": len(abbreviated_summary_text)})
                            summary_parts.append(f"来自模块“{dep_module_name}”的缩略摘要：\n{abbreviated_summary_text}")
                        except Exception as e:
                            log_event("ERROR", f"为模块 '{dep_module_name}' 生成缩略摘要失败: {e}", module_name=current_module_name)
                            summary_parts.append(f"来自模块“{dep_module_name}”的结论摘要 (生成缩略版失败，使用部分原文)：\n{original_text[:300]}...")
                    else:
                        log_event("WARNING", f"LLM不可用，无法为模块 '{dep_module_name}' 生成缩略摘要，使用部分原文替代。", module_name=current_module_name)
                        summary_parts.append(f"来自模块“{dep_module_name}”的结论摘要 (LLM不可用，使用部分原文)：\n{original_text[:300]}...")
                else:
                    log_event("WARNING", f"模块 '{dep_module_name}' 已完成但无文本摘要可供缩略。", module_name=current_module_name, details={"dependency": dep_module_name})
            else:
                log_event("WARNING", f"依赖的前序模块 '{dep_module_name}' 状态非 'Completed' 或无输出。", module_name=current_module_name, details={"dependency": dep_module_name, "status": dep_output_entry.get('status')})
        else:
            log_event("WARNING", f"依赖的前序模块 '{dep_module_name}' 在核心底稿中未找到。", module_name=current_module_name, details={"dependency": dep_module_name})
    
    if not summary_parts:
        return "未能获取任何相关的前序模块分析结论摘要。"
    return "\n\n".join(summary_parts)

