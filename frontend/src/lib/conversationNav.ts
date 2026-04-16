/** Paramètre d’URL pour ouvrir une conversation (nouvel onglet, lien partageable). */
export const CONV_SEARCH_PARAM = "conv";

/** Type MIME pour le glisser-déposer des conversations vers les projets. */
export const MONV_CONV_DRAG_TYPE = "application/x-monv-conversation-id";

export function conversationUrl(conversationId: string): string {
  const q = new URLSearchParams();
  q.set(CONV_SEARCH_PARAM, conversationId);
  return `/?${q.toString()}`;
}

export function readConversationIdFromDataTransfer(
  dt: DataTransfer
): string | null {
  const fromMime = dt.getData(MONV_CONV_DRAG_TYPE);
  if (fromMime) return fromMime;
  const plain = dt.getData("text/plain").trim();
  if (plain && /^[\da-f-]{36}$/i.test(plain)) return plain;
  return null;
}
