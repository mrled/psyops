"""Offline manifest checks; pass the upstream v0.41.0 Jellyfin CRD as argv[1]."""
import pathlib
import sys
import unittest

import jsonschema
import yaml

ROOT = pathlib.Path(__file__).parent
CRD = pathlib.Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None


class Manifests(unittest.TestCase):
    def setUp(self):
        self.docs = {}
        for path in ROOT.glob("*.yaml"):
            for doc in yaml.safe_load_all(path.read_text()):
                self.docs[doc["kind"]] = doc

    def test_server_is_isolated(self):
        pod = self.docs["StatefulSet"]["spec"]["template"]["spec"]
        self.assertFalse(pod["automountServiceAccountToken"])
        security = pod["securityContext"]
        self.assertEqual((security["runAsUser"], security["runAsGroup"]),
                         ("${plexUid}", "${plexGid}"))
        self.assertEqual(security["fsGroup"], "${plexGid}")
        self.assertIn(992, security["supplementalGroups"])
        server, = pod["containers"]
        self.assertTrue(server["image"].startswith("jellyfin/jellyfin:12.4@sha256:"))
        self.assertEqual(server["resources"]["limits"]["gpu.intel.com/i915"], 1)
        mounts = [m for m in server["volumeMounts"] if m["name"] == "media"]
        self.assertEqual(mounts, [{"name": "media", "mountPath": "/media", "readOnly": False}])
        volumes = {v["name"]: v for v in pod["volumes"]}
        self.assertEqual(volumes["media"]["persistentVolumeClaim"]["claimName"], "seedboxmedia-nfs-pvc")
        self.assertIn("emptyDir", volumes["cache"])
        self.assertIn("emptyDir", volumes["transcode"])
        self.assertEqual(self.docs["PersistentVolumeClaim"]["metadata"]["annotations"][
            "backup.seedboxk8s.micahrl.com/enabled"], "true")

    def test_operator_schema_and_libraries(self):
        self.assertIsNotNone(CRD, "Pass the upstream v0.41.0 CRD path")
        schema = yaml.safe_load(CRD.read_text())["spec"]["versions"][0]["schema"]["openAPIV3Schema"]

        # Kubernetes prunes unknown properties; reject them here rather than silently
        # accepting misspelled configuration that the operator would never see.
        def strict(node):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
            for child in node.get("properties", {}).values():
                strict(child)
            if "items" in node:
                strict(node["items"])
        strict(schema["properties"]["spec"])
        config = self.docs["JellyfinConfig"]
        jsonschema.validate(config, schema)
        spec = config["spec"]
        self.assertEqual(config["metadata"]["namespace"], "tortuga")
        self.assertEqual(spec["connection"]["url"], "http://jellyfin.tortuga.svc.cluster.local:8096")
        for ref in spec["adminUser"].values():
            self.assertEqual(ref["name"], "jellyfin-admin")
        self.assertEqual({lib["name"]: lib["paths"] for lib in spec["libraries"]}, {
            name: [f"/media/{name}"] for name in (
                "Movies", "TV", "KidsClips", "Clips", "Fitness", "MST3K",
                "MST3K-TV", "NonfictionVideo", "Shorts")})
        library_types = {lib["name"]: lib["collectionType"] for lib in spec["libraries"]}
        self.assertEqual(library_types["MST3K"], "movies")
        self.assertEqual(library_types["MST3K-TV"], "tvshows")
        for name in ("Clips", "Fitness", "NonfictionVideo", "Shorts"):
            self.assertEqual(library_types[name], "homevideos")
        self.assertEqual(spec["encoding"]["hardwareAccelerationType"], "qsv")
        self.assertEqual(set(spec["encoding"]["hardwareDecodingCodecs"]),
                         {"h264", "hevc", "mpeg2video", "vp8", "vp9"})
        self.assertTrue(spec["encoding"]["enableDecodingColorDepth10Hevc"])
        self.assertTrue(spec["encoding"]["enableDecodingColorDepth10Vp9"])
        self.assertTrue(spec["encoding"]["allowHevcEncoding"])
        self.assertFalse(spec["encoding"]["allowAv1Encoding"])
        self.assertTrue(spec["encoding"]["enableVppTonemapping"])

    def test_ingress_and_network_policy(self):
        ingress = yaml.safe_load((ROOT.parent / "jellyfin-ingress/IngressRoute.yaml").read_text())["spec"]
        self.assertEqual(ingress["ingressClassName"], "traefik-tailscale")
        self.assertNotIn("middlewares", ingress["routes"][0])
        self.assertEqual(ingress["routes"][0]["services"][0]["port"], 8096)
        rule, = self.docs["NetworkPolicy"]["spec"]["ingress"]
        self.assertEqual(rule["from"][0]["namespaceSelector"]["matchLabels"][
            "kubernetes.io/metadata.name"], "media-operator")
        self.assertEqual(rule["ports"], [{"port": 8096, "protocol": "TCP"}])
        flux = yaml.safe_load((ROOT.parents[1] / "fluxroot/kustomizations/jellyfin.yaml").read_text())
        self.assertEqual({d["name"] for d in flux["spec"]["dependsOn"]}, {
            "media-operator", "fluxcfg", "topolvm", "tortuga", "intel-gpu-plugin"})

    def test_operator_chart_and_bootstrap(self):
        operator = ROOT.parent / "media-operator"
        release = yaml.safe_load((operator / "HelmRelease.yaml").read_text())["spec"]
        self.assertEqual(release["chart"]["spec"]["chart"], "media-operator-mediaservers")
        self.assertEqual(release["chart"]["spec"]["version"], "0.41.0")
        self.assertEqual(release["values"]["watchNamespace"], "tortuga")
        self.assertFalse(release["values"]["metrics"]["enabled"])
        self.assertEqual(release["upgrade"]["crds"], "CreateReplace")
        self.assertFalse(list(operator.glob("CRD.*.yaml")))
        fluxroot = ROOT.parents[1] / "fluxroot/kustomizations"
        ingress = yaml.safe_load((fluxroot / "jellyfin-ingress.yaml").read_text())
        self.assertEqual(ingress["spec"]["dependsOn"], [{"name": "jellyfin"}])
        server = yaml.safe_load((fluxroot / "jellyfin.yaml").read_text())
        self.assertIn("status.initialized", server["spec"]["healthCheckExprs"][0]["current"])
        self.assertTrue(any(h["kind"] == "JellyfinConfig" for h in server["spec"]["healthChecks"]))


if __name__ == "__main__":
    unittest.main()
