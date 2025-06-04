# reporting.py
# Contains functions for generating the final HTML analysis report.
# Part of Application Version 0.10.0

import streamlit as st # For st.session_state access
import os
import json
from logger import log_event
from config import ANALYSIS_FRAMEWORK_SECTIONS # To get section structure

def generate_and_save_html_report():
    """
    Generates a comprehensive HTML report from the CWP and saves it to the run result directory.
    """
    if not st.session_state.get('current_run_result_dir'):
        log_event("ERROR", "无法生成HTML报告：当前运行结果目录未设置。", "ReportGeneration")
        if hasattr(st, 'sidebar') and hasattr(st.sidebar, 'error'):
            st.sidebar.error("错误：无法生成HTML报告，运行结果目录未设置。")
        return

    report_file_path = os.path.join(st.session_state.current_run_result_dir, "analysis_report.html")
    log_event("INFO", f"开始生成HTML分析报告: {report_file_path}", module_name="ReportGeneration")

    cwp = st.session_state.cwp
    company_info = cwp['base_data']['company_info']
    
    # Helper to safely get and format text for HTML
    def format_html_text(text_content, default_text="无内容。"):
        if text_content and isinstance(text_content, str):
            return text_content.replace('\n', "<br>") # Basic newline to <br>
        return default_text

    html_content = f"""
    <!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>财务分析报告 - {company_info.get('name', 'N/A')}</title>
    <style> 
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; color: #333; }} 
        h1, h2, h3, h4 {{ color: #2c3e50; }} 
        h1 {{ border-bottom: 2px solid #3498db; padding-bottom: 10px; }} 
        h2 {{ border-bottom: 1px solid #ecf0f1; padding-bottom: 5px; margin-top: 30px; }} 
        .module-output, .integrated-insight-section {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .prompt, .message-history {{ background-color: #eef; padding: 10px; border-radius: 4px; margin-top: 10px; white-space: pre-wrap; font-family: monospace; font-size: 0.9em; border: 1px dashed #ccc; }} 
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 15px; font-size: 0.9em; }} 
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }} 
        th {{ background-color: #f2f2f2; font-weight: bold; }} 
        .contradiction {{ background-color: #ffebee; border: 1px solid #e57373; padding: 10px; margin-bottom:10px; border-radius: 4px;}} 
        .risk-item {{ background-color: #fff3e0; border-left: 5px solid #ff9800; padding:10px; margin-bottom:10px; }}
        .opportunity-item {{ background-color: #e8f5e9; border-left: 5px solid #4caf50; padding:10px; margin-bottom:10px; }}
        details > summary {{ cursor: pointer; font-weight: bold; margin-bottom: 5px; }}
    </style></head><body>
    <h1>财务分析报告</h1><p><strong>公司名称:</strong> {company_info.get('name', 'N/A')}</p>
    <p><strong>所属行业:</strong> {company_info.get('industry', 'N/A')}</p>
    <p><strong>股票代码:</strong> {company_info.get('stock_code', 'N/A')}</p>
    <p><strong>分析角度:</strong> {company_info.get('analysis_perspective', '未指定')}</p>
    <p><strong>分析日期:</strong> {cwp['metadata_version_control'].get('analysis_timestamp', 'N/A')}</p>
    
    <div class='integrated-insight-section'><h2>最终总体财务分析摘要</h2><div>{format_html_text(cwp['integrated_insights'].get('overall_summary'), '无摘要信息。')}</div></div>
    <div class='integrated-insight-section'><h2>迭代形成的（当前）公司总体财务分析结论</h2><div>{format_html_text(cwp['integrated_insights'].get('current_overall_financial_conclusion'), '无迭代结论。')}</div></div>
    <div class='integrated-insight-section'><h2>用户提供的宏观经济分析结论</h2><div>{format_html_text(company_info.get('macro_analysis_conclusion_text'), '未提供')}</div></div>
    <div class='integrated-insight-section'><h2>系统生成的行业分析结论</h2><div>{format_html_text(company_info.get('industry_analysis_conclusion_text'), '未生成')}</div></div>
    """
    
    if cwp['integrated_insights'].get('key_risks'):
        html_content += "<div class='integrated-insight-section'><h2>主要风险点</h2>"
        for idx, risk in enumerate(cwp['integrated_insights']['key_risks']):
            html_content += f"<div class='risk-item'><p><strong>风险 {idx+1} (ID: {risk.get('id', 'N/A')}):</strong> {format_html_text(risk.get('description', 'N/A'))}</p>"
            html_content += f"<p><strong>分类:</strong> {risk.get('category', 'N/A')} | <strong>潜在影响:</strong> {risk.get('potential_impact', 'N/A')}</p>"
            if risk.get('source_modules'): html_content += f"<p><strong>来源模块:</strong> {', '.join(risk['source_modules'])}</p>"
            if risk.get('mitigating_factors_observed'): html_content += f"<p><strong>缓解因素:</strong> {format_html_text(risk['mitigating_factors_observed'])}</p>"
            if risk.get('notes_for_further_investigation'): html_content += f"<p><strong>进一步调查:</strong> {format_html_text(risk['notes_for_further_investigation'])}</p>"
            html_content += "</div>"
        html_content += "</div>"

    if cwp['integrated_insights'].get('key_opportunities'):
        html_content += "<div class='integrated-insight-section'><h2>主要机遇点</h2>"
        for idx, opp in enumerate(cwp['integrated_insights']['key_opportunities']):
            html_content += f"<div class='opportunity-item'><p><strong>机遇 {idx+1} (ID: {opp.get('id', 'N/A')}):</strong> {format_html_text(opp.get('description', 'N/A'))}</p>"
            html_content += f"<p><strong>分类:</strong> {opp.get('category', 'N/A')} | <strong>潜在收益:</strong> {opp.get('potential_benefit', 'N/A')}</p>"
            if opp.get('source_modules'): html_content += f"<p><strong>来源模块:</strong> {', '.join(opp['source_modules'])}</p>"
            if opp.get('actionability_notes'): html_content += f"<p><strong>行动建议/关注点:</strong> {format_html_text(opp['actionability_notes'])}</p>"
            html_content += "</div>"
        html_content += "</div>"

    if cwp['integrated_insights'].get('contradiction_logbook'):
        html_content += "<div class='integrated-insight-section'><h2>矛盾点记录本</h2>"
        for idx, item in enumerate(cwp['integrated_insights']['contradiction_logbook']):
            html_content += f"<div class='contradiction'>"
            html_content += f"<p><strong>矛盾点 {idx+1} (记录时间: {item['timestamp']})</strong></p>"
            html_content += f"<p><strong>引发模块:</strong> {item['module_name']} (置信度: {item['module_confidence']})</p>"
            html_content += f"<p><strong>矛盾描述:</strong> {format_html_text(item['contradiction_description'])}</p>"
            html_content += f"<details><summary>查看相关结论片段</summary>"
            html_content += f"<p><strong>模块结论片段:</strong><pre>{item['module_finding_snippet'].replace('<', '&lt;').replace('>', '&gt;')}</pre></p>"
            html_content += f"<p><strong>前期总体结论片段:</strong><pre>{item['previous_overall_conclusion_snippet'].replace('<', '&lt;').replace('>', '&gt;')}</pre></p>"
            html_content += f"</details></div>"
        html_content += "</div>"

    html_content += "<h2>详细分析模块</h2>"
    sections_for_html = st.session_state.cwp['metadata_version_control'].get('ai_planned_sections_for_display', ANALYSIS_FRAMEWORK_SECTIONS)
    
    for section_title, modules_in_section in sections_for_html.items():
        html_content += f"<h3>{section_title}</h3>"
        for module_name in modules_in_section:
            output_data = cwp['analytical_module_outputs'].get(module_name, {})
            if not output_data: continue 

            text_summary_html = format_html_text(output_data.get('text_summary'), '无文本摘要。')
            confidence_html = f"<p><strong>置信度:</strong> {output_data.get('confidence_score', 'N/A')}</p>"
            abbreviated_summary_html = output_data.get('abbreviated_summary', '')
            if abbreviated_summary_html:
                abbreviated_summary_html = f"<p><strong>缩略摘要:</strong><br>{format_html_text(abbreviated_summary_html)}</p>" 

            prompt_used_html = output_data.get('prompt_used', '').replace('<', '&lt;').replace('>', '&gt;')
            message_history_html = ""
            if output_data.get('message_history'):
                try: message_history_html = json.dumps(output_data['message_history'], indent=2, ensure_ascii=False).replace('<', '&lt;').replace('>', '&gt;')
                except: message_history_html = "交互历史无法序列化"
            html_content += f"<div class='module-output'><h4>{module_name}</h4><p><strong>状态:</strong> {output_data.get('status', 'N/A')} | <strong>时间:</strong> {output_data.get('timestamp', 'N/A')}</p>{confidence_html}<div><strong>分析结果:</strong><br>{text_summary_html}</div>{abbreviated_summary_html}"
            if output_data.get('prompt_used'): html_content += f"<details><summary>显示/隐藏使用的提示</summary><div class='prompt'><pre>{prompt_used_html}</pre></div></details>"
            if output_data.get('message_history'): html_content += f"<details><summary>显示/隐藏交互历史</summary><div class='message-history'><pre>{message_history_html}</pre></div></details>"
            html_content += "</div>"
            
    html_content += "<h2>核心底稿快照 (部分)</h2><h3>公司基本信息:</h3>"
    html_content += f"<pre>{json.dumps(cwp['base_data']['company_info'], indent=2, ensure_ascii=False)}</pre>"
    html_content += "<h3>财务报告期概览:</h3>"
    for report in cwp['base_data']['financial_reports']:
        html_content += f"<p><strong>{report['period_label']}:</strong> "; docs = [];
        if report.get('has_bs'): docs.append("资产负债表")
        if report.get('has_is'): docs.append("利润表")
        if report.get('has_cfs'): docs.append("现金流量表")
        if report.get('footnotes_processed_chunks'): docs.append(f"附注 (共 {len(report.get('footnotes_processed_chunks',[]))} 块)") 
        if report.get('mda_processed_chunks'): docs.append(f"MD&A (共 {len(report.get('mda_processed_chunks',[]))} 块)") 
        html_content += f"{', '.join(docs) if docs else '无核心文件或未处理'}</p>"
        
        if report.get("footnotes_processed_chunks"):
            html_content += f"<details><summary>{report['period_label']} 附注分块概述</summary>"
            for chunk_data in report["footnotes_processed_chunks"]:
                html_content += f"<p><strong>块ID: {chunk_data.get('chunk_id','N/A')} 概述:</strong> {format_html_text(chunk_data.get('overview_text','N/A'))[:200]}...</p>"
            html_content += "</details>"
        if report.get("mda_processed_chunks"):
            html_content += f"<details><summary>{report['period_label']} MD&A分块概述</summary>"
            for chunk_data in report["mda_processed_chunks"]:
                 html_content += f"<p><strong>块ID: {chunk_data.get('chunk_id','N/A')} 概述:</strong> {format_html_text(chunk_data.get('overview_text','N/A'))[:200]}...</p>"
            html_content += "</details>"
            
    html_content += "</body></html>"
    try:
        with open(report_file_path, "w", encoding="utf-8") as f: f.write(html_content)
        log_event("INFO", f"HTML分析报告已成功保存至: {report_file_path}", module_name="ReportGeneration")
        if hasattr(st, 'sidebar') and hasattr(st.sidebar, 'success'):
            st.sidebar.success(f"分析报告已保存至 {report_file_path}")
    except Exception as e:
        log_event("ERROR", f"保存HTML分析报告失败: {e}", module_name="ReportGeneration")
        if hasattr(st, 'sidebar') and hasattr(st.sidebar, 'error'):
            st.sidebar.error(f"保存HTML报告失败: {e}")

