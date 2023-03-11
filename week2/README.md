## Hov to add a synonym token filter
- Follow the example from: https://www.elastic.co/guide/en/elasticsearch/reference/7.17/analysis-synonym-tokenfilter.html

```json
# Example
PUT /test_index
{
  "settings": {
    "index": {
      "analysis": {
        "analyzer": {
          "synonym": {
            "tokenizer": "whitespace",
            "filter": [ "lowercase", "stemmer", "synonym" ]
          }
        },
            "filter": {
            "synonym": {
                "type": "synonym",
                "synonyms_path": "synonyms.csv"
            }
            }
      }
    }
  }
}
```

- Test if it's working
```json
GET /test_index/_analyze
{
  "analyzer": "synonym",
  "explain": "true",
  "text": ["georgia"]
}

...

 "name": "synonym",
"tokens": [
{
"token": "georgia",
"start_offset": 0,
"end_offset": 7,
"type": "word",
"position": 0,
"bytes": "[67 65 6f 72 67 69 61]",
"keyword": false,
"positionLength": 1,
"termFrequency": 1
},
{
"token": "florida",
"start_offset": 0,
"end_offset": 7,
"type": "SYNONYM",
"position": 0,
"bytes": "[66 6c 6f 72 69 64 61]",
"keyword": false,
"positionLength": 1,
"termFrequency": 1
},
{
"token": "michigan",
"start_offset": 0,
"end_offset": 7,
"type": "SYNONYM",
"position": 0,
"bytes": "[6d 69 63 68 69 67 61 6e]",
"keyword": false,
"positionLength": 1,
"termFrequency": 1
},
{
"token": "iowa",
"start_offset": 0,
"end_offset": 7,
"type": "SYNONYM",
"position": 0,
"bytes": "[69 6f 77 61]",
"keyword": false,
"positionLength": 1,
"termFrequency": 1
},
{
"token": "miami",
"start_offset": 0,
"end_offset": 7,
"type": "SYNONYM",
"position": 0,
"bytes": "[6d 69 61 6d 69]",
"keyword": false,
"positionLength": 1,
"termFrequency": 1
},
...
```