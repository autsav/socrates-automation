const STOPWORDS = new Set([
  "the", "a", "an", "of", "to", "is", "in", "and", "it", "you", "i",
]);

/** Strip everything but letters/numbers and lowercase, for classification. */
function clean(word: string): string {
  return word.replace(/[^\p{L}\p{N}]/gu, "").toLowerCase();
}

/**
 * Choose the word to emphasize in a quote:
 *  1. the last content word (has letters/numbers, not a stopword), else
 *  2. the longest content word, else
 *  3. the last word (index length-1), or 0 for empty input.
 */
export function pickEmphasisIndex(words: string[]): number {
  if (words.length === 0) return 0;

  for (let i = words.length - 1; i >= 0; i--) {
    const c = clean(words[i]);
    if (c && !STOPWORDS.has(c)) return i;
  }

  let best = -1;
  let bestLen = 0;
  for (let i = 0; i < words.length; i++) {
    const c = clean(words[i]);
    if (c.length > bestLen) {
      bestLen = c.length;
      best = i;
    }
  }
  return best >= 0 ? best : words.length - 1;
}
