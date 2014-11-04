import boto, json, worker, os, entry, logging, sys, time
from boto import dynamodb
from boto.s3.key import Key
from boto import elastictranscoder

def get_type(filepath):
    """Checks the type of the resource.
    Currently only supports type 'image' and 'video'"""
    res = os.popen("file "+filepath).read()
    if 'image' in res:
        return 'image'
    else:
        return 'video'

def make_thumbnail(filepath):
    logging.basicConfig(filename='/var/log/rlab.log',level=logging.DEBUG)
    # This generates a thumbnail for an image in filepath 
    if filepath == '' or filepath == None:
        raise IOError('No filepath given')
    
    target = filepath
    
    if get_type(filepath) == 'image':
        # For image, we do a resize:
        tnpath = filepath +'-tn.png'
        cmd = 'convert '+ target +' -thumbnail 320x200 -size 320x200 xc:black +swap -gravity center -composite '+ tnpath
        os.system(cmd)
        # @TODO: handle command line error
        #if framepath != None:
            # clean-up temporary frame image
            #os.remove(framepath)
        return tnpath

def transcode(filepath, pipelineid, presetid):
    logging.basicConfig(filename='/var/log/rlab.log',level=logging.DEBUG)
    transcoded = filepath+"-tx.mp4"

    try:
        # I expect the following parameters to be defined in configuration:
        # - bucket: S3 bucket containing the media files
        # - table: meta data index DynamoDB table
        # - pipeline: Elastic Transcoder ID, aka Pipeline ID
        # - preset: Elastic Transcoder Preset ID
        # - region: AWS Region
        with open("/var/www/rlab.par") as data_file:
            config = json.load(data_file)
    except:
        logging.error("%s" , sys.exc_info())
        sys.exit(1)
 
    # Create a job in the Elastic Transcoder pipeline:
    boto.elastictranscoder.connect_to_region(config['region'])
    et = boto.elastictranscoder.layer1.ElasticTranscoderConnection()

    in_path = filepath
    out_path = filepath + "-tx.mp4"
    
    params_in = { 'Key': in_path,
        'FrameRate': 'auto',
        'Resolution': 'auto',
        'AspectRatio': 'auto',
        'Interlaced': 'auto',
        'Container': 'auto',
    }

    params_out = { 'Key': out_path,
        'ThumbnailPattern': in_path+'-{count}',
        'Rotate': 'auto',
        'PresetId': presetid
    }

    retval = et.create_job(pipeline_id=pipelineid,
            input_name=params_in,
            output=params_out)
    
    return transcoded

def transcode_video(uid):
    logging.basicConfig(filename='/var/log/rlab.log',level=logging.DEBUG)    

    try:
        # I expect the following parameters to be defined in configuration:
        # - bucket: S3 bucket containing the media files
        # - table: meta data index DynamoDB table
        # - pipeline: Elastic Transcoder ID, aka Pipeline ID
        # - preset: Elastic Transcoder Preset ID
        # - region: AWS Region
        with open("/var/www/rlab.par") as data_file:
            config = json.load(data_file)
    except:
        logging.error("%s" , sys.exc_info())
        sys.exit(1)

    bucket = boto.connect_s3().get_bucket(config['bucket'])
    dao = entry.EntryDAO(config['table'], config['bucket'], config['region'])

    if('pipeline' in config):
        pipelineID = config['pipeline']
    else: 
        pipelineID = '1375346013443-vgzqvn'

    if('preset' in config):
        presetID = config['preset']
    else:
        presetID = '1377592073187-ppmxyu'

    try:
        en = dao.get(uid)
        logging.info("loaded en from dao: %s", en)
        # 1. Download the file to be transcoded
        original = en['resource']
        key = bucket.get_key(en['resource'])
        # 2. Launch transcoding
        logging.info("Transcode starting-- %s", original)
        transcoded = transcode(original, pipelineID, presetID)
        logging.info("Transcode call completed -- %s", transcoded)
    except:
        logging.error("%s" , sys.exc_info())
            

def run():
    logging.basicConfig(filename='/var/log/rlab.log',level=logging.DEBUG)

"""
    entry = {'title': 'hardcoded coding',
                 'comment': 'mycomment',
                 'type': worker.get_type('20130808-141356-075164'),
                 'timestamp': '20130808131132',
                 'resource': '20130808-141356-075164',
                 'eid': "35f0c9abca678d0b141ab40792fcca02",
                 'eib': "35f0c9abca678d0b141ab40792fcca02"
                 }

    print entry

    transcode_video(entry['eid'])
"""

if __name__ == '__main__':
    os.environ['LD_LIBRARY_PATH'] = '/usr/local/lib'
    os.environ['PATH'] = os.environ['PATH'] + ':/usr/local/bin'
    run()
