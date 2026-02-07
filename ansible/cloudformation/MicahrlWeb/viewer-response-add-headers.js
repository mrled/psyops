// NOTE: THIS FILE EXPECTS const kvsId = 'something'; TO BE DEFINED IN THE CFN TEMPLATE THAT USES IT

import cf from 'cloudfront';

// Max headers for entire request is 8KB
// We have to leave room for CloudFront and S3 headers too: 2-3KB
// We also don't keep track of our debug headers: keep them less than 1KB
const headerSizeLimitBytes = 4096;

async function handler(event) {
  var response = event.response;
  var request = event.request;
  var path = '';

  // Initialize headers object first
  response.headers = response.headers || {};

  try {
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

    var patternList = patterns.join(',');
    response.headers['x-mrldbg-patterns'] = { value: patternList.length > 200 ? patternList.substring(0, 200) + '...' : patternList };

    // Collect headers from all matching patterns
    var kvs = cf.kvs(kvsId);
    var headers = {};
    var matchedPatternIdxes = [];
    var totalAddedBytes = 0;
    var truncated = false;

    for (var i = 0; i < patterns.length; i++) {
      var pattern = patterns[i];
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
                // Estimate header size (name + value + overhead)
                var headerSize = headerName.length + headerValue.length + 4;
                if (totalAddedBytes + headerSize > headerSizeLimitBytes) {
                  truncated = true;
                  break; // Stop adding headers
                }
                headers[headerName] = { value: headerValue };
                totalAddedBytes += headerSize;
              }
            }
          }
          if (truncated) {
            break; // Stop processing patterns
          }
        }
        matchedPatternIdxes.push(i);
      } catch (err) {
        // Key not found or parse error, continue
        var errMsg = 'error';
        if (err && err.message) {
          errMsg = err.message;
        } else if (err) {
          errMsg = String(err);
        }
      }
    }

    var matchedList = matchedPatternIdxes.join(",");
    response.headers['x-mrldbg-matchedpatterns'] = { value: matchedList.length > 200 ? matchedList.substring(0, 200) + '...' : matchedList };
    response.headers['x-mrldbg-size'] = { value: String(totalAddedBytes) };
    if (truncated) {
      response.headers['x-mrldbg-truncated'] = { value: 'yes' };
    }

    // Apply headers to response
    var headerKeys = Object.keys(headers);
    for (var i = 0; i < headerKeys.length; i++) {
      var name = headerKeys[i];
      response.headers[name] = headers[name];
    }

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
    response.headers['x-mrldbg'] = { value: debugMsg };
    return response;
  }
}
