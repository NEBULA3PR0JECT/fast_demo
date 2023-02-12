from flask import Flask, request, jsonify
from flask_cors import CORS

from typing import List
from flask_arango import Arango
from arango import ArangoClient
import uuid
import os
import json
# Configuration
arango_host = "http://172.83.9.249:8529"
dbname = 'ipc_200'

app = Flask(__name__)
app.config.from_object(__name__)
arango = Arango(app)
cors = CORS(app)

wf_template = {
    "movies": {},
    "tasks": {},
    "inputs": {
        "videoprocessing": {
            "is_async": 'true',
            "movies": [{"movie_id": "", "url": '', "type": "image"}],
            "output": "db",
            "overwrite": 'true',
            "save_movies": 'true'
        }
    }
}

triplets_graph = {
    'graph': {
        'nodes': [

        ],
        'edges': [

        ],
    }
}

node_to_index = dict()

client = ArangoClient(hosts=arango_host)
db = client.db(dbname, username='nebula', password='nebula')

teset = dict()

def get_pipeline_data():
    pipeline_structure = None
    pipeline_structure = get_doc_by_key({'_key': '123456789'}, "pipeline_url")
    return pipeline_structure

def get_processed_image_url(movie_id):
    movie_structure = get_doc_by_key({'_id': movie_id}, "Movies")
    url_path = ''
    if movie_structure:
        postfix_url_path = movie_structure["url_path"][1:]
        prefix_url_path = "http://74.82.29.209:9000/"
        url_path = os.path.join(prefix_url_path, postfix_url_path)
        print("Retrieved URL Path: {}".format(url_path))
    return url_path

def get_llm_generated_text(movie_id):
    llm_structure = get_doc_by_key({'movie_id': movie_id}, "s4_llm_output")
    candidate = ''
    if llm_structure:
        candidate = llm_structure["candidate"]
        print("Retrieved Candidate: {}".format(candidate))
    return candidate

def get_llm_generated_triplets(movie_id):
    llm_structure = get_doc_by_key({'movie_id': movie_id}, "s4_llm_output")
    triplets = ''
    if llm_structure:
        triplets = llm_structure["triplets"]
        print("Retrieved Triplets: (Showing just first one) {}".format(triplets[0]))
    return triplets


# d07d980c-1c55-430f-8f6c-52953e918226
def get_doc_by_key2(key_dict: dict, collection: str) -> List:
    return db.collection(collection).find(key_dict)        

def get_doc_by_key(*args, **kwargs) -> dict:
    results = get_doc_by_key2(*args, **kwargs)
    if results:
        return results.pop()
    else:
        return None

def get_movie_id(pipeline_id):
    pipeline_structure = get_doc_by_key({'_key': pipeline_id}, "pipelines")
    movies = ''
    if pipeline_structure:
        movies = pipeline_structure["movies"]
    movie_id = ''
    if movies:
        movie_id = list(movies.keys())[0]
        print("Retrieved Movie ID: {}".format(movie_id))
    else:
        print("Couldn't retrieve Movie ID!")
    return movie_id

def update_db_with_new_data(url_link, pipeline_id):
    pipeline_dict = dict()
    pipeline_dict["unique_key"] = "123456789"
    pipeline_dict["url_link"] = url_link
    pipeline_dict["pipeline_id"] = pipeline_id
    pipeline_dict["fetching"] = True
    write_doc_by_key(db=db, doc=pipeline_dict, collection_name="pipeline_url", key_list=['unique_key'])
    print("Added to DB for fast image processing.")

def create_graph(triplets):
    counter = 0

    for tripletIdx, triplet in enumerate(triplets):
        # Add all the nodes and its edges to the triplets graph
        if triplet[0] not in node_to_index:
            node_to_index[triplet[0]] = tripletIdx
            triplets_graph["graph"]["nodes"].append(
                {'id': counter, 'label': triplet[0], 'color': '#e04141'}
            )
            triplets_graph["graph"]["nodes"].append(
                {'id': counter + 1, 'label': triplet[1], 'color': '#e09c41'}
            )
            triplets_graph["graph"]["nodes"].append(
                {'id': counter + 2, 'label': triplet[2], 'color': '#e0df41'}
            )
            triplets_graph["graph"]["edges"].append(
                {'from': counter, 'to': counter + 1}
            )
            triplets_graph["graph"]["edges"].append(
                {'from': counter + 1, 'to': counter + 2}
            )
            counter += 3
        else:  # Add only second and third node, and append the edges of the node which is already found.
            node_triple_idx = node_to_index[triplet[0]]
            triplets_graph["graph"]["nodes"].append(
                {'id': counter, 'label': triplet[1], 'color': '#e09c41'}
            )
            triplets_graph["graph"]["nodes"].append(
                {'id': counter + 1, 'label': triplet[2], 'color': '#e0df41'}
            )
            triplets_graph["graph"]["edges"].append(
                {'from': node_triple_idx, 'to': counter}
            )
            triplets_graph["graph"]["edges"].append(
                {'from': counter, 'to': counter + 1}
            )
            counter += 2
    return triplets_graph
    
    


