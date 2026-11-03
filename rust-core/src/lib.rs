use wasm_bindgen::prelude::*;

/// CRC-32/ISO-HDLC checksum for a single transfer chunk.
/// Used by the browser to detect corrupted or mismatched chunks.
#[wasm_bindgen]
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc: u32 = 0xffff_ffff;
    for byte in data {
        crc ^= *byte as u32;
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

/// Return a conservative filename safe to use in a browser download.
#[wasm_bindgen]
pub fn safe_filename(input: &str) -> String {
    let cleaned: String = input
        .chars()
        .filter(|c| !c.is_control() && *c != '/' && *c != '\\')
        .take(180)
        .collect();
    if cleaned.trim().is_empty() { "file-ricevuto".to_string() } else { cleaned }
}
