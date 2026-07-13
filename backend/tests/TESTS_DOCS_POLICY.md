# Tests Docs Policy

Politique Q14: les tests pytest verrouillent les contrats de code reels. La conformite
des documents, leur vocabulaire exact et leur structure redactionnelle appartiennent aux
audits, pas a la CI applicative.

Suppressions de tests purement documentaires:
- `test_repo_invariants.py::test_patch_11f_pulse_docs_mark_future_surfaces_outside_v1_contract` supprime: verifiait uniquement la lettre et les sections des docs Pulse, sans contrat de code executable.
- `test_repo_invariants.py::test_home_bootstrap_docs_define_metadata_only_and_status_available_not_health_check` supprime: verifiait uniquement des phrases de docs pour Home Bootstrap, deja couvert cote code par les tests endpoint/service.
- `test_imperium_screen_architecture_docs.py::test_frontend_architecture_63_defines_security_performance_and_non_goals` supprime: verifiait uniquement la redaction du document frontend architecture.
- `test_imperium_screen_architecture_docs.py::test_vault_screen_source_docs_are_available_in_audited_docs_master` supprime: verifiait uniquement la presence d'un ancien nom de document source.
- `test_imperium_screen_architecture_docs.py::test_vector_screen_source_docs_are_available_in_audited_docs_master` supprime: verifiait uniquement la presence d'un ancien nom de document source.
- `test_imperium_screen_architecture_docs.py::test_pulse_screen_source_docs_are_available_in_audited_docs_master` supprime: verifiait uniquement la presence d'un ancien nom de document source.
- `test_imperium_screen_architecture_docs.py::test_pulse_medical_and_logic_docs_define_required_v1_contracts` supprime: verifiait uniquement des phrases dans les docs Pulse medical/logique.
- `test_imperium_daily_plan_contracts.py::test_daily_plan_docs_explicitly_document_contract_rules` supprime: verifiait uniquement des phrases de docs daily-plan, sans contrat de code supplementaire.
- `test_docs_lot_2_features_vocab_arch.py::test_carrier_engagement_and_expert_orchestration_are_documented` supprime: verifiait uniquement la redaction de docs V3/Qwen/brain.
- `test_docs_patch_43_53_invariants.py::test_doc_53_overlay_exclusions_use_observable_mission_types` supprime: verifiait uniquement des titres et phrases du doc 53.
- `test_imperium_home_bootstrap.py::test_home_bootstrap_docs_metadata_only_no_health_check_no_ai_n8n_no_cross_module_write` supprime: verifiait uniquement des phrases de docs Home Bootstrap.
- `test_imperium_frontend_asset_registry.py::test_frontend_asset_registry_docs_metadata_only_static_v1_placeholder_policy_and_no_filesystem_checks` supprime: verifiait uniquement des phrases de docs asset registry, deja couvert par la reponse API.
- `test_imperium_frontend_actions.py::test_frontend_actions_docs_metadata_only_static_v1_not_health_not_discovery` supprime: verifiait uniquement des phrases de docs actions, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
- `test_imperium_frontend_app_manifest.py::test_frontend_app_manifest_docs_metadata_only_static_v1_not_discovery_not_health` supprime: verifiait uniquement des phrases de docs app-manifest, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
- `test_imperium_frontend_design_handoff.py::test_frontend_design_handoff_is_declared_in_contracts_index_and_docs` partiellement supprime: gardait le contrat code `contracts/index`, mais retirait les assertions de phrases docs design handoff.
- `test_imperium_frontend_empty_states.py::test_frontend_empty_states_docs_static_ui_copy_not_personalized_recommendation` supprime: verifiait uniquement des phrases de docs empty-states, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
- `test_imperium_frontend_layout.py::test_frontend_layout_docs_metadata_only_static_v1_not_theme_not_health_not_discovery` supprime: verifiait uniquement des phrases de docs layout, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
- `test_imperium_frontend_metadata_contracts.py::test_frontend_metadata_contract_docs_explicitly_state_metadata_only_and_non_runtime_behavior` supprime: verifiait uniquement la lettre des docs 04/05 pour la couche metadata, deja couvert par la matrice de routes et les reponses API.
- `test_imperium_frontend_module_cards.py::test_frontend_module_cards_docs_metadata_only_static_v1_not_runtime_status_or_availability_or_personalization_or_feature_flag` supprime: verifiait uniquement des phrases de docs module-cards, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
- `test_imperium_frontend_navigation.py::test_frontend_navigation_docs_metadata_only_static_v1_not_health_not_discovery` supprime: verifiait uniquement des phrases de docs navigation, deja couvert cote code par endpoint/shape/read-only/no-DB-write.
