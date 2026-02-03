import cf from 'cloudfront';

const kvsId = '${ReverseHeadersKeyValueStore}';

async function handler(event) {
  const response = event.response;
  const request = event.request;
  // CloudFront always provides normalized URIs with leading slash, but ensure it
  let path = request.uri;
  if (!path.startsWith('/')) {
    path = '/' + path;
  }

  // Build hierarchical path list: /, /one/, /one/two/, /one/two/three.txt
  const parts = path.split('/').filter(p => p);
  const paths = ['/'];

  // Add each parent directory with trailing slash
  for (let i = 0; i < parts.length - 1; i++) {
    paths.push('/' + parts.slice(0, i + 1).join('/') + '/');
  }

  // Add the full path as-is (unless it's just /)
  if (path !== '/') {
    paths.push(path);
  }

  // Collect headers from all paths in order (parent to child)
  const kvs = cf.kvs(kvsId);
  const headers = {};

  for (let i = 0; i < paths.length; i++) {
    const lookupPath = paths[i];
    try {
      const value = await kvs.get(lookupPath);
      if (value) {
        // Parse line-delimited headers: "Header-Name: value"
        const lines = value.split('\n');
        for (let j = 0; j < lines.length; j++) {
          const line = lines[j];
          const trimmed = line.trim();
          if (trimmed && trimmed.includes(':')) {
            const colonIndex = trimmed.indexOf(':');
            const headerName = trimmed.substring(0, colonIndex).trim().toLowerCase();
            const headerValue = trimmed.substring(colonIndex + 1).trim();
            if (headerName) {
              headers[headerName] = { value: headerValue };
            }
          }
        }
      }
    } catch (err) {
      // Key not found, continue
    }
  }

  // Handle special pattern for path-based headers with $1 substitution
  try {
    const patternValue = await kvs.get('**/*');
    if (patternValue) {
      const lines = patternValue.split('\n');
      for (let j = 0; j < lines.length; j++) {
        const line = lines[j];
        const trimmed = line.trim();
        if (trimmed && trimmed.includes(':')) {
          const colonIndex = trimmed.indexOf(':');
          const headerName = trimmed.substring(0, colonIndex).trim().toLowerCase();
          let headerValue = trimmed.substring(colonIndex + 1).trim();
          // Replace {/path} with the request path (always has leading /)
          headerValue = headerValue.replace('{/path}', path);
          if (headerName) {
            headers[headerName] = { value: headerValue };
          }
        }
      }
    }
  } catch (err) {
    // Pattern not found, continue
  }

  // Apply headers to response
  response.headers = response.headers || {};
  const headerKeys = Object.keys(headers);
  for (let i = 0; i < headerKeys.length; i++) {
    const name = headerKeys[i];
    response.headers[name] = headers[name];
  }

  return response;
}
