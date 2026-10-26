/* MPL-2.0. Read-only responses from the fixed IP lookup endpoints. */
export class CloakfoxIPProbeChild extends JSWindowActorChild {
  receiveMessage(message) {
    if (message.name !== 'ReadIPResponse') throw new Error('Unknown IP probe query');
    const doc = this.document;
    const url = new URL(doc.documentURI);
    const allowed = url.protocol === 'https:' && !url.username && !url.password &&
      ((['api.ipify.org','api6.ipify.org','api64.ipify.org'].includes(url.hostname) && url.pathname === '/') ||
       (url.hostname === 'httpbin.org' && url.pathname === '/ip'));
    if (!allowed || this.browsingContext.parent) throw new Error('Not an IP lookup document');
    // Firefox's JSON viewer keeps the original response in a Text node.
    const rawJSON = doc.defaultView.wrappedJSObject.JSONView?.json?.data;
    const body = typeof rawJSON === 'string' ? rawJSON : doc.body?.textContent || '';
    if (!body || body.length > 4096) throw new Error('Invalid IP response');
    return {url:doc.documentURI, body};
  }
}
