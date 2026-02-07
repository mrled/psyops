# MicahrlWeb Stack Management

The stack for deploying <https://me.micahrl.com> and <https://com.micahrl.me> to AWS.

## TODO

- Consider moving to CDK
  - The CFN stack was exceeding 1kloc which was unwieldy, so we split it up with Jinja2 includes that Ansible manages.
    I don't love doing this, and maybe it should be CDK instead.

## CloudFront Function JavaScript

**CloudFront Function code must be written in a restricted JavaScript runtime**
called `cloudfront-js-2.0`.
In general, use ES5 syntax, and make sure the functions execute in 1ms or less and contain less than 10KB of code.

- See [AWS docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/functions-javascript-runtime-20.html)
  for specific language features.
  "The CloudFront Functions JavaScript runtime environment is compliant with ECMAScript (ES) version 5.1 and also supports some features of ES versions 6 through 12. It also provides some nonstandard methods that are not part of the ES specifications."
- There are very serious limits that will cause 500 errors with no logging at all
  - Total execution time <= 1ms
  - Total function size <= 10KB
  - Viewer Response:
    - Total response size (of headers -- not counting what is retrieved from S3) <= 8KB
    - Total header count <= 70
    - Individual header size (name + value) <= 1783B


## Deployment Commands

Create a deployment user with access keys:

```bash
# Create a user, add to the deployer group, and create access keys (will only be displayed once)
aws iam create-user --user-name github-micahrl-obverse-reverse-deployer
aws iam add-user-to-group --user-name github-micahrl-obverse-reverse-deployer --group-name <DeployerGroupName>
aws iam create-access-key --user-name github-micahrl-obverse-reverse-deployer

# Use hugo to deploy the site
hugo deploy --invalidateCDN ...
```

## Athena Query Examples

Query in AWS Console: Athena → Query Editor → Select workgroup from stack outputs

```sql
# Top 10 pages by requests (with actual domain)
SELECT host_header, uri_stem, COUNT(*) as requests
FROM <DatabaseName>.cloudfront_access_logs
GROUP BY host_header, uri_stem
ORDER BY requests DESC
LIMIT 10;

# Top 10 paths across all domains
SELECT uri_stem, COUNT(*) as requests
FROM <DatabaseName>.cloudfront_access_logs
GROUP BY uri_stem
ORDER BY requests DESC
LIMIT 10;

# 404 errors
SELECT host_header, uri_stem, COUNT(*) as count
FROM <DatabaseName>.cloudfront_access_logs
WHERE status_code = 404
GROUP BY host_header, uri_stem
ORDER BY count DESC;

# Traffic by status code
SELECT status_code, COUNT(*) as requests
FROM <DatabaseName>.cloudfront_access_logs
GROUP BY status_code
ORDER BY requests DESC;
```

## KeyValueStore Management - Redirects

```bash
# List all KeyValueStores
aws cloudfront list-key-value-stores

# List all keys in the obverse KVS
aws cloudfront-keyvaluestore list-keys --kvs-arn <ObverseKeyValueStoreArn>

# Put a redirect mapping (e.g., /old-path -> /new-path)
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseKeyValueStoreArn> \
  --puts '[{"Key":"/old-path","Value":"/new-path"}]'

# Put multiple redirects at once
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseKeyValueStoreArn> \
  --puts '[{"Key":"/old1","Value":"/new1"},{"Key":"/old2","Value":"/new2"}]'

# Delete a redirect
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseKeyValueStoreArn> \
  --deletes '[{"Key":"/old-path"}]'

# Redirect chains are automatically followed (max 10 levels)
# Example: /a -> /b, /b -> /c, request for /a will serve /c

# Create a new KeyValueStore (for testing or migration)
aws cloudfront create-key-value-store --name my-new-kvs --comment "My redirects"

# Delete a KeyValueStore (must not be associated with any functions)
aws cloudfront delete-key-value-store --if-match ETAG_FROM_DESCRIBE --name my-old-kvs

# View function configuration to see current KVS association
aws cloudfront get-function --name <StackName>-obverse-index-rewrite

# To change which KVS a function uses, update the CloudFormation template
# and redeploy the stack - manual function updates would cause drift

# Same commands work for reverse using: <ReverseKeyValueStoreArn> and <StackName>-reverse-index-rewrite
```

## KeyValueStore Management - Custom Headers

Headers are stored as line-delimited "Header-Name: value" strings. The function checks patterns hierarchically and applies headers in order of specificity.

### Pattern Types

1. **Root path**: `/` - Applies to all requests
2. **Directory paths**: `/blog/`, `/blog/post/` - Must end with `/`, applies to all files in that directory and subdirectories
3. **Extension wildcards**: `*.xml`, `*.html` - Applies to all files with that extension
4. **Exact paths**: `/blog/rss.xml` - Applies only to that specific file

### Specificity Order

For a request to `/blog/post/article.html`, patterns are checked and applied in this order:
1. `/` - root (least specific)
2. `/blog/` - first parent directory
3. `/blog/post/` - second parent directory
4. `*.html` - extension wildcard
5. `/blog/post/article.html` - exact path (most specific)

More specific patterns override headers from less specific patterns.

### Path Substitution

Any header value can use `{/path}` which will be replaced with the request path (always includes leading `/`).

### Value Format

Values are line-delimited headers in the format `header-name: value`:

```
header-name: header value
another-header: another value
```

### Examples

```bash
# Add headers to all paths (root)
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/","Value":"onion-location: http://example.onion{/path}\nx-frame-options: DENY"}]'

# Add headers to all files in /blog/ and subdirectories
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/blog/","Value":"cache-control: public, max-age=3600"}]'

# Add headers to all XML files
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"*.xml","Value":"content-type: application/xml; charset=utf-8\nx-content-type-options: nosniff"}]'

# Add headers to a specific file (overrides all other patterns)
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/blog/post.html","Value":"x-robots-tag: noindex"}]'

# List all header mappings
aws cloudfront-keyvaluestore list-keys --kvs-arn <ObverseHeadersKeyValueStoreArn>

# Delete a header mapping
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --deletes '[{"Key":"/blog/"}]'

# Same commands work for reverse using: <ReverseHeadersKeyValueStoreArn>
```
