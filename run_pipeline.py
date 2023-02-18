from const_vars import WF_TEMPLATE
from arango import ArangoClient
from database.arangodb import NEBULA_DB
import uuid
from nebula3_videoprocessing.videoprocessing.expert.videoprocessing_expert import VideoProcessingExpert
from visual_clues.visual_clues.run_visual_clues import TokensPipeline
from nebula3_fusion.run_fusion_task import test as fusion_test
from nebula3_llm_task.run_llm_task import test as llm_test
from visual_clues.visual_clues.run_sprint4 import test as visual_clues_test
import os 
import time
from nebula3_reid.facenet_pytorch.pipeline_task.reid_task import test_pipeline_task
from nebula3_reid.facenet_pytorch.examples.reid_inference_mdf import FaceReId
from nebula3_llm_task.llm_orchestration import LlmTaskInternal

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

    def init_pipeline(self, url_link, pipeline_id = ''):
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
            if not pipeline_id:
                pipeline_entry['id'] = str(uuid.uuid4())
            else:
                pipeline_entry['id'] = pipeline_id
            pipeline_entry['_key'] = pipeline_entry['id']
            self.db.collection("pipelines").insert(pipeline_entry)
            pipeline_id = pipeline_entry['id']
            return pipeline_id
        else:
            return ''
    
    def update_pipeline_status(self, current_task):
        pipeline_dict = dict()
        pipeline_dict["unique_key"] = "123456789"
        pipeline_dict["url_link"] = ""
        pipeline_dict["pipeline_id"] = ""
        pipeline_dict["fetching"] = True
        pipeline_dict["current_task"] = current_task
        self.nre.write_doc_by_key(doc=pipeline_dict, collection_name="pipeline_url", key_list=['unique_key'])
    



def main():
    
    videoprocessing_instance = VideoProcessingExpert()
    pipeline_instance = InitialPipeline()
    pipeline_id = pipeline_instance.init_pipeline('https://d1nslcd7m2225b.cloudfront.net/Pictures/480xany/8/6/3/1388863_fullriverred_499613.jpeg') #"5b0c75bf-5fd6-4c1e-9f7e-5f51a9a96bd8"
    # Necessary for videoprocessing task
    os.environ['ARANGO_HOST'] = "172.83.9.249"
    os.environ['EXPERT_RUN_MODE'] = 'task'
    os.environ['PIPELINE_ID'] = pipeline_id
    
    start_time = time.time()
    videoprocessing_instance.run_pipeline_task()
    end_time = time.time() - start_time
    # print("Video #{} took: {}".format(idx, end_time))

    # run reid
    reid_instance = FaceReId()
    test_pipeline_task(pipeline_id, reid_instance)
    # end_time2 = time.time() - start_time
    # print("Total time it took for videprocessing: {}".format(end_time2))
    # Get movie id for visual clues, reid and llm.
    pipeline_structure = pipeline_instance.nre.get_pipeline_structure(pipeline_id)
    movie_id = list(pipeline_structure['movies'].keys())[0]
    # run visual_clues test
    visual_clues_instance = TokensPipeline()
    visual_clues_test(visual_clues_instance)
    # run fusion
    fusion_test()
    # run llm
    llm_instance = LlmTaskInternal()
    llm_test(llm_instance)
    end_time = time.time() - start_time
    print("Total time it took for whole pipeline: {}".format(end_time))


    ##########################
    # Clean the document first from previous url and pipeline_id if it wasn't empty.
    pipeline_dict = dict()
    pipeline_dict["unique_key"] = "123456789"
    pipeline_dict["url_link"] = ""
    pipeline_dict["pipeline_id"] = ""
    pipeline_dict["fetching"] = False
    pipeline_dict["current_task"] = ""
    pipeline_instance.nre.write_doc_by_key(doc=pipeline_dict, collection_name="pipeline_url", key_list=['unique_key'])

    while True:
        time.sleep(1)
        rc = pipeline_instance.nre.get_doc_by_key({'_key': "123456789"}, "pipeline_url")
        pipeline_id = ''
        url_link = ''
        if rc:
            url_link = rc["url_link"]
            if rc["pipeline_id"]: # this is for my web gui
                pipeline_id = pipeline_instance.init_pipeline(url_link, rc["pipeline_id"])
            else: # This is for 8032 - it doesnt append pipeline id to the pipeline_url document..
                pipeline_id = pipeline_instance.init_pipeline(url_link)


        if url_link:
            start_time = time.time() #"5b0c75bf-5fd6-4c1e-9f7e-5f51a9a96bd8")
            # Necessary for videoprocessing task
            os.environ['ARANGO_HOST'] = "172.83.9.249"
            os.environ['EXPERT_RUN_MODE'] = 'task'
            os.environ['PIPELINE_ID'] = pipeline_id
            videoprocessing_instance.run_pipeline_task()
            pipeline_instance.update_pipeline_status("videoprocessing")
            end_time2 = time.time() - start_time
            print("Total time it took for videprocessing: {}".format(end_time2))
            # Get movie id for visual clues, reid and llm.
            
            pipeline_structure = pipeline_instance.nre.get_pipeline_structure(pipeline_id)
            if pipeline_structure['movies']:
                movie_id = list(pipeline_structure['movies'].keys())[0]

                # run reid
                start_time_reid = time.time()
                test_pipeline_task(pipeline_id, reid_instance)
                pipeline_instance.update_pipeline_status("reid")
                end_time2 = time.time() - start_time_reid
                print("Total time it took for REID: {}".format(end_time2))

                # run visual_clues 
                start_time_visual_clues = time.time()
                visual_clues_test(visual_clues_instance)
                pipeline_instance.update_pipeline_status("visual_clues")
                end_time2 = time.time() - start_time_visual_clues
                print("Total time it took for Visual Clues: {}".format(end_time2))
                
                # run fusion
                start_time_fusion = time.time()
                fusion_test()
                pipeline_instance.update_pipeline_status("fusion")
                end_time2 = time.time() - start_time_fusion
                print("Total time it took for FUSION: {}".format(end_time2))
                
                # run llm
                start_time_llm = time.time()
                llm_test(llm_instance)
                pipeline_instance.update_pipeline_status("llm")
                end_time2 = time.time() - start_time_llm
                print("Total time it took for LLM Task: {}".format(end_time2))

                end_time = time.time() - start_time
                print("Total time it took for whole pipeline: {}".format(end_time))

            time.sleep(2)
            rc2 = pipeline_instance.nre.get_doc_by_key({'_key': "123456789"}, "pipeline_url")
            cur_url_link = rc2["url_link"]
            pipeline_dict = dict()
            pipeline_dict["unique_key"] = rc["unique_key"]
            
            pipeline_dict["url_link"] = ""
            pipeline_dict["pipeline_id"] = ""
            pipeline_dict["fetching"] = False
            pipeline_dict["current_task"] = "done"
            pipeline_instance.nre.write_doc_by_key(doc=pipeline_dict, collection_name="pipeline_url", key_list=['unique_key'])

        else:
            print("Waiting for URL...")

if __name__ == '__main__':
    main()
