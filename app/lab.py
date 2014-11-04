# web framework-related imports
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from datetime import datetime
import os, logging, json, sys

# AWS-related imports
import boto, boto.utils

# application-related imports
from entry import EntryDAO
import worker

#
# initialization
#
application = Flask(__name__)
application.config['UPLOAD_FOLDER'] = "/tmp/"
application.config['PARAM_FILE'] = "/var/www/rlab.par"
application.logger.addHandler(logging.StreamHandler())
application.logger.setLevel(logging.DEBUG)
logging.basicConfig(filename='/var/log/rlab.log',level=logging.INFO)

try:
    # The following parameters are expected to be defined in user_data:
    # - bucket: S3 bucket containing the media files
    # - table: meta data index DynamoDB table
    # - distrib: CloudFront distrib for video streaming
    # - pipeline: pipeline ID for Elastic Transcoder
    # - preset: preset ID for Elastic Transcoder
    # - region: AWS Region
    application.logger.info(application.config['PARAM_FILE'])
    with open(application.config['PARAM_FILE']) as data_file:
        config = json.load(data_file)
    application.logger.info("config: %s", config)

except:
    application.logger.error("%s" , sys.exc_info())
    sys.exit(1)

__TABLE = config['table'] 
__BUCKET = config['bucket']
__DISTRIB = config.get('distrib', None)
__PIPELINE = config.get('pipeline', None)
__PRESET = config.get('preset', None)
__REGION = config.get('region', None)
application.logger.error("__TABLE: %s", __TABLE)
application.logger.error("__BUCKET: %s", __BUCKET)
application.logger.error("__DISTRIB: %s", __DISTRIB)
application.logger.error("__PIPELINE: %s", __PIPELINE)
application.logger.error("__PRESET: %s", __PRESET)
application.logger.error("__REGION: %s", __REGION)


__DAO = EntryDAO(__TABLE, __BUCKET, __REGION)


application.logger.error("__TABLE: %s", __TABLE)
application.logger.error("__BUCKET: %s", __BUCKET)
application.logger.error("__DISTRIB: %s", __DISTRIB)
application.logger.error("__PIPELINE: %s", __PIPELINE)
application.logger.error("__PRESET: %s", __PRESET)
application.logger.error("__REGION: %s", __REGION)
application.logger.error("__DAO: %s", __DAO)

#
# Request handlers
#

@application.before_request
def before_request():
    """Decorator executed before each HTTP request"""
    # @TODO is it good practice to open a DyDB connection for each request? Can we cache/pool those objects?
    g.dao = __DAO
    g.bucket = __BUCKET
    g.distrib = __DISTRIB
    g.pipeline = __PIPELINE
    g.preset = __PRESET
    g.region = __REGION

@application.route('/')
def route_home():
    """List of media entries for the specific page"""
    return render_template('index.html', entries=g.dao.list(), bucket=g.bucket)

@application.route('/view/<e_unid>')
def route_view(e_unid):
    """Views a specific entry
    @NOTE: do we need to support entry updates?    
    :type e_unid: string
    :param key_name: The unique Id of the entry to view"""
    # @TODO: we need to include the relevant information for "NEXT" and "PREVIOUS" actions, or it's too much pre-compute?
    return render_template('view.html',
                           entry = g.dao.get(e_unid),
                           bucket = g.bucket,
                           distrib = g.distrib)

@application.route('/delete/<e_unid>')
def route_delete(e_unid):
    """Deletes a specific entry
    (Unfortunately web browsers can't send DELETE requests.)
    @special thanks to Nicola Previati for his deep programming skills
    :type e_unid: string
    :param key_name: The unique Id of the entry to delete"""
    g.dao.delete(e_unid)
    return redirect(url_for('route_home'))

@application.route('/add', methods=['GET', 'POST'])
def route_add():
    """File upload route.
    If it's an HTTP GET request, returns the file upload form
    If it's an HTTP POST, extract the file and params and add it to the system. Then redirect to the "view" page with the entry ID"""
    if request.method == 'POST' :
        rfile = request.files['file']
        if rfile.read(1) == '':
            # usually, we shouldn't get to that ode. The web interface should
            # have some javascript control blocking form submits without files
            application.logger.warn('Received empty file')
            # @TODO return something more understandable for the user than an HTTP error code.
            abort(400)
        else:
            # if I can read 1 byte, the file is not empty ... so let's put back
            # at the beginning of the file the read pointer so we can save the
            # complete contents.
            rfile.seek(0)
        
        application.logger.info("-> Call route_add -<")
        application.logger.info("file: %s", file)
    
        # saves the file with a name based on the current timestamp
        rfilepath = os.path.join(application.config['UPLOAD_FOLDER'],
                                 datetime.today().strftime('%Y%m%d-%H%M%S-%f'))

        rfile.save(rfilepath)
        
        application.logger.info("filepath: %s", rfilepath)

        entry = {'title': request.form['title'],
                 'comment': request.form['comment'],
                 'type': worker.get_type(rfilepath),
                 'timestamp': datetime.today().strftime('%b %d %Y %H:%M:%S'),
                 'resource': rfilepath}

        # create a unid for the entry and store the data
        unid = g.dao.add(entry)
        entry['eid'] = unid

        # if the resource is a video call the transcoder
        if entry['type'] == 'video':
            transcoded = worker.transcode_video(unid)
        return redirect(url_for('route_view', e_unid=unid))
    else:
        return render_template('add.html')

if __name__ == '__main__':
    logging.basicConfig(filename='/var/log/rlab.log',level=logging.DEBUG)
    application.run(debug=True)
