#!/bin/bash
set -e
if [ $# -ne 3 ]; then
  echo "Usage: tokenize_corpus.sh <CORPUS_DIR> <PATH_OF_STOPWORDS_FILE> <VOCAB_DIR>"
  exit 1
fi
python3 tokenize_corpus.py "$1" "$2" "$3"
