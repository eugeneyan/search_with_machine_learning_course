import os
import argparse
from pathlib import Path

def transform_training_data(title, comment):
    # IMPLEMENT
    return title + ' ' + comment

def transform_rating(rating, bucket_rating=False):
    if not bucket_rating:
        return rating
    
    else:
        _rating = float(rating)
        if _rating >= 4:
            return 'positive'
        elif _rating <= 2:
            return 'negative'
        else:
            return 'neutral'


# Directory for review data
directory = r'/workspace/datasets/product_data/reviews/'
parser = argparse.ArgumentParser(description='Process some integers.')
general = parser.add_argument_group("general")
general.add_argument("--input", default=directory,  help="The directory containing reviews")
general.add_argument("--output", default="/workspace/datasets/fasttext/output.fasttext", help="the file to output to")
general.add_argument("--bucket_rating", default=False, action='store_true', 
                     help='Convert the rating to bins of positive, neutral, and negative')

args = parser.parse_args()
output_file = args.output
path = Path(output_file)
output_dir = path.parent
if os.path.isdir(output_dir) == False:
        os.mkdir(output_dir)

if args.input:
    directory = args.input


print("Writing results to %s" % output_file)
with open(output_file, 'w') as output:
    for filename in os.listdir(directory):
        if filename.endswith('.xml'):
            with open(os.path.join(directory, filename)) as xml_file:
                for line in xml_file:
                    if '<rating>'in line:
                        rating = line[12:15]
                    elif '<title>' in line:
                        title = line[11:len(line) - 9]
                    elif '<comment>' in line:
                        comment = line[13:len(line) - 11]
                    elif '</review>'in line:
                        output.write("__label__%s %s\n" % (transform_rating(rating, args.bucket_rating), transform_training_data(title, comment)))
