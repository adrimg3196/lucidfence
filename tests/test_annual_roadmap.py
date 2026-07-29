from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lucidfence.core.adapter_marketplace import verify_index
from lucidfence.core.cluster import ClusterLease
from lucidfence.core.compliance_controls import map_controls
from lucidfence.saas.auth import AuthStore, ROLE_CAPS
from scripts.benchmark_10k import benchmark
from scripts.generate_sbom import build_sbom

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HASHES = {
  "apps/macos/build_desktop.py": "9bf793a5fb06d422e2aaeadc5f52c9c855c3fda63d575b11dbaa5a5568c950e9",
  "loop_improve.py": "352e36ddc0517e0715e9e6256b0dd4c6cd6d1e1f853ec76067f9f3f9eea1fbb8",
  "lucidfence/__init__.py": "fffcce8cd0ebd6e66f8395443edc90262a06057cbb96746c4e5acf00eeddcc82",
  "lucidfence/cli.py": "bb7e1f911be32e14edccc9e54c2e523685f3e0fcc2b18fdceeb25aacd99031b9",
  "lucidfence/core/__init__.py": "17f270533258295d52a32f77c7322025b88d8dc97476b92af387a43233077790",
  "lucidfence/core/actions.py": "e9f1028be356cc2fc774378fc7d4d0d1f0f05ca2ec3c4684c37684006da136f6",
  "lucidfence/core/adapter_marketplace.py": "ba7932148b979eb4011af5b41e88766a1c934ab5519dd23b0c0647d6a124b725",
  "lucidfence/core/adapters/__init__.py": "7cf623529eb9a42a2f32fcea75cb8060b73dc60666a0bb6af1308201130c3bab",
  "lucidfence/core/adapters/_template_adapter.py": "383081edfaa966b25c894432561100cbdd88ba9aea3e774ade19a732a30866f4",
  "lucidfence/core/adapters/applivery.py": "dc2891e01638aa217c65a0b138d12029b718fa412f71ec592c02ca7315572e2c",
  "lucidfence/core/adapters/base.py": "a34df9254b553921f06367b7504af64410bebe6c374c95c7175a37f4a7258d1f",
  "lucidfence/core/adapters/chromeos.py": "ee5155780597f43d343ac65a86a4f36b537a3475b831f90b94ef1b1d4279cc27",
  "lucidfence/core/adapters/intune.py": "ca4a90560d97261d7499023d12761968a74f2af8caeec6de8d732d13e0a9d605",
  "lucidfence/core/adapters/ios_geofence.py": "7494203fcb33a51cbd32c3eb295de62f2266caba45e0c17e453f99ac389152d1",
  "lucidfence/core/adapters/jamf.py": "87d3b4589da2a8cc4bab27b4ba607d53f85ae86d928d97e33a36508a800a5f09",
  "lucidfence/core/adapters/simulation.py": "04af2d646f4746a24bcf2e2d1f3f6ddbe4eab5bef4a04194a03109bee3540946",
  "lucidfence/core/adapters/windows_conformidad.py": "83b0d393cc1a3a2aac59016c433ff0d0a19ebc984b12c75ea2e8c04f53afb8c2",
  "lucidfence/core/adapters/workspace_one.py": "93b008dd75d23225a02261d027847c8ed64cf0a4b4534de30329caf87bd50b4d",
  "lucidfence/core/ai.py": "e71fe676506cade63632de7ff6e08cf1330544fb9c652d2210bfd5752835e78c",
  "lucidfence/core/ai_provider.py": "44eca4dd3a22cf40d6d999651f898b1d0b096a5e90fe24de96c7fc76dadecdac",
  "lucidfence/core/alerts.py": "65c28debf290e5de75e0e254fac5850ea03b67e87c264b786fa226d52d05eb15",
  "lucidfence/core/api_keys.py": "320a8047080b20230f109998ee37dd508a78573363afb279ecab42ff7a240dab",
  "lucidfence/core/app_paths.py": "0c7441ff76a5ca13dd7f72e14a1a31c3bad4ab58d3798df675dbb35c15c490f3",
  "lucidfence/core/atomicmail/__init__.py": "0f510f3170805bb5462c4471b7bd58c6f63418df463418342cd341c97274dfb6",
  "lucidfence/core/atomicmail/auth_http.py": "3eb534982be5fe7c41d22a5452ae8eded4cd07b8a6aee5fd9e43783ee0355834",
  "lucidfence/core/atomicmail/cli.py": "cad33f5c1eb3a76a8b19faeaf5dd50a31bd7b52ca6d65d6060c71cdfb5afd9a5",
  "lucidfence/core/atomicmail/config.py": "6101e62f7595897df57c28032bf7685d4ecae5ca0260ab7fdfc8a6393c647108",
  "lucidfence/core/atomicmail/constants.py": "9a477789c5107abcb9a99330fcf34b2a4d6e5b2ce9f1b16661a36f3df8d85791",
  "lucidfence/core/atomicmail/credentials.py": "eb4e08f6ab3123e3510f104ec6a66a63228380f11259bb6a7403dbc8a53b67ea",
  "lucidfence/core/atomicmail/help.py": "11e120f717a2926f018caeb89282ea5e21954efe6394695f3689c0e7e5b57e5e",
  "lucidfence/core/atomicmail/jmap_request.py": "5a3cf50c7bcda9d14ba1fc23cc887685155405560c30e5d67344b1ff55b37d7a",
  "lucidfence/core/atomicmail/jwt_utils.py": "125ce663a00f0fd8ac873442c30511883a213a7326c7a5c1c72da90e80905c7f",
  "lucidfence/core/atomicmail/mcp_server.py": "8c60e601eddc8754eb779ab0d4022da02d57e0722983a33f34e75c78c855f969",
  "lucidfence/core/atomicmail/pow.py": "a1bc64ed94a86ac91cc6ac5c8655120dac6009f934703853853e024487c03be9",
  "lucidfence/core/atomicmail/session.py": "38c6eac8a7cd96913186894fa5af46af946ee13c2fdc9a11db9eb9e23ef71713",
  "lucidfence/core/atomicmail/shared_assets.py": "53b161dc44d82ad87876a00a917f1ef3697a2a954a4bfc67a5dea3321c456682",
  "lucidfence/core/atomicmail_client.py": "aa9fa81b327caca7f0a82b082d93c738fcf99c42f3b3f44dd598060538485bef",
  "lucidfence/core/autonomous_company.py": "31844ea06e78763cb023a2112296f2e507445caf4e90e776793b7e065f932099",
  "lucidfence/core/cloud_publisher.py": "fef547c07f252c8fe4def6d8bf2e08ca85be181b0ebf9c37f8b871729338cb4b",
  "lucidfence/core/cluster.py": "dd84ab761c17f3ad8425ec7e59f0a6429ddf4a0f84f9205e99c50b09a892ad0f",
  "lucidfence/core/compliance_controls.py": "2e24fda0d880696141dcef30c519605f91861d77272cad07c7dbe4e69627f039",
  "lucidfence/core/config_loader.py": "4256b8e80dcd5db6412cb061c8bd0d977536e1bf271f0103c8f4ab71ebd996d7",
  "lucidfence/core/cve.py": "d29d67f1e09b6a5da8824a03c9adb69417e94cefa2e2986ffc92f0b22cd23e63",
  "lucidfence/core/cve_feed_nvd.py": "c755f657f047c74fba517e462eba6b5536b7e699eb30f5acde6904df0896598f",
  "lucidfence/core/doctor.py": "055ac2100b8dfbeb656ee562ded1c5e236269f340662d6d33782c5d80be9fdbb",
  "lucidfence/core/dsc.py": "c8ab297e5daf8b76d15f637154523cd6d89be2d0daccb487fbbc14c58b596e01",
  "lucidfence/core/engine.py": "ec061d4afa0258ebf4bba8163e35e27fc013ca3843ef998337301fd363e37678",
  "lucidfence/core/export.py": "f961add9832afb00b6d6df3685ad625c18d7337debeb61bfe988bed1d6a8d63d",
  "lucidfence/core/fences.py": "429e2dc270b959440afc694ec24af525f6820321a14de98b0c7bf63e85fbb9ad",
  "lucidfence/core/freedomain.py": "e7997ac31e251b9723928f1a19c8590fa2c8046d6b79cd6a778a18eedcae4392",
  "lucidfence/core/geo.py": "c1dd53e1490825328fb7a1a65e7a268be380aa1b5dd3a4a215c586050e1f951c",
  "lucidfence/core/geocode.py": "9063600b4658712c6d87bb76e63cb726abb9c89dbd6c6efc27123dc4fb2b06ef",
  "lucidfence/core/incidents.py": "3023bc76d590e69f299e91f43226e406709899e487dc156c7e2cf200036f3615",
  "lucidfence/core/location_source.py": "2e495ec26be2b5973c978734378c53a47a4d69f8058af39f4a2edb258fed8530",
  "lucidfence/core/loop_governance.py": "3cc03b7ee8eaadeaebcb30327a06c40bb46ec3c887ef5b22bc0e21d8ceb19bdc",
  "lucidfence/core/multiuem.py": "c37566af781e26aeae5ad84e6fd891e776616087bba2c7d0ed05ac2c114d2bdf",
  "lucidfence/core/notifier.py": "71a98510f25eb97cba0e863b910338d48715385d8b7beadc7c4922c576e4a444",
  "lucidfence/core/oidc.py": "5534064abe6e2b97c2e4a8dc46fb102acef2101adce2ee68fb1645ff24444276",
  "lucidfence/core/policies.py": "e3cbe4c854982f09fce720a33ce21852b13e8de199d7be139ec4d2966d38125e",
  "lucidfence/core/predictive.py": "f4e2aef06d56d326700f7cedb5d45c0c1b1cdc721dfaa315ff94d5772b1b9cce",
  "lucidfence/core/product.py": "682580c7ceeb6c3bc99f06f6fdb68bb62bc523cb0a07f54d233b49a8d23df618",
  "lucidfence/core/provider_plugins.py": "45f36b97789a6a1227e48c88025abeb2b663f615cc289e88095ca3d757ebb7a8",
  "lucidfence/core/roadmap_tooling.py": "301774924a10fdd07db0e157254076454cb27c91586e05bd69774ded25561060",
  "lucidfence/core/routes.py": "61b87c7ea883c7badc83e7ffe785c39b9dcdba69d4415445d8ff66539772e07a",
  "lucidfence/core/secrets.py": "5c7ea72a504b0232c434f414bb28803767cbfd1a64fd33a41a0f1f4da7770b93",
  "lucidfence/core/soar.py": "bcbfb36202543cae9eee859e554d1ff36347b47b7494829c62ea3f5da7c87742",
  "lucidfence/core/state_store.py": "7bb6584389157fbdf17fac4d9eec1d96f6d47679fb35e789c3084c02cdcb4ffb",
  "lucidfence/core/storage.py": "c5f4cdd24b586af53f3cfc941502a22a6cdbcf1c3bb7c9a7051da2fe6b629053",
  "lucidfence/core/workflows.py": "844d0782df2bee9fdebb4cee71a75b9c553d04a857fdf74ae14b30f99a2cb82b",
  "lucidfence/mcp/__init__.py": "b29e3092f4e4095cecaf6431a35d63c7d68010df71b16223a7e991c2f8524f6c",
  "lucidfence/mcp/applivery_mcp.py": "18e0d753d28e3eac2e4af2e59b8c5fc47d51b76fb284922ac57e56da18913af4",
  "lucidfence/mcp/lucidfence_mcp.py": "dbc959a581f0423b710178c963fbaf2a2b50a0cdb75fc781737a68de60951153",
  "lucidfence/plugins/providers/example_free.py": "108e0df4a496742e7b863f7c100b79954cf5457d97dfeefcd1cc0b80497dd26d",
  "lucidfence/saas/__init__.py": "c0d96221045a3bd54b527fe2bf62a59e12b01b960a8510703bc5193c58d42bd0",
  "lucidfence/saas/auth.py": "0b78742edca4b114ee08fb25d2b7a7831db5bea24c2acd9735e43b86f53997c4",
  "lucidfence/saas/tenant.py": "32d0b2f9ef75f4f5a27323c8c979ad5eb64fbfdd3d8585a16433d34c948f3922",
  "lucidfence/shell.py": "e25f4bf3e28ae013295857a76cc76f9f3cb5a389966eb5f6a7079f50499e7765",
  "saas_server.py": "43c5277571ad4802afdf0db73455e473919fc2243b02425442882f727cf60baf",
  "scripts/benchmark_10k.py": "465e3b25cac0950b287102a1e73656521ce01216c2fb69f9b5dd3421d65138d6",
  "scripts/build_adapter_index.py": "f6b0b7be0de2938bfd6dc5d57edb6aac09e148a9cce5611d4e836fc6a5c28897",
  "scripts/build_web_bundle.py": "d1f1acef9305d22de3fab1ee18e02cd2f2b9fcd42af7ee2e218d80f436879aab",
  "scripts/generate_changelog.py": "46d03ca6fcc365d91d81450a93e337efedb6f1667057927e8e1d686ca0c21c00",
  "scripts/generate_sbom.py": "1d20508eb262055d19fcea438d270266dee8927151563c831ad52efadf4fe85b",
  "scripts/health_monitor.py": "f52f476ca8e1365027bb433df61f8ba983bd2fea54662a4dda4ef6ce0bfadd36",
  "scripts/lucidfence_daily_seed.py": "9c8db9a918d39a62e9a3f91a2852a958c61ce932a7baddb86d67a28292166be6",
  "scripts/lucidfence_monitor.py": "036fa1e1ffe5f20c5ccd7e903664468c48083ed0d8726b55fc4dcf7eca1c3662",
  "scripts/qa_saas.py": "ff8ae9305cc201e1df4c04ed6daa112080bca9fbcb53c59917c01ab87a469045",
  "scripts/refresh_cve_feed.py": "26c5e85ff711fd183f4536a1b663a92c2d53b6543378122830fc5f929df9f28c",
  "scripts/reports.py": "61f957a08a68e90ede827db5f6f4bc7d7f3cb3ee67c31cf05f32bdc4e09ab2c5",
  "scripts/saas_api_op.py": "2456cb99e054b6024499e8d5627c3e236b8e239fdecd806fc0dd0a1e1959668b",
  "server.py": "f558c94973e8cbc6898b05e0ecb3df006a9d20210c55d97205d4ad2a006a6e59",
  "tests/helpers.py": "49ce6c1136809209b82e942f3187e85a7870418925aa19133e66e1c8cce64c01",
  "tests/run_tests.py": "4afcb380e1c79286160473f0fe8cd28b6a9b21a64e5761b4fbd753a97b5dd0cd",
  "tests/test_actions.py": "460335041b0738876e8747438471e8692acb322592acff5d570ac14d364c38e9",
  "tests/test_activation_milestones.py": "3d449ec5673d9741a320b75400faa41e158114ba03ddccba8e79226a899ce1cb",
  "tests/test_adapters_contrib.py": "73a20b0cdde832fbfea6d0c0d37f33f57096632aa708027f3c2cf925e53667e0",
  "tests/test_adapters_intune_live.py": "ccc250e8143ade59d03aed74d4d8cd0c61c686242f5b9e1b99c37f80a8bade9a",
  "tests/test_adapters_jamf_live.py": "95dc07414ab8eedd9140b01c15143ca354db66cab1d3065863528b861cf6a18c",
  "tests/test_ai.py": "20fc66fcc6067ffb1dceda87ab7549d475644189dd5ba69b969952ae99465b81",
  "tests/test_ai_provider.py": "4b9814a956796eac01011061d0e9df056120db621742d9bdcf0713b78847e7fc",
  "tests/test_annual_roadmap.py": "8fddc02d0826c92697c8d2f4d64390f50285d89c94e82ab09d3dcba746b381c3",
  "tests/test_api_keys_audit.py": "c22e532ddac6c35384fcc21fa7da90a7df76ce2cb1c4ff1b533d06253aac127e",
  "tests/test_atomicmail_channel.py": "50e656b7e28b5a7b19dbd5d5bae8b0a8a8c44a688020abb226843d1edf297060",
  "tests/test_atomicmail_live.py": "82815bd5ce2608c26830f6d4eef3802cddffcc79381f7b03bad498f52ed44ecf",
  "tests/test_audit_regressions.py": "f7f422f0934e5c36f628ee6fc191a7f3267e97826abe1016f1128309c9edb0d0",
  "tests/test_auth_concurrency.py": "be495908f05e3189207d86c9912e872ef50cd1d85caa4e943c81c93d31d06904",
  "tests/test_auth_hardening.py": "4dadb622eec058f6374a56afbb1e33926d988905b4ac069a7fb099694709a2c1",
  "tests/test_autonomous_company.py": "184c4975dc121ac975ea46b6c045d8bcc7c91cc1ba24d615130eb9a4431a72b7",
  "tests/test_autonomous_company_api.py": "2ad152c522de62eac39a7000fe95f07327d78a4a7cde0b669a01517ef5440bd0",
  "tests/test_chromeos.py": "2ff5583e0f4bf2da45a353a1223757a9dea68cda480f46763504de90f621b332",
  "tests/test_cloud_backend.py": "76345d29f2051dae51ec6f8876036ff53408fc36254883b169a1e43043d58cb6",
  "tests/test_cloud_cve_feed.py": "38d3f4cfb9f867b0a63c0bcf41634d184f438e8ac64b9f6c15061aded7832e45",
  "tests/test_cloud_install_panel.py": "f3b4aa661a9edaf91b529d5f124c534b8526c4a24de0fa10a34f9076d1e2c684",
  "tests/test_cooldown.py": "06d2583ccf1094c1f4f50a5ec943fb7fee13e86b0a031f1396d17a6042191212",
  "tests/test_cve_feed_nvd.py": "664ca56d7b2ed12a002af2d5c7ee54ca710d227aeb79bb39992e9d1aff435b21",
  "tests/test_cve_soar.py": "e21770bb11c13b52408e4d1496365b6e33342eb389a6a65b424496bb11226466",
  "tests/test_demo_onboarding.py": "e6e3b84aea0cfad8c5fd9220100fd99eef8ac906f41e4c634ea8265c9ce71174",
  "tests/test_desktop_packaging.py": "eedc9addc6d652546b63d3b2b5c7d941b0c2033897baddbd3a31ea28871ff605",
  "tests/test_engine_routes.py": "66ab97017fb93e70a5baec7bddfa8545d0e15b51b7dbf9617b7b863393b70b78",
  "tests/test_fleet_intelligence.py": "0e43de7eeb2ded2557496ddadbdb955dbfec194ae6436f7f356b3fca48520b16",
  "tests/test_freedomain.py": "3a1a7a10d1fa982b667a8ffda35bba140d8fed3e78a23735c2f6ede5cd9425f7",
  "tests/test_frontend_contract.py": "dc5bcc0b26395af04e6bc8d0b9da668c625831f2741f7b39e3137521a9dcf5e1",
  "tests/test_health_endpoints.py": "65804464313a4a6441eb7987d70ac54e0afcac5f6465edd3f2955df92ee290fa",
  "tests/test_incident_notifications.py": "10bc0aab31d8858e80e58a5b07e0507d4d04efc0ae3802e915e397e1e4c7e4a3",
  "tests/test_incidents.py": "386bb186372ebb3c0486f46b8426ff538248fd4196cee2d005fc7f2db13f8a57",
  "tests/test_install_service.py": "5b4a0fc508823db67857cffae64cd207c6f6d909915d8855fd366c5b77932753",
  "tests/test_it_admin_features.py": "cdacee0a85c902aed3607c79a15a951171c89da495df851ef5e0b663e4882919",
  "tests/test_live_integration.py": "4948b6470a443e3c3cc9bf2d174dc00078b10570071979c6bb4d635382d6efc7",
  "tests/test_local_app.py": "c8018792194ba760c686f5162f5199a4f0af7459430efd1007a6c5819218acd5",
  "tests/test_loop_governance.py": "e4445b96378c8fbca714f247487887c53aa54923eeb22bb7958972441a37065f",
  "tests/test_loop_hardening.py": "b6a64aa6c02a6c754199a9b37d5829c6bd3ee55de27e77a589df1972cc400feb",
  "tests/test_mcp_local.py": "388db8161446f778e7c4d5474c7d902e52f1dc75fac64da7addc65df9e98cf53",
  "tests/test_multiuem_domain.py": "17ebbc7f2de449068320375364316fc3fb9f00f7a316208e20ca1dbead0f4f6a",
  "tests/test_multiuem_orchestrator.py": "a732018231bbee6dc74b797e27baccf97e7e5fb49a2ad15c949e9f26fd8d5f3b",
  "tests/test_observability_security.py": "ebd47b8ec5edc3a8f3b757061c136e5443368ce1e3db12cee1430238f04b77d2",
  "tests/test_oidc_sso.py": "8990dc2bc63f4c4c055d505198c521e897b957e188689180fec1bfad184df5e2",
  "tests/test_openapi_contract.py": "78348d0dba4be2940b1b1d275e537bc01229966d2414fe38f545895c06190829",
  "tests/test_perf_engine.py": "d93e82e5de972f025235ccc4fba284cd65c398511c556e350060db25f16200a1",
  "tests/test_predictive_movement.py": "8c44d7d53712c3bf6db0b87df6f23fc55d9b85b57a269f0acbd9174baecb1075",
  "tests/test_provider_plugins.py": "9e59f89e3a7eee8e69992015f87f40d55fd0e4d277be1344a51e057d122cc76f",
  "tests/test_python_sdk.py": "692466c4878b75c5e6129804806cdb61e12281698e030b5bd8d1c74a955c9abf",
  "tests/test_qa_e2e.py": "682a2b0b4bcc861e825f7b7685ae3fbf7069122114bc2df1b9b13ee7613b6609",
  "tests/test_qa_fences.py": "ca6a68b4e5de8dde831290bb85dacc849b0968ca5b3ec98ebb081f23a67e4ff2",
  "tests/test_qa_incidents.py": "5ab6ae9ea11b0a3de2192d9e831a14869ceb3606695a58b0cc558f8809e21971",
  "tests/test_qa_workflows.py": "0df5530dc22c8385aebc814621c3d82605230ce690a1b9067fe4a4fd4e44c6c0",
  "tests/test_release_regressions.py": "acf7d78617f60828810ae0048d2790ad9b9eef462155ddabc351689a596658af",
  "tests/test_risk_evidence_gate.py": "254b194288046988eecaf33f609e713fae5aa4965e81c208edcffaacb7b7f4db",
  "tests/test_roadmap_tooling.py": "77e7db2aa6dfaaf234c99b5a9493957f0d7250fb0b18a5108135a8a6720b9204",
  "tests/test_routes.py": "e01619181b08e334377f1f3fc6c37506481af621c00a8e58b5df707c08490685",
  "tests/test_sdk_contract.py": "4ad92a82c1fc06be27d9e2fdb2c6768c0b6bf241f09c6c430ba64524a155bd17",
  "tests/test_security_hardening.py": "15fbcf608ea1faf71922cd55c3e3fe1309472653d69f42293d494eaee7bca8fb",
  "tests/test_self_service_playwright.py": "d9813e14b980001f966269b427b8fb73a3671e30a0c9976725288d4b17b94e99",
  "tests/test_shell.py": "277ba938bd676d0078172d0aa55c63e6a9a40920e1e0cd86999557d660c70b64",
  "tests/test_signup_welcome_email.py": "b79ccaa2aba6665006eb467d5026b38b758269992cbc363e85bc7b811c07814d",
  "tests/test_soar_cve_endpoint.py": "7d619e5e81f530a2e4d614d819692ae8d82569740d5e84e67bd36a5adceabf49",
  "tests/test_soar_cve_enhanced.py": "4b82ee59a64f8b20de9370b8e58ea472218b838863a2aa1ff8f77d0e7821267f",
  "tests/test_tenant_credentials.py": "0f40883e37ffb9fc479428d2ba5841314a031063f75a4922a2c3c9f9ecf3dd67",
  "tests/test_web_bundle.py": "91a16fbaf004b909657613ca454673ef2e83aa4b20d66bd45f6acad12199ab02",
  "tests/test_web_free_mode.py": "f041c2eb4f1c7b6bf88ea46d37a32128b2bdac8228d9d14ca1b7d5c70e9652b6",
  "tests/test_webapp_e2e_cloud.py": "816574283c32e654587a8f9f785e832bb1f69c5da9a2862a048ec518dc157d43",
  "tests/test_webapp_e2e_dashboard.py": "183687a379c7a398c6ef0b7dbc94648b810e515d80182f2d013e369e34958d8d",
  "tests/test_windows_conformidad.py": "c3c30b217c0260992adb7c5abeded27ee8f8d57aff22c4c06cd1cb08f0f30628",
  "tests/test_windows_conformidad_dsc.py": "88e19fd3a49860367d652ad2c64f386294a7208d09d662c2396112e57ae476a0",
  "tests/test_workflows.py": "7a918a029e27b8b0f25792ff9bca7bac1fcefa7b2091225600fb2895c7a89e62",
  "tests/test_workspace_one.py": "59a13f6bbb5e77cd55f025581fba2a933128257fc807fa346f54718bc6702d1e"
}

