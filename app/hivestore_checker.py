import urllib3
import json

#This tool can be used to input documents and test the store. Just copy/paste the json in the doc.
url = 'localhost:5000/hivestore_insert'
doc = {}
http = urllib3.PoolManager()


def insert_json():
    enc_data = json.dumps(doc).encode('utf-8')
    r = http.request('POST',
                     url,
                     body=enc_data,
                     headers={'Content-Type': 'application/json'}
                     )
    return


if __name__ == '__main__':
    for i in range(10):
        insert_json()
