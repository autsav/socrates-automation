export interface WordTime {
  w: string;
  start: number;
  end: number;
  cls?: string;
}

/** Index of the word active at `sceneSeconds` (seconds from scene start); the
 *  last-started word after it ends; -1 before the first word or when empty. */
export function wordAt(sceneSeconds: number, words: WordTime[]): number {
  let idx = -1;
  for (let i = 0; i < words.length; i++) {
    if (sceneSeconds >= words[i].start) idx = i;
    else break;
  }
  return idx;
}
