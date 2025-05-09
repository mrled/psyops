---
title: Argo Workflows
---

I use Argo Workflows for running data pipelines, building artifacts, and sometimes deploying applications to the cluster.

(It has some functionality that overlaps with Flux,
but I think of Flux as deploying cluster configuration and third party apps from raw manifests,
while Argo Workflows is for items that require build steps.)

My argowf namespace includes both Argo Workflows itself,
and all of the workflow jobs,
which makes it easy to include common dependencies and credentials.
For a cluster used by many different teams,
you probably want jobs to run in different namespaces.

* [Argo Workflows documentation](https://argo-workflows.readthedocs.io/en/latest/)
* {{< repolink "kubernasty/applications/argowf" >}}

## Terminology:

EventSource
:    Emits events for Argo WF to listen to. For instance, a webhook listener, which will also deploy a Service.

Sensor
:    Triggers a given workflow based on a WorkflowTemplate based on events from an EventSource.

WorkflowTemplate
:    An abstract template that Workflows can be created from.

Workflow
:    A single instance or run of a Workflow. Made up of individual Jobs.

## Simplest sensor: trigger when a repo changes

You probably want to get this working first.

1.  Deploy a [WorkflowTemplate](https://argo-workflows.readthedocs.io/en/latest/workflow-templates/);
    here we'll assume called `build-example` is already created.
2.  A webhook EventSource
    ```yaml
    apiVersion: argoproj.io/v1alpha1
    kind: EventSource
    metadata:
    name: example-webhook
    namespace: argowf
    spec:
    replicas: 2
    service:
        ports:
        - name: http
            port: 12000
            targetPort: 12000
    webhook:
        gitea-webhook:
        endpoint: /gitea
        method: POST
        port: "12000" # Has to be a string because lol
    ```
3.  Configure a repository in Gitea to call that webhook on every push
4.  Configure a Sensor.
    Replace `REPO_OWNER/REPO_NAME` with the owner and name of the repo in Gitea.
    Note: you'll also need to define a [trigger](),

    ```yaml
    apiVersion: argoproj.io/v1alpha1
    kind: Sensor
    metadata:
    name: workflow-build-example-project
    namespace: argowf
    spec:
    template:
        serviceAccountName: argowf-sensor
        container:
        env:
            - name: LOG_LEVEL
            value: "debug"

    dependencies:
        - name: gitea-webhook-dep
          eventSourceName: example-webhook
          eventName: gitea-webhook
          filters:
            data:
            - path: body.repository.full_name
                type: string
                value:
                - "REPO_OWNER/REPO_NAME"

    triggers:
    - template:
        name: argo-workflow-trigger
        argoWorkflow:
          operation: submit
          source:
            resource:
              apiVersion: argoproj.io/v1alpha1
              kind: Workflow
              metadata:
                generateName: wf-build-example-
                namespace: argowf
              spec:
                workflowTemplateRef:
                  name: build-example
    ```
4.  This will trigger your `build-example` WorkflowTemplate
    any time you push to the `REPO_OWNER/REPO_NAME` git repository in your Gitea server.

## Sensor for specific repo paths

It's possible to trigger only on specific paths,
but it isn't well documented and the syntax is really confusing.

To make this work, you need to add another data filter.
For instance, this will match on any file starting with `some/path/.*` (including subfolders):

```yaml
      filters:
        # Require that all of the data filters match; boolean AND
        dataLogicalOperator: "and"
        data:
          # The same filter we had above, matching on the specific repo
          - path: body.repository.full_name
            type: string
            value:
              - "REPO_OWNER/REPO_NAME"
          # A new filter, requiring that at least one of the files added/changed/removed in the commit is under some/path/ in the repo
          - path: "[body.commits.#.modified.@flatten,body.commits.#.added.@flatten,body.commits.#.removed.@flatten].@flatten.@flatten"
            type: string
            value:
              - '"some/path/.*'
```

How does this work?

First, note that how this works depends entirely on the webhook payload from your Git server.
I'm using Gitea, which is supposedly compatible with Github,
but this isn't a standard.
If you're using some other Git server,
you'll need to figure out what its webhook payload body looks like.

Gitea (and GitHub) send(s) a rather large JSON payload, including a list of commits
and a list of files modified/added/removed in each.
For instance, a commit that changes `some/path/README.md`
and adds `some/path/main.c`
will include this (heavily truncated):

```json
{
  "body": {
    "commits": [
      {
        "added": [
          "some/path/main.c"
        ],
        "modified": [
          "some/path/README.md"
        ]
      }
    ]
  }
}
```

In the `path` field of a data filter,
Argo Workflows supports something called
[GJSON Path syntax](https://github.com/tidwall/gjson/blob/master/SYNTAX.md#multipaths),
which we use to collapse all modified, added, and removed lists into a SINGLE list
containing all the files that were added, modified, or removed, like this:

```json
["some/path/main.c", "some/path/README.md"]
```

The `value` field of the data filter is a regexp that operates
**on that JSON string, as a string**.
To be clear, it doesn't understand JSON at all,
and **does not operate on individual list items**.
For non-pathological repositories you can just match on double quotes `"`
as the beginning/end of file names;
in theory you could have a repo with files that contain quotes,
but my advice is: do not do that.

Here's a simple case matching a single sub-path:

```yaml
- path: "[body.commits.#.modified.@flatten,body.commits.#.added.@flatten,body.commits.#.removed.@flatten].@flatten.@flatten"
  type: string
  value:
  - '"some/path/.*'
```

Note that the whole thing is wrapped in single quotes `'`;
this is so the double quote `"` character is parsed as part of the string.

Here's a more complicated case,
matching any of several sub-paths,
separated by pipes.
Note the double quote `"` as the first character,
indicating that all of these path fragments must be at the beginning.

```yaml
- path: "[body.commits.#.modified.@flatten,body.commits.#.added.@flatten,body.commits.#.removed.@flatten].@flatten.@flatten"
  type: string
  value:
  - '"(path/one|path/two/that/is/deeper|path3|etc)'
```

References:

* [argoproj/argo-events#1127: Unsure of the best practice for a filter with multiple paths](https://github.com/argoproj/argo-events/issues/1127)
* [argoproj/argo-events#1097: Allow for JSON string to be processed in the Sensor DataFilter](https://github.com/argoproj/argo-events/issues/1097)
* Documentation was written with information about GJSON, but somehow that documentation has been lost from the current docs?
    * [argoproj/argo-events#1130: docs: Enhance the filters tutorial for #1097](https://github.com/argoproj/argo-events/pull/1130/files),
      the PR that contains GJSON documentation
    * [argoproj/argo-events#3525: Example documentation for filtering webhooks based on repo and path](https://github.com/argoproj/argo-events/issues/3525),
      a ticket I opened to address this

## Viewing webhook payloads

Once a Sensor is deployed,
push commits to your repo
and it will log lines like this:

```text
{"level":"debug","ts":1746792865.183243,"logger":"argo-events.sensor","caller":"sensors/listener.go:206","msg":"Event [ID 'f0e737ebd34d49c9967593884dd00e8e', Source 'webhook', Time '2025-05-09T12:14:25Z', Data '{\"header\":{\"Accept-Encoding\":[\"gzip\"],\"Content-Length\":[\"5530\"],\"Content-Type\":[\"application/json\"],\"User-Agent\":[\"Go-http-client/1.1\"],\"X-Gitea-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Gitea-Event\":[\"push\"],\"X-Gitea-Event-Type\":[\"push\"],\"X-Gitea-Signature\":[\"\"],\"X-Github-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Github-Event\":[\"push\"],\"X-Github-Event-Type\":[\"push\"],\"X-Gogs-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Gogs-Event\":[\"push\"],\"X-Gogs-Event-Type\":[\"push\"],\"X-Gogs-Signature\":[\"\"],\"X-Hub-Signature\":[\"sha1=\"],\"X-Hub-Signature-256\":[\"sha256=\"]},\"body\":{\"ref\":\"refs/heads/master\",\"before\":\"bab20bdea9bdd3fb5d8eced9e511d84e95a2344e\",\"after\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"compare_url\":\"https://gitea.micahrl.me/kubernasty/psyops/compare/bab20bdea9bdd3fb5d8eced9e511d84e95a2344e...5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"commits\":[{\"id\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"message\":\"Testing trigger\\n\",\"url\":\"https://gitea.micahrl.me/kubernasty/psyops/commit/5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"author\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"committer\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"verification\":null,\"timestamp\":\"2025-05-09T07:14:15-05:00\",\"added\":[\"test\"],\"removed\":[],\"modified\":[]}],\"total_commits\":1,\"head_commit\":{\"id\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"message\":\"Testing trigger\\n\",\"url\":\"https://gitea.micahrl.me/kubernasty/psyops/commit/5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"author\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"committer\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"verification\":null,\"timestamp\":\"2025-05-09T07:14:15-05:00\",\"added\":[\"test\"],\"removed\":[],\"modified\":[]},\"repository\":{\"id\":69,\"owner\":{\"id\":9,\"login\":\"kubernasty\",\"login_name\":\"\",\"full_name\":\"\",\"email\":\"\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/c34a8025880252fa6c7f8a244fe06693\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-14T00:45:06Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"kubernasty\"},\"name\":\"psyops\",\"full_name\":\"kubernasty/psyops\",\"description\":\"Personal SYs OPS \",\"empty\":false,\"private\":false,\"fork\":false,\"template\":false,\"parent\":null,\"mirror\":false,\"size\":6630,\"language\":\"\",\"languages_url\":\"https://gitea.micahrl.me/api/v1/repos/kubernasty/psyops/languages\",\"html_url\":\"https://gitea.micahrl.me/kubernasty/psyops\",\"url\":\"https://gitea.micahrl.me/api/v1/repos/kubernasty/psyops\",\"link\":\"\",\"ssh_url\":\"git@gitea.micahrl.me:kubernasty/psyops.git\",\"clone_url\":\"https://gitea.micahrl.me/kubernasty/psyops.git\",\"original_url\":\"\",\"website\":\"\",\"stars_count\":0,\"forks_count\":0,\"watchers_count\":3,\"open_issues_count\":0,\"open_pr_counter\":0,\"release_counter\":0,\"default_branch\":\"master\",\"archived\":false,\"created_at\":\"2025-03-14T11:33:20Z\",\"updated_at\":\"2025-05-08T12:10:58Z\",\"archived_at\":\"1970-01-01T00:00:00Z\",\"permissions\":{\"admin\":true,\"push\":true,\"pull\":true},\"has_issues\":true,\"internal_tracker\":{\"enable_time_tracker\":true,\"allow_only_contributors_to_track_time\":true,\"enable_issue_dependencies\":true},\"has_wiki\":true,\"has_pull_requests\":true,\"has_projects\":true,\"has_releases\":true,\"has_packages\":true,\"has_actions\":false,\"ignore_whitespace_conflicts\":false,\"allow_merge_commits\":true,\"allow_rebase\":true,\"allow_rebase_explicit\":true,\"allow_squash_merge\":true,\"allow_rebase_update\":true,\"default_delete_branch_after_merge\":false,\"default_merge_style\":\"merge\",\"default_allow_maintainer_edit\":false,\"avatar_url\":\"\",\"internal\":false,\"mirror_interval\":\"\",\"mirror_updated\":\"0001-01-01T00:00:00Z\",\"repo_transfer\":null},\"pusher\":{\"id\":7,\"login\":\"micahrl\",\"login_name\":\"\",\"full_name\":\"Micah Ledbetter\",\"email\":\"micahrl@noreply.gitea.micahrl.me\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/af55804917c3a55df562df80e45861b9b808064b66cfb34e8096e0a0718751ff\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-13T19:28:53Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"micahrl\"},\"sender\":{\"id\":7,\"login\":\"micahrl\",\"login_name\":\"\",\"full_name\":\"Micah Ledbetter\",\"email\":\"micahrl@noreply.gitea.micahrl.me\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/af55804917c3a55df562df80e45861b9b808064b66cfb34e8096e0a0718751ff\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-13T19:28:53Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"micahrl\"}}}'] discarded due to filtering","sensorName":"sensor-build-psyopsos","triggerName":"argo-workflow-trigger"}
```

There's some json-in-json nonsense going on there,
but you can pull out the `Data` value including single quotes from column 206-5741,
strip the single quote escapes,
and pass it to jq for easier reading:

```sh
payload='{\"header\":{\"Accept-Encoding\":[\"gzip\"],\"Content-Length\":[\"5530\"],\"Content-Type\":[\"application/json\"],\"User-Agent\":[\"Go-http-client/1.1\"],\"X-Gitea-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Gitea-Event\":[\"push\"],\"X-Gitea-Event-Type\":[\"push\"],\"X-Gitea-Signature\":[\"\"],\"X-Github-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Github-Event\":[\"push\"],\"X-Github-Event-Type\":[\"push\"],\"X-Gogs-Delivery\":[\"3d224aa6-4bc0-4796-aca2-bea8ca69a1a9\"],\"X-Gogs-Event\":[\"push\"],\"X-Gogs-Event-Type\":[\"push\"],\"X-Gogs-Signature\":[\"\"],\"X-Hub-Signature\":[\"sha1=\"],\"X-Hub-Signature-256\":[\"sha256=\"]},\"body\":{\"ref\":\"refs/heads/master\",\"before\":\"bab20bdea9bdd3fb5d8eced9e511d84e95a2344e\",\"after\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"compare_url\":\"https://gitea.micahrl.me/kubernasty/psyops/compare/bab20bdea9bdd3fb5d8eced9e511d84e95a2344e...5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"commits\":[{\"id\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"message\":\"Testing trigger\\n\",\"url\":\"https://gitea.micahrl.me/kubernasty/psyops/commit/5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"author\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"committer\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"verification\":null,\"timestamp\":\"2025-05-09T07:14:15-05:00\",\"added\":[\"test\"],\"removed\":[],\"modified\":[]}],\"total_commits\":1,\"head_commit\":{\"id\":\"5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"message\":\"Testing trigger\\n\",\"url\":\"https://gitea.micahrl.me/kubernasty/psyops/commit/5eecb1fbd4863044355d0fa615acc08bf66ad47b\",\"author\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"committer\":{\"name\":\"Micah R Ledbetter\",\"email\":\"me@micahrl.com\",\"username\":\"micahrl\"},\"verification\":null,\"timestamp\":\"2025-05-09T07:14:15-05:00\",\"added\":[\"test\"],\"removed\":[],\"modified\":[]},\"repository\":{\"id\":69,\"owner\":{\"id\":9,\"login\":\"kubernasty\",\"login_name\":\"\",\"full_name\":\"\",\"email\":\"\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/c34a8025880252fa6c7f8a244fe06693\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-14T00:45:06Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"kubernasty\"},\"name\":\"psyops\",\"full_name\":\"kubernasty/psyops\",\"description\":\"Personal SYs OPS \",\"empty\":false,\"private\":false,\"fork\":false,\"template\":false,\"parent\":null,\"mirror\":false,\"size\":6630,\"language\":\"\",\"languages_url\":\"https://gitea.micahrl.me/api/v1/repos/kubernasty/psyops/languages\",\"html_url\":\"https://gitea.micahrl.me/kubernasty/psyops\",\"url\":\"https://gitea.micahrl.me/api/v1/repos/kubernasty/psyops\",\"link\":\"\",\"ssh_url\":\"git@gitea.micahrl.me:kubernasty/psyops.git\",\"clone_url\":\"https://gitea.micahrl.me/kubernasty/psyops.git\",\"original_url\":\"\",\"website\":\"\",\"stars_count\":0,\"forks_count\":0,\"watchers_count\":3,\"open_issues_count\":0,\"open_pr_counter\":0,\"release_counter\":0,\"default_branch\":\"master\",\"archived\":false,\"created_at\":\"2025-03-14T11:33:20Z\",\"updated_at\":\"2025-05-08T12:10:58Z\",\"archived_at\":\"1970-01-01T00:00:00Z\",\"permissions\":{\"admin\":true,\"push\":true,\"pull\":true},\"has_issues\":true,\"internal_tracker\":{\"enable_time_tracker\":true,\"allow_only_contributors_to_track_time\":true,\"enable_issue_dependencies\":true},\"has_wiki\":true,\"has_pull_requests\":true,\"has_projects\":true,\"has_releases\":true,\"has_packages\":true,\"has_actions\":false,\"ignore_whitespace_conflicts\":false,\"allow_merge_commits\":true,\"allow_rebase\":true,\"allow_rebase_explicit\":true,\"allow_squash_merge\":true,\"allow_rebase_update\":true,\"default_delete_branch_after_merge\":false,\"default_merge_style\":\"merge\",\"default_allow_maintainer_edit\":false,\"avatar_url\":\"\",\"internal\":false,\"mirror_interval\":\"\",\"mirror_updated\":\"0001-01-01T00:00:00Z\",\"repo_transfer\":null},\"pusher\":{\"id\":7,\"login\":\"micahrl\",\"login_name\":\"\",\"full_name\":\"Micah Ledbetter\",\"email\":\"micahrl@noreply.gitea.micahrl.me\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/af55804917c3a55df562df80e45861b9b808064b66cfb34e8096e0a0718751ff\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-13T19:28:53Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"micahrl\"},\"sender\":{\"id\":7,\"login\":\"micahrl\",\"login_name\":\"\",\"full_name\":\"Micah Ledbetter\",\"email\":\"micahrl@noreply.gitea.micahrl.me\",\"avatar_url\":\"https://gitea.micahrl.me/avatars/af55804917c3a55df562df80e45861b9b808064b66cfb34e8096e0a0718751ff\",\"language\":\"\",\"is_admin\":false,\"last_login\":\"0001-01-01T00:00:00Z\",\"created\":\"2024-06-13T19:28:53Z\",\"restricted\":false,\"active\":false,\"prohibit_login\":false,\"location\":\"\",\"website\":\"\",\"description\":\"\",\"visibility\":\"public\",\"followers_count\":0,\"following_count\":0,\"starred_repos_count\":0,\"username\":\"micahrl\"}}}'
echo "$payload" | sed 's/\\//g' | jq -C .
```
