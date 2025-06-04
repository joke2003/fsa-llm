# integration_services.py
# Contains functions for integrating analysis results, logging contradictions,
# and consolidating risks/opportunities.
# Part of Application Version 0.10.0

import streamlit as st # For st.session_state
import json
from datetime import datetime
from logger import log_event
from llm_setup import get_llm_instance
from config import ANALYSIS_FRAMEWORK_SECTIONS # To get ordered module list for consolidation

def update_overall_conclusion_and_log_contradictions(module_name: str, new_finding_text: str, new_finding_confidence: str):
    """
    Updates the current overall financial conclusion by integrating new module findings
    and logs any contradictions found using an LLM.
    """
    llm = get_llm_instance()
    if not llm:
        log_event("ERROR", "LLM not available, cannot update overall conclusion or check contradictions.", "UpdateOverallConclusion")
        return

    log_event("MODULE_EVENT", f"开始更新总体结论并检查与模块 '{module_name}' 的矛盾点。", "UpdateOverallConclusion")
    
    cwp_insights = st.session_state.cwp['integrated_insights']
    prev_overall_conclusion = cwp_insights.get('current_overall_financial_conclusion', "这是首次分析，尚无前期总体结论。")
    
    prompt = f"""
    您是一位专业的财务分析整合员。您的任务是根据一个已有的“当前公司总体财务分析结论”和刚刚完成的“新模块分析结论”（及其置信度），来更新总体结论，并识别新结论与旧总体结论之间是否存在矛盾。

    **已知信息：**
    1.  **当前公司总体财务分析结论（更新前）：**
        ```
        {prev_overall_conclusion}
        ```
    2.  **新完成的“{module_name}”模块分析结论：**
        ```
        {new_finding_text}
        ```
        该模块分析结论的置信度为： **{new_finding_confidence}** (置信度解读参考: 较高如85%-100%应重点采纳, 较低如50%-70%应谨慎采纳或指出不确定性, "N/A"或"无法解析"表示置信度信息缺失或有问题)

    **您的任务：**
    1.  **更新总体结论：** 请结合上述两部分信息，生成一个新的“（更新后）公司总体财务分析结论”。在整合新模块结论时，请充分考虑其置信度。更新后的结论应保持连贯和逻辑性，并逐步累积形成对公司更全面的判断。力求客观、中立，并准确反映新信息的价值。如果新模块结论置信度很低（例如低于60%）或与前期结论严重冲突且缺乏强有力证据，可以考虑在更新的总体结论中对其进行弱化处理或指出其不确定性。
    2.  **识别矛盾点：** 判断“新模块分析结论”中的核心观点或关键数据，是否与更新前的“当前公司总体财务分析结论”中的某些内容存在明显的不一致或矛盾。
        * 如果存在矛盾，请清晰、简要地描述这个矛盾点是什么（例如：“新模块指出流动比率显著下降，而前期总体结论认为短期偿债能力良好”）。
        * 如果不存在明显矛盾，请明确说明“无明显矛盾”。

    **请以严格的JSON格式返回您的输出，包含以下键：**
    ```json
    {{
      "updated_overall_conclusion": "（更新后）公司总体财务分析结论的完整文本...",
      "contradiction_found": true_or_false,
      "contradiction_description": "如果 contradiction_found 为 true，此处描述矛盾点；否则为 '无明显矛盾'。"
    }}
    ```
    """
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages, response_format={'type': 'json_object'}) 
        response_content = response.content if hasattr(response, 'content') else str(response)
        
        cleaned_json_str = response_content.strip()
        if cleaned_json_str.startswith("```json"): cleaned_json_str = cleaned_json_str[7:]
        if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3]
        
        parsed_update = json.loads(cleaned_json_str.strip())
        
        updated_conclusion = parsed_update.get("updated_overall_conclusion", prev_overall_conclusion) 
        contradiction_found = parsed_update.get("contradiction_found", False)
        contradiction_description = parsed_update.get("contradiction_description", "未明确说明是否有矛盾。")
        
        st.session_state.cwp['integrated_insights']['current_overall_financial_conclusion'] = updated_conclusion
        log_event("CWP_INTERACTION", "“当前公司总体财务分析结论”已更新。", "UpdateOverallConclusion", {"new_conclusion_snippet": updated_conclusion[:200]+"..."})
        
        if contradiction_found and contradiction_description.lower() not in ["无明显矛盾。", "无明显矛盾", "", "无矛盾", "未发现矛盾"]:
            contradiction_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "module_name": module_name,
                "module_confidence": new_finding_confidence, 
                "contradiction_description": contradiction_description,
                "module_finding_snippet": new_finding_text[:300]+"...",
                "previous_overall_conclusion_snippet": prev_overall_conclusion[:300]+"..."
            }
            st.session_state.cwp['integrated_insights']['contradiction_logbook'].append(contradiction_entry)
            log_event("WARNING", f"发现矛盾点！模块 '{module_name}' 的结论与前期总体结论存在矛盾。", "UpdateOverallConclusion", details=contradiction_entry)
        else:
            log_event("INFO", f"模块 '{module_name}' 的结论与前期总体结论未发现明显矛盾。", "UpdateOverallConclusion")

    except json.JSONDecodeError:
        error_detail = f"LLM未能返回有效的JSON。原始回复: {response_content[:500]}..."
        log_event("ERROR", "更新总体结论时，LLM未能返回有效的JSON。", "UpdateOverallConclusion", details={"raw_response_snippet": response_content[:200]+"..."})
    except Exception as e:
        log_event("ERROR", f"更新总体结论并检查矛盾点时发生错误: {e}", "UpdateOverallConclusion", {"exception_details": str(e)})