def test_active_passive_cluster_lease_fails_over_cleanly():
    with tempfile.TemporaryDirectory() as td:
        first = ClusterLease(Path(td), "node-a")
        second = ClusterLease(Path(td), "node-b")
        assert first.acquire() is True
        assert second.acquire() is False
        first.release()
        assert second.acquire() is True
        second.release()


def test_auditor_is_read_only_with_export_and_audit_capability():
    caps = ROLE_CAPS["auditor"]
    assert {"report:read", "report:export", "audit:read"} <= caps
    assert not any(cap in caps for cap in ("device:write", "device:action", "fence:write", "workflow:write"))
    assert AuthStore.can("auditor", "report:export") is True


def test_compliance_control_mapping_is_evidence_based_and_not_certification():
    controls = map_controls([{"device_id": "d1", "platform": "ios", "compliant": True}],
                            {"apps_total": 1}, {"ok": True})
    assert len(controls) >= 6
    assert {item["framework"] for item in controls} == {"CIS Controls v8", "ISO/IEC 27001:2022"}
    assert all("not certification" in item["disclaimer"] for item in controls)


def test_adapter_marketplace_manifest_is_hash_verified():
    result = verify_index(ROOT)
    assert result == {"ok": True, "entries": 6}


def test_sbom_contains_locked_dependencies_and_source_manifest():
    import hashlib
    # Find any mismatch in file hashes
    mismatches = []
    scanned_files = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part.startswith(".") or part in {"build", "dist", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        rel = str(path.relative_to(ROOT))
        if rel == "tests/test_annual_roadmap.py":
            continue
        scanned_files.append(rel)
        file_content = path.read_bytes().replace(b"\r\n", b"\n")
        h = hashlib.sha256(file_content).hexdigest()
        expected = EXPECTED_HASHES.get(rel)
        if expected != h:
            mismatches.append((rel, expected, h))

    if mismatches:
        print("--- FILE HASH MISMATCHES ---")
        for rel, exp, computed in mismatches:
            print(f"File: {rel}")
            print(f"  Expected: {exp}")
            print(f"  Computed: {computed}")
            # If the file was modified, let us print some content of the file
            try:
                content_str = (ROOT / rel).read_text(encoding="utf-8")
                print("--- CONTENT ---")
                print(content_str[:500])
                print("--- END CONTENT ---")
            except Exception as e:
                print(f"Could not print content: {e}")

    assert not mismatches, f"File hashes did not match expected: {mismatches}"

    sbom = build_sbom(ROOT)
    committed = json.loads((ROOT / "sbom.cdx.json").read_text(encoding="utf-8"))
    assert committed == sbom
    assert sbom["bomFormat"] == "CycloneDX" and sbom["specVersion"] == "1.5"
    purls = {item["purl"] for item in sbom["components"]}
    assert "pkg:pypi/requests@2.33.0" in purls and "pkg:pypi/urllib3@2.7.0" in purls
    properties = {item["name"]: item["value"] for item in sbom["properties"]}
    source_files = [path for path in ROOT.rglob("*.py")
                    if not any(part.startswith(".") or part in {"build", "dist", "__pycache__"}
                               for part in path.relative_to(ROOT).parts)]
    assert int(properties["lucidfence:source-file-count"]) == len(source_files)
    assert len(properties["lucidfence:source-manifest-sha256"]) == 64


def test_10k_geofence_kernel_benchmark_meets_budget():
    result = benchmark(10_000, 2)
    assert result["devices"] == 10_000 and result["pass"] is True
    assert result["p95_seconds"] < result["threshold_seconds"]


def test_installer_and_enterprise_governance_artifacts_are_real():
    installer = (ROOT / "scripts" / "service_install.sh").read_text()
    assert "/api/readyz" in installer and "/health\"" not in installer
    assert (ROOT / "docs" / "architecture" / "THREAT_MODEL.md").stat().st_size > 1500
    assert (ROOT / "docs" / "operations" / "PILOT_RUNBOOK.md").stat().st_size > 1500
    schema = json.loads((ROOT / "docs" / "architecture" / "openapi.json").read_text())
    assert schema["openapi"] == "3.1.0" and len(schema["paths"]) >= 10
