"""Guard the private network template (audit H-4, Task 6).

Azure is never contacted here. The template is read as text, like the
other infra guards, so these hold on a machine with no Azure CLI.

Most of what can go wrong with a private endpoint fails silently: the
name still resolves, to the public address, and the app keeps working
over the internet exactly as before. These pin the handful of strings
where a typo would do that.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "azure" / "network.bicep"
APP_TEMPLATE = ROOT / "infra" / "azure" / "container-apps-app.bicep"


class PrivateNetworkTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")
        cls.code = re.sub(r"//.*$", "", cls.source, flags=re.MULTILINE)

    def test_creates_only_network_resources(self):
        resources = re.findall(
            r"^resource\s+\w+\s+'([^']+)'\s*=\s*\{", self.code, re.MULTILINE
        )
        self.assertEqual(
            resources,
            [
                "Microsoft.Network/virtualNetworks@2024-05-01",
                "Microsoft.Network/privateDnsZones@2020-06-01",
                "Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01",
                "Microsoft.Network/privateEndpoints@2024-05-01",
                "Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01",
            ],
        )

    def test_the_database_server_is_referenced_never_created(self):
        # the server pre-exists and is not ours to recreate or reconfigure
        self.assertIn("flexibleServers@2024-08-01' existing =", self.code)
        self.assertNotIn("flexibleServers@2024-08-01' = {", self.code)
        for forbidden in ("administratorLogin", "publicNetworkAccess", "firewallRules"):
            self.assertNotIn(forbidden, self.code)

    def test_the_private_dns_zone_has_the_one_name_azure_answers_on(self):
        # "privelink" instead of "privatelink" resolves to nothing, and the
        # app then cannot reach its database at all
        self.assertIn("'privatelink.postgres.database.azure.com'", self.code)
        # the comment above it spells the mistake out on purpose, so this
        # looks at the code rather than the prose
        self.assertNotIn("privelink", self.code)

    def test_the_zone_is_linked_to_the_network(self):
        # without the link the zone exists and nothing consults it, so the
        # server name keeps resolving to its public address
        self.assertIn("virtualNetworkLinks@", self.code)
        self.assertIn("registrationEnabled: false", self.code)
        self.assertIn("privateDnsZoneGroups@", self.code)

    def test_the_endpoint_points_at_the_postgres_group(self):
        self.assertIn("groupIds: ['postgresqlServer']", self.code)

    def test_the_app_subnet_is_delegated_and_the_data_subnet_is_not(self):
        self.assertIn("serviceName: 'Microsoft.App/environments'", self.code)
        self.assertIn("privateEndpointNetworkPolicies: 'Disabled'", self.code)
        # one delegation only: the data subnet must stay undelegated or the
        # private endpoint cannot be placed in it
        self.assertEqual(self.code.count("delegations:"), 1)

    def test_the_app_subnet_is_large_enough_for_a_workload_profile_environment(self):
        prefix = re.search(
            r"param appSubnetPrefix string = '([\d.]+)/(\d+)'", self.code
        )
        self.assertIsNotNone(prefix, "appSubnetPrefix is missing")
        self.assertLessEqual(int(prefix.group(2)), 27)

    def test_it_carries_the_fictional_only_tag(self):
        self.assertIn("'data-classification': 'fictional-only'", self.code)

    def test_the_subnet_id_it_outputs_is_what_the_app_template_takes(self):
        self.assertIn("output appSubnetId string =", self.code)
        app = re.sub(
            r"//.*$", "", APP_TEMPLATE.read_text(encoding="utf-8"), flags=re.MULTILINE
        )
        self.assertIn("param appSubnetId string = ''", app)
        self.assertIn("infrastructureSubnetId: appSubnetId", app)
        # empty keeps the old public environment, so this template still
        # deploys unchanged until the network exists
        self.assertIn("empty(appSubnetId) ? null :", app)
        # the website stays public; it is the database that goes private
        self.assertIn("internal: false", app)


if __name__ == "__main__":
    unittest.main()
