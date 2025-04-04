# MongoDB Community Operator

This operator is pretty bad and has lots of bugs and missing features.
You might consider another solution,
like defining your own StatefulSets
or using Percona Mongo Operator.

- You have to deploy RBAC yourself in each other namespace
  <https://github.com/mongodb/helm-charts/issues/361>,
  copy the resources from here yourself lol
  <https://github.com/mongodb/helm-charts/blob/main/charts/community-operator/templates/operator_roles.yaml>
- You can't provision
- It has a concept of "members" and "arbiters",
  where members are full cluster members who vote and store data,
  while arbiters only vote.
  But it can't set different resource limits for arbiters
  <https://github.com/mongodb/mongodb-kubernetes-operator/issues/962>,
  and when it redeploys the cluster because of an update to the resource document,
  it'll kill one arbiter and one member at the same time.
