# core_analysis_engine.py
# Contains the main logic for executing a single financial analysis module.
# Part of Application Version 0.10.0

import streamlit as st # For st.session_state
import pandas as pd
import json
from datetime import datetime

from logger import log_event
from llm_setup import get_llm_instance
from prompts import MODULE_PROMPTS
from utils import get_latest_period_info, format_core_statements_for_llm, get_prior_analyses_summary
from integration_services import update_overall_conclusion_and_log_contradictions, consolidate_risks_and_opportunities
from reporting import generate_and_save_html_report
from config import TOTAL_MODULES_COUNT # For progress calculation if AI planner fails

# Import tool services for pre-fetching, though not for dynamic LLM tool calls in this function
from tool_services import custom_duckduckgo_search, execute_get_relevant_document_content
from planning_services import select_relevant_chunks_llm, compress_selected_text_llm
from config import COMPRESSED_DOC_MAX_CHARS


def run_llm_module_analysis(module_name_full: str, section_name: str):
    """
    Executes a single financial analysis module using pre-fetched information.
    The LLM is expected to return a JSON object with 'analysis_text' and 'confidence_score'.
    No dynamic tool calls are made by the LLM in this function.
    """
    llm = get_llm_instance()
    log_event("MODULE_EVENT", f"模块 '{module_name_full}' 开始执行 (新版预获取信息流程)。", module_name=module_name_full)
    st.session_state.current_module_processing = f"正在分析: {module_name_full}"
    
    company_info = st.session_state.cwp['base_data']['company_info']
    all_reports = st.session_state.cwp['base_data']['financial_reports']
    _, local_latest_period_label = get_latest_period_info(st.session_state.cwp) 
    all_period_labels_str = ", ".join([r['period_label'] for r in all_reports]) if all_reports else "无"
    analysis_perspective = company_info.get("analysis_perspective", "未指定分析角度") 
    macro_conclusion = company_info.get("macro_analysis_conclusion_text", "用户未提供宏观经济分析结论或未成功加载。")
    industry_conclusion = company_info.get("industry_analysis_conclusion_text", "行业分析结论（基于波特五力模型）尚未生成或不可用。")

    # --- Retrieve pre-fetched information based on planned needs ---
    pre_fetched_search_results_str = "未规划或执行任何外部搜索查询。"
    pre_fetched_document_contents_str = "未规划或执行任何文档内容提取。"
    
    module_info_needs_plan = st.session_state.cwp['metadata_version_control'].get('information_needs_by_module', {}).get(module_name_full)
    
    # 1. Prepare Pre-fetched Search Results
    if module_info_needs_plan and module_info_needs_plan.get("search_queries"):
        log_event("INFO", f"模块 '{module_name_full}' 需要执行 {len(module_info_needs_plan['search_queries'])} 条搜索查询。", "InfoPreFetching", {"queries": module_info_needs_plan['search_queries']})
        all_search_results_for_module = []
        for query_idx, query in enumerate(module_info_needs_plan["search_queries"]):
            search_result_text = custom_duckduckgo_search(query)
            all_search_results_for_module.append(f"针对查询“{query}”的预获取搜索结果 {query_idx+1}：\n{search_result_text}\n---")
        if all_search_results_for_module:
            pre_fetched_search_results_str = "\n".join(all_search_results_for_module)
        else:
            pre_fetched_search_results_str = "所有为本模块预规划的搜索查询均未返回有效结果。"
        log_event("CWP_INTERACTION", f"模块 '{module_name_full}' 的预获取搜索结果已准备。", "InfoPreFetching", {"length": len(pre_fetched_search_results_str)})

    # 2. Prepare Pre-fetched Document Contents
    if module_info_needs_plan and module_info_needs_plan.get("document_extractions"):
        log_event("INFO", f"模块 '{module_name_full}' 需要执行 {len(module_info_needs_plan['document_extractions'])} 个文档内容提取。", "InfoPreFetching", {"extractions_plan": module_info_needs_plan['document_extractions']})
        all_extracted_contents_for_module = []
        
        grouped_extractions = {}
        for extr_spec in module_info_needs_plan["document_extractions"]:
            key = (extr_spec["document_type"], extr_spec["period_label"])
            if key not in grouped_extractions: grouped_extractions[key] = []
            grouped_extractions[key].append(extr_spec["analysis_context"])

        for (doc_type, period_label), analysis_contexts in grouped_extractions.items():
            doc_chunks_with_overviews = []
            target_report_entry = next((r for r in all_reports if r['period_label'] == period_label), None)
            if target_report_entry:
                processed_chunks_key = 'footnotes_processed_chunks' if doc_type == "footnotes" else 'mda_processed_chunks'
                doc_chunks_with_overviews = target_report_entry.get(processed_chunks_key, [])
            
            if not doc_chunks_with_overviews:
                log_event("WARNING", f"未找到模块 '{module_name_full}' 规划提取的文档 '{doc_type}' ({period_label}) 的预处理分块数据。", "InfoPreFetching")
                all_extracted_contents_for_module.append(f"未能提取文档 '{doc_type}' ({period_label}) 的内容：未找到预处理分块数据。")
                continue

            selected_chunk_ids = select_relevant_chunks_llm(analysis_contexts, doc_chunks_with_overviews)
            
            if selected_chunk_ids:
                concatenated_original_text = ""
                for chunk_id_to_fetch in selected_chunk_ids:
                    found_chunk = next((chunk for chunk in doc_chunks_with_overviews if chunk["chunk_id"] == chunk_id_to_fetch), None)
                    if found_chunk: concatenated_original_text += found_chunk.get("original_text", "") + "\n\n"
                    else: log_event("WARNING", f"规划选中的块ID '{chunk_id_to_fetch}' 未在 {doc_type} ({period_label}) 的分块中找到。", "InfoPreFetching")
                
                if concatenated_original_text.strip():
                    combined_analysis_context_for_compression = f"为模块 '{module_name_full}' 分析以下方面：{'; '.join(analysis_contexts)}"
                    compressed_text = compress_selected_text_llm(concatenated_original_text, combined_analysis_context_for_compression, COMPRESSED_DOC_MAX_CHARS)
                    all_extracted_contents_for_module.append(f"从文档 '{doc_type}' ({period_label}) 中针对上下文 '{'; '.join(analysis_contexts)}' 提取并压缩的内容：\n{compressed_text}\n---")
                else: all_extracted_contents_for_module.append(f"未能从文档 '{doc_type}' ({period_label}) 中为上下文 '{'; '.join(analysis_contexts)}' 提取到有效内容（选中的块为空）。")
            else:
                all_extracted_contents_for_module.append(f"未能从文档 '{doc_type}' ({period_label}) 中为上下文 '{'; '.join(analysis_contexts)}' 确定相关内容块。")
        
        if all_extracted_contents_for_module:
            pre_fetched_document_contents_str = "\n".join(all_extracted_contents_for_module)
        else:
            pre_fetched_document_contents_str = "所有为本模块预规划的文档提取均未返回有效内容。"
        log_event("CWP_INTERACTION", f"模块 '{module_name_full}' 的预获取文档内容已准备。", "InfoPreFetching", {"length": len(pre_fetched_document_contents_str)})
    
    # --- Prepare prompt for the main analysis LLM ---
    core_statements_data_str = format_core_statements_for_llm(all_reports)
    prior_analyses_summary = get_prior_analyses_summary(module_name_full)

    prompt_config = MODULE_PROMPTS.get(module_name_full, MODULE_PROMPTS["DEFAULT_PROMPT"])
    prompt_template = prompt_config["main_prompt_template"]
    
    prompt_context = {
        "公司名称": company_info.get("name", "未知公司"), 
        "行业名称": company_info.get("industry", "未知行业"),
        "最新报告期标签": local_latest_period_label if local_latest_period_label else "无最新报告期",
        "所有报告期标签": all_period_labels_str, 
        "财务数据摘要": "相关的文档细节已通过 '[预获取的文档提取内容]' 提供。原始文档清单主要用于参考。", 
        "核心三表数据_所有报告期": core_statements_data_str, 
        "前期分析结论摘要": prior_analyses_summary, 
        "模块名称": module_name_full,
        "分析角度": analysis_perspective,
        "宏观经济分析结论": macro_conclusion, 
        "行业分析结论": industry_conclusion,
        "[预获取的搜索查询结果]": pre_fetched_search_results_str, 
        "[预获取的文档提取内容]": pre_fetched_document_contents_str 
    }
    current_prompt_text = prompt_template
    try:
        for key, value in prompt_context.items(): 
            if f"[{key}]" in current_prompt_text:
                current_prompt_text = current_prompt_text.replace(f"[{key}]", str(value))
            elif key in current_prompt_text: 
                 current_prompt_text = current_prompt_text.replace(key, str(value))
        
        log_event("INFO", "模块提示语已生成。", module_name=module_name_full, details={"prompt_length": len(current_prompt_text)})
        log_event("LLM_PROMPT_DETAIL", f"准备发送给LLM的完整提示语 for module '{module_name_full}'", 
                  module_name=module_name_full, details={"full_prompt": current_prompt_text})
    except Exception as e: 
        log_event("ERROR", f"生成模块提示时发生错误: {e}", module_name=module_name_full, details={"prompt_context_keys": list(prompt_context.keys())})
        st.error(f"生成模块 '{module_name_full}' 的提示时发生错误: {e}")
        st.session_state.cwp['analytical_module_outputs'][module_name_full] = {"text_summary": f"提示生成错误: {e}", "structured_data": {}, "status": "Error", "timestamp": pd.Timestamp.now().isoformat(), "confidence_score": "N/A", "abbreviated_summary": None}
        return

    messages = [{"role": "user", "content": current_prompt_text}]
    llm_response_text = ""
    confidence_score_from_llm = "N/A (处理中)"

    try:
        if not llm: 
            llm_response_text = f"LLM not available. Cannot process {module_name_full}."
            log_event("ERROR", llm_response_text, module_name=module_name_full)
        else:
            log_event("MODULE_EVENT", f"向LLM发送最终分析请求 (期望JSON输出)。", module_name=module_name_full)
            # No tools passed here, only expecting JSON output based on prompt.
            response_message = llm.invoke(messages, response_format={'type': 'json_object'}) 
            
            if hasattr(response_message, 'content') and response_message.content:
                llm_response_text = response_message.content
                log_event("INFO", "LLM已返回分析结果。", module_name=module_name_full)
            else:
                log_event("ERROR", f"LLM响应中无有效内容: {type(response_message)}", module_name=module_name_full, details={"response": str(response_message)})
                llm_response_text = f"LLM response format error or empty content for {module_name_full}."
        
        log_event("LLM_FINAL_CONVERSATION", f"LLM的最终分析交互记录 for module '{module_name_full}'", module_name=module_name_full, details={"conversation": messages})
        
        final_analysis_text_content = llm_response_text 
        if llm_response_text and "LLM response format error" not in llm_response_text and "LLM not available" not in llm_response_text:
            try:
                cleaned_json_str = llm_response_text.strip(); 
                if cleaned_json_str.startswith("```json"): cleaned_json_str = cleaned_json_str[7:]
                if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3]
                parsed_response = json.loads(cleaned_json_str.strip()); final_analysis_text_content = parsed_response.get("analysis_text", llm_response_text); confidence_score_from_llm = parsed_response.get("confidence_score", "N/A (JSON中未提供)")
                log_event("INFO", f"LLM响应已解析为JSON。置信度: {confidence_score_from_llm}", module_name=module_name_full)
            except json.JSONDecodeError: final_analysis_text_content = llm_response_text; confidence_score_from_llm = "N/A (JSON解析失败)"; log_event("WARNING", "LLM响应不是有效的JSON格式，将使用原始文本。", module_name=module_name_full, details={"raw_response_snippet": llm_response_text[:200]+"..."})
        else:
            if not llm_response_text: final_analysis_text_content = "LLM未能生成有效响应。"
            confidence_score_from_llm = "N/A (无响应或错误)"; 
            log_event("ERROR", final_analysis_text_content if final_analysis_text_content else "LLM响应为空", module_name=module_name_full)
        
        st.session_state.cwp['analytical_module_outputs'][module_name_full] = {"text_summary": final_analysis_text_content, "confidence_score": confidence_score_from_llm, "structured_data": {}, "status": "Completed" if final_analysis_text_content and not final_analysis_text_content.startswith("LLM未能生成有效响应") and "LLM response format error" not in final_analysis_text_content else "Error/Incomplete", "timestamp": pd.Timestamp.now().isoformat(), "prompt_used": current_prompt_text, "message_history": messages, "abbreviated_summary": None}
        log_event("CWP_INTERACTION", "模块分析结果已写入核心底稿。", module_name=module_name_full)
        
        if st.session_state.cwp['analytical_module_outputs'][module_name_full]['status'] == 'Completed':
            update_overall_conclusion_and_log_contradictions(module_name_full, final_analysis_text_content, confidence_score_from_llm)
            if module_name_full == "1.1 波特五力模型": 
                log_event("MODULE_EVENT", "模块 '1.1 波特五力模型' 完成，准备生成其缩略摘要作为行业分析结论。", module_name=module_name_full)
                if llm:
                    summarization_prompt = f"""请将以下“波特五力模型”分析的完整结论，总结为一段不超过1000个汉字（约500-700字为佳）的“行业分析结论”摘要。此摘要将作为后续其他财务分析模块的重要参考。请确保摘要准确反映了行业竞争格局的核心要点。原始文本如下：\n---\n{final_analysis_text_content[:15000]}\n---\n1000字以内的行业分析结论摘要："""
                    try:
                        summary_messages = [{"role": "user", "content": summarization_prompt}]; summary_response = llm.invoke(summary_messages) 
                        industry_conclusion_summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                        st.session_state.cwp['base_data']['company_info']['industry_analysis_conclusion_text'] = industry_conclusion_summary
                        st.session_state.cwp['analytical_module_outputs'][module_name_full]['abbreviated_summary'] = industry_conclusion_summary 
                        log_event("CWP_INTERACTION", "行业分析结论 (来自波特五力模型摘要) 已生成并存入核心底稿。", module_name=module_name_full, details={"length": len(industry_conclusion_summary)})
                    except Exception as e: log_event("ERROR", f"为“1.1 波特五力模型”生成行业分析结论摘要失败: {e}", module_name=module_name_full); st.session_state.cwp['base_data']['company_info']['industry_analysis_conclusion_text'] = "行业分析结论摘要生成失败。"
                else: st.session_state.cwp['base_data']['company_info']['industry_analysis_conclusion_text'] = "LLM不可用，无法生成行业分析结论摘要。"
    except Exception as e:
        log_event("ERROR", f"模块分析执行期间发生严重错误: {e}", module_name=module_name_full)
        st.error(f"模块 '{module_name_full}' 分析执行期间发生严重错误: {e}")
        st.session_state.cwp['analytical_module_outputs'][module_name_full] = {"text_summary": f"分析执行失败: {e}", "structured_data": {}, "status": "Error", "timestamp": pd.Timestamp.now().isoformat(), "prompt_used": current_prompt_text, "confidence_score": "N/A (执行错误)", "abbreviated_summary": None}
    
    log_event("MODULE_EVENT", f"模块 '{module_name_full}' 执行结束。", module_name=module_name_full)
    completed_modules = len(st.session_state.cwp['analytical_module_outputs'])
    
    current_total_modules_to_run = TOTAL_MODULES_COUNT
    if st.session_state.cwp['base_data']['company_info'].get('ai_planner_enabled', False) and \
       st.session_state.cwp['metadata_version_control'].get('ai_planned_modules'):
        current_total_modules_to_run = len(st.session_state.cwp['metadata_version_control']['ai_planned_modules'])
        if current_total_modules_to_run == 0: 
            current_total_modules_to_run = TOTAL_MODULES_COUNT

    st.session_state.analysis_progress = min(100, int((completed_modules / current_total_modules_to_run) * 100)) if current_total_modules_to_run > 0 else 0
    
    if st.session_state.analysis_progress >= 100 and completed_modules >= current_total_modules_to_run : 
        st.session_state.current_module_processing = "✅ 分析全部完成！"; log_event("INFO", "所有规划的分析模块已完成，准备提炼风险与机遇。")
        consolidate_risks_and_opportunities(); log_event("INFO", "风险与机遇已提炼，准备生成最终报告。"); generate_and_save_html_report() 
