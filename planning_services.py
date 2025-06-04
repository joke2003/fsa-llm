# planning_services.py
# Contains functions related to AI planning of analysis routes and information needs,
# including chunk selection and text compression for document content.
# Part of Application Version 0.10.0+

import json
import re
from logger import log_event
from llm_setup import get_llm_instance
from config import ALL_DEFINED_MODULES_LIST, COMPRESSED_DOC_MAX_CHARS 
from prompts import MODULE_PROMPTS 

def get_ai_planned_analysis_route(company_info_dict: dict, macro_conclusion_str: str, all_available_modules_list: list) -> dict | None:
    """
    Uses LLM to plan the most relevant and efficient sequence of analysis modules,
    and also provide reasoning for the plan.
    Returns:
        dict: {"planned_modules": list_of_modules, "planning_reasoning": "reasoning_text"}
              or None if planning fails.
    """
    llm = get_llm_instance()
    if not llm:
        log_event("ERROR", "LLM not available, AI Task Planner cannot run. Defaulting to all modules.", "AIPlanner")
        return {"planned_modules": all_available_modules_list, "planning_reasoning": "LLM不可用，执行所有预定义模块作为后备计划。"}
    
    log_event("MODULE_EVENT", "AI任务规划器开始运行 (含理由生成)...", "AIPlanner")
    available_modules_str = "\n".join([f"- {name}" for name in all_available_modules_list])
    
    planner_prompt = f"""
    您是一位经验丰富的首席财务分析师，负责为特定公司和分析角度规划最有效率的财务分析模块执行顺序，并解释您的规划理由。

    **当前分析目标：**
    - 公司名称: {company_info_dict.get('name', '未知')}
    - 所属行业: {company_info_dict.get('industry', '未知')}
    - 分析角度: {company_info_dict.get('analysis_perspective', '未指定')}
    - （可选）用户提供的宏观经济分析结论摘要: 
      ```
      {macro_conclusion_str[:1000] + "..." if len(macro_conclusion_str) > 1000 else macro_conclusion_str}
      ```

    **所有可用的分析模块列表如下（请从中选择并排序）：**
    ```
    {available_modules_str}
    ```

    **您的任务：**
    1.  根据上述公司信息、分析角度和宏观背景，请选择出最相关、最有价值的分析模块，并给出一个**有序的模块名称列表**。目标是形成一个既全面又有针对性的分析路径，避免不必要的模块以提高效率。
    2.  请提供一段**详细的规划理由** (planning_reasoning)，解释您为什么选择这些模块、为什么按照这个顺序排列，以及这个规划如何服务于当前的分析角度和公司情况。理由应清晰、有逻辑，帮助用户理解您的决策过程。

    请以JSON格式返回您的输出，包含以下两个键：
    - `planned_modules`: 一个包含模块全名的字符串列表，按推荐的执行顺序列出。
    - `planning_reasoning`: 一个字符串，包含您对规划的详细解释。

    **JSON输出格式示例：**
    ```json
    {{
      "planned_modules": ["1.1 波特五力模型", "1.5 财务报表结构与趋势分析", "2.1 综合比率分析"],
      "planning_reasoning": "鉴于该公司为成长型科技公司，且分析角度为股权投资，我们首先通过波特五力模型评估其行业竞争力。接着，财务报表结构与趋势分析有助于我们快速把握其资产配置和盈利模式的特点。最后，综合比率分析将深入评估其运营效率和盈利能力，这些都是股权投资者高度关注的方面。后续模块可根据这些初步分析的结果进一步动态调整。"
    }}
    ```
    如果无法进行有效规划或认为所有模块都与当前分析角度和公司情况相关，请在 `planned_modules` 中返回包含所有可用模块的列表，并在 `planning_reasoning` 中说明这是基于全面性考虑的后备计划。
    确保返回的模块名称与“所有可用的分析模块列表”中提供的名称完全一致。
    """
    try:
        messages = [{"role": "user", "content": planner_prompt}]
        response = llm.invoke(messages, response_format={'type': 'json_object'}) 
        response_content = response.content if hasattr(response, 'content') else str(response)
        
        cleaned_json_str = response_content.strip()
        if cleaned_json_str.startswith("```json"): cleaned_json_str = cleaned_json_str[7:]
        if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3]
        
        parsed_plan = json.loads(cleaned_json_str.strip())
        planned_modules = parsed_plan.get("planned_modules")
        planning_reasoning = parsed_plan.get("planning_reasoning", "AI未能提供规划理由。")

        if planned_modules and isinstance(planned_modules, list) and all(isinstance(m, str) for m in planned_modules):
            valid_planned_modules = [m for m in planned_modules if m in all_available_modules_list]
            if len(valid_planned_modules) < len(planned_modules):
                log_event("WARNING", "AI规划器返回了列表中不存在的模块名，已被过滤。", "AIPlanner", {"original_plan": planned_modules, "valid_plan": valid_planned_modules})
            
            if not valid_planned_modules: # If all planned modules were invalid or list was empty
                log_event("ERROR", "AI规划器未能返回有效的模块列表（过滤后为空或类型错误），将执行所有模块。", "AIPlanner", {"planned_modules_from_llm": planned_modules})
                return {"planned_modules": all_available_modules_list, "planning_reasoning": "AI规划的模块列表无效，已采用所有预定义模块作为后备计划。"}
            
            log_event("INFO", f"AI规划器成功规划模块列表和理由。", "AIPlanner", {"modules": valid_planned_modules, "reasoning_snippet": planning_reasoning[:100]+"..."})
            return {"planned_modules": valid_planned_modules, "planning_reasoning": planning_reasoning}
        else:
            log_event("ERROR", "AI规划器返回的模块列表格式不正确或包含非字符串，将执行所有模块。", "AIPlanner", {"raw_response": response_content})
            return {"planned_modules": all_available_modules_list, "planning_reasoning": "AI规划返回格式错误，已采用所有预定义模块作为后备计划。"}
    except json.JSONDecodeError:
        log_event("ERROR", "AI规划器未能返回有效的JSON，将执行所有模块。", "AIPlanner", {"raw_response": response_content})
        return {"planned_modules": all_available_modules_list, "planning_reasoning": "AI规划返回非JSON格式，已采用所有预定义模块作为后备计划。"}
    except Exception as e:
        log_event("ERROR", f"AI规划器执行时发生错误: {e}", "AIPlanner", {"exception_details": str(e)})
        return {"planned_modules": all_available_modules_list, "planning_reasoning": f"AI规划器执行出错 ({e})，已采用所有预定义模块作为后备计划。"}

