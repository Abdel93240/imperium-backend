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
