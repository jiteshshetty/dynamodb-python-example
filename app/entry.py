import random, boto, json, worker, logging, os, sys
from boto import dynamodb
from boto.s3.key import Key


def path_to_s3(path, bucket):
    name = path[path.rfind('/')+1:]
    obj = Key(bucket)
    obj.key = name
    obj.set_contents_from_filename(path)
    os.remove(path)
    return name    


class EntryDAO:
    """ Data Access Object for entries"""
    def __init__(self, table_name, bucket_name, region):
        logging.error("conectando a s3 con boto")
        sco = boto.connect_s3()
        logging.error("conectado a s3 con boto")
        # @TODO: raise exception if there is no bucket for given name
        self.bucket = sco.get_bucket(bucket_name)
        # @TODO: put the region in a global parameter
        self.region = region
        # @TODO: raise exception if there is no table for given name
        ctx = boto.dynamodb.connect_to_region(region)
        self.table = ctx.get_table(table_name)
        logging.error("fin del _init_")
    
    
    def __get_unid(self):
        """Generates a random string of hex chars.
        Pretty basic, only luck makes it bullet-proof for duplicates"""
        # @TODO: use DynamoDB counters for entry IDs
        crappy_unid = ''
        for i in range(32):
            crappy_unid += random.choice('0123456789abcdef')
        return crappy_unid


    def __path_to_s3(self, path):
        logging.basicConfig(filename='/var/log/rlab.log',level=logging.INFO)

        try:
            return path_to_s3(path, self.bucket)
        except:
            logging.error("File to S3 -- %s" , sys.exc_info())

    
    def list(self, index=None, limit=10):
        """Returns a list of entries starting at the specific index"""
        dbres = self.table.scan(max_results=limit, exclusive_start_key=index)
        res = []
        for dbr in dbres:        
            if ('thumbnail' in dbr):
                pass
            else:
                # thumbnail is not present in DB
                logging.info("thumbnail does not exist")
                rawname = dbr['resource']
                t_video_name = rawname + '-tx.mp4'
                thumb_name = rawname + '-00003.png'
                obj = Key(self.bucket)
                obj.key = thumb_name
                # if thumbnails exists in self.bucket update thumbnail and resource
                if (obj.exists()):
                    # delete the other three thumbnails and source for video:
                    self.bucket.delete_key(rawname+'-00001.png')
                    self.bucket.delete_key(rawname+'-00002.png')
                    self.bucket.delete_key(rawname+'-00004.png')
                    self.bucket.delete_key(rawname)
                    # update resource and thumbnail
                    dbr['resource'] = t_video_name
                    dbr['thumbnail'] = thumb_name
                    self.update(dbr)
            res.append(dbr)
        return res

    
    def add(self, entry):
        logging.basicConfig(filename='/var/log/rlab.log',level=logging.INFO)

        """Adds the entry to the repository"""
        # create a thumbnail if the resource is an image
        if entry['type'] == 'image':
            entry['thumbnail'] = worker.make_thumbnail(entry['resource'])
            entry['thumbnail'] = self.__path_to_s3(entry['thumbnail'])
        # insert resource to S3
        entry['resource'] = self.__path_to_s3(entry['resource'])
        # insert contents in DynamoDB
        e_unid = self.__get_unid()
        entry['eid'] = e_unid

        logging.info("-> eid: %s", e_unid)

        self.table.new_item(hash_key=e_unid, attrs=entry).put()

        logging.info("-> Exitting DAO.add, returning e_unid")

        return e_unid
    
    
    def update(self, entry):
        """Updates an entry in the repository"""
        i = self.table.get_item(hash_key=entry['eid'])
        for nm in entry:
            i[nm] = entry[nm]
        i.put()
    
    
    def delete(self, e_unid):
        """Removes the entry from the repository"""
        # @TODO I probably need to catch potential exceptions here
        entry = self.table.get_item(hash_key=e_unid)
        # Delete entry objects from S3
        self.bucket.delete_key(entry['resource'])
        if entry.has_key('thumbnail'):
            self.bucket.delete_key(entry['thumbnail'])
        # Delete the entry in DyDB        
        entry.delete() 
    
    
    def get(self, e_unid):
        """Gets an entry object based on its UNID"""
        return self.table.get_item(hash_key=e_unid)
