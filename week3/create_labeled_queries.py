import os
import argparse
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import csv

from logger import logger

# Useful if you want to perform stemming.
import nltk
stemmer = nltk.stem.PorterStemmer()

categories_file_name = r'/workspace/datasets/product_data/categories/categories_0001_abcat0010000_to_pcmcat99300050000.xml'

queries_file_name = r'/workspace/datasets/train.csv'
output_file_name = r'/workspace/datasets/fasttext/labeled_queries.txt'

parser = argparse.ArgumentParser(description='Process arguments.')
general = parser.add_argument_group("general")
general.add_argument("--min_queries", default=1,  help="The minimum number of queries per category label (default is 1)")
general.add_argument("--output", default=output_file_name, help="the file to output to")

args = parser.parse_args()
output_file_name = args.output

if args.min_queries:
    min_queries = int(args.min_queries)

# The root category, named Best Buy with id cat00000, doesn't have a parent.
root_category_id = 'cat00000'

tree = ET.parse(categories_file_name)
root = tree.getroot()

# Parse the category XML file to map each category id to its parent category id in a dataframe.
categories = []
parents = []
for child in root:
    id = child.find('id').text
    cat_path = child.find('path')
    cat_path_ids = [cat.find('id').text for cat in cat_path]
    leaf_id = cat_path_ids[-1]
    if leaf_id != root_category_id:
        categories.append(leaf_id)
        parents.append(cat_path_ids[-2])
parents_df = pd.DataFrame(list(zip(categories, parents)), columns =['category', 'parent'])

# Read the training data into pandas, only keeping queries with non-root categories in our category tree.
queries_df = pd.read_csv(queries_file_name)[['category', 'query']]
queries_df = queries_df[queries_df['category'].isin(categories)]
logger.info(f'Number of queries: {len(queries_df):,}')

# IMPLEMENT ME: Convert queries to lowercase, and optionally implement other normalization, like stemming.
# Convert queries to lower case, replace non-alphanumeric chars with a space and replace consecutive spaces with a single space
queries_df['query'] = queries_df['query'].str.lower().str.replace('[^a-z0-9]+', ' ', regex=True).str.replace(' +', ' ', regex=True)

# Use the nltk stemmer to stem all query tokens
queries_df['query'] = queries_df['query'].apply(lambda x: ' '.join([stemmer.stem(word) for word in x.split()]))
logger.info('Queries normalized')

assert queries_df['query'].loc[1855395] == 'beat by dr dre monster pro over the ear headphon'

# IMPLEMENT ME: Roll up categories to ancestors to satisfy the minimum number of queries per category.
query_count = queries_df.groupby('category').agg(query_count=('query', 'count')).reset_index()
query_count.loc[query_count['category'] == 'abcat0701001', 'query_count'].sum() == 13830

# Roll up categories to ancestors to satisfy the minimum number of queries per category.
while True:
    # Count the number of rows per query
    query_count = queries_df.groupby('category').agg(query_count=('query', 'count')).reset_index()
    
    # Merge in query counts and parent category. Substitute parent category with root category id if missing
    queries_df = queries_df.merge(query_count, on='category', how='left').merge(parents_df, on='category', how='left')
    queries_df.loc[queries_df['parent'].isnull(), 'parent'] = root_category_id
    
    # If category count less than min_queries, update category with parent
    queries_df.loc[queries_df['query_count'] < min_queries, 'category'] = queries_df['parent']
    
    # Keep only necessary queries
    queries_df = queries_df[['category', 'query']]
    
    # If no query counts are below min queries, end loop
    if (query_count['query_count'] < min_queries).sum() == 0:
        break
logger.info('Categories rolled up')

# Create labels in fastText format.
queries_df['label'] = '__label__' + queries_df['category']

# Output labeled query data as a space-separated file, making sure that every category is in the taxonomy.
queries_df = queries_df[queries_df['category'].isin(categories)]
queries_df['output'] = queries_df['label'] + ' ' + queries_df['query']
queries_df[['output']].to_csv(output_file_name, header=False, sep='|', escapechar='\\', quoting=csv.QUOTE_NONE, index=False)
