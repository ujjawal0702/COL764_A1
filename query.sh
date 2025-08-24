#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: tokenize_corpus.sh <CORPUS_DIR> <PATH_OF_STOPWORDS_FILE> <VOCAB_DIR>"
  exit 1
fi

CORPUS_DIR="$1"
STOPWORDS_FILE="$2"
VOCAB_DIR="$3"

mkdir -p "$VOCAB_DIR"

python3 tokenize_corpus.py "$CORPUS_DIR" "$STOPWORDS_FILE" "$VOCAB_DIR"
