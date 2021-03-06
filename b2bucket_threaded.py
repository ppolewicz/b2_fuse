import logging
import threading

from time import time
from Queue import LifoQueue, Empty
from threading import Lock
from collections import defaultdict

from b2bucket import *
  
#Threaded operations, memory only
class B2BucketThreaded(B2Bucket): 
    def __init__(self, *args):
        super(B2BucketThreaded, self).__init__( *args)
        
        num_threads=50
        self.queue = LifoQueue(num_threads*2)
        
        self.file_locks = defaultdict(Lock)
        
        self.running = True
        
        self.threads = []
        print "Thread ",
        for i in xrange(num_threads):
            t = threading.Thread(target=self._file_updater)
            t.start()
            self.threads.append(t)
            
            print ".",
            
        print 
        
        self.pre_queue_lock = Lock()
        self.pre_queue_running = True
        self.pre_queue = LifoQueue(num_threads*2)
        
        self.pre_file_dict = {}
        
        self.pre_thread = threading.Thread(target=self._prepare_update)
        self.pre_thread.start()
        
        
    
    def _prepare_update(self):
        while self.pre_queue_running:
            try:
                filename, operation, data  = self.pre_queue.get(True,1)
                self.pre_file_dict[filename] = (time(), operation, data)
                self.pre_queue.task_done()
            except Empty:
                for filename, (timestamp, operation, data) in self.pre_file_dict.items():
                    if time()-timestamp > 15:
                        self.queue.put((filename, operation, data))
                    
                        del self.pre_file_dict[filename]
        
        for filename, (timestamp, operation, data) in self.pre_file_dict.items():
            self.queue.put((filename, operation, data))
            del self.pre_file_dict[filename]
            
    def _file_updater(self):
        upload_url = self._get_upload_url()
        while self.running:
            try:
                filename, operation, data  = self.queue.get(True,1)
            except Empty:
                continue
            
            
            with self.file_locks[filename]:
                if operation == "deletion":
                    super(B2BucketThreaded,self)._delete_file(filename)
                    self.queue.task_done()
                    
                elif operation == "upload":
                    try:
                        super(B2BucketThreaded,self)._put_file(filename, data, upload_url, False)
                    except UploadFailed:
                        self.logger.error("Failed to upload %s" % filename)
                    self.queue.task_done()
                    
                else:
                    self.logger.error("Invalid operation %s on %s" % (operation, filename))
                
            
    
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        self.logger.info("Waiting for all B2 requests to complete")
        
        self.logger.info("Pre-Queue contains %s elements", self.pre_queue.qsize())
        self.pre_queue.join()
        
        self.logger.info("Joining pre queue thread")
        self.pre_queue_running = False
        self.pre_thread.join()
        
        self.logger.info("Queue contains %s elements", self.queue.qsize())
        self.queue.join()
        
        self.logger.info("Joining threads")
        self.running = False
        for t in self.threads:
            t.join()
            
            
            
    def put_file(self, filename, data):
        with self.pre_queue_lock:
            self.logger.info("Postponing upload of %s (%s)", filename, len(data))
            
            self.pre_queue.put((filename, "upload", data), True)
            
            new_file = {}
            new_file['fileName'] = filename
            new_file['fileId'] = None
            new_file['uploadTimestamp'] = time()
            new_file['action'] = 'upload'
            new_file['contentLength'] = len(data)
                
            return new_file
        
    def delete_file(self, filename):  
        with self.pre_queue_lock:
            self.logger.info("Postponing deletion of %s", filename)
            self.pre_queue.put((filename, "deletion", None),True)
            
    
    def get_file(self, filename):
        with self.file_locks[filename]:
            return super(B2BucketThreaded,self).get_file(filename)
    


