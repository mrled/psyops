// NOTE: THIS FILE EXPECTS const kvsId = 'something'; TO BE DEFINED IN THE CFN TEMPLATE THAT USES IT

import cf from 'cloudfront';

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

  // If we found a different path through KVS, return a 301 redirect
  if (lookupUri !== uri) {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        'location': { value: lookupUri }
      }
    };
  }

  // Append index.html to trailing slashes
  if (request.uri.endsWith('/')) {
    request.uri += 'index.html';
  }

  return request;
}
