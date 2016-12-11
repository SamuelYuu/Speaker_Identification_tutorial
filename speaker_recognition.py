#!/usr/bin/env python
from __future__ import print_function
import subprocess
import sys
from threading import Thread
from Queue import Queue, Empty
import os
import struct
import urllib2
import subrecord
import math
import time

RECORD_KHZ = 8 #kHZ
INTERVAL = 1000 #mili
SPEECH_ADD_URL = 'http://edison-api.belugon.com/speechAdd?speaker=%s&timestamp=%d'
CMD_MFCC = '/usr/local/bin/x2x +sf | /usr/local/bin/frame | /usr/local/bin/mfcc -s %d' % RECORD_KHZ
CMD_ENROLL = '/usr/local/bin/gmm -l 12'
CMD_PREDICT = '/usr/local/bin/gmmp -a -l 12 %s'
DIR_GMM = '/home/root/.speakerdata/'

INPUT_BUF_SIZE = (INTERVAL / 1000 ) * RECORD_KHZ * 1000 * 16 / 8 # 16 bit
MFCC_BUF_SIZE = 32

def main():
    if len(sys.argv) < 3 or ( sys.argv[1] != 'enroll' and sys.argv[1] != 'predict' ):
        print('Usage: ' + sys.argv[0] + ' enroll|predict file.raw|live')
        sys.exit(0)
    if sys.argv[1] == 'enroll':
        process_enroll()
    if sys.argv[1] == 'predict':
        if sys.argv[2] == 'live':
            process_predict_live()
        else:
            process_predict()

def process_enroll():
    name = raw_input('Name: ')
    gmm_result_queue = Queue()
    with open(sys.argv[2], 'rb') as f:
        buf = bytearray(INPUT_BUF_SIZE)
        p = subprocess.Popen([CMD_MFCC], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p_gmm = subprocess.Popen(CMD_ENROLL.split(), stdin=p.stdout, stdout=subprocess.PIPE)
        gmm_thread = Thread(target=get_gmm_result, args=[p_gmm.stdout, gmm_result_queue])
        gmm_thread.start()
        while True:
            n = f.readinto(buf)
            if n == 0:
                break
            if n < len(buf):
                p.stdin.write(buf[:n])
                break
            p.stdin.write(buf)
        p.stdin.close()
        p.wait()
        p_gmm.wait()
    gmm_data = gmm_result_queue.get()
    with open(DIR_GMM + name + '.gmm', 'wb') as gmm_file:
        gmm_file.write(gmm_data)

def process_predict():
    mfcc_result_queue = Queue()
    with open(sys.argv[2], 'rb') as f:
        buf = bytearray(INPUT_BUF_SIZE)
        while True:
            n = f.readinto(buf)
            if n == 0:
                break
            p = subprocess.Popen([CMD_MFCC], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            mfcc_thread = Thread(target=get_mfcc_result, args=[p.stdout, mfcc_result_queue])
            mfcc_thread.start()
            if n < len(buf):
                p.stdin.write(buf[:n])
            else:
                p.stdin.write(buf)
            p.stdin.close()
            p.wait()
            mfcc_data = mfcc_result_queue.get()
            best_match_name = find_best_gmm_match(mfcc_data)
            result_thread = Thread(target=send_result, args=[best_match_name])
            result_thread.start()

def process_predict_live():
    mfcc_result_queue = Queue()
    voice_data_queue = Queue()
    voice_capture_thread = Thread(target=subrecord.voice_capture, args=[math.floor(RECORD_KHZ * 1000), INPUT_BUF_SIZE, voice_data_queue])
    voice_capture_thread.start()
    sample = 0;
    start_time = int(time.time())
    try:
        while True:
            buf = voice_data_queue.get()
            n = len(buf)
            p = subprocess.Popen([CMD_MFCC], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            mfcc_thread = Thread(target=get_mfcc_result, args=[p.stdout, mfcc_result_queue])
            mfcc_thread.start()
            p.stdin.write(buf)
            p.stdin.close()
            p.wait()
            mfcc_data = mfcc_result_queue.get()
            best_match_name = find_best_gmm_match(mfcc_data)
        #result_thread = Thread(target=send_result, args=[best_match_name])
        #result_thread.start()
            sample += 1
            print('Sample: %d\tDuration: %d\tQueueLength: %d\tSampleLength: %s\tspeaker: %s' %
                (sample, int(time.time()) - start_time, voice_data_queue.qsize(), n, best_match_name))
    except (KeyboardInterrupt, SystemExit):
        print("Termination")
        voice_capture_thread.join()
        sys.exit()

def find_best_gmm_match(mfcc_data):
    gmm_result_queue = Queue()
    best_match_name = 'none'
    best_match_logp = float('-inf')
    for filename in os.listdir(DIR_GMM):
        if not filename.endswith('.gmm'):
            continue
        path = os.path.join(DIR_GMM, filename)
        p_gmm = subprocess.Popen((CMD_PREDICT % path).split(),  stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        gmm_thread = Thread(target=get_gmm_result, args=[p_gmm.stdout, gmm_result_queue])
        gmm_thread.start()
        p_gmm.stdin.write(mfcc_data)
        p_gmm.stdin.close()
        p_gmm.wait()
        result = gmm_result_queue.get()
        #print(filename)
        ave_logp = struct.unpack('f', result)[0]
        #print(ave_logp)
        if ave_logp > best_match_logp:
            best_match_logp = ave_logp
            best_match_name = os.path.splitext(filename)[0]
    return best_match_name

def send_result(name):
    timestamp = time.time()
    request_url = SPEECH_ADD_URL % (name,timestamp)
    response_json = urllib2.urlopen(request_url)

def get_mfcc_result(out,result_queue):
    buf = out.read()
    result_queue.put(buf)

def get_gmm_result(out,result_queue):
    buf = out.read()
    result_queue.put(buf)

if __name__ == '__main__':
    main()