def plan_all_module_information_needs(modules_to_plan_for: list, company_info: dict, macro_conclusion: str, industry_conclusion: str, available_docs_summary: str) -> dict:
    """
    Uses LLM to plan information needs (search queries and document extractions) 
    for a list of modules in a single batch call.
    """
    llm = get_llm_instance()
    if not llm:
        log_event("ERROR", "LLM not available, cannot plan information needs.", "InfoNeedsPlanner")
        return {module_name: {"search_queries": [], "document_extractions": []} for module_name in modules_to_plan_for}

    if not modules_to_plan_for:
        log_event("INFO", "No modules provided for information needs planning.", "InfoNeedsPlanner")
        return {}

    log_event("MODULE_EVENT", f"开始为 {len(modules_to_plan_for)} 个模块批量规划信息需求...", "InfoNeedsPlanner")
    
    module_descriptions_parts = []
    for module_name in modules_to_plan_for:
        prompt_template_for_desc = MODULE_PROMPTS.get(module_name, {}).get('main_prompt_template', '通用分析模块')
        match = re.search(r"请针对.*?进行(.*?分析)。", prompt_template_for_desc.strip(), re.DOTALL)
        if match and match.group(1):
            desc_snippet = match.group(1).strip()
        else: 
            desc_snippet = prompt_template_for_desc.split('\n')[0].replace("请针对 [公司名称]（所属行业：[行业名称]，最新报告期：[最新报告期标签]，分析角度：[分析角度]）进行", "").strip()[:150]
        module_descriptions_parts.append(f"- **{module_name}**: {desc_snippet.strip()}...")
    module_descriptions = "\n".join(module_descriptions_parts)

    prompt = f"""
    您是一位高级财务分析策略师。基于以下公司背景和分析目标，请为后续的每一个指定的财务分析模块，规划其所需的信息。

    **公司背景与分析目标：**
    - 公司名称: {company_info.get('name', '未知')}
    - 所属行业: {company_info.get('industry', '未知')}
    - 分析角度: {company_info.get('analysis_perspective', '未指定')}
    - 宏观经济分析结论摘要: ```{macro_conclusion[:1000]}...```
    - 行业分析结论摘要: ```{industry_conclusion[:1000]}...```

    **可供查询的文档资源摘要 (实际查询时需指定报告期和具体内容):**
    ```
    {available_docs_summary}
    ```

    **待规划信息需求的模块列表及其简要目标：**
    ```
    {module_descriptions}
    ```

    **您的任务：**
    为上述列表中的**每一个模块**，分别规划出其完成分析所必需的：
    1.  `search_queries`: 一个字符串列表，包含应执行的搜索引擎查询。查询应具体、有针对性，旨在获取该模块分析所需的外部数据、行业基准、市场信息、竞争对手情况等。如果模块不需要外部搜索，则返回空列表 `[]`。
    2.  `document_extractions`: 一个对象列表。每个对象代表一个从公司财务报表附注(footnotes)或管理层讨论与分析(mda)中提取具体内容的需求。每个对象应包含：
        * `document_type`: 字符串，"footnotes" 或 "mda"。
        * `period_label`: 字符串，需要查询的报告期标签 (例如 "2023 Annual", "2022 Q3")。通常应优先考虑最新报告期，但根据模块需要也可指定历史报告期。
        * `analysis_context`: 字符串，清晰描述需要从该文档的该报告期中提取的具体内容或回答的具体问题 (例如：“详细的收入确认会计政策原文及近三年变更情况”、“管理层对主要业务分部未来一年经营风险的详细讨论和应对措施”、“商誉减值的具体构成及减值测试方法和关键假设”等)。
        如果模块不需要从附注或MD&A中提取特定信息，则返回空列表 `[]`。

    **请以严格的JSON格式返回您的输出。顶层是一个JSON对象，其键是模块的完整标准名称，每个模块名对应的值是另一个包含该模块 `search_queries` (字符串数组) 和 `document_extractions` (对象数组) 的JSON对象。**
    确保所有模块名称与输入列表中的完全一致。如果某个模块不需要任何搜索或文档提取，其对应的 `search_queries` 和 `document_extractions` 应为空列表 `[]`。

    **JSON输出格式示例 (仅为结构示意，具体内容需根据模块判断)：**
    ```json
    {{
      "1.1 波特五力模型": {{
        "search_queries": ["XX行业2023年平均市盈率", "[公司名称] 最新信用评级"],
        "document_extractions": [
          {{"document_type": "footnotes", "period_label": "[最新报告期标签]", "analysis_context": "关于主要供应商和客户集中度的描述"}},
          {{"document_type": "mda", "period_label": "[最新报告期标签]", "analysis_context": "管理层对行业竞争格局的看法"}}
        ]
      }},
      "1.2 SWOT 分析": {{
        "search_queries": ["公司[公司名称]核心竞争力分析"],
        "document_extractions": []
      }}
      // ... 为列表中的其他所有模块提供类似结构 ...
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
        
        planned_needs = json.loads(cleaned_json_str.strip())
        
        validated_needs = {}
        for module_name in modules_to_plan_for:
            if module_name in planned_needs and isinstance(planned_needs[module_name], dict):
                module_plan = planned_needs[module_name]
                sq = module_plan.get("search_queries", [])
                de = module_plan.get("document_extractions", [])
                validated_needs[module_name] = {
                    "search_queries": [q for q in sq if isinstance(q, str)] if isinstance(sq, list) else [],
                    "document_extractions": [
                        item for item in de 
                        if isinstance(item, dict) and 
                           all(k in item for k in ["document_type", "period_label", "analysis_context"]) and
                           isinstance(item["document_type"], str) and 
                           isinstance(item["period_label"], str) and 
                           isinstance(item["analysis_context"], str)
                    ] if isinstance(de, list) else []
                }
            else: 
                log_event("WARNING", f"AI未能为模块 '{module_name}' 规划有效的信息需求，将使用空需求列表。", "InfoNeedsPlanner")
                validated_needs[module_name] = {"search_queries": [], "document_extractions": []}

        log_event("INFO", f"批量信息需求规划完成。规划了 {len(validated_needs)} 个模块的需求。", "InfoNeedsPlanner", {"planned_module_names": list(validated_needs.keys())})
        return validated_needs
    except json.JSONDecodeError as je:
        log_event("ERROR", f"批量信息需求规划时，LLM未能返回有效的JSON: {je}", "InfoNeedsPlanner", {"raw_response": response_content})
    except Exception as e:
        log_event("ERROR", f"批量信息需求规划时发生错误: {e}", "InfoNeedsPlanner", {"exception_details": str(e)})
    return {module_name: {"search_queries": [], "document_extractions": []} for module_name in modules_to_plan_for}


def select_relevant_chunks_llm(analysis_contexts: list, chunk_overviews_with_ids: list) -> list:
    """Uses LLM to select relevant chunk IDs based on analysis context and chunk overviews."""
    llm = get_llm_instance()
    if not llm or not chunk_overviews_with_ids:
        return []
    
    overall_need = "; ".join(analysis_contexts)
    valid_overviews = [c for c in chunk_overviews_with_ids if isinstance(c, dict) and 'chunk_id' in c and 'overview_text' in c]
    if not valid_overviews:
        log_event("WARNING", "No valid chunk overviews provided to select_relevant_chunks_llm.", "SelectRelevantChunks")
        return []

    formatted_overviews = "\n".join([f"- ID: {c['chunk_id']}, 概述: {str(c['overview_text'])[:200]}..." for c in valid_overviews])

    prompt = f"""
    基于以下针对当前分析模块的综合信息需求：
    "{overall_need}"

    以及以下文档文本块的概述列表（每个概述都附带其唯一的 chunk_id）：
    {formatted_overviews}

    请判断并返回一个JSON列表，其中包含与上述综合信息需求**最相关**的文本块的 `chunk_id`。
    目标是选择出能够最好地满足当前分析模块具体信息需求的文本块。如果多个块从不同方面满足需求，请都包含进来。如果没有任何块看起来相关，请返回一个空列表。

    JSON输出格式示例：
    ```json
    {{
      "relevant_chunk_ids": ["chunk_id_1", "chunk_id_3"]
    }}
    ```
    """
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages, response_format={'type': 'json_object'})
        content = response.content if hasattr(response, 'content') else str(response)
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"): cleaned_content = cleaned_content[7:]
        if cleaned_content.endswith("```"): cleaned_content = cleaned_content[:-3]
        
        parsed = json.loads(cleaned_content.strip())
        selected_ids = parsed.get("relevant_chunk_ids", [])
        if isinstance(selected_ids, list) and all(isinstance(item, str) for item in selected_ids):
            log_event("INFO", f"选择器LLM选择了 {len(selected_ids)} 个相关块。", "SelectRelevantChunks", {"selected_ids": selected_ids})
            return selected_ids
        else:
            log_event("ERROR", "选择器LLM返回的chunk_ids格式不正确。", "SelectRelevantChunks", {"raw_response": content})
            return []
    except Exception as e:
        log_event("ERROR", f"选择相关文本块时出错: {e}", "SelectRelevantChunks", {"raw_response_snippet": content[:200] if 'content' in locals() else "N/A"})
        return []

def compress_selected_text_llm(concatenated_text: str, overall_module_context: str, target_max_chars: int = COMPRESSED_DOC_MAX_CHARS) -> str:
    """Uses LLM to compress concatenated text, focusing on module context."""
    llm = get_llm_instance()
    if not llm or not concatenated_text.strip():
        return "无相关内容可压缩。"
    
    max_compressor_input = target_max_chars * 4 
    text_to_compress = concatenated_text
    if len(concatenated_text) > max_compressor_input:
        text_to_compress = concatenated_text[:max_compressor_input]
        log_event("WARNING", f"Text for compression was very long ({len(concatenated_text)} chars), truncated to {max_compressor_input} for compressor LLM.", "CompressSelectedText")

    prompt = f"""
    请将以下拼接的文本段落压缩并提炼成一段连贯的摘要，目标总长度不超过 {target_max_chars} 个字符。
    在压缩时，请务必优先保留与以下分析上下文最相关的信息：
    "分析上下文：{overall_module_context}"

    确保关键事实、数据、会计政策的精确描述或管理层的明确观点得到保留。

    待压缩的拼接文本内容如下：
    ---
    {text_to_compress} 
    --- 
    {target_max_chars}字符以内的压缩结果：
    """
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages) 
        compressed_text = response.content if hasattr(response, 'content') else str(response)
        log_event("INFO", f"文本已压缩，目标长度 {target_max_chars}，实际长度 {len(compressed_text)}。", "CompressSelectedText")
        return compressed_text
    except Exception as e:
        log_event("ERROR", f"压缩选定文本时出错: {e}", "CompressSelectedText")
        return f"压缩文本时出错: {e}. 原始文本片段(部分): {concatenated_text[:500]}..."
