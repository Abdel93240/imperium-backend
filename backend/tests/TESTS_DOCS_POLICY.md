# Tests Docs Policy

Politique Q14: les tests pytest verrouillent les contrats de code reels. La conformite
des documents, leur vocabulaire exact et leur structure redactionnelle appartiennent aux
audits, pas a la CI applicative.

Suppressions de tests purement documentaires:
- `test_repo_invariants.py::test_patch_11f_pulse_docs_mark_future_surfaces_outside_v1_contract` supprime: verifiait uniquement la lettre et les sections des docs Pulse, sans contrat de code executable.
- `test_repo_invariants.py::test_home_bootstrap_docs_define_metadata_only_and_status_available_not_health_check` supprime: verifiait uniquement des phrases de docs pour Home Bootstrap, deja couvert cote code par les tests endpoint/service.
