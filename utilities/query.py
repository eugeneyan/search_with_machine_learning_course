# A simple client for querying driven by user input on the command line.  Has hooks for the various
# weeks (e.g. query understanding).  See the main section at the bottom of the file
from opensearchpy import OpenSearch
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import argparse
import json
import os
from getpass import getpass
from urllib.parse import urljoin
import pandas as pd
import fileinput
import logging
import fasttext

from logger import logger


# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# logging.basicConfig(format='%(levelname)s:%(message)s')

# Import trained model. Set k_preds (number of predictions) and prob_threshold (probability threshold).
query_classifier: fasttext.FastText._FastText = fasttext.load_model('/workspace/models/query_classifier.bin')
k_preds = 5
prob_threshold = 0.5

# expects clicks and impressions to be in the row
def create_prior_queries_from_group(
        click_group):  # total impressions isn't currently used, but it mayb worthwhile at some point
    click_prior_query = ""
    # Create a string that looks like:  "query": "1065813^100 OR 8371111^89", where the left side is the doc id and the right side is the weight.  In our case, the number of clicks a document received in the training set
    if click_group is not None:
        for item in click_group.itertuples():
            try:
                click_prior_query += "%s^%.3f  " % (item.doc_id, item.clicks / item.num_impressions)

            except KeyError as ke:
                pass  # nothing to do in this case, it just means we can't find priors for this doc
    return click_prior_query


# expects clicks from the raw click logs, so value_counts() are being passed in
def create_prior_queries(doc_ids, doc_id_weights,
                         query_times_seen):  # total impressions isn't currently used, but it mayb worthwhile at some point
    click_prior_query = ""
    # Create a string that looks like:  "query": "1065813^100 OR 8371111^89", where the left side is the doc id and the right side is the weight.  In our case, the number of clicks a document received in the training set
    click_prior_map = ""  # looks like: '1065813':100, '8371111':809
    if doc_ids is not None and doc_id_weights is not None:
        for idx, doc in enumerate(doc_ids):
            try:
                wgt = doc_id_weights[doc]  # This should be the number of clicks or whatever
                click_prior_query += "%s^%.3f  " % (doc, wgt / query_times_seen)
            except KeyError as ke:
                pass  # nothing to do in this case, it just means we can't find priors for this doc
    return click_prior_query