#Threaded operations, disk only
class B2BucketThreadedLocal(B2Bucket): 
    def __init__(self, *args):
        super(B2BucketThreaded, self).__init__( *args)
        
        num_threads=50
        self.queue = LifoQueue(num_threads*2)
        
        self.file_locks = defaultdict(Lock)
        
        self.running = True
        
        self.threads = []
        print "Thread ",
        for i in xrange(num_threads):
            t = threading.Thread(target=self._file_updater)
            t.start()
            self.threads.append(t)
            
            print ".",
            
        print 
        
        self.pre_queue_lock = Lock()
        self.pre_queue_running = True
        self.pre_queue = LifoQueue(num_threads*2)
        
        self.pre_file_dict = {}
        
        self.pre_thread = threading.Thread(target=self._prepare_update)
        self.pre_thread.start()
        
        
    
    def _prepare_update(self):
        while self.pre_queue_running:
            try:
                filename, local_filename, operation  = self.pre_queue.get(True,1)
                self.pre_file_dict[filename] = (time(), local_filename, operation)
                self.pre_queue.task_done()
            except Empty:
                for filename, (timestamp, local_filename, operation) in self.pre_file_dict.items():
                    if time()-timestamp > 15:
                        self.queue.put((filename, local_filename, operation))
                    
                        del self.pre_file_dict[filename]
        
        for filename, (timestamp, local_filename, operation) in self.pre_file_dict.items():
            self.queue.put((filename, local_filename, operation))
            del self.pre_file_dict[filename]
            
    def _file_updater(self):
        while self.running:
            try:
                filename, local_filename, operation  = self.queue.get(True,1)
            except Empty:
                continue
            
            
            with self.file_locks[filename]:
                if operation == "deletion":
                    super(B2BucketThreaded,self)._delete_file(filename)
                    self.queue.task_done()
                    
                elif operation == "upload":
                    super(B2BucketThreaded,self)._put_file(filename, local_filename)
                    self.queue.task_done()
                    
                elif operation == "download":
                    super(B2BucketThreaded,self)._get_file(filename, local_filename)
                    self.queue.task_done()
                    
                else:
                    self.logger.error("Invalid operation %s on %s" % (operation, filename))
                
            
    
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        self.logger.info("Waiting for all B2 requests to complete")
        
        self.logger.info("Pre-Queue contains %s elements", self.pre_queue.qsize())
        self.pre_queue.join()
        
        self.logger.info("Joining pre queue thread")
        self.pre_queue_running = False
        self.pre_thread.join()
        
        self.logger.info("Queue contains %s elements", self.queue.qsize())
        self.queue.join()
        
        self.logger.info("Joining threads")
        self.running = False
        for t in self.threads:
            t.join()
            
            
    def put_file(self, filename, local_filename):
        with self.pre_queue_lock:
            self.logger.info("Postponing upload of %s (%s)", filename, len(data))
            
            self.pre_queue.put((filename, local_filename, "upload"), True)
            
            new_file = {}
            new_file['fileName'] = filename
            new_file['fileId'] = None
            new_file['uploadTimestamp'] = time()
            new_file['action'] = 'upload'
            new_file['contentLength'] = len(data)
                
            return new_file
        
    def delete_file(self, filename):  
        with self.pre_queue_lock:
            self.logger.info("Postponing deletion of %s", filename)
            self.pre_queue.put((filename, None, "deletion"),True)
            
    
    def get_file(self, filename, local_filename):
        with self.pre_queue_lock:
            self.logger.info("Postponing download of %s", filename)
            self.pre_queue.put((filename, local_filename, "download"),True)

        
if __name__=="__main__":
    from b2_fuse import load_config
    import random 
            
    config = load_config()
        
    account_id = config['accountId']
    application_key = config['applicationKey']
    bucket_id = config['bucketId']
   
    with B2BucketThreaded(account_id, application_key, bucket_id) as bucket:
        start = time()
        for i in xrange(50):
            filename = "junk-%s.txt" % random.randint(0,100000000)
            bucket.put_file(filename,"ascii")
        
    end = time()
    
    print "Uploads took %s seconds" % (end-start)
    
    print "Files in bucket %s" % len(bucket.list_dir())
