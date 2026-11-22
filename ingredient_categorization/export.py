import ast
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'RecipeNLG_dataset.csv'
OUT = HERE / 'unique_values.csv'

df = pd.read_csv(SRC)

ner_lists = df['NER'].dropna().apply(ast.literal_eval)
# unique() keeps first-seen order. Batch numbers in labeled/ and labeled_manual/ depend on this
# exact row order, so don't sort or reshuffle.
unique_ner = pd.Series(ner_lists.explode().dropna().unique(), name='NER')
unique_ner.to_csv(OUT, index=False)
