// Reflow source text into bullets without rewriting or dropping its claims.
const sentences = new Intl.Segmenter('ro', { granularity: 'sentence' });

export function sentencePoints(text: string): string[] {
  return [...sentences.segment(text)].map((part) => part.segment.trim()).filter(Boolean);
}
