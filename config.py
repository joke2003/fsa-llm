# config.py
# Stores global configurations, constants, and framework definitions for the financial analyzer.
# Part of Application Version 0.10.0

# --- Application Basic Configuration ---
APP_TITLE = "智能财务分析助手"
APP_ICON = "📈"
BASE_RESULT_DIR = "result" 
DEBUG_LOG_FILE_NAME = "debug.txt" 

# --- Text Processing & LLM Call Parameters ---
CHUNK_MAX_CHARS_FOR_OVERVIEW = 4000 # Max characters per chunk for overview generation by LLM
MAX_THREADS_FOR_OVERVIEW = 3      # Number of threads for parallel chunk overview generation
COMPRESSED_DOC_MAX_CHARS = 5000   # Target max characters for document snippets compressed by LLM before main analysis
# Max characters for full document text to be passed to sub-LLM in execute_get_relevant_document_content (if not using chunking for it)
MAX_INPUT_TEXT_LENGTH_FOR_TOOL_SUMMARIZER = 20000 
# Max length for the summary returned by execute_get_relevant_document_content's internal LLM
TOOL_SUMMARIZER_MAX_LENGTH = 1500 # Increased from 1000 to allow more detail if needed

# --- Analysis Framework Definitions ---
ANALYSIS_FRAMEWORK_SECTIONS = { 
    "战略定位、治理与行业环境": ["1.1 波特五力模型", "1.2 SWOT 分析", "1.4 公司治理与管理层素质评估", "1.5 财务报表结构与趋势分析"],
    "经营业绩与效率评估": ["2.1 综合比率分析", "2.2 杜邦分析", "2.3 分部信息分析", "2.4 Piotroski F-Score 模型"],
    "盈利质量与会计政策": ["3.1 财务报表附注深度解读与关键会计政策评估", "3.2 Beneish M-Score", "3.3 Dechow F-Score (理念)", "3.4 应计项目分析", "3.5 经营活动现金流量与净利润的比较分析"],
    "信用风险与破产预测": ["4.1 Altman Z-Score", "4.2 Ohlson O-Score (如适用)", "4.3 利息保障倍数及现金流偿债能力分析", "4.4 营运资金充足性与流动性分析"],
    "增长潜力与可持续性": ["5.1 可持续增长率模型 (SGR)", "5.2 内部增长率模型 (IGR)", "5.3 再投资率 (RR) 与投入资本回报率 (ROIC) 分析", "5.4 盈利与现金流增长匹配度分析"],
    "财务预测与建模": ["6.1 销售预测方法探讨", "6.2 成本与费用结构预测探讨", "6.3 资产负债表项目预测探讨", "6.4 三表联动模型构建提示", "6.5 情景分析与敏感性测试提示"],
    "公司估值": ["7.1 公司自由现金流模型 (FCFF)", "7.2 股权自由现金流模型 (FCFE)", "7.3 股利贴现模型 (DDM)", "7.4 剩余收益模型 (RIM)", "7.5 可比公司分析/市场乘数法", "7.6 基于账面价值的估值"]
}

MODULE_DEPENDENCIES = { 
    "1.2 SWOT 分析": ["1.1 波特五力模型"], 
    "1.5 财务报表结构与趋势分析": ["1.1 波特五力模型", "1.2 SWOT 分析", "1.4 公司治理与管理层素质评估"],
    "2.2 杜邦分析": ["2.1 综合比率分析"],
    "3.1 财务报表附注深度解读与关键会计政策评估": ["1.4 公司治理与管理层素质评估"],
    "3.3 Dechow F-Score (理念)": ["3.1 财务报表附注深度解读与关键会计政策评估", "3.2 Beneish M-Score", "3.4 应计项目分析"],
    "3.5 经营活动现金流量与净利润的比较分析": ["3.4 应计项目分析"],
    "4.1 Altman Z-Score": ["2.1 综合比率分析"],
    "4.2 Ohlson O-Score (如适用)": ["2.1 综合比率分析"],
    "4.3 利息保障倍数及现金流偿债能力分析": ["2.1 综合比率分析", "3.5 经营活动现金流量与净利润的比较分析"],
    "4.4 营运资金充足性与流动性分析": ["2.1 综合比率分析"],
    "5.1 可持续增长率模型 (SGR)": ["2.1 综合比率分析", "2.2 杜邦分析"],
    "5.2 内部增长率模型 (IGR)": ["2.1 综合比率分析"],
    "5.3 再投资率 (RR) 与投入资本回报率 (ROIC) 分析": ["2.1 综合比率分析", "6.2 成本与费用结构预测探讨"], 
    "5.4 盈利与现金流增长匹配度分析": ["2.1 综合比率分析", "3.5 经营活动现金流量与净利润的比较分析"],
    "6.1 销售预测方法探讨": ["1.2 SWOT 分析", "2.1 综合比率分析"], 
    "6.2 成本与费用结构预测探讨": ["6.1 销售预测方法探讨", "2.1 综合比率分析"],
    "6.3 资产负债表项目预测探讨": ["6.1 销售预测方法探讨", "6.2 成本与费用结构预测探讨", "2.1 综合比率分析", "4.4 营运资金充足性与流动性分析"],
    "6.4 三表联动模型构建提示": ["6.1 销售预测方法探讨", "6.2 成本与费用结构预测探讨", "6.3 资产负债表项目预测探讨"],
    "6.5 情景分析与敏感性测试提示": ["6.4 三表联动模型构建提示"],
    "7.1 公司自由现金流模型 (FCFF)": ["6.4 三表联动模型构建提示", "5.3 再投资率 (RR) 与投入资本回报率 (ROIC) 分析"], 
    "7.2 股权自由现金流模型 (FCFE)": ["6.4 三表联动模型构建提示"], 
    "7.3 股利贴现模型 (DDM)": ["6.4 三表联动模型构建提示"], 
    "7.4 剩余收益模型 (RIM)": ["6.4 三表联动模型构建提示"], 
    "7.5 可比公司分析/市场乘数法": ["1.1 波特五力模型", "1.2 SWOT 分析", "2.1 综合比率分析"],
    "7.6 基于账面价值的估值": ["1.5 财务报表结构与趋势分析", "3.1 财务报表附注深度解读与关键会计政策评估"]
}

ALL_DEFINED_MODULES_LIST = [mod for mods_in_sec in ANALYSIS_FRAMEWORK_SECTIONS.values() for mod in mods_in_sec]
TOTAL_MODULES_COUNT = len(ALL_DEFINED_MODULES_LIST)

# LLM Call parameters
MAX_TOOL_ITERATIONS = 7 # Max tool iterations if dynamic tool calling were still used (kept for reference or future use)

# Placeholder for prompts version, actual prompts are in prompts.py
PROMPTS_VERSION = "1.9.5" 
