/** Retire émojis / pictogrammes (texte assistant, QCM). */

const EMOJI_RE =
  /[\u{1F300}-\u{1FAFF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}]+/gu;

export function stripEmojis(text: string): string {
  if (!text) return text;
  return text.replace(EMOJI_RE, "").replace(/\s{2,}/g, " ").trim();
}
