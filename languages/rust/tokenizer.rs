// tokenizer.rs — Fast token counting + text chunking in Rust
// ใช้ใน RAG pipeline เพื่อ chunk เร็วๆ โดยไม่ต้องโหลด Python
//
// ไม่ใช้ crate ภายนอก ใช้เฉพาะ std (ถ้าต้องการนับ token แม่นยำให้เพิ่ม tiktoken-rs เอง)
//
// รัน: rustc --edition 2021 tokenizer.rs && ./tokenizer   (Windows: tokenizer.exe)

use std::collections::HashMap;

/// นับ tokens โดยประมาณ (ไม่ต้อง tiktoken — ใช้ word-based estimate)
/// rule of thumb: 1 token ≈ 0.75 words (English), ≈ 1–2 chars (Thai)
pub fn estimate_tokens(text: &str) -> usize {
    let words: Vec<&str> = text.split_whitespace().collect();
    let word_count = words.len();
    // Thai/CJK characters นับหนักกว่า
    let char_count = text.chars().count();
    let thai_chars = text.chars().filter(|c| ('\u{0E00}'..='\u{0E7F}').contains(c)).count();

    if thai_chars > word_count {
        // ข้อความไทย: ~1 token ต่อ 1.5 ตัวอักษร
        (char_count * 2 / 3).max(1)
    } else {
        // ข้อความอังกฤษ: ~1 token ต่อ 0.75 คำ
        (word_count * 4 / 3).max(1)
    }
}

/// แบ่ง text เป็น chunks ตาม token limit
pub fn chunk_by_tokens(text: &str, max_tokens: usize, overlap_tokens: usize) -> Vec<String> {
    let sentences: Vec<&str> = text.split(". ").collect();
    let mut chunks: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut current_tokens = 0;

    for sentence in &sentences {
        let s_tokens = estimate_tokens(sentence);

        if current_tokens + s_tokens > max_tokens && !current.is_empty() {
            chunks.push(current.trim().to_string());
            // overlap: เก็บ sentence สุดท้ายไว้ใน chunk ถัดไป
            let words: Vec<&str> = current.split_whitespace().collect();
            let overlap_words = overlap_tokens.min(words.len());
            current = words[words.len() - overlap_words..].join(" ");
            current_tokens = estimate_tokens(&current);
        }

        if !current.is_empty() {
            current.push_str(". ");
        }
        current.push_str(sentence);
        current_tokens += s_tokens;
    }

    if !current.trim().is_empty() {
        chunks.push(current.trim().to_string());
    }

    chunks
}

/// วิเคราะห์ vocabulary ของ text
pub fn vocab_stats(text: &str) -> HashMap<String, usize> {
    let mut freq: HashMap<String, usize> = HashMap::new();
    for word in text.split_whitespace() {
        let clean: String = word.chars()
            .filter(|c| c.is_alphanumeric())
            .collect::<String>()
            .to_lowercase();
        if clean.len() > 2 {
            *freq.entry(clean).or_insert(0) += 1;
        }
    }
    freq
}

fn main() {
    let sample = "Retrieval-Augmented Generation combines the power of large language models \
                  with external knowledge retrieval. The system embeds documents into vectors. \
                  When a query arrives, it finds the most similar documents and injects them \
                  as context before generating a response. This approach reduces hallucination.";

    println!("=== Rust Tokenizer Demo ===\n");
    println!("text ({} chars):", sample.len());
    println!("{}\n", &sample[..80]);

    println!("estimated tokens: {}", estimate_tokens(sample));

    let chunks = chunk_by_tokens(sample, 30, 5);
    println!("\nchunks (max 30 tokens, overlap 5):");
    for (i, chunk) in chunks.iter().enumerate() {
        println!("  [{}] ~{} tokens: {}...", i + 1, estimate_tokens(chunk), &chunk[..chunk.len().min(50)]);
    }

    let stats = vocab_stats(sample);
    let mut sorted: Vec<(&String, &usize)> = stats.iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(a.1));
    println!("\ntop words:");
    for (word, count) in sorted.iter().take(5) {
        println!("  {}: {}", word, count);
    }
}
