# document_processing.py
# Contains functions for document preprocessing like chunking and overview generation.
# Part of Application Version 0.10.0+

import concurrent.futures
import re
from logger import log_event 
from llm_setup import get_llm_instance 
from config import CHUNK_MAX_CHARS_FOR_OVERVIEW, MAX_THREADS_FOR_OVERVIEW

def smart_chunk_document(text: str, doc_type: str, period_label: str, max_chars: int = CHUNK_MAX_CHARS_FOR_OVERVIEW) -> list:
    """
    Splits a long document text into smaller, more manageable chunks.
    Tries to split by common section or paragraph separators first, then by length.
    """
    chunks = []
    if not text or not text.strip():
        return chunks

    section_patterns = [
        r"\n\s*(附注\s*[一二三四五六七八九十零百千万亿\d零一二三四五六七八九十]+[、．\.])",
        r"\n\s*([（(][一二三四五六七八九十零百千万亿\d零一二三四五六七八九十]+[）)\.])", 
        r"\n\s*([一二三四五六七八九十零百千万亿\d零一二三四五六七八九十]+[、．\.])",    
        r"\n\s*(§\s*\d+(\.\d+)*)", 
        r"\n\n+" 
    ]
    
    split_points = [0]
    for pattern in section_patterns:
        for match in re.finditer(pattern, text):
            split_points.append(match.start())
    split_points.append(len(text))
    split_points = sorted(list(set(split_points))) 

    raw_sections = []
    for i in range(len(split_points) - 1):
        section_text = text[split_points[i]:split_points[i+1]].strip()
        if section_text:
            raw_sections.append(section_text)
    
    if not raw_sections: 
        raw_sections = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not raw_sections or (len(raw_sections) == 1 and len(raw_sections[0]) > max_chars * 2):
             raw_sections = [p.strip() for p in text.split('\n') if p.strip()]

    chunk_idx = 0
    for section_idx, section_content in enumerate(raw_sections):
        current_chunk_text = ""
        words = section_content.split() 
        temp_chunk = []
        current_len = 0
        for word in words:
            if current_len + len(word) + 1 > max_chars:
                if temp_chunk:
                    chunks.append({
                        "chunk_id": f"{doc_type}_{period_label.replace(' ', '_')}_{chunk_idx}",
                        "text": " ".join(temp_chunk)
                    })
                    chunk_idx += 1
                    temp_chunk = []
                    current_len = 0
                while len(word) > max_chars:
                    chunks.append({
                        "chunk_id": f"{doc_type}_{period_label.replace(' ', '_')}_{chunk_idx}",
                        "text": word[:max_chars]
                    })
                    word = word[max_chars:]
                    chunk_idx +=1
            temp_chunk.append(word)
            current_len += len(word) + 1
        
        if temp_chunk: 
            chunks.append({
                "chunk_id": f"{doc_type}_{period_label.replace(' ', '_')}_{chunk_idx}",
                "text": " ".join(temp_chunk)
            })
            chunk_idx += 1
            
    log_event("INFO", f"Document '{doc_type}' for '{period_label}' split into {len(chunks)} smart chunks.", "SmartChunking")
    return chunks

def generate_chunk_overview_llm(chunk_text: str, chunk_id: str) -> str:
    """Generates a ~1000 character overview for a given text chunk using LLM."""
    llm = get_llm_instance()
    if not llm: return "Error: LLM not available for chunk overview."
    
    prompt = f"""请为以下文本块生成一个简洁的概述，准确描述其核心内容，目标长度在1000个字符左右（大约300-350个汉字）。
    请确保概述能够抓住文本块最关键的信息点，以便后续基于此概述判断该文本块与特定分析上下文的相关性。
    文本块内容：
    ---
    {chunk_text[:CHUNK_MAX_CHARS_FOR_OVERVIEW + 1000]} 
    ---
    1000字符左右的概述：
    """ 
    try:
        messages = [{"role": "user", "content": prompt}]
        response = llm.invoke(messages) 
        overview = response.content if hasattr(response, 'content') else str(response)
        log_event("INFO", f"Generated overview for chunk {chunk_id}", "ChunkOverviewLLM", {"overview_length": len(overview)})
        return overview
    except Exception as e:
        log_event("ERROR", f"Error generating overview for chunk {chunk_id}: {e}", "ChunkOverviewLLM")
        return f"Error generating overview: {e}"

def preprocess_document_text(doc_text: str, doc_type: str, period_label: str) -> list:
    """Chunks document and generates overviews for each chunk using multithreading."""
    if not doc_text or not doc_text.strip():
        log_event("WARNING", f"Document text for {doc_type} of {period_label} is empty. Skipping preprocessing.", "PreprocessDocument")
        return []
    
    log_event("INFO", f"Starting preprocessing for {doc_type} of {period_label}.", "PreprocessDocument")
    chunks_with_text = smart_chunk_document(doc_text, doc_type, period_label, CHUNK_MAX_CHARS_FOR_OVERVIEW)
    if not chunks_with_text:
        log_event("WARNING", f"No chunks created for {doc_type} of {period_label}. Original text might be too short or empty after stripping.", "PreprocessDocument")
        return []
        
    processed_chunks = []
    futures_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS_FOR_OVERVIEW) as executor:
        for chunk in chunks_with_text:
            if chunk.get('text', '').strip():
                future = executor.submit(generate_chunk_overview_llm, chunk['text'], chunk['chunk_id'])
                futures_map[future] = chunk
            else:
                log_event("WARNING", f"Skipping empty chunk {chunk.get('chunk_id', 'N/A')} during overview generation.", "PreprocessDocument")
                processed_chunks.append({
                    "chunk_id": chunk.get('chunk_id', f"empty_chunk_{doc_type}_{period_label}"),
                    "original_text": "",
                    "overview_text": "文本块为空，无法生成概述。"
                })

        for future in concurrent.futures.as_completed(futures_map):
            chunk_data = futures_map[future]
            try:
                overview = future.result()
                processed_chunks.append({
                    "chunk_id": chunk_data['chunk_id'],
                    "original_text": chunk_data['text'],
                    "overview_text": overview
                })
            except Exception as exc:
                log_event("ERROR", f"Chunk {chunk_data['chunk_id']} overview generation failed: {exc}", "PreprocessDocument")
                processed_chunks.append({
                    "chunk_id": chunk_data['chunk_id'],
                    "original_text": chunk_data['text'],
                    "overview_text": "为此文本块生成概述时出错。"
                })
    log_event("INFO", f"Finished preprocessing {len(processed_chunks)} chunks for {doc_type} of {period_label}.", "PreprocessDocument")
    return processed_chunks
