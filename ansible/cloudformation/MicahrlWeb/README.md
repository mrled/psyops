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

Headers are stored as line-delimited "Header-Name: value" strings. Headers are looked up hierarchically and merged (child overrides parent).

```bash
# Example: Add headers to the root path
# These will apply to all responses unless overridden
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/","Value":"X-Frame-Options: DENY\nX-Content-Type-Options: nosniff"}]'

# Example: Override a header for a specific directory
# For /blog/post.html, this will add both headers from / and the custom one from /blog/
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/blog/","Value":"Cache-Control: public, max-age=3600"}]'

# Example: Add headers to a specific file
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"/blog/post.html","Value":"X-Robots-Tag: noindex"}]'

# Example: Special pattern for path-based headers with {/path} substitution
# This applies to ALL paths and {/path} is replaced with the request path (always includes leading /)
# Useful for Onion-Location headers pointing to Tor hidden services
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --puts '[{"Key":"**/*","Value":"Onion-Location: http://example.onion{/path}"}]'

# For path /one/two/three.txt, headers are looked up in this order:
# 1. / (root)
# 2. /one/ (first directory)
# 3. /one/two/ (second directory)
# 4. /one/two/three.txt (the file itself)
# 5. **/* (special pattern with {/path} = /one/two/three.txt)
# Later definitions override earlier ones for the same header name
# Different headers from parents are combined

# List all header mappings
aws cloudfront-keyvaluestore list-keys --kvs-arn <ObverseHeadersKeyValueStoreArn>

# Delete a header mapping
aws cloudfront-keyvaluestore update-keys --kvs-arn <ObverseHeadersKeyValueStoreArn> \
  --deletes '[{"Key":"/blog/"}]'

# Same commands work for reverse using: <ReverseHeadersKeyValueStoreArn>
```
