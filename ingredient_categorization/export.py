import ast

import pandas as pd


SRC = 'RecipeNLG_dataset.csv'
OUT_DIR = 'exports'

df = pd.read_csv(SRC)

ner_lists = df['NER'].dropna().apply(ast.literal_eval)
unique_ner = pd.Series(ner_lists.explode().dropna().unique(), name='NER')
unique_ner.to_csv('unique_values.csv', index=False)