# Hardcoded query here.  Better to use search templates or other query config.
def create_query(user_query, click_prior_query, filters, sort="_score", sortDir="desc", size=10, source=None, synonyms=False):
    if synonyms:
        name_field = 'name.synonyms'
        logger.info('Querying via synonyms')
    else:
        name_field = 'name'
    
    query_obj = {
        'size': size,
        "sort": [
            {sort: {"order": sortDir}}
        ],
        "query": {
            "function_score": {
                "query": {
                    "bool": {
                        "must": [

                        ],
                        "should": [  #
                            {
                                "match": {
                                    name_field : {
                                        "query": user_query,
                                        "fuzziness": "1",
                                        "prefix_length": 2,
                                        # short words are often acronyms or usually not misspelled, so don't edit
                                        "boost": 0.01
                                    }
                                }
                            },
                            {
                                "match_phrase": {  # near exact phrase match
                                    "name.hyphens": {
                                        "query": user_query,
                                        "slop": 1,
                                        "boost": 50
                                    }
                                }
                            },
                            {
                                "multi_match": {
                                    "query": user_query,
                                    "type": "phrase",
                                    "slop": "6",
                                    "minimum_should_match": "2<75%",
                                    "fields": [f"{name_field}^10", "name.hyphens^10", "shortDescription^5",
                                               "longDescription^5", "department^0.5", "sku", "manufacturer", "features",
                                               "categoryPath"]
                                }
                            },
                            {
                                "terms": {
                                    # Lots of SKUs in the query logs, boost by it, split on whitespace so we get a list
                                    "sku": user_query.split(),
                                    "boost": 50.0
                                }
                            },
                            {  # lots of products have hyphens in them or other weird casing things like iPad
                                "match": {
                                    "name.hyphens": {
                                        "query": user_query,
                                        "operator": "OR",
                                        "minimum_should_match": "2<75%"
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1,
                        "filter": filters  # Filters are added
                    }
                },
                "boost_mode": "multiply",  # how _score and functions are combined
                "score_mode": "sum",  # how functions are combined
                "functions": [
                    {
                        "filter": {
                            "exists": {
                                "field": "salesRankShortTerm"
                            }
                        },
                        "gauss": {
                            "salesRankShortTerm": {
                                "origin": "1.0",
                                "scale": "100"
                            }
                        }
                    },
                    {
                        "filter": {
                            "exists": {
                                "field": "salesRankMediumTerm"
                            }
                        },
                        "gauss": {
                            "salesRankMediumTerm": {
                                "origin": "1.0",
                                "scale": "1000"
                            }
                        }
                    },
                    {
                        "filter": {
                            "exists": {
                                "field": "salesRankLongTerm"
                            }
                        },
                        "gauss": {
                            "salesRankLongTerm": {
                                "origin": "1.0",
                                "scale": "1000"
                            }
                        }
                    },
                    {
                        "script_score": {
                            "script": "0.0001"
                        }
                    }
                ]

            }
        }
    }
    if click_prior_query is not None and click_prior_query != "":
        query_obj["query"]["function_score"]["query"]["bool"]["should"].append({
            "query_string": {
                # This may feel like cheating, but it's really not, esp. in ecommerce where you have all this prior data,  You just can't let the test clicks leak in, which is why we split on date
                "query": click_prior_query,
                "fields": ["_id"]
            }
        })
    if user_query == "*" or user_query == "#":
        # replace the bool
        try:
            query_obj["query"] = {"match_all": {}}
        except:
            logger.info("Couldn't replace query for *")
    if source is not None:  # otherwise use the default and retrieve all source
        query_obj["_source"] = source
            
    return query_obj


def search(client, user_query, index="bbuy_products", sort="_score", sortDir="desc", synonyms=False, query_filter=False):
    #### W3: classify the query and select categories up to the probability threshold
    filters = None
    if query_filter:
        query_categories, scores = query_classifier.predict(user_query, k=k_preds)
        logger.info(f'Classification result: {query_categories}, {scores}')
        
        cum_prob = 0
        category_list = []

        for category, score in zip(query_categories, scores):
            logger.info(f'Category: {category}, Score: {score}')
            
            category_list.append(category.replace('__label__', ''))
            cum_prob += score
            
            if cum_prob > prob_threshold:
                break
        logger.info(f'Category list: {category_list}, Cumulative probability: {cum_prob}')
        
    #### W3: create filters and boosts
    # Add query category as a filter (Note: The filters are part of the bool query in the query_obj, where query_obj["query"]["bool"]["filter"]])
    # https://www.elastic.co/guide/en/elasticsearch/reference/7.17/query-dsl-bool-query.html
        filters = [
                {'terms': {'categoryPathIds': category_list}}  # We can pass a list: https://stackoverflow.com/a/48616917/3611239
        ]
    
    # Note: you may also want to modify the `create_query` method above
    query_obj = create_query(user_query, click_prior_query=None, filters=filters, sort=sort, sortDir=sortDir, synonyms=synonyms, source=['name', 'shortDescription', 'categoryPathIds', 'image'])
    logger.debug(query_obj)
    response = client.search(query_obj, index=index)
    logger.debug(f'Response: {response}')
    if response and response['hits']['hits'] and len(response['hits']['hits']) > 0:
        hits = response['hits']['hits']
        logger.debug(json.dumps(response, indent=2))
        
    return response



if __name__ == "__main__":
    host = 'localhost'
    port = 9200
    auth = ('admin', 'admin')  # For testing only. Don't store credentials in code.
    parser = argparse.ArgumentParser(description='Build LTR.')
    general = parser.add_argument_group("general")
    general.add_argument("-i", '--index', default="bbuy_products",
                         help='The name of the main index to search')
    general.add_argument("-s", '--host', default="localhost",
                         help='The OpenSearch host name')
    general.add_argument("-p", '--port', type=int, default=9200,
                         help='The OpenSearch port')
    general.add_argument('--user',
                         help='The OpenSearch admin.  If this is set, the program will prompt for password too. If not set, use default of admin/admin')
    general.add_argument('--query', type=str, default='ipod',
                         help='The query to search.')
    general.add_argument('--synonyms', default=False, action='store_true',
                         help='Searches via the name.synonyms field instead of name.')
    general.add_argument('--query_filter', default=False, action='store_true',
                         help='Filters via the results from query classification.')


    args = parser.parse_args()

    if len(vars(args)) == 0:
        parser.print_usage()
        exit()

    host = args.host
    port = args.port
    if args.user:
        password = getpass()
        auth = (args.user, password)
    synonyms = args.synonyms
    query_filter = args.query_filter

    base_url = "https://{}:{}/".format(host, port)
    opensearch = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_compress=True,  # enables gzip compression for request bodies
        http_auth=auth,
        # client_cert = client_cert_path,
        # client_key = client_key_path,
        use_ssl=True,
        verify_certs=False,  # set to true if you have certs
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    index_name = args.index
    query = args.query
    # query_prompt = "\nEnter your query (type 'Exit' to exit or hit ctrl-c):"
    # print(query_prompt)
    # for line in fileinput.input():
    #     query = line.rstrip()
    #     if query == "Exit":
    #         break
    search(client=opensearch, user_query=query, index=index_name, synonyms=synonyms, query_filter=query_filter)

    # print(query_prompt)
