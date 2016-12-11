#!/usr/bin/env python
import subprocess
import numpy
import time
import os
import sys
import Queue
import io

def voice_capture(inrate, bufsize,  v_queue):

    #inrate=int(8000);
    rate_str="-r"+str(inrate)
    byte_buffer=bytearray(bufsize)
    j=0
    
    record_proc = subprocess.Popen(["arecord","-fS16_LE",rate_str,"-c1","-traw"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    
    rate=int(inrate/100)
    noise=80
    open_factor=2.5
    gaussain_filter=[0.006,0.061,0.242,0.383,0.242,0.061,0.006]
    amp=numpy.zeros((rate,))
    
    for i in range(0,rate-1):
        data=record_proc.stdout.read(2)
        a=ord(data[0])+ord(data[1])*256
        if a>32767:
            a=a-65536
        amp[i]=a
    amp=numpy.abs(amp)
    amp=numpy.convolve(amp,gaussain_filter,'same')
    noise=amp.mean()
    while 1:
        for i in range(0,rate-1):
            data=record_proc.stdout.read(2)
            a=ord(data[0])+ord(data[1])*256
            if a>32767:
                a=a-65536
            amp[i]=a
        amp=numpy.abs(amp)
        amp=numpy.convolve(amp,gaussain_filter,'same')
        if amp.mean()>open_factor*noise:
            print("Start!   noise:{}    voice:{}    factor:{}".format(noise,amp.mean(),open_factor))
            amp=numpy.zeros((rate,))
            silent=0
            while silent<5000:    
                for i in range(0,rate-1):
                    data=record_proc.stdout.read(2)
                    byte_buffer[j]=data[0]
                    byte_buffer[j+1]=data[1]
                    j=j+2
                    if (j>=bufsize):
                        j=0
                        v_queue.put(byte_buffer)
                    a=ord(data[0])+ord(data[1])*256
                    if a>32767:
                        a=a-65536
                    amp[i]=a
                amp=numpy.abs(amp)
                amp=numpy.convolve(amp,gaussain_filter,'same')
                if amp.mean()<(open_factor+1)*noise:
                    noise=0.6*noise+0.4*amp.mean()
                    silent=silent+1
                else:
                    silent=0
            print("Ends!    noise:{}    voice:{}    factor:{}".format(noise,amp.mean(),open_factor))
            v_queue.put(byte_buffer[:j])
            j = 0
        else:
            noise=0.6*noise+0.4*amp.mean()
            #print("Ends!    noise:{}    voice:{}    factor:{}".format(noise,amp.mean(),open_factor))