def consolidate_risks_and_opportunities():
    """
    Consolidates key risks and opportunities from all module outputs and the overall conclusion
    using an LLM.
    """
    llm = get_llm_instance()
    if not llm:
        log_event("ERROR", "LLM not available, cannot consolidate risks and opportunities.", "RiskOpportunityConsolidation")
        return

    log_event("MODULE_EVENT", "开始提炼关键风险与机遇点。", "RiskOpportunityConsolidation")
    
    module_summaries = []
    # Use ANALYSIS_FRAMEWORK_SECTIONS to get an ordered list of all modules
    ordered_module_names = [mod_name for section_modules in ANALYSIS_FRAMEWORK_SECTIONS.values() for mod_name in section_modules]
    
    for module_name in ordered_module_names:
        if module_name in st.session_state.cwp['analytical_module_outputs']:
            output = st.session_state.cwp['analytical_module_outputs'][module_name]
            if output.get('status') == 'Completed':
                summary_text = output.get('abbreviated_summary') or output.get('text_summary', '')
                confidence = output.get('confidence_score', 'N/A')
                module_summaries.append(f"--- 模块: {module_name} (置信度: {confidence}) ---\n{summary_text[:1000]}...\n") # Limit length of each summary
                
    current_overall_conclusion = st.session_state.cwp['integrated_insights'].get('current_overall_financial_conclusion', "无当前总体结论。")
    
    prompt = f"""
    您是一位资深的风险管理与战略分析专家。请全面审阅以下提供的所有财务分析模块的结论摘要，以及当前形成的总体财务分析结论。

    **当前公司总体财务分析结论：**
    ```
    {current_overall_conclusion}
    ```

    **各模块分析结论摘要汇总：**
    ```
    {"\n".join(module_summaries)}
    ```

    **您的任务是：**
    1.  **识别并总结关键风险点 (Key Risks):** 从所有信息中，提炼出该公司面临的 **3至5个最主要** 的风险。对于每个风险，请提供以下信息：
        * `id`: 风险的唯一标识符 (例如 "R001", "R002")。
        * `description`: 对风险的清晰、简洁描述。
        * `category`: 风险分类 (例如：财务-流动性, 战略-市场竞争, 经营-供应链, 行业特定风险, 公司治理风险等)。
        * `source_modules`: 列出主要支持或揭示此风险的分析模块名称 (列表形式，例如 ["1.2 SWOT 分析", "4.3 利息保障倍数及现金流偿债能力分析"])。
        * `potential_impact`: 风险的潜在影响程度 (请评估为：高, 中, 低)。
        * `mitigating_factors_observed`: (可选) 如果分析中提及了公司已采取的或已存在的缓解该风险的因素，请简述。
        * `notes_for_further_investigation`: (可选) 针对此风险，建议后续需要特别关注或线下调研的要点。
    2.  **识别并总结关键机遇点 (Key Opportunities):** 从所有信息中，提炼出该公司面临的 **3至5个最主要** 的机遇。对于每个机遇，请提供以下信息：
        * `id`: 机遇的唯一标识符 (例如 "O001", "O002")。
        * `description`: 对机遇的清晰、简洁描述。
        * `category`: 机遇分类 (例如：市场机遇, 技术创新机遇, 政策利好机遇, 战略合作机遇等)。
        * `source_modules`: 列出主要支持或揭示此机遇的分析模块名称 (列表形式)。
        * `potential_benefit`: 机遇的潜在收益或价值实现程度 (请评估为：高, 中, 低)。
        * `actionability_notes`: (可选) 公司抓住此机遇的建议、前提条件或需关注的执行层面问题。
    请确保风险和机遇列表简洁、准确、具有洞察力，避免重复，并**按您评估的重要性进行排序（最重要的在前）**。
    请将您的输出严格按照以下JSON格式返回：
    ```json
    {{
      "key_risks": [
        {{
          "id": "R001", "description": "...", "category": "...", "source_modules": ["...", "..."],
          "potential_impact": "高", "mitigating_factors_observed": "...", "notes_for_further_investigation": "..."
        }}
      ],
      "key_opportunities": [
        {{
          "id": "O001", "description": "...", "category": "...", "source_modules": ["...", "..."],
          "potential_benefit": "高", "actionability_notes": "..."
        }}
      ]
    }}
    ```
    """
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages, response_format={'type': 'json_object'}) 
        response_content = response.content if hasattr(response, 'content') else str(response)
        
        cleaned_json_str = response_content.strip()
        if cleaned_json_str.startswith("```json"): cleaned_json_str = cleaned_json_str[7:]
        if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3]
        
        parsed_risks_ops = json.loads(cleaned_json_str.strip())
        
        st.session_state.cwp['integrated_insights']['key_risks'] = parsed_risks_ops.get("key_risks", [])
        st.session_state.cwp['integrated_insights']['key_opportunities'] = parsed_risks_ops.get("key_opportunities", [])
        log_event("CWP_INTERACTION", "关键风险与机遇点已提炼并存入核心底稿。", "RiskOpportunityConsolidation", 
                  details={"num_risks": len(st.session_state.cwp['integrated_insights']['key_risks']), 
                           "num_opportunities": len(st.session_state.cwp['integrated_insights']['key_opportunities'])})
    except json.JSONDecodeError:
        log_event("ERROR", "提炼风险机遇时，LLM未能返回有效的JSON。", "RiskOpportunityConsolidation", {"raw_response": response_content})
    except Exception as e:
        log_event("ERROR", f"提炼风险机遇时发生错误: {e}", "RiskOpportunityConsolidation", {"exception_details": str(e)})

