import cf from 'cloudfront';

const kvsId = '${ReverseHeadersKeyValueStore}';

async function handler(event) {
  const response = event.response;
  const request = event.request;
  const path = request.uri;

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

  for (const lookupPath of paths) {
    try {
      const value = await kvs.get(lookupPath);
      if (value) {
        // Parse line-delimited headers: "Header-Name: value"
        const lines = value.split('\n');
        for (const line of lines) {
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
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed && trimmed.includes(':')) {
          const colonIndex = trimmed.indexOf(':');
          const headerName = trimmed.substring(0, colonIndex).trim().toLowerCase();
          let headerValue = trimmed.substring(colonIndex + 1).trim();
          // Replace $1 with the request path
          headerValue = headerValue.replace('$1', path);
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
  for (const [name, header] of Object.entries(headers)) {
    response.headers[name] = header;
  }

  return response;
}