def write_doc_by_key(db, doc , collection_name: str, overwrite : bool = True, key_list: List = []) -> bool:
        if not db.has_collection(collection_name):
            db.create_collection(collection_name)
        collection = db.collection(collection_name)        
        key_dict = {k: doc[k] for k in key_list}
        curr_doc = collection.find(key_dict) if key_dict else None
        if not curr_doc:           
            result = collection.insert(doc)
            return result, True
        assert len(curr_doc) <= 1
        if curr_doc and overwrite:   #update doc that exists
            curr_doc = curr_doc.pop()
            update_doc = {**curr_doc, **doc}
            result = collection.update(update_doc)
            return result, True

@app.route('/get_fetching_status', methods=["POST"])
def get_fetching_status_():
    if request.method == 'POST':
        test = request.get_json(force=True)
        pipeline_data = get_pipeline_data()
        fetching_status = pipeline_data['fetching']
    return jsonify(fetching_status = fetching_status)

@app.route('/get_task_status', methods=["POST"])
def get_task_status_():
    if request.method == 'POST':
        test = request.get_json(force=True)
        pipeline_data = get_pipeline_data()
        current_task = pipeline_data['current_task']
    return jsonify(current_task = current_task)
    
@app.route('/insert_pipeline_id', methods=["POST", "GET"])
def insert_pipeline_id_():
    if request.method == 'POST':
        url_link_json = request.get_json(force=True)
        url_link = url_link_json['urlLink']
        print("Recieved URL Link: {}".format(url_link))
        pipeline_entry = wf_template
        pipeline_entry['inputs']['videoprocessing']['movies'][0]["url"] = url_link
        pipeline_entry['id'] = str(uuid.uuid4())
        pipeline_entry['_key'] = pipeline_entry['id']
        print(pipeline_entry)
        # db.collection("pipelines").insert(pipeline_entry)
        print("Successfully inserted pipeline id: {} to database.".format(pipeline_entry['id']))
        update_db_with_new_data(url_link, pipeline_entry['id'])

        # get_movie_id(pipeline_entry['id'])
    
    return jsonify(pipeline_id = pipeline_entry['id'])


@app.route('/get_generated_caption_url', methods=["POST"])
def get_generated_caption_url_():
    if request.method == 'POST':
        movie_id = ''
        pipeline_id = request.get_json(force=True)
        print("Pipeline ID to get Movies: {}".format(pipeline_id))
        if pipeline_id:
            movie_id = get_movie_id(pipeline_id)
        image_url = ''
        if movie_id:
            image_url = get_processed_image_url(movie_id)
            print(image_url)
    return jsonify(image_url = image_url)

@app.route('/get_generated_triplets', methods=["POST"])
def indeget_generated_triplets_():
    if request.method == 'POST':
        pipeline_id = request.get_json(force=True)
        movie_id = ''
        print("Pipeline ID to get Movies: {}".format(pipeline_id))
        if pipeline_id:
            movie_id = get_movie_id(pipeline_id)
        triplets = []
        if movie_id:
            triplets = get_llm_generated_triplets(movie_id)
            if triplets:
                triplets = create_graph(triplets)
    return jsonify(triplets = triplets)

@app.route('/get_generated_text', methods=["POST"])
def get_generated_text_():
    if request.method == 'POST':
        pipeline_id = request.get_json(force=True)
        movie_id = ''
        print("Pipeline ID to get Movies: {}".format(pipeline_id))
        if pipeline_id:
            movie_id = get_movie_id(pipeline_id)
        candidate = ''
        if movie_id:
            candidate = get_llm_generated_text(movie_id)
        print(candidate)
    return jsonify(candidate = candidate)

if __name__ == "__main__":
    app.run(host="0.0.0.0")