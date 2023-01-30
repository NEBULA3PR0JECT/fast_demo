from const_vars import WF_TEMPLATE
from arango import ArangoClient
from database.arangodb import NEBULA_DB
import uuid
from nebula3_videoprocessing.videoprocessing.expert.videoprocessing_expert import VideoProcessingExpert
from visual_clues.visual_clues.run_visual_clues import TokensPipeline
from nebula3_llm_task.run_llm_task import test
import os 
import time
from nebula3_reid.facenet_pytorch.pipeline_task.reid_task import test_pipeline_task

class InitialPipeline:
    def __init__(self):
        self.dbname = "ipc_200"
        self.arango_host = "http://172.83.9.249:8529"
        self.client = ArangoClient(hosts=self.arango_host)
        self.db = self.client.db(self.dbname, username='nebula', password='nebula')
        self.wf_template = WF_TEMPLATE
        self.nre = NEBULA_DB()

    def validate_url(self, url_link):
        return url_link

    def init_pipeline(self, url_link):
        """
        Inserts Initial data to our pipelines document and returns pipeline_id
        """
        if url_link != '':
            movie_url = url_link
            if movie_url.split('.')[-1] == 'mp4' or movie_url.split('.')[-1] == 'avi' or "youtube" in movie_url:
                _movie = {"movie_id": "", "url": movie_url, "type": "movie"}
            else:
                _movie = {"movie_id": "", "url": movie_url, "type": "image"}
            pipeline_entry = self.wf_template.copy()
            pipeline_entry['inputs']['videoprocessing']['movies'] = [_movie]
            pipeline_entry['id'] = str(uuid.uuid4())
            pipeline_entry['_key'] = pipeline_entry['id']
            self.db.collection("pipelines").insert(pipeline_entry)
            pipeline_id = pipeline_entry['id']
            return pipeline_id
        else:
            return ''


def main():
    
    pipeline_instance = InitialPipeline()
    start_time = time.time()
    pipeline_id = pipeline_instance.init_pipeline('https://variety.com/wp-content/uploads/2017/01/john-wick-2.jpg') #"5b0c75bf-5fd6-4c1e-9f7e-5f51a9a96bd8"
    # Necessary for videoprocessing task
    os.environ['ARANGO_HOST'] = "172.83.9.249"
    os.environ['EXPERT_RUN_MODE'] = 'task'
    os.environ['PIPELINE_ID'] = pipeline_id
    
    videoprocessing_instance = VideoProcessingExpert()
    videoprocessing_instance.run_pipeline_task()

    test_pipeline_task(pipeline_id)
    # end_time2 = time.time() - start_time
    # print("Total time it took for videprocessing: {}".format(end_time2))
    # Get movie id for visual clues, reid and llm.
    pipeline_structure = pipeline_instance.nre.get_pipeline_structure(pipeline_id)
    movie_id = list(pipeline_structure['movies'].keys())[0]
    visual_clues_instance = TokensPipeline()
    visual_clues_instance.run_visual_clues_pipeline(movie_id)
    # run llm
    test()
    end_time = time.time() - start_time
    print("Total time it took for whole pipeline: {}".format(end_time))


    ##########################

    while True:
        time.sleep(1)
        rc = pipeline_instance.nre.get_doc_by_key({'_key': "123456789"}, "pipeline_url")
        url_link = rc["url_link"]

        if url_link:
            start_time = time.time()
            pipeline_id = pipeline_instance.init_pipeline(url_link) #"5b0c75bf-5fd6-4c1e-9f7e-5f51a9a96bd8"
            # Necessary for videoprocessing task
            os.environ['ARANGO_HOST'] = "172.83.9.249"
            os.environ['EXPERT_RUN_MODE'] = 'task'
            os.environ['PIPELINE_ID'] = pipeline_id
            videoprocessing_instance.run_pipeline_task()
            end_time2 = time.time() - start_time
            print("Total time it took for videprocessing: {}".format(end_time2))
            # Get movie id for visual clues, reid and llm.
            
            pipeline_structure = pipeline_instance.nre.get_pipeline_structure(pipeline_id)
            if pipeline_structure['movies']:
                movie_id = list(pipeline_structure['movies'].keys())[0]
                test_pipeline_task(pipeline_id)
                visual_clues_instance.run_visual_clues_pipeline(movie_id)
                # run llm
                test()
                end_time = time.time() - start_time
                print("Total time it took for whole pipeline: {}".format(end_time))

            rc2 = pipeline_instance.nre.get_doc_by_key({'_key': "123456789"}, "pipeline_url")
            cur_url_link = rc2["url_link"]
            pipeline_dict = dict()
            pipeline_dict["unique_key"] = rc["unique_key"]
            if cur_url_link == url_link: # if someone appends new image url before the previous one is done I want to keep it in queue.
                pipeline_dict["url_link"] = ""
                pipeline_instance.nre.write_doc_by_key(doc=pipeline_dict, collection_name="pipeline_url", key_list=['unique_key'])

        else:
            print("Waiting for URL...")

if __name__ == '__main__':
    main()