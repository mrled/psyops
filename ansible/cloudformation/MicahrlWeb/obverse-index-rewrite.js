import cf from 'cloudfront';

const kvsId = '${ObverseKeyValueStore}';

async function handler(event) {
  const request = event.request;
  const uri = request.uri;

  // Try KVS lookup with recursion protection
  const kvs = cf.kvs(kvsId);
  let lookupUri = uri;
  const maxRedirects = 10;
  let redirectCount = 0;

  while (redirectCount < maxRedirects) {
    try {
      const value = await kvs.get(lookupUri);
      if (value) {
        lookupUri = value;
        redirectCount++;
      } else {
        break;
      }
    } catch (err) {
      // Key not found or other error, break out
      break;
    }
  }

  // If we found a different path through KVS, use it
  if (lookupUri !== uri) {
    request.uri = lookupUri;
  }
  // Otherwise fall back to index.html normalization for trailing slashes
  else if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }

  return request;
}
