import cf from 'cloudfront';

const kvsId = '${ObverseHeadersKeyValueStore}';

async function handler(event) {
  var response = event.response;
  var request = event.request;
  var path = '';

  // Initialize headers object first
  response.headers = response.headers || {};
  response.headers['x-micahrl-debug-headers-will-inject'] = { value: "im-doing-my-best" };

  try {
    // throw new Error("Test error to verify debug header is added and contains message");

    // CloudFront always provides normalized URIs with leading slash
    path = request.uri;
    if (path.charAt(0) !== '/') {
      path = '/' + path;
    }

    // Build list of patterns to check in order of specificity (least to most)
    // For /blog/post/file.html, we check: /, /blog/, /blog/post/, *.html, /blog/post/file.html
    var patterns = [];

    // 1. Root path (always check)
    patterns.push('/');

    // 2. Each parent directory with trailing /
    var parts = path.split('/').filter(function(p) { return p; });
    for (var i = 0; i < parts.length - 1; i++) {
      patterns.push('/' + parts.slice(0, i + 1).join('/') + '/');
    }

    // 3. Extension wildcard (e.g., *.xml, *.html)
    var lastSegment = parts[parts.length - 1] || '';
    var lastDotIndex = lastSegment.lastIndexOf('.');
    if (lastDotIndex !== -1 && lastDotIndex < lastSegment.length - 1) {
      var ext = lastSegment.substring(lastDotIndex + 1);
      patterns.push('*.' + ext);
    }

    // 4. Exact path (most specific)
    if (path !== '/') {
      patterns.push(path);
    }

    response.headers['x-micahrl-debug-patterns'] = { value: patterns.join(',') };

    // Collect headers from all matching patterns
    var kvs = cf.kvs(kvsId);
    var headers = {};
    var parsedPatternIdxes = [];

    // TODO: don't use patternId, use pattern index number, bc we list the patterns in x-micahrl-debug-patterns header.

    for (var i = 0; i < patterns.length; i++) {
      var pattern = patterns[i];
      var patternId = pattern.replace(/[^a-zA-Z0-9]/g, '_');
      try {
        var value = await kvs.get(pattern);
        if (value) {
          // Parse line-delimited headers: "header-name: value\nheader-name: value"
          var lines = value.split('\n');
          for (var j = 0; j < lines.length; j++) {
            var line = lines[j].trim();
            if (line && line.indexOf(':') !== -1) {
              var colonIndex = line.indexOf(':');
              var headerName = line.substring(0, colonIndex).trim().toLowerCase();
              var headerValue = line.substring(colonIndex + 1).trim();
              // Replace {/path} with the request path
              headerValue = headerValue.replace('{/path}', path);
              if (headerName) {
                headers[headerName] = { value: headerValue };
              }
            }
          }
        }
        parsedPatternIdxes.push(i);
        // response.headers['x-micahrl-debug-pattern-value-' + patternId] = { value: value || '' };
      } catch (err) {
        // Key not found or parse error, continue
        var errMsg = 'error';
        if (err && err.message) {
          errMsg = err.message;
        } else if (err) {
          errMsg = String(err);
        }
        // response.headers['x-micahrl-debug-pattern-error-' + patternId] = { value: errMsg.substring(0, 100) };
      }
    }

    var pasredPatternIdxesStr = parsedPatternIdxes.map(function(idx) { return patterns[idx]; }).join(',');
    response.headers['x-micahrl-debug-patterns-parsed'] = { value: pasredPatternIdxesStr };

    // Apply headers to response
    var headerKeys = Object.keys(headers);
    for (var i = 0; i < headerKeys.length; i++) {
      var name = headerKeys[i];
      response.headers[name] = headers[name];
    }

    response.headers['x-micahrl-debug-headers-injected'] = { value: "yes-goddammit" };

    return response;

  } catch (err) {
    // Critical error - add debug header and return response unchanged
    var debugMsg = '';
    if (err && err.message) {
      debugMsg = err.message;
    } else if (err) {
      debugMsg = String(err);
    } else {
      debugMsg = "some idiot threw null/undefined"
    }
    // Limit length and sanitize
    debugMsg = debugMsg.substring(0, 200).replace(/[\r\n]+/g, ' ');
    response.headers['x-micahrl-debug'] = { value: debugMsg };
    return response;
  }
}
