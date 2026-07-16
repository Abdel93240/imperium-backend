#!/usr/bin/env bash
# Pré-vol du serving embeddings : refuse de démarrer hors Tailscale ou sans modèle.
set -euo pipefail

: "${EMBEDDINGS_BIND_ADDR:?EMBEDDINGS_BIND_ADDR manquant (IP Tailscale de Tower)}"
: "${EMBEDDINGS_MODEL_GGUF:?EMBEDDINGS_MODEL_GGUF manquant}"
: "${LLAMA_SERVER_BIN:?LLAMA_SERVER_BIN manquant}"

if [[ "$EMBEDDINGS_BIND_ADDR" == "0.0.0.0" || "$EMBEDDINGS_BIND_ADDR" == "::" ]]; then
  echo "REFUS: le serving embeddings ne s'expose que sur l'IP Tailscale, jamais 0.0.0.0" >&2
  exit 1
fi

# L'IP doit appartenir au range Tailscale (100.64.0.0/10) ou être localhost (tests).
if [[ "$EMBEDDINGS_BIND_ADDR" != 127.* && "$EMBEDDINGS_BIND_ADDR" != 100.* ]]; then
  echo "REFUS: $EMBEDDINGS_BIND_ADDR n'est ni localhost ni une IP Tailscale (100.64/10)" >&2
  exit 1
fi

[[ -x "$LLAMA_SERVER_BIN" ]] || { echo "llama-server introuvable: $LLAMA_SERVER_BIN" >&2; exit 1; }
[[ -f "$EMBEDDINGS_MODEL_GGUF" ]] || { echo "Modèle GGUF introuvable: $EMBEDDINGS_MODEL_GGUF" >&2; exit 1; }
exit 0
