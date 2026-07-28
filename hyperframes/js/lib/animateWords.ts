export interface WordTime {
  w: string;
  start: number;
  end: number;
  cls?: string;
}

/** Split text into word spans inside `container`, then add GSAP tweens to `tl`
 *  at absolute times `offset + word.start`. */
export function animateWords(
  tl: gsap.core.Timeline,
  container: HTMLElement,
  words: WordTime[],
  offsetSec: number,
): void {
  if (!words || words.length === 0) {
    // No word times: simple fade-in of the whole container text
    tl.fromTo(
      container,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" },
      offsetSec,
    );
    return;
  }

  // Wrap each word in a span
  const html = words
    .map((w, i) => `<span class="word-span" id="word-${i}">${escapeHtml(w.w)}</span>`)
    .join(" ");
  container.innerHTML = html;

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    tl.fromTo(
      `#word-${i}`,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: Math.min(0.4, w.end - w.start), ease: "power3.out" },
      offsetSec + w.start,
    );
  }
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
