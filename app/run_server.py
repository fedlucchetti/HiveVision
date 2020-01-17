from bson import json_util, ObjectId
from threading import Thread
from PIL import Image
import numpy as np
import base64
import flask
from flask import request
from flask_httpauth import HTTPBasicAuth
from users import User
from pymongo import MongoClient
from pymongo import errors
import redis
import uuid
import time
import json
import sys
import io
import os

#Image queue variables
IMAGE_WIDTH = 600
IMAGE_HEIGHT = 400
IMAGE_CHANS = 3
IMAGE_DTYPE = "float32"
IMAGE_QUEUE = "image_queue"
SERVER_SLEEP = 0.25
CLIENT_SLEEP = 0.25
BATCH_SIZE = 10

#DB variables - MongoDB auth can be changed during runtime in production with mongo cli
MON_USER = "teststore"
MON_PASS = "passwd"
MON_HOST = "mongo"
MON_PORT = 27017
mon_auth = 'mongodb://{}:{}@{}:{}'.format(MON_USER, MON_PASS, MON_HOST, str(MON_PORT))

RED_HOST = 'redis'
RED_PORT = '6379'

#Initial App Setup
app = flask.Flask(__name__)
db = redis.StrictRedis(host=RED_HOST, port=RED_PORT, db=0)
mon_client = MongoClient(mon_auth)
db_mon = mon_client['hivestore']
coll_store = db_mon['hivestore_coll1']
u = User(mon_client)
#auth = HTTPBasicAuth()

#MongoDB helper: this converts an ObjectId to its string, needed for safe jsonify usage
def oid_cleanup(docs):
    for i in docs:
        i['_id'] = ObjectId.__str__(i['_id'])
    return docs


#MongoDB helper: naive sanitizer for hive docs, goal is to limit tampering.
#Token based system needed when hives send data?
def sanitize_hive_doc(doc):
    if len(doc) == 13 \
        and sys.getsizeof(doc) < 1200:
        return True
    else:
        return False


def base64_encode_image(a):
    return base64.b64encode(a).decode("utf-8")


def base64_decode_image(a, dtype, shape):
    a = bytes(a, encoding="utf-8")
    a = np.frombuffer(base64.decodestring(a), dtype=dtype)
    a = a.reshape(shape)
    return a


def prepare_image(image, target):
    if image.mode != "RGB":
        image = image.convert("RGB")
    image = image.resize(target)
    image = np.expand_dims(image, axis=0)
    return image


#Part of the unused image classification queue. Good for later on. Adapted from
#  https://www.pyimagesearch.com/2018/01/29/scalable-keras-deep-learning-rest-api/
def classify_process():

    print("* Loading ndvi pipeline...")
    while True:
        queue = db.lrange(IMAGE_QUEUE, 0, BATCH_SIZE - 1)
        imageIDs = []
        batch = None
        for q in queue:
            q = json.loads(q.decode("utf-8"))
            image = base64_decode_image(q["image"], IMAGE_DTYPE,
                                        (1, IMAGE_HEIGHT, IMAGE_WIDTH, IMAGE_CHANS))
            if batch is None:
                batch = image
            else:
                batch = np.vstack([batch, image])
            imageIDs.append(q["id"])

        if len(imageIDs) > 0:
            print("* Batch size: {}".format(batch.shape))
            preds = '{"predictions": "true"}'
            results = preds

            for (imageID, resultSet) in zip(imageIDs, results):
                output = []

                for (imagenetID, label, prob) in resultSet:
                    r = {"label": label, "probability": float(prob)}
                    output.append(r)

                db.set(imageID, json.dumps(output))
            db.ltrim(IMAGE_QUEUE, len(imageIDs), -1)

        time.sleep(SERVER_SLEEP)

@app.route('/auth')
# @auth.login_required
def get_resource():
    #TODO
    return flask.jsonify({ 'data': 'Hello, %s!' % u.usernames}), 200

@app.route("/hello", methods=["GET"])
def hello():
    #Debug print, remove in production
    print('/hello * accessed by {} - {}'.format(request.environ['REMOTE_ADDR'],time.ctime()))
    result = "Hello to PlantHive's HiveVision API."
    return flask.jsonify(result), 200


@app.route("/testdb", methods=["GET"])
def testdb():
    dbres = db.set('testdb',1)
    info = db.info("Stats")
    mon_info = db_mon.command("serverStatus")
    if info and mon_info is not None:
        result = '{} * {} \n {}'.format(dbres, info['total_commands_processed'], \
                                        (mon_info['uptimeEstimate']/3600))
    else:
        result = 'DB problem'
        return flask.jsonify(result), 400
    return flask.jsonify(result), 200


@app.route("/hivestore_insert", methods=["POST"])
def hivestore_insert():
    if flask.request.method == "POST":
        locjson = flask.request.get_json(force=False)
        if locjson is None:
            flask.abort(400)
    if sanitize_hive_doc(locjson):
        #Move doc to db
        try:
            result = coll_store.insert(locjson)
        except errors.ServerSelectionTimeoutError as e:
            print(e)
            result = 'No object was inserted - MongoDB failure'
        except errors.InvalidDocument as e:
            print(e)
            result = 'No object was inserted - Invalid Document'
        response = flask.jsonify(result)
        response.status_code = 200
    else:
        result = 'No object was inserted - Invalid Document'
    return flask.jsonify(result), 400


#only for debugging purposes - delete in production
@app.route("/hivestore_getthemall", methods=["GET"])
def hivestore_getthemall():
    try:
        data = [doc for doc in coll_store.find()]
        data = oid_cleanup(data)
    except errors.OperationFailure as e:
        print(e)
        result = 'MongoDB failure'
    return flask.jsonify(data), 200


#this should be accessed only with an admin token. implement later
@app.route("/hivestore_counthives", methods=["GET"])
def hivestore_counthives():
    try:
        result = [i for i in coll_store.distinct('serialnumber')]
        result = len(result)
    except errors.OperationFailure as e:
        print(e)
        result = 'MongoDB counthives failure'
    return flask.jsonify(result), 200


#unused image queue route. useful for image-based stuff
@app.route("/test", methods=["POST"])
def predict():
    data = {"success": False}

    if flask.request.method == "POST":
        if flask.request.files.get("image"):
            image = flask.request.files["image"].read()
            image = Image.open(io.BytesIO(image))
            image = prepare_image(image, (IMAGE_WIDTH, IMAGE_HEIGHT))
            image = image.copy(order="C")
            k = str(uuid.uuid4())
            d = {"id": k, "image": base64_encode_image(image)}
            t = db.rpush(IMAGE_QUEUE, json.dumps(d))
            #print(string(t))
            while True:
                # attempt to grab the output predictions
                output = db.get(k)

                if output is not None:
                    # add the output predictions to our data
                    # dictionary so we can return it to the client
                    output = output.decode("utf-8")
                    data["predictions"] = json.loads(output)
                    #db.delete(k)
                    break
                time.sleep(CLIENT_SLEEP)
        data["success"] = True
    return flask.jsonify(data)


#this only runs if run_server.py is run directly (at http://localhost:5000), not for production use!!!
if __name__ == "__main__":
    print("* Starting backend service...")
    t = Thread(target=classify_process, args=())
    t.daemon = True
    t.start()

    print("* Starting web service...")
    app.run(host='localhost')
